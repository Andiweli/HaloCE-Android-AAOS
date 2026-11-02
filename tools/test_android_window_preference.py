#!/usr/bin/env python3
"""Check that the Xbox memory window returns to the last run's address.

A saved game holds pointers into the window and loads only where it was
written (source/saved games/game_state.c). The production
host_memory_initialize and host_memory_prefer_window (host_memory.c) and
host_main.c's window_preference_read/_write run in this Linux process,
reserving real address space below 4 GB: the last run's address is taken
first when it is free, even over the Xbox's own; a taken or unusable one
falls back as before and is said in the log; the file keeps the address
the run used. Each case runs in a fresh process. No device needed.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_upstream_optimizations import function  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
memory = (ROOT / 'port/android/host/host_memory.c').read_text()
main = (ROOT / 'port/android/host/host_main.c').read_text()
abi = (ROOT / 'port/android/include/halo_android_abi.h').read_text()


def define(source, name):
    return re.search(r'^#define ' + name + r'\b.*$', source, re.M).group() + '\n'


harness = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
enum { HOST_LOG_INFO, HOST_LOG_WARN, HOST_LOG_ERROR };
static char logged[8192];
static void host_logf(int priority, const char *format, ...)
{
	va_list arguments;
	size_t used = strlen(logged);
	(void)priority;
	va_start(arguments, format);
	vsnprintf(logged + used, sizeof(logged) - used, format, arguments);
	va_end(arguments);
	strncat(logged, "\n", sizeof(logged) - strlen(logged) - 1);
}
static char save_root[512];
''' + ''.join(define(abi, n) for n in ('HALO_GUEST_WINDOW_BASE', 'HALO_GUEST_WINDOW_SIZE', 'HALO_GUEST_WINDOW_ALIGNMENT'))
harness += ''.join(define(memory, n) for n in ('PAGE', 'LOW_START', 'LOW_LIMIT'))
harness += 'static uint64_t window_base, window_end;\nstatic uint64_t image_base, image_end;\n'
for name in ('round_up', 'find_gap', 'log_conflicts', 'reserve'):
    harness += function(memory, name) + '\n'
harness += re.search(r'^/\* host_memory_prefer_window.*?\nstatic uint64_t preferred_window;\n', memory, re.M | re.S).group()
harness += function(memory, 'host_memory_prefer_window') + '\n' + function(memory, 'host_memory_initialize') + '\n'
harness += 'uint32_t host_memory_window_base(void) { return (uint32_t)window_base; }\n'
for name in ('window_preference_path', 'window_preference_read', 'window_preference_write'):
    harness += function(main, name) + '\n'
harness += r'''
static void block(uint64_t address)
{
	void *result = mmap((void *)address, HALO_GUEST_WINDOW_SIZE, PROT_NONE,
		MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_FIXED_NOREPLACE, -1, 0);
	assert(result == (void *)address);
}
static void write_file(const char *text)
{
	char path[600];
	FILE *file;
	window_preference_path(path, sizeof(path));
	file = fopen(path, "w");
	fputs(text, file);
	fclose(file);
}
static unsigned int file_value(void)
{
	char path[600];
	unsigned int value = 0;
	FILE *file;
	window_preference_path(path, sizeof(path));
	file = fopen(path, "r");
	if (!file) return 0;
	if (fscanf(file, "%x", &value) != 1) value = 0;
	fclose(file);
	return value;
}
int main(int argc, char **argv)
{
	const char *which = argv[2];
	snprintf(save_root, sizeof(save_root), "%s", argv[1]);
	if (!strcmp(which, "first"))  /* no file: the Xbox's address, remembered */
	{
		window_preference_read();
		assert(host_memory_initialize(0x40000000u, 0x1000) == 0 && window_base == HALO_GUEST_WINDOW_BASE);
		window_preference_write();
		assert(file_value() == HALO_GUEST_WINDOW_BASE);
	}
	else if (!strcmp(which, "moved"))  /* the Xbox's taken: somewhere else, remembered */
	{
		block(HALO_GUEST_WINDOW_BASE);
		window_preference_read();
		assert(host_memory_initialize(0x40000000u, 0x1000) == 0 && window_base != HALO_GUEST_WINDOW_BASE);
		window_preference_write();
		assert(file_value() == (unsigned int)window_base);
		printf("%08x\n", (unsigned int)window_base);
	}
	else if (!strcmp(which, "again"))  /* the last run's is taken first, the Xbox's free or not */
	{
		window_preference_read();
		assert(host_memory_initialize(0x40000000u, 0x1000) == 0);
		assert(window_base == strtoul(argv[3], NULL, 16));
		assert(strstr(logged, "where the last run had it"));
		window_preference_write();
		assert(file_value() == (unsigned int)window_base);
	}
	else if (!strcmp(which, "taken"))  /* the last run's taken: the Xbox's, said, remembered */
	{
		block(strtoul(argv[3], NULL, 16));
		window_preference_read();
		assert(host_memory_initialize(0x40000000u, 0x1000) == 0 && window_base == HALO_GUEST_WINDOW_BASE);
		assert(strstr(logged, "is taken: its saved games do not load"));
		window_preference_write();
		assert(file_value() == HALO_GUEST_WINDOW_BASE);
	}
	else if (!strcmp(which, "unusable"))  /* unaligned, low, past 4 GB or not a number: ignored */
	{
		static const char *const texts[] = { "81000000\n", "00000000\n", "f8000000\n", "fffff000\n", "window\n", "" };
		unsigned int index;
		for (index = 0; index < sizeof(texts) / sizeof(texts[0]); index++)
		{
			preferred_window = 0;
			write_file(texts[index]);
			window_preference_read();
			assert(!preferred_window);
		}
		write_file("90000000\n");
		window_preference_read();
		assert(preferred_window == 0x90000000u);
	}
	printf("%s ok\n", which);
	return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='halo-window-') as name:
    folder = Path(name)
    saves = folder / 'save'
    saves.mkdir()
    (folder / 'test.c').write_text(harness)
    subprocess.run(['cc', '-std=gnu11', '-O1', '-Wall', '-Wno-unused-function', str(folder / 'test.c'),
                    '-o', str(folder / 'test')], check=True)

    def run(*arguments):
        return subprocess.run([str(folder / 'test'), str(saves), *arguments], check=True,
                              capture_output=True, text=True).stdout

    run('first')
    moved = run('moved').split()[0]
    run('again', moved)                 # the Xbox's address free now, the last run's still taken first
    (saves / 'memory_window.txt').write_text('90000000\n')
    run('again', '90000000')
    run('taken', '90000000')
    run('unusable')
print(f'Window preference: the Xbox address the first time, remembered; elsewhere ({moved}) when it is taken, '
      'remembered and taken first next run even with the Xbox address free; a taken or unusable preference '
      'falls back and is said.')
