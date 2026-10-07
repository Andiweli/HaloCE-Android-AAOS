#!/usr/bin/env python3
"""Run the real input mapping and crouch/weapon code with a small engine fixture.

No duplicated input algorithm: the C bodies are read from the production files.
Run from the project root: python3 tools/test_android_gamepad_integration.py
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def block(source, marker, declaration=False):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + (";" if declaration else "")


def enclosing_enum(source, name):
    start = source.rfind("enum\n", 0, source.index(name))
    return block(source[start:], "enum\n", True)


def main():
    abstraction = (ROOT / "source/input/input_abstraction.c").read_text()
    control = (ROOT / "source/game/player_control.c").read_text()
    units = (ROOT / "source/units/units.c").read_text()
    input_header = (ROOT / "source/input/input.h").read_text()
    preferences_header = (ROOT / "source/input/input_abstraction.h").read_text()
    crouch = control[control.index("byte effective_buttons[NUMBER_OF_ACTION_CONTROL_BUTTONS]"):]
    crouch = block(crouch, "if (player->unit_index != NONE)")
    rotate = block(control, "if (TEST_FLAG(input.player_control_flags, _player_control_rotate_weapons_bit) ||")
    next_weapon = block(units, "static short unit_weapon_next_index(\n")
    look_marker = control.index("/* Apply the physical stick's sensitivity to foot and vehicle look.")
    stick_look = block(control[control.rfind("{", 0, look_marker):], "{")
    fixture = r'''
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>
#include "halo_android_gamepad.h"
#include "halo_android_controls.h"
typedef unsigned char byte, boolean;
typedef float real;
typedef struct { real x, y; } real_point2d;
typedef struct { short x, y; } point2d;
#define MAXIMUM_GAMEPADS 4
#define MAXIMUM_WEAPONS_PER_UNIT 4
#define SHORT_MAX 32767
#define TRUE 1
#define FALSE 0
#define NONE -1
#define MAX(a,b) ((a)>(b)?(a):(b))
#define PIN(a,b,c) ((a)<(b)?(b):((a)>(c)?(c):(a)))
#define FLAG(b) (1u<<(b))
#define TEST_FLAG(f,b) (((f)&FLAG(b))!=0)
#define SET_FLAG(f,b,v) ((f)=(v)?((f)|FLAG(b)):((f)&~FLAG(b)))
#define TAG_BLOCK_GET_ELEMENT(a,b,c) ((void)0)
#define match_assert(file,line,c) assert(c)
#define match_vassert(file,line,c,...) assert(c)
#define csmemcpy memcpy
#define csmemset memset
#define _error_controller_unplugged 1
#define _error_controller_unplugged_start_to_continue 2
#define _error_silent 0
static void error(int kind,const char *message) { (void)kind;(void)message;assert(0); }
static real arctangent(real y,real x) { return atan2f(y,x); }
static real sine(real x) { return sinf(x); }
static real cosine(real x) { return cosf(x); }
static real square_root(real x) { return sqrtf(x); }
'''
    fixture += enclosing_enum(input_header, "FIRST_GAMEPAD_ANALOG_BUTTON")
    fixture += enclosing_enum(input_header, "_gamepad_stick_left")
    fixture += enclosing_enum(abstraction, "_game_control_jump")
    fixture += enclosing_enum(abstraction, "_joystick_controls_default")
    fixture += enclosing_enum(control, "_player_control_rotate_weapons_bit,")
    fixture += "\n" + "\n".join(re.findall(r"^#define (?:STICK_|RIGHT_STICK_|LEFT_STICK_).*", abstraction, re.M))
    fixture += "\n" + block(preferences_header, "struct game_input_preferences\n", True)
    fixture += block(input_header, "struct gamepad_state\n", True)
    fixture += block(abstraction, "struct game_input_state\n", True)
    fixture += block(abstraction, "struct input_abstraction_runtime_globals\n", True)
    fixture += r'''
static struct input_abstraction_runtime_globals input_abstraction_globals;
static struct gamepad_state pads[MAXIMUM_GAMEPADS];
static int connected[MAXIMUM_GAMEPADS] = {1,0,0,0};
static struct halo_android_gamepad_state android_gamepads[MAXIMUM_GAMEPADS];
static real_point2d android_look_sensitivity[MAXIMUM_GAMEPADS];
static real left_sensitivity=1.f,right_sensitivity=1.f;
static unsigned int published_look_mask;
static short primary_controller;
static real player_look_yaw_rate[MAXIMUM_GAMEPADS], player_look_pitch_rate[MAXIMUM_GAMEPADS];
static const real gamepad_axis_normalization_scale = 1.f / SHORT_MAX;
static const real stick_direction_angles[] = {STICK_DIAGONAL_ANGLE,STICK_SECOND_QUADRANT_DIAGONAL_ANGLE,-STICK_DIAGONAL_ANGLE,-STICK_SECOND_QUADRANT_DIAGONAL_ANGLE};
static int we_are_at_the_main_menu, menu, paused, cinematic, overlay, in_game = 1;
struct player_datum { long unit_index; short desired_weapon_index, zoom_level; };
static struct player_datum players[MAXIMUM_GAMEPADS] = {{100,0,0},{NONE,0,0},{NONE,0,0},{NONE,0,0}};
static const struct gamepad_state *input_get_gamepad_state(short i) { return connected[i]?&pads[i]:NULL; }
static int input_has_gamepad(short i) { return connected[i]; }
static unsigned long system_milliseconds(void) { return 1000; }
static int ui_widgets_active(void) { return menu; }
static int game_in_progress(void) { return in_game; }
static int game_time_get_paused(void) { return paused; }
static int cinematic_in_progress(void) { return cinematic; }
int host_settings_active(void) { return overlay; }
void host_settings_sticks(float *left,float *right) { *left=left_sensitivity;*right=right_sensitivity; }
void host_settings_stick_look_mask(unsigned int mask) { published_look_mask=mask; }
static long local_player_get_player_index(short i) { return i; }
static struct player_datum *player_get(long i) { return &players[i]; }
static int local_player_is_piloting_aircraft(short i) { (void)i;return 0; }
static int main_menu_is_active(void) { return we_are_at_the_main_menu; }
static int global_network_game_client_get(void) { return 0; }
static int local_player_exists(long i) { return i==0; }
static int player_ui_get_single_player_local_player_controller(int i) { return i==0?primary_controller:i; }
static short player_ui_android_get_overlay_joystick_preset(void) { return NONE; }
static int player_ui_local_player_wants_to_play_multiplayer(short i) { (void)i;return 0; }
static int virtual_keyboard_active(void) { return 0; }
static void virtual_keyboard_close(void) {}
static void display_error_deferred(int a,int b,int c,int d) { (void)a;(void)b;(void)c;(void)d; }
enum { _biped_airborne_bit, _unit_control_crouch_modifier_bit = 0, _button_crouch = _game_control_crouch };
struct biped_datum { struct { unsigned int flags; } biped; };
static struct biped_datum test_biped;
static struct biped_datum *biped_try_and_get(long i) { return i==NONE?NULL:&test_biped; }
static int controls_enable_crouch;
struct tested_input { struct { float i,j; } throttle; unsigned int unit_control_flags, player_control_flags; };
static float magnitude_squared2d(const void *p) { const float *v=p;return v[0]*v[0]+v[1]*v[1]; }
struct unit_datum { struct { long weapon_object_indices[4], weapon_last_used_at_game_time[4]; short desired_weapon_index; } unit; };
static struct unit_datum test_unit = {{{10,11,12,13},{0,0,0,0},0}};
static struct unit_datum *unit_get(long i) { (void)i;return &test_unit; }
static int unit_can_use_weapon(long u,long w) { (void)u;(void)w;return 1; }
static int weapon_must_be_readied(long w) { (void)w;return 0; }
static long unit_inventory_get_weapon(long u,short i) { (void)u;return i==NONE?NONE:test_unit.unit.weapon_object_indices[i]; }
'''
    fixture += next_weapon
    fixture += "\nstatic short unit_inventory_next_weapon(long u,short i,short delta) { return unit_weapon_next_index(u,i,delta); }\n"
    fixture += block(abstraction, "static unsigned int android_stick_look_mask(")
    fixture += block(abstraction, "static void android_publish_stick_look(")
    fixture += block(abstraction, "void input_abstraction_update_local_player_preferences(")
    fixture += block(abstraction, "void input_abstraction_android_reset_gamepad(")
    fixture += block(abstraction, "short input_abstraction_android_take_weapon_delta(")
    fixture += block(abstraction, "void input_abstraction_android_get_look_sensitivity(")
    fixture += block(abstraction, "static void set_default_game_input_preferences(\n\tstruct game_input_preferences *preferences)\n{")
    fixture += block(abstraction, "void input_abstraction_reset_controller_detection_timer(")
    fixture += block(abstraction, "void input_abstraction_initialize(")
    fixture += block(abstraction, "void input_abstraction_update(\n\tvoid)\n{")
    fixture += "\nstatic int tested_crouch(float forward,float sideways,int held) { struct player_datum *player=&players[0]; struct tested_input value={{forward,sideways},0,0}; struct tested_input *input=&value; byte effective_buttons[12]={0}; effective_buttons[_button_crouch]=held;\n"
    fixture += crouch + "\nreturn !!(input->unit_control_flags&FLAG(_unit_control_crouch_modifier_bit)); }\n"
    fixture += "static short tested_rotate(unsigned int flags,short desired) { struct tested_input input={{0,0},0,flags}; struct player_datum value={100,desired,0}; struct player_datum *player=&value;\n"
    fixture += rotate + "\nreturn player->desired_weapon_index; }\n"
    fixture += "static void tested_stick_look(short gamepad_index,float *yaw,float *pitch) { real look_yaw_rate=*yaw,look_pitch_rate=*pitch;\n"
    fixture += stick_look + "\n*yaw=look_yaw_rate;*pitch=look_pitch_rate; }\n"
    fixture += r'''
static void sample(unsigned int down,short x,short y)
{
    memset(pads[0].buttons,0,sizeof(pads[0].buttons));
    if(down&HALO_ANDROID_DPAD_UP) pads[0].buttons[_gamepad_binary_button_dpad_up]=1;
    if(down&HALO_ANDROID_DPAD_DOWN) pads[0].buttons[_gamepad_binary_button_dpad_down]=1;
    if(down&HALO_ANDROID_DPAD_LEFT) pads[0].buttons[_gamepad_binary_button_dpad_left]=1;
    if(down&HALO_ANDROID_DPAD_RIGHT) pads[0].buttons[_gamepad_binary_button_dpad_right]=1;
    pads[0].sticks[0].x=x;pads[0].sticks[0].y=y;
    input_abstraction_update();
}
int main(void)
{
    struct game_input_state *state=&input_abstraction_globals.input_states[0];
    int preset,i;
    primary_controller=2;published_look_mask=1;
    input_abstraction_initialize();
#ifdef HALO_ANDROID
    assert(published_look_mask==2); /* Input initializes before the player UI/controller mapping. */
#endif
    primary_controller=0;
    for(preset=0;preset<NUMBER_OF_JOYSTICK_CONTROLS;preset++) {
        input_abstraction_globals.player_control_preferences[0].joystick_controls=preset;
        sample(0,0,0);sample(HALO_ANDROID_DPAD_DOWN|HALO_ANDROID_DPAD_LEFT,0,0);
#ifdef HALO_ANDROID
        assert(state->buttons[_game_control_crouch]);
        assert(!state->forward_movement&&!state->strafe&&!state->yaw&&!state->pitch);
        assert(input_abstraction_android_take_weapon_delta(0)==-1);
        sample(0,0,0);assert(state->buttons[_game_control_crouch]);
        sample(HALO_ANDROID_DPAD_UP,0,0);assert(!state->buttons[_game_control_crouch]);
#else
        assert(state->forward_movement||state->strafe||state->yaw||state->pitch);
#endif
        menu=1;sample(HALO_ANDROID_DPAD_DOWN|HALO_ANDROID_DPAD_LEFT,0,0);
        assert(state->forward_movement||state->strafe||state->yaw||state->pitch);
        assert(!input_abstraction_android_take_weapon_delta(0));
        menu=0;sample(0,0,0);
    }
    input_abstraction_globals.player_control_preferences[0].joystick_controls=0;
    for(i=0;i<8;i++) {
        static const short axes[8][2]={{32767,0},{-32767,0},{0,32767},{0,-32767},{32767,32767},{-32767,32767},{32767,-32767},{-32767,-32767}};
        sample(0,axes[i][0],axes[i][1]);pads[0].buttons[_gamepad_binary_button_left_thumb]=1;input_abstraction_update();
        assert(state->buttons[_game_control_crouch]);
#ifdef HALO_ANDROID
        assert(tested_crouch(state->forward_movement,state->strafe,state->buttons[_game_control_crouch]));
#else
        assert(!tested_crouch(state->forward_movement,state->strafe,state->buttons[_game_control_crouch]));
#endif
        sample(0,axes[i][0],axes[i][1]);assert(!state->buttons[_game_control_crouch]);
    }
    assert(tested_rotate(FLAG(_player_control_rotate_weapons_bit),1)==2);
#ifdef HALO_ANDROID
    /* The actual mapping and look-rate block must follow physical sticks in
       all presets, preserve 100%, and scale full-deflection look beyond 100%. */
    for(preset=0;preset<NUMBER_OF_JOYSTICK_CONTROLS;preset++) {
        struct game_input_state baseline;
        float yaw_rate=20.f,pitch_rate=10.f;
        struct game_input_preferences preferences=input_abstraction_globals.player_control_preferences[0];
        static const unsigned int masks[4]={2,1,3,3};
        preferences.joystick_controls=preset;
        input_abstraction_update_local_player_preferences(0,&preferences);
        assert(published_look_mask==masks[preset]); /* Immediate profile notification, before polling input. */
        pads[0].sticks[1].x=9000;pads[0].sticks[1].y=-7000;
        left_sensitivity=right_sensitivity=1.f;
        sample(0,11000,13000);baseline=*state;
        tested_stick_look(0,&yaw_rate,&pitch_rate);assert(yaw_rate==20.f&&pitch_rate==10.f);
        left_sensitivity=.5f;right_sensitivity=1.5f;
        sample(0,11000,13000);
        {
            int right_forward=preset==1||preset==3,right_strafe=preset==1||preset==2;
            assert(state->forward_movement==baseline.forward_movement);
            assert(state->strafe==baseline.strafe);
            assert(state->yaw==baseline.yaw&&state->pitch==baseline.pitch);
            tested_stick_look(0,&yaw_rate,&pitch_rate);
            assert(yaw_rate==(right_strafe?10.f:30.f));
            assert(pitch_rate==(right_forward?5.f:15.f));
        }
        menu=1;sample(0,11000,13000);assert(state->forward_movement==baseline.forward_movement&&state->strafe==baseline.strafe&&published_look_mask==masks[preset]);
        yaw_rate=20.f;pitch_rate=10.f;tested_stick_look(0,&yaw_rate,&pitch_rate);assert(yaw_rate==20.f&&pitch_rate==10.f);menu=0;
    }
    input_abstraction_globals.player_control_preferences[0].joystick_controls=0;
    left_sensitivity=right_sensitivity=1.5f;
    pads[0].sticks[1].x=32767;pads[0].sticks[1].y=0;
    sample(0,32767,32767);assert(state->forward_movement==1.f&&state->strafe==-1.f&&state->yaw==-1.f);
    {float yaw=20.f,pitch=10.f;tested_stick_look(0,&yaw,&pitch);assert(yaw==30.f&&pitch==15.f);}
    /* Legacy diagonal shaping can exceed 1 before the engine normalizes
       movement. Look-only sensitivity must retain it at every setting. */
    input_abstraction_globals.player_control_preferences[0].joystick_controls=2;
    left_sensitivity=right_sensitivity=1.f;
    sample(0,32767,32767);assert(state->forward_movement==sqrtf(2.f));
    left_sensitivity=1.5f;sample(0,32767,32767);assert(state->forward_movement==sqrtf(2.f));
    left_sensitivity=.5f;sample(0,32767,32767);assert(state->forward_movement==sqrtf(2.f));
    input_abstraction_globals.player_control_preferences[0].joystick_controls=0;
    paused=1;sample(0,10000,0);assert(android_look_sensitivity[0].x==1.f);paused=0;
    overlay=1;sample(0,10000,0);assert(android_look_sensitivity[0].x==1.f&&published_look_mask==2);overlay=0;
    /* Other profiles cannot overwrite the primary player's role. Switching
       primary controllers and the pre-profile NONE state use the actual UI mapping. */
    {
        struct game_input_preferences preferences=input_abstraction_globals.player_control_preferences[2];
        preferences.joystick_controls=1;
        input_abstraction_update_local_player_preferences(2,&preferences);assert(published_look_mask==2);
        primary_controller=2;input_abstraction_update_local_player_preferences(2,&preferences);assert(published_look_mask==1);
        overlay=1;input_abstraction_update();assert(published_look_mask==1);overlay=0;
        primary_controller=NONE;input_abstraction_update();assert(published_look_mask==2);
        primary_controller=0;
    }
    left_sensitivity=right_sensitivity=1.f;pads[0].sticks[1].x=pads[0].sticks[1].y=0;
    puts("Stick integration: all profile roles, immediate updates, primary controller, unchanged movement, 50/150% look, menus, pause and overlay passed.");
    assert(tested_rotate(FLAG(_player_control_rotate_weapons_bit)|FLAG(_player_control_rotate_weapons_backwards_bit),1)==0);
    assert(tested_rotate(FLAG(_player_control_rotate_weapons_bit)|FLAG(_player_control_rotate_weapons_backwards_bit),0)==3);
    for(i=0;i<5;i++) {
        sample(0,0,0);
        if(i==0) paused=1;if(i==1) cinematic=1;if(i==2) we_are_at_the_main_menu=1;if(i==3) players[0].unit_index=NONE;if(i==4) overlay=1;
        sample(HALO_ANDROID_DPAD_DOWN|HALO_ANDROID_DPAD_RIGHT,0,0);
        assert(!state->buttons[_game_control_crouch]&&!input_abstraction_android_take_weapon_delta(0));
        paused=cinematic=we_are_at_the_main_menu=overlay=0;players[0].unit_index=100;
        sample(HALO_ANDROID_DPAD_DOWN|HALO_ANDROID_DPAD_RIGHT,0,0);
        assert(!state->buttons[_game_control_crouch]&&!input_abstraction_android_take_weapon_delta(0));
    }
    sample(0,0,0);sample(HALO_ANDROID_DPAD_DOWN,0,0);assert(state->buttons[_game_control_crouch]);
    input_abstraction_android_reset_gamepad(0);sample(HALO_ANDROID_DPAD_DOWN,0,0);assert(!state->buttons[_game_control_crouch]);
    connected[0]=0;input_abstraction_update();connected[0]=1;sample(0,0,0);assert(!state->buttons[_game_control_crouch]);
    puts("Android integration: all four presets, L3 movement in eight directions, menus, lifecycle and previous/next weapons passed.");
#else
    puts("Non-Android integration: original D-pad movement and full-stick crouch behavior preserved.");
#endif
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="halo-gamepad-") as directory:
        source = Path(directory) / "integration.c"
        source.write_text(fixture)
        for android in (True, False):
            binary = Path(directory) / ("android" if android else "original")
            command = [os.environ.get("CC", "cc"), "-std=c99", "-I", str(ROOT / "port/linux/include")]
            if android:
                command.append("-DHALO_ANDROID")
            subprocess.run(command + [str(source), "-lm", "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
