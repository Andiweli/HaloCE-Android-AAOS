/*
CHEATS.C

symbols in this file:
00094C50 0020:
	_cheats_initialize (0000)
00094C70 0010:
	_cheats_dispose (0000)
00094C80 0010:
	_cheats_dispose_from_old_map (0000)
00094C90 00b0:
	_cheats_update (0000)
00094D40 0090:
	_cheats_load (0000)
00094DD0 0060:
	_cheat_active_camouflage_local_player (0000)
00094E30 0060:
	_cheat_player_index (0000)
00094E90 0010:
	_cheats_initialize_for_new_map (0000)
00094EA0 00b0:
	_cheat_teleport_to_camera (0000)
00094F50 0050:
	_cheat_active_camouflage (0000)
00094FA0 0150:
	_cheat_objects (0000)
000950F0 00d0:
	_cheat_all_weapons (0000)
000951C0 0050:
	_cheat_all_powerups (0000)
00095210 0050:
	_cheat_all_vehicles (0000)
0025AC64 003b:
	??_C@_0DL@LCJIJOPI@Cannot?5execute?5cheats?5attached?5t@ (0000)
0025ACA0 0005:
	??_C@_04JNJDPIIA@?$AN?6?7?$DL?$AA@ (0000)
0025ACA8 000e:
	??_C@_0O@KAFNGCBO@d?3?2cheats?4txt?$AA@ (0000)
0025ACB8 003a:
	??_C@_0DK@OACLODJP@Camera?5is?5outside?5BSP?4?4?4?5cannot?5@ (0000)
0025ACF4 001d:
	??_C@_0BN@DPPGFJCA@c?3?2halo?2SOURCE?2game?2cheats?4c?$AA@ (0000)
0025AD14 0004:
	__real@3ec90fdb (0000)
0043D808 0c81:
	_cheat_strings (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "cseries/errors.h"
#include "cheats.h"
#include "cache/cache_files.h"
#include "camera/director.h"
#include "camera/observer.h"
#include "game/game_globals.h"
#include "game/players.h"
#include "hs/hs.h"
#include "input/input.h"
#include "interface/terminal.h"
#include "items/weapon_definitions.h"
#include "main/console.h"
#include "math/real_math.h"
#include "objects/objects.h"
#include "rasterizer/rasterizer_console_vars.h"
#include "scenario/scenario.h"
#include "tag_files/tag_groups.h"
#include "units/units.h"

/* ---------- constants */

enum
{
	MAXIMUM_CHEATS = NUMBER_OF_GAMEPAD_BUTTONS,
	MAXIMUM_CHEAT_LENGTH = 200
};

#define CHEATS_FILENAME "d:\\cheats.txt"

/* ---------- macros */

#define TAG_BLOCK_TRY_AND_GET_ELEMENT(block_address, index, type) \
	((block_address)->count ? TAG_BLOCK_GET_ELEMENT((block_address), (index), type) : NULL)

/* ---------- structures */

/* ---------- prototypes */

/* ---------- globals */

static char cheat_strings[MAXIMUM_CHEATS][MAXIMUM_CHEAT_LENGTH] = {0};
/* January emits this otherwise unreferenced byte after cheat_strings.
 * Its original name and purpose are unknown; the name is descriptive only. */
static boolean cheats_unused_flag = FALSE;

/* ---------- code */

void cheats_initialize(
	void)
{
	csmemset(cheat_strings, 0, sizeof(cheat_strings));

	return;
}

void cheats_dispose(
	void)
{
	return;
}

void cheats_dispose_from_old_map(
	void)
{
	return;
}

/* network_game_globals.c's */
boolean network_game_distributed_client(void);
/* bipeds.c's, player_control.c's */
extern boolean rider_ejection;
extern boolean player_autoaim_flag;
extern boolean player_magnetism_flag;
/* game_time.c's */
boolean game_time_reset_speed(void);

/* port: what the machine draws of the world put back as it draws it for
everyone: nothing seen through walls (wireframe, a drawing mode, the
environment or its parts left out), past fog, or under grass and water;
whether any was other */
static boolean cheats_network_client_rasterizer_enforce(
	void)
{
	boolean changed = FALSE;
	boolean *environment_part;

	if (rasterizer_debug_options.wireframe_enabled || rasterizer_debug_options.drawing_mode != 0 ||
		!rasterizer_debug_options.draw_water || !rasterizer_debug_options.draw_detail_objects ||
		!rasterizer_debug_options.draw_lens_flares || !rasterizer_debug_options.fog_atmospheric_enabled ||
		!rasterizer_debug_options.fog_planar_enabled)
	{
		changed = TRUE;
	}
	rasterizer_debug_options.wireframe_enabled = FALSE;
	rasterizer_debug_options.drawing_mode = 0;
	rasterizer_debug_options.draw_water = TRUE;
	rasterizer_debug_options.draw_detail_objects = TRUE;
	rasterizer_debug_options.draw_lens_flares = TRUE;
	rasterizer_debug_options.fog_atmospheric_enabled = TRUE;
	rasterizer_debug_options.fog_planar_enabled = TRUE;
	/* (the environment and its parts, lightmaps to screen fog, all drawn,
	as rasterizer_frame_begin leaves them from its switch: 2, given) */
	for (environment_part = &rasterizer_debug_options.draw_environment_lightmaps;
		environment_part <= &rasterizer_debug_options.draw_environment_fog_screen;
		environment_part++)
	{
		if (!*environment_part)
			changed = TRUE;
		*environment_part = TRUE;
	}
	if (rasterizer_debug_options.draw_environment != 2)
		changed = TRUE;
	rasterizer_debug_options.draw_environment = 2;

	return changed;
}

/* port: a client in another's game plays by the host's rules: none of its
own cheats, its own game speed or its own changes to how players play, nor
what its drawing shows it that others' does not, set before it joined too
(after, hs_compile_and_evaluate refuses them); each frame and each tick */
void cheats_network_client_enforce(
	void)
{
	static struct cheat_globals const none = { 0 };
	boolean changed;

	if (!network_game_distributed_client())
		return;
	changed = csmemcmp(&cheat, &none, sizeof(cheat)) != 0 || !rider_ejection || !player_autoaim_flag ||
		!player_magnetism_flag;
	csmemset(&cheat, 0, sizeof(cheat));
	rider_ejection = TRUE;
	player_autoaim_flag = TRUE;
	player_magnetism_flag = TRUE;
	changed |= game_time_reset_speed();
	changed |= cheats_network_client_rasterizer_enforce();
	if (changed)
	{
		console_warning("playing in another's game: its host's rules (cheats, game speed and drawing put back)");
		error(_error_log, "playing in another's game: cheats, game speed and drawing put back to the host's");
	}

	return;
}

void cheats_update(
	void)
{
	cheats_network_client_enforce();
	if (cheat.controller_enabled)
	{
		short local_player_index;

		for (local_player_index = local_player_get_next(NONE);
			local_player_index!=NONE;
			local_player_index = local_player_get_next(local_player_index))
		{
			struct gamepad_state const *gamepad = input_get_gamepad_state(local_player_index);

			if (gamepad && gamepad->buttons[_gamepad_binary_button_back]>0)
			{
				short button_index;

				for (button_index = 0; button_index<MAXIMUM_CHEATS; button_index++)
				{
					if (cheat_strings[button_index][0] && gamepad->buttons[button_index]>0)
					{
						director_inhibit_input(local_player_index);

						if (gamepad->buttons[button_index]==1)
						{
							console_printf(FALSE, cheat_strings[button_index]);
							if (!hs_compile_and_evaluate(cheat_strings[button_index]))
								cheat_strings[button_index][0] = 0;
						}
					}
				}
			}
		}
	}

	return;
}

void cheats_load(
	void)
{
	FILE *file = fopen(CHEATS_FILENAME, "r");

	if (file)
	{
		short cheat_index;

		for (cheat_index = 0; cheat_index<MAXIMUM_CHEATS; cheat_index++)
		{
			if (!fgets(cheat_strings[cheat_index], MAXIMUM_CHEAT_LENGTH-1, file))
				break;

			csstrtok(cheat_strings[cheat_index], "\r\n\t;");

			if ((cheat_index==_gamepad_binary_button_back || cheat_index==_gamepad_binary_button_start)
				&& cheat_strings[cheat_index][0])
			{
				cheat_strings[cheat_index][0] = 0;
				error(2, "Cannot execute cheats attached to the back or start button");
			}
		}

		fclose(file);
	}

	return;
}

void cheat_active_camouflage_local_player(
	short local_player_index)
{
	if (local_player_index>=0 && local_player_index<MAXIMUM_LOCAL_PLAYERS)
	{
		long player_index = local_player_get_player_index(local_player_index);

		if (player_index!=NONE)
		{
			struct player_datum *player = player_get(player_index);
			struct unit_datum *unit = unit_get(player->unit_index);

			unit->unit.active_camouflage = 1.0f;
			if (TEST_FLAG(unit->unit.flags, _unit_active_camouflaged_bit))
				unit->unit.flags |= FLAG(_unit_super_camouflaged_bit);
			unit->unit.flags |= FLAG(_unit_active_camouflaged_bit);
		}
	}

	return;
}

static long cheat_player_index(
	void)
{
	struct data_iterator iterator;
	struct player_datum *player;
	long player_index = NONE;

	data_iterator_new(&iterator, player_data);
	while ((player = (struct player_datum *)data_iterator_next(&iterator))!=NULL)
	{
		if (player->unit_index!=NONE)
		{
			player_index = iterator.datum_index;
			break;
		}
	}

	return player_index;
}

void cheats_initialize_for_new_map(
	void)
{
	cheats_load();

	return;
}

void cheat_teleport_to_camera(
	void)
{
	long player_index = cheat_player_index();

	if (player_index!=NONE)
	{
		struct player_datum *player = player_get(player_index);

		if (player->local_player_index!=NONE)
		{
			struct observer_result const *result = observer_get_camera(player->local_player_index);

			match_assert("c:\\halo\\SOURCE\\game\\cheats.c", 256, result);

			if (result->location.cluster_index!=NONE)
			{
				long object_index = unit_get(player->unit_index)->object.parent_object_index;

				if (object_index==NONE)
					object_index = player->unit_index;

				object_set_position(object_index, &result->position, NULL, NULL);
			}
			else
			{
				terminal_printf(global_real_argb_orange, "Camera is outside BSP... cannot initiate teleportation...");
			}
		}
	}

	return;
}

void cheat_active_camouflage(
	void)
{
	long player_index = cheat_player_index();

	if (player_index!=NONE)
	{
		struct player_datum *player = player_get(player_index);
		struct unit_datum *unit = unit_get(player->unit_index);

		unit->unit.active_camouflage = 1.0f;
		if (TEST_FLAG(unit->unit.flags, _unit_active_camouflaged_bit))
			unit->unit.flags |= FLAG(_unit_super_camouflaged_bit);
		unit->unit.flags |= FLAG(_unit_active_camouflaged_bit);
	}

	return;
}

static void cheat_objects(
	struct tag_reference *references,
	short reference_count)
{
	long player_index = cheat_player_index();

	if (player_index!=NONE)
	{
		struct player_datum *player = player_get(player_index);
		struct unit_datum *unit = unit_get(player->unit_index);
		real_point3d origin;
		real_vector3d forward, up;
		short reference_index;

		object_get_origin(player->unit_index, &origin);
		object_get_orientation(player->unit_index, &forward, &up);

		for (reference_index = 0; reference_index<reference_count; reference_index++)
		{
			if (references[reference_index].index!=NONE)
			{
				struct object_placement_data data;
				real angle_separation = CEILING(2*_pi/reference_count, _pi/8);
				real angle = arctangent(forward.i, forward.j)+
					(reference_index-reference_count/2)*angle_separation;

				object_placement_data_new(&data, references[reference_index].index, NONE);

				data.position.x = cosine(angle)*1.5f+origin.x;
				data.position.y = sine(angle)*1.5f+origin.y;
				data.position.z = origin.z+0.8f;
				data.forward = forward;
				data.up = up;

				object_new(&data);
			}
		}
	}

	return;
}

void cheat_all_weapons(
	void)
{
	struct game_globals *globals = scenario_get_game_globals();

	if (TAG_BLOCK_TRY_AND_GET_ELEMENT(&globals->weapon_list, 0, struct tag_reference))
	{
		cheat_objects(
			TAG_BLOCK_TRY_AND_GET_ELEMENT(&globals->weapon_list, 0, struct tag_reference),
			(short)globals->weapon_list.count);
	}
	else
	{
		struct tag_reference references[MAXIMUM_CHEATS];
		struct tag_iterator iterator;
		long tag_index;
		short reference_count = 0;

		tag_iterator_new(&iterator, WEAPON_DEFINITION_TAG);
		for (tag_index = tag_iterator_next(&iterator);
			tag_index!=NONE && reference_count<NUMBEROF(references);
			tag_index = tag_iterator_next(&iterator))
		{
			references[reference_count].index = tag_index;
			reference_count++;
		}

		cheat_objects(references, reference_count);
	}

	return;
}

void cheat_all_powerups(
	void)
{
	struct game_globals *globals = scenario_get_game_globals();

	cheat_objects(
		TAG_BLOCK_TRY_AND_GET_ELEMENT(&globals->cheat_powerups, 0, struct tag_reference),
		(short)globals->cheat_powerups.count);

	return;
}

void cheat_all_vehicles(
	void)
{
	struct game_globals *globals = scenario_get_game_globals();

	if (globals->multiplayer_information.count)
	{
		cheat_objects(
			TAG_BLOCK_ADDRESS(TAG_BLOCK_GET_ELEMENT(&globals->multiplayer_information, 0,
				struct game_globals_multiplayer_information)->vehicles),
			(short)TAG_BLOCK_GET_ELEMENT(&globals->multiplayer_information, 0,
				struct game_globals_multiplayer_information)->vehicles.count);
	}

	return;
}

#ifdef HALO_ANDROID
#include "halo_android_controls.h"
#include "units/vehicle_definitions.h"
#include "tag_files/tag_files.h"

/* port: the in-game menu's Warthog (SettingsOverlay.java): the map's
Warthog, the plain one before the rocket one, or NONE where the map has
none (The Pillar of Autumn's) */
static long android_cheat_warthog(
	void)
{
	struct tag_iterator iterator;
	long tag_index, found = NONE;

	tag_iterator_new(&iterator, VEHICLE_DEFINITION_TAG);
	for (tag_index = tag_iterator_next(&iterator);
		tag_index!=NONE;
		tag_index = tag_iterator_next(&iterator))
	{
		char const *name = tag_get_name(tag_index);

		if (name && strstr(name, "warthog"))
		{
			if (!strstr(name, "rwarthog"))
				return tag_index;
			if (found==NONE)
				found = tag_index;
		}
	}

	return found;
}

/* port: it a few metres ahead of the player, where it does not land on him */
static boolean android_cheat_spawn_warthog(
	void)
{
	long player_index = cheat_player_index();
	long definition_index = android_cheat_warthog();
	struct object_placement_data data;
	struct player_datum *player;
	real_point3d origin;
	real_vector3d forward, up;
	real length;

	if (player_index==NONE || definition_index==NONE)
		return FALSE;
	player = player_get(player_index);
	object_get_origin(player->unit_index, &origin);
	object_get_orientation(player->unit_index, &forward, &up);
	length = square_root(forward.i*forward.i+forward.j*forward.j);
	if (length<0.01f)
	{
		forward.i = 1.0f;
		forward.j = 0.0f;
		length = 1.0f;
	}
	forward.i /= length;
	forward.j /= length;
	forward.k = 0.0f;
	object_placement_data_new(&data, definition_index, NONE);
	data.position.x = origin.x+forward.i*4.5f;
	data.position.y = origin.y+forward.j*4.5f;
	data.position.z = origin.z+0.6f;
	data.forward = forward;
	data.up.i = 0.0f;
	data.up.j = 0.0f;
	data.up.k = 1.0f;

	return object_new(&data)!=NONE;
}

/* port: the in-game menu's cheats, once a frame from main_loop: the
switches as the original's cheat globals (cheat_deathless_player,
cheat_infinite_ammo, cheat_bottomless_clip, cheat_omnipotent), set when the
menu changes them so the console's stay as they are; the buttons once,
answered to the menu. Never in another's network game, whose host's rules
cheats_network_client_enforce keeps. */
void android_cheats_update(
	boolean in_game)
{
	static unsigned int applied;
	static boolean applied_valid;
	unsigned int actions;
	unsigned int bits = host_settings_cheats(&actions);
	boolean playing = in_game && !network_game_distributed_client() && cheat_player_index()!=NONE;
	short action;

	/* another's game puts all of them back (cheats_network_client_enforce):
	afterwards the menu's all four again */
	if (network_game_distributed_client())
		applied_valid = FALSE;
	else if (!applied_valid || bits!=applied)
	{
		unsigned int changed = applied_valid ? bits^applied : HALO_ANDROID_CHEAT_SWITCHES;

		if (changed & HALO_ANDROID_CHEAT_HEALTH)
			cheat.deathless_player = (bits & HALO_ANDROID_CHEAT_HEALTH)!=0;
		if (changed & HALO_ANDROID_CHEAT_AMMO)
			cheat.infinite_ammo = (bits & HALO_ANDROID_CHEAT_AMMO)!=0;
		if (changed & HALO_ANDROID_CHEAT_NEVER_RELOAD)
			cheat.bottomless_clip = (bits & HALO_ANDROID_CHEAT_NEVER_RELOAD)!=0;
		if (changed & HALO_ANDROID_CHEAT_ONE_HIT_KILL)
			cheat.omnipotent = (bits & HALO_ANDROID_CHEAT_ONE_HIT_KILL)!=0;
		error(_error_log, "android cheats: %s%s%s%s",
				bits & HALO_ANDROID_CHEAT_HEALTH ? "deathless " : "",
				bits & HALO_ANDROID_CHEAT_AMMO ? "infinite_ammo " : "",
				bits & HALO_ANDROID_CHEAT_NEVER_RELOAD ? "bottomless_clip " : "",
				bits & HALO_ANDROID_CHEAT_ONE_HIT_KILL ? "omnipotent" : "");
		applied = bits;
		applied_valid = TRUE;
	}

	for (action = 0; action<HALO_ANDROID_CHEAT_ACTIONS; action++)
	{
		int result;

		if (!(actions & (1u<<action)))
			continue;
		if (!playing)
			result = HALO_ANDROID_CHEAT_RESULT_NO_GAME;
		else if (action==HALO_ANDROID_CHEAT_ACTION_WEAPONS)
		{
			cheat_all_weapons();
			result = HALO_ANDROID_CHEAT_RESULT_DONE;
		}
		else
			result = android_cheat_spawn_warthog() ? HALO_ANDROID_CHEAT_RESULT_DONE : HALO_ANDROID_CHEAT_RESULT_MISSING;
		host_settings_cheat_done(action, result);
	}

	return;
}
#endif
