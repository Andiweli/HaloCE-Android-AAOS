#!/usr/bin/env python3
"""Check the settings' 60 FPS switch of the Android port.

The production halo_interpolation_enabled/halo_interpolation_update
(port/linux/src/sdl_platform.c) and main_update_time_unthrottled with the
main loop's switch (source/main/main.c) run against stubs: 30 FPS until the
switch is on, one change reported per switch, and a frame after switching
starts the clocks afresh instead of jumping by the time spent at 30 FPS.
No device, no game assets.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_upstream_optimizations import function  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
platform = (ROOT / 'port/linux/src/sdl_platform.c').read_text()
main = (ROOT / 'source/main/main.c').read_text()

# the main loop's switch, as it stands before main_update_time()
loop = main[main.index('void main_loop('):]
switch = loop[loop.index('#ifdef HALO_ANDROID\n\t\t\t/* the settings\' 60 FPS switch'):loop.index('main_update_time();')]
assert switch.rstrip().endswith('#endif'), switch
assert 'render_interpolation_reset();' in switch and 'main_reset_time();' in switch
assert 'unthrottled_previous_counter.QuadPart = 0;' in switch
switch = switch.replace('#ifdef HALO_ANDROID', '').replace('#endif', '')

harness = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define TRUE 1
#define FALSE 0
#define HALO_ANDROID 1
typedef int BOOL;
typedef unsigned char boolean;
typedef float real;
typedef union { long long QuadPart; } LARGE_INTEGER;
#define CEILING(n,ceiling) ((n)>(ceiling)?(ceiling):(n))
#define PIN(n,floor,ceiling) ((n)<(floor) ? (floor) : CEILING((n),(ceiling)))
enum { _game_connection_local = 0 };
static int config_value, host_value, logs, resets, time_resets;
static long long counter_now = 1;
static boolean debug_force_frame_rate_update;
static struct { boolean movie; real recording_dt; int connection; unsigned long frame_start_milliseconds;
	real seconds_elapsed; unsigned long long rasterizer_initial_index; } main_globals;
static struct { unsigned long long frame_and_vertical_blank_index; } rasterizer_globals;
int config_boolean(const char *name) { assert(!strcmp(name, "display.interpolation")); return config_value; }
int host_settings_sixty_fps(void) { return host_value; }
void platform_log(const char *format, ...) { (void)format; logs++; }
void QueryPerformanceCounter(LARGE_INTEGER *value) { value->QuadPart = counter_now; }
void QueryPerformanceFrequency(LARGE_INTEGER *value) { value->QuadPart = 1000; }
unsigned long system_milliseconds(void) { return 0; }
void profile_seconds_elapsed(real seconds) { (void)seconds; }
void render_interpolation_reset(void) { resets++; }
static void main_reset_time(void) { time_resets++; }
'''
harness += re.search(r'^static int interpolation_enabled = -1;$', platform, re.M).group() + '\n'
harness += function(platform, 'halo_interpolation_enabled') + '\n'
harness += function(platform, 'halo_interpolation_update') + '\n'
harness += re.search(r'^static LARGE_INTEGER unthrottled_previous_counter;$', main, re.M).group() + '\n'
harness += function(main, 'main_update_time_unthrottled') + '\n'
harness += 'static void frame(void)\n{\n' + switch + '\n\tif (halo_interpolation_enabled()) main_update_time_unthrottled();\n}\n'
harness += r'''
int main(void)
{
	/* the host starts the game with display.interpolation false */
	frame();
	assert(!halo_interpolation_enabled() && !resets && !logs);
	/* switched on: once */
	host_value = 1; frame();
	assert(halo_interpolation_enabled() && resets == 1 && time_resets == 1 && logs == 1);
	assert(main_globals.seconds_elapsed == 0.0f);
	counter_now += 17; frame();
	assert(resets == 1 && main_globals.seconds_elapsed == 0.017f);
	/* off for 5 seconds, then on: no jump by the 5 seconds */
	host_value = 0; frame();
	assert(!halo_interpolation_enabled() && resets == 2 && time_resets == 2);
	counter_now += 5000; frame();
	host_value = 1; frame();
	assert(halo_interpolation_enabled() && resets == 3 && time_resets == 3 && main_globals.seconds_elapsed == 0.0f);
	counter_now += 16; frame();
	assert(main_globals.seconds_elapsed == 0.016f && logs == 3);
	/* the same setting again changes nothing */
	frame(); frame();
	assert(resets == 3 && time_resets == 3 && logs == 3);
	puts("60 FPS switch: 30 FPS by default, one reset per change, the clocks restart without a jump after 30 FPS.");
	return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='halo-frame-rate-') as name:
    folder = Path(name)
    (folder / 'test.c').write_text(harness)
    subprocess.run(['cc', '-std=gnu11', '-O1', '-Wall', '-Wno-unused-function', '-ffp-contract=off',
                    str(folder / 'test.c'), '-o', str(folder / 'test')], check=True)
    subprocess.run([str(folder / 'test')], check=True)
