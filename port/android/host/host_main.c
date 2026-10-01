/*
HOST_MAIN.C

Entry point of the Android port (SDL_main, called by SDLActivity on its
own thread).

It loads the guest image (the game, built as ILP32 code) from the APK's
assets, gives it an environment describing where the game data and saves
live, and runs its main() on a thread of its own with its stack in guest
memory (host_thread.c), on which everything here after startup runs; the
SDL thread waits for it.

Storage (see port/android/README.md): the game data (the directory holding
maps/) is the app's external files directory,
/sdcard/Android/data/<package>/files, where the launcher activity copies it
on first run; saves go to its save/ subdirectory. The settings,
config.toml, live there too (port/linux/src/port_config.c, which the game
reads); this file reads only debug.sample_seconds from it, for the sampler
that runs here.
*/

#include "host.h"
#include "tomlc17.h"

#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include <android/log.h>
#include <errno.h>
#include <jni.h>
#include <pthread.h>
#include <ftw.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

void host_install_signal_handlers(void);

/* ---------- logging and termination */

static FILE *diagnostic_file;
static char diagnostic_path[1024], diagnostic_marker[1024], diagnostic_error[1024];
static pthread_mutex_t diagnostic_mutex = PTHREAD_MUTEX_INITIALIZER;

JNIEXPORT void JNICALL Java_com_halo_decomp_StartDiagnostics_nativeOpen(
    JNIEnv *env, jclass cls, jstring path, jstring marker)
{
    const char *p = (*env)->GetStringUTFChars(env, path, NULL);
    const char *m = (*env)->GetStringUTFChars(env, marker, NULL);
    (void)cls;
    if (p && m) {
        snprintf(diagnostic_path, sizeof(diagnostic_path), "%s", p);
        snprintf(diagnostic_marker, sizeof(diagnostic_marker), "%s", m);
        diagnostic_file = fopen(p, "a");
        if (diagnostic_file) {
            setvbuf(diagnostic_file, NULL, _IONBF, 0);
            fprintf(diagnostic_file, "Native diagnostic revision: Patch18 (upstream + Android/AAOS); page size: %ld\n", sysconf(_SC_PAGESIZE));
        }
    }
    if (p) (*env)->ReleaseStringUTFChars(env, path, p);
    if (m) (*env)->ReleaseStringUTFChars(env, marker, m);
}

static void diagnostic_write(int priority, const char *text)
{
    int saved_errno = errno;
    pthread_mutex_lock(&diagnostic_mutex);
    if (priority >= ANDROID_LOG_ERROR)
        snprintf(diagnostic_error, sizeof(diagnostic_error), "%s", text);
    if (diagnostic_file && (priority >= ANDROID_LOG_ERROR || ftell(diagnostic_file) < 2*1024*1024))
        fprintf(diagnostic_file, "%lld [%d] %s\n", (long long)time(NULL), priority, text);
    pthread_mutex_unlock(&diagnostic_mutex);
    errno = saved_errno;
}

void host_logf(int priority, const char *format, ...)
{
    char text[4096];
    va_list arguments;
    va_start(arguments, format);
    vsnprintf(text, sizeof(text), format, arguments);
    va_end(arguments);
    __android_log_write(priority, "halo", text);
    diagnostic_write(priority, text);
}

void host_log(int priority, const char *text)
{
    __android_log_write(priority, "halo", text);
    diagnostic_write(priority, text);
}

void host_fatal(const char *format, ...)
{
    char message[1024], details[3200];
    va_list arguments;
    va_start(arguments, format);
    vsnprintf(message, sizeof(message), format, arguments);
    va_end(arguments);
    pthread_mutex_lock(&diagnostic_mutex);
    snprintf(details, sizeof(details), "%s\n\n%s\n\nDiagnostic file: %s",
        message, diagnostic_error, diagnostic_file ? diagnostic_path : "unavailable");
    pthread_mutex_unlock(&diagnostic_mutex);
    host_log(ANDROID_LOG_FATAL, details);
    if (diagnostic_file) fsync(fileno(diagnostic_file));
    SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Halo - start diagnostic", details, NULL);
    _exit(1);
}

void host_abort(const char *reason)
{
	host_logf(ANDROID_LOG_FATAL, "guest abort: %s", reason);
	abort();
}

void host_exit(int code)
{
	host_logf(HOST_LOG_INFO, "the game exited (%d)", code);
	if (code == 0 && diagnostic_marker[0]) unlink(diagnostic_marker);
	/* the process ends with the game; Android restarts it from the
	launcher next time */
	_exit(code);
}

int host_errno(void)
{
	return errno;
}

/* ---------- paths */

static char data_root[512];
static char save_root[512];

void host_android_path(int which, char *buffer, uint32_t size)
{
	snprintf(buffer, size, "%s", which ? save_root : data_root);
}

static int directory_has_maps(const char *root)
{
	char path[600];
	struct stat information;

	snprintf(path, sizeof(path), "%s/maps/ui.map", root);
	return stat(path, &information) == 0;
}

/* Directories the app creates in its external storage are private to it
(mode 0770 under the app's own group), so the shell user (adb) cannot list
them. Open the save tree for reading, with set-group-ID directories as
posix_make_directory creates them (port/linux/src/posix_files.c). */
static int share_entry(const char *path, const struct stat *information, int type, struct FTW *walk)
{
	(void)information;
	(void)walk;
	if (type == FTW_D || type == FTW_DP)
		chmod(path, 02775);
	else if (type == FTW_F)
		chmod(path, 0664);
	return 0;
}

static void share_save_tree(const char *root)
{
	nftw(root, share_entry, 16, FTW_PHYS);
}

/* ---------- the guest's environment */

#define ENVIRONMENT_MAXIMUM 64

struct environment
{
	char *entries[ENVIRONMENT_MAXIMUM];
	int count;
};

static void environment_set(struct environment *environment, const char *name, const char *value)
{
	size_t length = strlen(name);
	char *entry;
	int index;

	entry = malloc(length + strlen(value) + 2);
	sprintf(entry, "%s=%s", name, value);
	for (index = 0; index < environment->count; index++)
	{
		if (!strncmp(environment->entries[index], name, length) && environment->entries[index][length] == '=')
		{
			free(environment->entries[index]);
			environment->entries[index] = entry;
			return;
		}
	}
	if (environment->count < ENVIRONMENT_MAXIMUM)
		environment->entries[environment->count++] = entry;
	else
		free(entry);
}

/* debug.sample_seconds from config.toml, as text for the sampler, or 0 */
static int config_sample_seconds(const char *path, char *text, size_t size)
{
	toml_result_t result = toml_parse_file_ex(path);
	int found = 0;

	if (!result.ok)
		return 0;
	{
		toml_datum_t seconds = toml_seek(result.toptab, "debug.sample_seconds");
		double value = seconds.type == TOML_FP64 ? seconds.u.fp64 :
			seconds.type == TOML_INT64 ? (double)seconds.u.int64 : 0.0;

		if (value > 0.0)
		{
			snprintf(text, size, "%g", value);
			found = 1;
		}
	}
	toml_free(result);
	return found;
}

/* POSIX TZ for the current local offset (the guest's musl has no zone
database) */
static void time_zone(char *buffer, size_t size)
{
	time_t now = time(NULL);
	struct tm local;
	long offset;

	localtime_r(&now, &local);
	offset = -local.tm_gmtoff;
	snprintf(buffer, size, "<L>%s%ld:%02ld", offset < 0 ? "-" : "", labs(offset) / 3600, (labs(offset) / 60) % 60);
}

/* copies argv and the environment into guest memory */
static uint32_t make_boot(const struct environment *environment)
{
	size_t size = 0x10000;
	char *memory = host_low_map(size, PROT_READ | PROT_WRITE);
	struct halo_guest_boot *boot = (struct halo_guest_boot *)memory;
	uint32_t *argv = (uint32_t *)(memory + sizeof(*boot));
	uint32_t *environ_list = argv + 2;
	char *strings = (char *)(environ_list + ENVIRONMENT_MAXIMUM + 1);
	int index;

	if (!memory)
		host_fatal("cannot allocate the guest's environment");
	strcpy(strings, "halo");
	argv[0] = (uint32_t)(uintptr_t)strings;
	argv[1] = 0;
	strings += strlen(strings) + 1;
	for (index = 0; index < environment->count; index++)
	{
		size_t length = strlen(environment->entries[index]) + 1;

		if (strings + length > memory + size)
			break;
		memcpy(strings, environment->entries[index], length);
		environ_list[index] = (uint32_t)(uintptr_t)strings;
		strings += length;
	}
	environ_list[index] = 0;
	boot->argc = 1;
	boot->argv = (uint32_t)(uintptr_t)argv;
	boot->environment = (uint32_t)(uintptr_t)environ_list;
	boot->page_size = (uint32_t)getpagesize();
	boot->contiguous_base = host_memory_window_base();
	return (uint32_t)(uintptr_t)boot;
}

/* ---------- main */

#define MAIN_STACK_SIZE (16 * 1024 * 1024)

static void *game_main(void *unused)
{
	struct environment environment = { { 0 }, 0 };
	const char *external;
	char zone[64];
	char path[600];
	size_t image_size = 0;
	void *image;
	uint32_t boot;

	(void)unused;
	external = SDL_GetAndroidExternalStoragePath();
	if (!external)
		host_fatal("Android storage is unavailable: %s", SDL_GetError());
	snprintf(data_root, sizeof(data_root), "%s", external);
	snprintf(save_root, sizeof(save_root), "%s/save", external);
	/* readable by adb (the shell user), for managing saves */
	mkdir(save_root, 0775);
	share_save_tree(save_root);
	if (!directory_has_maps(data_root))
	{
		host_fatal("The Halo game data was not found.\n\nCopy the PAL game data (build 01.01.14.2342), "
			"the folder that contains maps, into\n%s\nor import it from the launcher screen.", data_root);
	}

	environment_set(&environment, "HOME", save_root);
	environment_set(&environment, "HALO_DATA_ROOT", data_root);
	environment_set(&environment, "HALO_SAVE_ROOT", save_root);
	time_zone(zone, sizeof(zone));
	environment_set(&environment, "TZ", zone);
	snprintf(path, sizeof(path), "%s/config.toml", data_root);

    {
        static const char *images[] = { "halo_guest.elf", "halo_guest_20000000.elf",
            "halo_guest_60000000.elf", "halo_guest_a0000000.elf" };
        unsigned int attempt;
        for (attempt = 0; attempt < sizeof(images)/sizeof(images[0]); attempt++) {
            int result;
            host_logf(HOST_LOG_INFO, "trying linked guest image: %s", images[attempt]);
            image = SDL_LoadFile(images[attempt], &image_size);
            if (!image) host_fatal("cannot read %s from the APK: %s", images[attempt], SDL_GetError());
            result = host_load_image(image, image_size);
            SDL_free(image);
            if (result == 0) break;
            if (result != -2) host_fatal("cannot load %s; see diagnostic for details", images[attempt]);
        }
        if (attempt == sizeof(images)/sizeof(images[0]))
            host_fatal("All four linked game-image addresses are occupied; see diagnostic for details");
    }

	/* only now that the image holds its address: bringing the display up
	maps memory of its own, and on a device where one of those mappings
	lands on the image's address there is nowhere else to put it, because
	the image is an executable linked to run there (host_loader.c) */
	{
		/* the game renders 480 lines at the display's aspect ratio
		(landscape) unless display.screen_width says otherwise (d3d8_gl.c) */
		const SDL_DisplayMode *mode;
		char width[16];

		SDL_InitSubSystem(SDL_INIT_VIDEO);
		mode = SDL_GetDesktopDisplayMode(SDL_GetPrimaryDisplay());
		if (mode && mode->w > 0 && mode->h > 0)
		{
			int longer = mode->w > mode->h ? mode->w : mode->h;
			int shorter = mode->w > mode->h ? mode->h : mode->w;

			snprintf(width, sizeof(width), "%d", (480 * longer / shorter) & ~1);
			environment_set(&environment, "HALO_DISPLAY_WIDTH", width);
			host_logf(HOST_LOG_INFO, "display %dx%d: rendering %sx480", mode->w, mode->h, width);
		}
	}

	{
		char seconds[32];

		if (config_sample_seconds(path, seconds, sizeof(seconds)))
			host_debug_start_sampler(seconds);
	}
	boot = make_boot(&environment);
	host_logf(HOST_LOG_INFO, "data %s, saves %s", data_root, save_root);
	host_run_guest_main(boot);
}

int main(int argc, char *argv[])
{
	(void)argc;
	(void)argv;
	host_logf(HOST_LOG_INFO, "Halo for Android starting");
	host_install_signal_handlers();

	if (host_native_thread_create(game_main, NULL, MAIN_STACK_SIZE) != 0)
		host_fatal("cannot start the game thread");
	/* the game ends the process itself (host_exit) */
	for (;;)
		pause();
}
