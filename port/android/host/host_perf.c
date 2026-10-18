/* NVIDIA Shield performance test (port/android/include/halo_android_perf.h).
 * The UI thread stores the settings and reads the frame timing text; the
 * render thread reads the settings once a frame and publishes the text about
 * once a second. Never call guest code through JNI. */
#include "host.h"
#include "halo_android_perf.h"
#include <jni.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>

static pthread_mutex_t perf_lock = PTHREAD_MUTEX_INITIALIZER;
static unsigned int perf_settings;
static char perf_text[512];

JNIEXPORT void JNICALL Java_com_halo_decomp_SettingsOverlay_nativePerf(JNIEnv *e, jclass c, jint settings)
{
	(void)e; (void)c;
	pthread_mutex_lock(&perf_lock);
	perf_settings = (unsigned int)settings | HALO_PERF_SET;
	pthread_mutex_unlock(&perf_lock);
}

JNIEXPORT jstring JNICALL Java_com_halo_decomp_PerfOverlay_nativeText(JNIEnv *e, jclass c)
{
	char text[sizeof(perf_text)];

	(void)c;
	pthread_mutex_lock(&perf_lock);
	memcpy(text, perf_text, sizeof(text));
	pthread_mutex_unlock(&perf_lock);
	/* the renderer writes ASCII only, which is also modified UTF-8 */
	return (*e)->NewStringUTF(e, text);
}

unsigned int host_perf_settings(void)
{
	unsigned int settings;

	pthread_mutex_lock(&perf_lock);
	settings = perf_settings;
	pthread_mutex_unlock(&perf_lock);
	return settings;
}

/* the counter's text, and a summary line for Logcat and halo-diagnostic.txt
(either may be NULL) */
void host_perf_publish(const char *overlay, const char *line)
{
	if (overlay)
	{
		pthread_mutex_lock(&perf_lock);
		snprintf(perf_text, sizeof(perf_text), "%s", overlay);
		pthread_mutex_unlock(&perf_lock);
	}
	if (line)
		host_logf(HOST_LOG_INFO, "%s", line);
}
