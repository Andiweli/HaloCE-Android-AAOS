#!/usr/bin/env python3
"""Check the Android controller ports of port/linux/src/xinput_sdl.c.

The production sdl_gamepads and connected_gamepads run against a scripted
SDL gamepad list that follows a Shield TV log: the remote and its "tvQA"
twin listed first, controllers that sleep and return under new IDs, and a
fifth controller. Controllers with sticks must keep their ports; remotes
must never take one; the Xbox insertion mask must follow. No device needed.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_upstream_optimizations import function  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'port/linux/src/xinput_sdl.c').read_text()
start = source.index('static SDL_JoystickID port_ids[PORT_COUNT];')
state = source[start:source.index('#endif', start)]
production = '\n'.join([state, function(source, 'sdl_gamepads'), function(source, 'connected_gamepads')])

harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define HALO_ANDROID 1
#define TRUE 1
#define FALSE 0
#define PORT_COUNT 4
#define XDEVICE_PORT0_MASK 1UL
typedef int BOOL;
typedef unsigned long DWORD;
typedef uint32_t SDL_JoystickID;
typedef struct SDL_Gamepad SDL_Gamepad;
typedef enum { SDL_GAMEPAD_AXIS_LEFTX, SDL_GAMEPAD_AXIS_LEFTY, SDL_GAMEPAD_AXIS_RIGHTX } SDL_GamepadAxis;
/* the scripted SDL: device id -> whether it has both sticks */
static struct { SDL_JoystickID id; BOOL sticks; } devices[16];
static int device_count, logs;
static SDL_Gamepad *as_gamepad(SDL_JoystickID id) { return (SDL_Gamepad *)(uintptr_t)(0x1000 + id); }
static SDL_JoystickID id_of(SDL_Gamepad *gamepad) { return gamepad ? (SDL_JoystickID)((uintptr_t)gamepad - 0x1000) : 0; }
static SDL_JoystickID *SDL_GetGamepads(int *count) {
 static SDL_JoystickID ids[17]; for (int i = 0; i < device_count; i++) ids[i] = devices[i].id;
 *count = device_count; return ids;
}
static void SDL_free(void *memory) { (void)memory; }
static SDL_Gamepad *SDL_GetGamepadFromID(SDL_JoystickID id) { return as_gamepad(id); }
static BOOL SDL_GamepadHasAxis(SDL_Gamepad *gamepad, SDL_GamepadAxis axis) {
 (void)axis; for (int i = 0; i < device_count; i++) if (devices[i].id == id_of(gamepad)) return devices[i].sticks; return FALSE;
}
static void platform_log(const char *format, ...) { (void)format; logs++; }
static void plug(SDL_JoystickID id, BOOL sticks) { devices[device_count].id = id; devices[device_count++].sticks = sticks; }
static void unplug(SDL_JoystickID id) {
 for (int i = 0; i < device_count; i++) if (devices[i].id == id) { memmove(&devices[i], &devices[i + 1], (device_count - i - 1) * sizeof(devices[0])); device_count--; return; }
 assert(0);
}
''' + production + r'''
static void expect(SDL_JoystickID p0, SDL_JoystickID p1, SDL_JoystickID p2, SDL_JoystickID p3, DWORD mask, int extras) {
 SDL_Gamepad *gamepads[PORT_COUNT];
 sdl_gamepads(gamepads);
 SDL_JoystickID expected[PORT_COUNT] = { p0, p1, p2, p3 };
 for (int port = 0; port < PORT_COUNT; port++) {
  if (id_of(gamepads[port]) != expected[port]) {
   fprintf(stderr, "port %d: controller %u, expected %u\n", port, id_of(gamepads[port]), expected[port]); assert(0);
  }
 }
 assert(connected_gamepads() == mask);
 assert(port0_extra_count == extras);
}
int main(void) {
 /* the Shield log: remote 2 and its tvQA twin 3 listed first, controllers 4 and 5 */
 plug(2, FALSE); plug(3, FALSE); plug(4, TRUE); plug(5, TRUE);
 expect(4, 5, 0, 0, 0x3, 2);
 /* the remotes merge into port 0, whatever their order */
 assert(id_of(port0_extras[0]) == 2 && id_of(port0_extras[1]) == 3);
 /* a third controller switched on later takes the next port */
 plug(7, TRUE);
 expect(4, 5, 7, 0, 0x7, 2);
 /* controller 4 sleeps; nobody moves; port 0 stays connected (touch, keyboard) */
 unplug(4);
 expect(0, 5, 7, 0, 0x7, 2);
 /* it wakes as 8 and gets its port back: the lowest free one */
 plug(8, TRUE);
 expect(8, 5, 7, 0, 0x7, 2);
 /* a fourth and a fifth controller: the fifth waits for a free port */
 plug(9, TRUE); plug(10, TRUE);
 expect(8, 5, 7, 9, 0xf, 2);
 unplug(5);
 expect(8, 10, 7, 9, 0xf, 2);
 /* only remotes: they still drive port 0 (menus) */
 unplug(8); unplug(10); unplug(7); unplug(9);
 expect(0, 0, 0, 0, 0x1, 2);
 /* a controller after the remotes takes port 0 */
 plug(11, TRUE);
 expect(11, 0, 0, 0, 0x1, 2);
 assert(logs > 0);
 puts("Android controller ports: remotes never take a port, controllers keep theirs across sleep/new IDs, a later or fifth controller takes the lowest free port, insertion mask follows.");
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='halo-gamepad-ports-') as name:
    folder = Path(name)
    (folder / 'test.c').write_text(harness)
    subprocess.run(['cc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wno-unused-function', '-fsanitize=address,undefined',
                    str(folder / 'test.c'), '-o', str(folder / 'test')], check=True)
    subprocess.run([str(folder / 'test')], check=True)
