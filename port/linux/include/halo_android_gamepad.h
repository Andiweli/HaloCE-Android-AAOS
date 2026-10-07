#ifndef HALO_ANDROID_GAMEPAD_H
#define HALO_ANDROID_GAMEPAD_H

enum halo_android_dpad_button
{
	HALO_ANDROID_DPAD_UP = 1,
	HALO_ANDROID_DPAD_DOWN = 2,
	HALO_ANDROID_DPAD_LEFT = 4,
	HALO_ANDROID_DPAD_RIGHT = 8,
};

/* Runtime input state, deliberately separate from profiles and saved games. */
struct halo_android_gamepad_state
{
	unsigned int previous_dpad;
	int crouch_latched;
	short weapon_delta;
};

static void halo_android_gamepad_reset(struct halo_android_gamepad_state *state)
{
	/* A direction held during a menu, respawn or map change needs releasing. */
	state->crouch_latched = 0;
	state->weapon_delta = 0;
}

static void halo_android_gamepad_update(
	struct halo_android_gamepad_state *state,
	unsigned int dpad,
	int gameplay_active)
{
	unsigned int pressed = dpad & ~state->previous_dpad;

	state->previous_dpad = dpad;
	state->weapon_delta = 0;
	if (!gameplay_active)
	{
		halo_android_gamepad_reset(state);
		return;
	}

	if (pressed & HALO_ANDROID_DPAD_UP)
		state->crouch_latched = 0;
	else if (pressed & HALO_ANDROID_DPAD_DOWN)
		state->crouch_latched = 1;

	/* Holding a direction cannot repeatedly cycle weapons. Opposites cancel. */
	if (!(dpad & HALO_ANDROID_DPAD_RIGHT) && (pressed & HALO_ANDROID_DPAD_LEFT))
		state->weapon_delta = -1;
	else if (!(dpad & HALO_ANDROID_DPAD_LEFT) && (pressed & HALO_ANDROID_DPAD_RIGHT))
		state->weapon_delta = 1;
}

static short halo_android_gamepad_take_weapon_delta(struct halo_android_gamepad_state *state)
{
	short delta = state->weapon_delta;
	state->weapon_delta = 0;
	return delta;
}

void input_abstraction_android_reset_gamepad(short controller_index);
short input_abstraction_android_take_weapon_delta(short controller_index);
void input_abstraction_android_get_look_sensitivity(short controller_index, float *yaw, float *pitch);

#endif
