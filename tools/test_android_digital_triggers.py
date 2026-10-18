#!/usr/bin/env python3
"""Check the digital L2/R2 of Android pads (port/android/host/host_sdl.c).

Android reports the L2 and R2 keys of handhelds (Anbernic's, some Bluetooth
pads) as KEYCODE_BUTTON_L2 and R2, which SDL's Android driver makes joystick
buttons 15 and 16. The production host_sdl_gamepad_digital_triggers and the
guest's sdl_gamepad_state (port/linux/src/xinput_sdl.c) run against real SDL
3.4.16, the version the Android build uses: virtual joysticks stand for the
Android pads, with the mappings SDL gives them on Android (made up by
SDL_CreateMappingForAndroidGamepad, or SDL_gamepad_db.h's). Keys must pull
the triggers where the mapping leaves them free, and only there: an analog
trigger, a mapped trigger button, the share button of an Xbox pad and the
shoulders stay as they were. No device needed.

Usage: test_android_digital_triggers.py [--sdl-source DIR] [--sdl-build DIR]
Builds SDL for the host into --sdl-build once (cmake, ninja).
"""
from pathlib import Path
import argparse
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_upstream_optimizations import function  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('--sdl-source', type=Path, default=ROOT / 'build/android/third_party/SDL3')
parser.add_argument('--sdl-build', type=Path, default=ROOT / 'build/test/sdl3-host')
args = parser.parse_args()

library = args.sdl_build / 'libSDL3.a'
if not library.exists():
    subprocess.run(['cmake', '-S', str(args.sdl_source), '-B', str(args.sdl_build), '-G', 'Ninja',
                    '-DCMAKE_BUILD_TYPE=RelWithDebInfo', '-DSDL_UNIX_CONSOLE_BUILD=ON', '-DSDL_SHARED=OFF',
                    '-DSDL_STATIC=ON', '-DSDL_TESTS=OFF', '-DSDL_EXAMPLES=OFF', '-DSDL_VIDEO=OFF', '-DSDL_AUDIO=OFF',
                    '-DSDL_RENDER=OFF', '-DSDL_GPU=OFF', '-DSDL_CAMERA=OFF', '-DSDL_DIALOG=OFF',
                    '-DSDL_SENSOR=OFF', '-DSDL_POWER=OFF', '-DSDL_X11=OFF', '-DSDL_WAYLAND=OFF', '-DSDL_INSTALL=OFF'],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['ninja', '-C', str(args.sdl_build)], check=True, stdout=subprocess.DEVNULL)

host = (ROOT / 'port/android/host/host_sdl.c').read_text()
xinput = (ROOT / 'port/linux/src/xinput_sdl.c').read_text()
xbox = (ROOT / 'port/include/xdk/xdk_xbox.h').read_text()
defines = '\n'.join(re.findall(r'^#define XINPUT_GAMEPAD_\w+ .*$', xbox, re.M))
production = '\n'.join([
    function(host, 'host_sdl_gamepad_digital_triggers'),
    function(xinput, 'stick'), function(xinput, 'merge_button'), function(xinput, 'sdl_gamepad_state')])

# What SDL gives an Android pad: its made-up mapping lists the buttons of
# the key mask and triggers only for a fifth and sixth axis.
FACE = 'a:b0,b:b1,x:b2,y:b3,back:b4,start:b6,leftstick:b7,rightstick:b8,'
SHOULDERS = 'leftshoulder:b9,rightshoulder:b10,'
DPAD = 'dpup:b11,dpdown:b12,dpleft:b13,dpright:b14,'
STICKS = 'leftx:a0,lefty:a1,rightx:a2,righty:a3,'
MADE_UP = '*,' + FACE + SHOULDERS + DPAD + STICKS
TRIGGER_AXES = 'lefttrigger:a4,righttrigger:a5,'
XBOX_SERIES = ('Xbox Series X Controller,a:b0,b:b1,back:b4,misc1:b15,dpdown:b12,dpleft:b13,dpright:b14,dpup:b11,'
               'guide:b5,leftshoulder:b9,leftstick:b7,lefttrigger:a4,leftx:a0,lefty:a1,rightshoulder:b10,'
               'rightstick:b8,righttrigger:a5,rightx:a2,righty:a3,start:b6,x:b2,y:b3,')
EIGHTBITDO = ('8BitDo SF30 Pro,a:b1,b:b0,back:b4,dpdown:b12,dpleft:b13,dpright:b14,dpup:b11,leftshoulder:b9,'
              'leftstick:b7,lefttrigger:b15,leftx:a0,lefty:a1,rightshoulder:b10,rightstick:b8,righttrigger:b16,'
              'rightx:a2,righty:a3,start:b6,x:b3,y:b2,')
for text in (XBOX_SERIES, EIGHTBITDO):
    assert text in (args.sdl_source / 'src/joystick/SDL_gamepad_db.h').read_text(), text[:30]


def pad(name, axes, buttons, mapping):
    return '{ "%s", %d, %d, "%s" }' % (name, axes, buttons, mapping)


harness = r'''
#include <SDL3/SDL.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define HALO_ANDROID 1
#define TRUE 1
#define FALSE 0
typedef int BOOL;
typedef unsigned char BYTE;
typedef unsigned short WORD;
typedef short SHORT;
typedef struct { WORD wButtons; BYTE bAnalogButtons[8]; SHORT sThumbLX, sThumbLY, sThumbRX, sThumbRY; } XINPUT_GAMEPAD;
''' + defines + r'''
enum { _handle_gamepad = 3 };
static SDL_Gamepad *opened[8];
static void *handle_get(uint32_t handle, int type) { assert(type == _handle_gamepad); return opened[handle]; }
/* the guest's SDL_Gamepad is the host handle */
static uint32_t handle_of(SDL_Gamepad *gamepad);
''' + production.replace('host_sdl_gamepad_digital_triggers((unsigned int)(uintptr_t)gamepad)',
                         'host_sdl_gamepad_digital_triggers(handle_of(gamepad))') + r'''
static const struct { const char *name; int axes, buttons; const char *mapping; } pads[] = {
''' + ',\n'.join([
    # Anbernic RG477V as the report reads: sticks, a hat, keys L1 R1 L2 R2
    pad('handheld with digital L2 and R2', 4, 17, MADE_UP),
    # the same pad in its analog trigger (Xbox) mode: no L2/R2 keys
    pad('handheld with analog triggers', 6, 15, MADE_UP + TRIGGER_AXES),
    # trigger axes listed, but the keys move instead
    pad('handheld with idle trigger axes', 6, 17, MADE_UP + TRIGGER_AXES),
    # the share button (KEYCODE_MEDIA_RECORD) is button 15 too
    pad('Xbox Series in the SDL mapping', 6, 16, XBOX_SERIES),
    pad('Xbox-like in a made-up mapping', 6, 16, MADE_UP + TRIGGER_AXES),
    # SDL maps the keys itself
    pad('8BitDo in the SDL mapping', 4, 17, EIGHTBITDO),
    # no keys beyond the D-pad
    pad('remote', 0, 15, '*,a:b0,b:b4,' + DPAD),
]) + r'''
};
static uint32_t handle_of(SDL_Gamepad *gamepad)
{
	for (uint32_t index = 0; index < 8; index++)
		if (opened[index] == gamepad) return index;
	assert(0);
	return 0;
}
/* SDL's Java side scales Android's axes to -1...1: a trigger at rest is -32768 */
static XINPUT_GAMEPAD state(SDL_Gamepad *gamepad, SDL_Joystick *joystick, int button, int trigger_pulled)
{
	Sint16 trigger_axis = trigger_pulled ? SDL_JOYSTICK_AXIS_MAX : SDL_JOYSTICK_AXIS_MIN;
	XINPUT_GAMEPAD result = { 0 };
	int count = SDL_GetNumJoystickButtons(joystick);
	for (int index = 0; index < count; index++) SDL_SetJoystickVirtualButton(joystick, index, index == button);
	if (SDL_GetNumJoystickAxes(joystick) > 5) { SDL_SetJoystickVirtualAxis(joystick, 4, trigger_axis); SDL_SetJoystickVirtualAxis(joystick, 5, trigger_axis); }
	SDL_UpdateJoysticks();
	sdl_gamepad_state(gamepad, &result);
	return result;
}
int main(void)
{
	if (!SDL_Init(SDL_INIT_GAMEPAD)) { fprintf(stderr, "%s\n", SDL_GetError()); return 2; }
	for (unsigned p = 0; p < sizeof(pads) / sizeof(pads[0]); p++)
	{
		SDL_VirtualJoystickDesc desc;
		char guid[64], mapping[1024];
		SDL_INIT_INTERFACE(&desc);
		desc.type = SDL_JOYSTICK_TYPE_GAMEPAD;
		desc.naxes = (Uint16)pads[p].axes;
		desc.nbuttons = (Uint16)pads[p].buttons;
		desc.nhats = 1;
		desc.vendor_id = 0x1234;
		desc.product_id = (Uint16)(0x100 + p);
		desc.name = pads[p].name;
		SDL_JoystickID id = SDL_AttachVirtualJoystick(&desc);
		if (!id) { fprintf(stderr, "virtual joystick: %s\n", SDL_GetError()); return 3; }
		SDL_GUIDToString(SDL_GetJoystickGUIDForID(id), guid, sizeof(guid));
		snprintf(mapping, sizeof(mapping), "%s,%s", guid, pads[p].mapping);
		/* the made-up mapping's name is "*" */
		if (pads[p].mapping[0] == '*') snprintf(mapping, sizeof(mapping), "%s,%s,%s", guid, pads[p].name, pads[p].mapping + 2);
		assert(SDL_AddGamepadMapping(mapping) >= 0);
		SDL_Gamepad *gamepad = SDL_OpenGamepad(id);
		assert(gamepad);
		opened[p] = gamepad;
		SDL_Joystick *joystick = SDL_GetGamepadJoystick(gamepad);
		assert(SDL_GetNumJoystickButtons(joystick) == pads[p].buttons);

		XINPUT_GAMEPAD idle = state(gamepad, joystick, -1, 0);
		assert(!idle.bAnalogButtons[XINPUT_GAMEPAD_LEFT_TRIGGER] && !idle.bAnalogButtons[XINPUT_GAMEPAD_RIGHT_TRIGGER]);
		int l2 = pads[p].buttons > 15 ? state(gamepad, joystick, 15, 0).bAnalogButtons[XINPUT_GAMEPAD_LEFT_TRIGGER] : 0;
		int r2 = pads[p].buttons > 16 ? state(gamepad, joystick, 16, 0).bAnalogButtons[XINPUT_GAMEPAD_RIGHT_TRIGGER] : 0;
		int analog = pads[p].axes > 5 ? state(gamepad, joystick, -1, 1).bAnalogButtons[XINPUT_GAMEPAD_RIGHT_TRIGGER] : 0;
		XINPUT_GAMEPAD l1 = state(gamepad, joystick, 9, 0), r1 = state(gamepad, joystick, 10, 0);
		/* the shoulders stay white and black, and pull no trigger */
		int shoulders = strstr(pads[p].mapping, "leftshoulder:b9") != NULL;
		assert(l1.bAnalogButtons[XINPUT_GAMEPAD_WHITE] == (shoulders ? 255 : 0) && !l1.bAnalogButtons[XINPUT_GAMEPAD_LEFT_TRIGGER]);
		assert(r1.bAnalogButtons[XINPUT_GAMEPAD_BLACK] == (shoulders ? 255 : 0) && !r1.bAnalogButtons[XINPUT_GAMEPAD_RIGHT_TRIGGER]);
		/* a press of the share button or of L2 pulls nothing else */
		if (pads[p].buttons > 15) {
			XINPUT_GAMEPAD share = state(gamepad, joystick, 15, 0);
			assert(!share.bAnalogButtons[XINPUT_GAMEPAD_RIGHT_TRIGGER] && !share.bAnalogButtons[XINPUT_GAMEPAD_WHITE]);
		}
		printf("%s|%d|%d|%d\n", pads[p].name, l2, r2, analog);
	}
	SDL_Quit();
	return 0;
}
'''

expected = {
    'handheld with digital L2 and R2': (255, 255, 0),
    'handheld with analog triggers': (0, 0, 255),
    'handheld with idle trigger axes': (255, 255, 255),
    'Xbox Series in the SDL mapping': (0, 0, 255),
    'Xbox-like in a made-up mapping': (0, 0, 255),
    '8BitDo in the SDL mapping': (255, 255, 0),
    'remote': (0, 0, 0),
}
with tempfile.TemporaryDirectory(prefix='halo-digital-triggers-') as name:
    folder = Path(name)
    (folder / 'test.c').write_text(harness)
    subprocess.run(['cc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wno-unused-function', '-fsanitize=address,undefined',
                    '-I', str(args.sdl_source / 'include'), str(folder / 'test.c'), str(library),
                    '-lm', '-lpthread', '-ldl', '-o', str(folder / 'test')], check=True)
    output = subprocess.run([str(folder / 'test')], check=True, stdout=subprocess.PIPE, text=True).stdout
    results = {}
    for line in output.splitlines():
        pad_name, l2, r2, analog = line.split('|')
        results[pad_name] = (int(l2), int(r2), int(analog))
    failed = [f'{k}: L2/R2/analog {results.get(k)}, expected {v}' for k, v in expected.items() if results.get(k) != v]
    if failed:
        raise SystemExit('FAIL\n' + '\n'.join(failed))
    print(f'PASS: {len(expected)} Android pads against SDL 3.4.16: digital L2/R2 keys pull the triggers where '
          'the mapping leaves them free (made-up mappings); analog triggers, SDL-mapped trigger buttons, the '
          'Xbox share button and the shoulders (white, black) unchanged.')
