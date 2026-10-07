/* cc -std=c99 -Wall -Wextra -Werror tools/test_android_gamepad.c -o /tmp/halo-gamepad-test */
#include <assert.h>
#include <stdio.h>
#include "../port/linux/include/halo_android_gamepad.h"

int main(void)
{
	struct halo_android_gamepad_state a = {0}, b = {0};
	int frame;

	/* DOWN latches across release; another DOWN cannot toggle it off. */
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_DOWN, 1);
	assert(a.crouch_latched);
	halo_android_gamepad_update(&a, 0, 1);
	assert(a.crouch_latched);
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_DOWN, 1);
	assert(a.crouch_latched);
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_UP, 1);
	assert(!a.crouch_latched);
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_UP | HALO_ANDROID_DPAD_DOWN, 1);
	assert(a.crouch_latched); /* Only DOWN is a new press in this sample. */
	halo_android_gamepad_update(&a, 0, 1);
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_UP | HALO_ANDROID_DPAD_DOWN, 1);
	assert(!a.crouch_latched); /* Simultaneous new presses prefer standing. */

	/* LEFT is -1, RIGHT is +1; holding and repeated reads do not cycle. */
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_LEFT, 1);
	assert(halo_android_gamepad_take_weapon_delta(&a) == -1);
	assert(halo_android_gamepad_take_weapon_delta(&a) == 0);
	for (frame = 0; frame < 300; ++frame)
	{
		halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_LEFT, 1);
		assert(halo_android_gamepad_take_weapon_delta(&a) == 0);
	}
	halo_android_gamepad_update(&a, 0, 1);
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_LEFT, 1);
	assert(halo_android_gamepad_take_weapon_delta(&a) == -1);
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_RIGHT, 1);
	assert(halo_android_gamepad_take_weapon_delta(&a) == 1);
	halo_android_gamepad_update(&a, 0, 1);
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_LEFT | HALO_ANDROID_DPAD_RIGHT, 1);
	assert(halo_android_gamepad_take_weapon_delta(&a) == 0);

	/* Menu/pause/cinematic samples must not leak actions when gameplay resumes. */
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_DOWN | HALO_ANDROID_DPAD_RIGHT, 0);
	assert(!a.crouch_latched && !a.weapon_delta);
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_DOWN | HALO_ANDROID_DPAD_RIGHT, 1);
	assert(!a.crouch_latched && !a.weapon_delta);
	halo_android_gamepad_update(&a, 0, 1);
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_DOWN | HALO_ANDROID_DPAD_RIGHT, 1);
	assert(a.crouch_latched && a.weapon_delta == 1);

	/* Local players have independent latches and pending weapon changes. */
	halo_android_gamepad_update(&b, HALO_ANDROID_DPAD_UP | HALO_ANDROID_DPAD_LEFT, 1);
	assert(!b.crouch_latched && b.weapon_delta == -1);
	assert(a.crouch_latched && a.weapon_delta == 1);
	halo_android_gamepad_reset(&a);
	assert(!a.crouch_latched && !a.weapon_delta);
	assert(b.weapon_delta == -1);
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_DOWN | HALO_ANDROID_DPAD_RIGHT, 1);
	assert(!a.crouch_latched && !a.weapon_delta);
	halo_android_gamepad_update(&a, 0, 0); /* Controller disconnect. */
	halo_android_gamepad_update(&a, HALO_ANDROID_DPAD_DOWN, 1);
	assert(a.crouch_latched);

	puts("Android gamepad: explicit crouch/stand, weapon directions, held buttons, menus and resets passed.");
	return 0;
}
