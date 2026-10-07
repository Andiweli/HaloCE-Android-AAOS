#!/usr/bin/env python3
"""Exercise Halo's real controller-menu callback and profile save/cancel path.

Only file storage and widget plumbing are mocked; profile/application functions
are extracted from production C, including the Android overlay notification.
Run from the project root: python3 tools/test_android_profile_controls.py
"""
from pathlib import Path
import os
import subprocess
import tempfile

from test_android_gamepad_integration import block, enclosing_enum

ROOT = Path(__file__).resolve().parents[1]


def main():
    ui = (ROOT / "source/interface/player_ui.c").read_text()
    widgets = (ROOT / "source/interface/ui_widget_event_handler_functions.c").read_text()
    abstraction = (ROOT / "source/input/input_abstraction.c").read_text()
    profile = (ROOT / "source/saved games/player_profile.h").read_text()
    input_header = (ROOT / "source/input/input.h").read_text()
    preferences = (ROOT / "source/input/input_abstraction.h").read_text()
    fixture = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "halo_android_controls.h"
typedef unsigned char byte, boolean;
typedef unsigned short word;
typedef float real;
typedef struct { real x, y; } real_point2d;
#define TRUE 1
#define FALSE 0
#define NONE -1
#define MAXIMUM_GAMEPADS 4
#define MAXIMUM_NUMBER_OF_LOCAL_PLAYERS 4
#define NUMBEROF(a) (sizeof(a)/sizeof((a)[0]))
#define FLAG(b) (1u<<(b))
#define TEST_FLAG(f,b) (((f)&FLAG(b))!=0)
#define SET_FLAG(f,b,v) ((f)=(v)?((f)|FLAG(b)):((f)&~FLAG(b)))
#define match_assert(file,line,c) assert(c)
#define match_vassert(file,line,c,...) assert(c)
#define csmemcpy memcpy
#define csmemset memset
#define csmemcmp memcmp
#define ustrncmp wcsncmp
enum { _saved_game_file_type_player_profile=0, _saved_game_file_type_game_variant=1,
       _saved_game_file_index_read_only_bit=30, _variant_is_system_default_bit=0, _error_silent=0 };
static void error(int kind,const char *message,...) { (void)kind;(void)message; }
struct game_variant { wchar_t human_readable_game_description[12]; word flags; };
'''
    fixture += enclosing_enum(profile, "MAXIMUM_PLAYER_PROFILE_NAME_LENGTH")
    fixture += enclosing_enum(profile, "_button_preset_standard = 0")
    fixture += enclosing_enum(profile, "_joystick_preset_standard = 0")
    fixture += enclosing_enum(input_header, "FIRST_GAMEPAD_ANALOG_BUTTON")
    fixture += enclosing_enum(abstraction, "_game_control_jump")
    fixture += enclosing_enum(abstraction, "_joystick_controls_default")
    for marker in ("struct player_profile_controller_settings\n", "struct player_profile\n"):
        fixture += block(profile, marker, True)
    for marker in ("struct player_ui_local_player\n", "union player_ui_edit_profile_data\n",
                   "struct player_ui_edit_profile\n", "struct player_ui_globals\n"):
        fixture += block(ui, marker, True)
    fixture += block(preferences, "struct game_input_preferences\n", True)
    fixture += block(abstraction, "struct game_input_state\n", True)
    fixture += block(abstraction, "struct input_abstraction_runtime_globals\n", True)
    fixture += r'''
static struct player_ui_globals player_ui_globals;
static struct input_abstraction_runtime_globals input_abstraction_globals;
static struct player_profile disk_profiles[32];
static int save_count, at_main_menu;
static unsigned int published_look_mask;
static short android_menu_joystick_preset=NONE;
static struct widget_instance {
    short type;
    struct widget_instance *child, *next;
    struct { short selected_index; } data3C;
} root_widget, joystick_item, button_item, joystick_spinner, button_spinner;
struct event_record { short controller_index; };
static int main_menu_is_active(void) { return at_main_menu; }
static int saved_game_file_get_type(long i) { return i==100?1:(i>=0&&i<32?0:NONE); }
static int player_profile_get(long i,struct player_profile *p) { *p=disk_profiles[i];return TRUE; }
static void player_profile_save(long i,struct player_profile *p) { disk_profiles[i]=*p;save_count++; }
static int playlist_profile_get(long i,struct game_variant *p) { (void)i;memset(p,0,sizeof(*p));return TRUE; }
static void playlist_profile_save(long i,struct game_variant *p) { (void)i;(void)p; }
static long playlist_profile_new(short i,const wchar_t *name) { (void)i;(void)name;return NONE; }
static int saved_game_file_get_path_to_enclosing_directory(long i,char *p) { (void)i;(void)p;return FALSE; }
static void saved_game_file_remember_last_used_multiplayer_variant_directory(char *p) { (void)p; }
void host_settings_stick_look_mask(unsigned int mask) { published_look_mask=mask; }
static void clear_profile_edit_data(void);
short player_ui_get_single_player_local_player_controller(short i);
void player_ui_set_active_player_profile(short i,long index,struct player_profile *profile);
#ifdef HALO_ANDROID
short player_ui_android_get_overlay_joystick_preset(void);
#endif
'''
    fixture += block(ui, "short player_ui_get_single_player_local_player_controller(")
    fixture += block(ui, "struct player_profile *player_ui_get_edit_player_profile(")
    optional = "short player_ui_android_get_overlay_joystick_preset("
    if optional in ui:
        fixture += block(ui, optional)
    fixture += "\n#ifdef HALO_ANDROID\n"
    fixture += block(abstraction, "static unsigned int android_stick_look_mask(")
    fixture += block(abstraction, "static void android_publish_stick_look(")
    fixture += "\n#endif\n"
    fixture += block(abstraction, "void input_abstraction_update_local_player_preferences(")
    fixture += block(ui, "static void generate_default_player_profile(\n\tstruct player_profile *profile)\n{")
    fixture += block(ui, "static void reset_local_player_profile(\n\tshort local_player_index)\n{")
    fixture += block(ui, "void player_ui_initialize(")
    fixture += block(ui, "static void set_local_player_controls_from_player_profile(")
    fixture += block(ui, "void player_ui_set_active_player_profile(")
    fixture += block(ui, "static void clear_profile_edit_data(\n\tvoid)\n{")
    fixture += block(ui, "void player_ui_begin_editing_profile(")
    fixture += block(ui, "void player_ui_end_editing_profile(")
    fixture += block(ui, "boolean player_ui_edit_profile_is_dirty(")
    fixture += block(ui, "boolean player_ui_save_profile(")
    fixture += block(widgets, "static boolean player_profile_change_controller_settings(\n\tstruct widget_instance *widget,\n\tstruct event_record *event,\n\tboolean *widget_deleted)\n{")
    fixture += r'''
static void publish(void)
{
#ifdef HALO_ANDROID
    int i;
    for(i=0;i<MAXIMUM_GAMEPADS;i++) android_publish_stick_look((short)i);
#endif
}
static void choose(short preset)
{
    joystick_spinner.data3C.selected_index=preset;
    button_spinner.data3C.selected_index=_button_preset_standard;
    assert(player_profile_change_controller_settings(&root_widget,NULL,NULL));
    publish();
}
static short runtime_preset(int i) { return input_abstraction_globals.player_control_preferences[i].joystick_controls; }
static void expect_mask(unsigned int mask)
{
#ifdef HALO_ANDROID
    if(published_look_mask!=mask)
        fprintf(stderr,"Expected overlay mask %u, got %u (main menu %d, edit profile %ld, saved menu preset %d)\n",
                mask,published_look_mask,at_main_menu,player_ui_globals.edit_profile_index,android_menu_joystick_preset);
    assert(published_look_mask==mask);
#else
    (void)mask;
#endif
}
int main(void)
{
    int i,preset;
    static const unsigned int masks[]={2,1,3,3};
    player_ui_globals.initialized=TRUE;
    player_ui_globals.edit_profile_index=NONE;
    for(i=0;i<4;i++) {
        player_ui_globals.local_players[i].active_profile_index=NONE;
        player_ui_globals.single_player_controller[i]=NONE;
    }
    for(i=0;i<32;i++) disk_profiles[i].controller_settings.look_sensitivity=3;
    root_widget.type=3;root_widget.child=&joystick_item;
    joystick_item.child=&joystick_spinner;joystick_item.next=&button_item;
    button_item.child=&button_spinner;joystick_spinner.type=button_spinner.type=2;
    player_ui_globals.single_player_controller[0]=0;
    player_ui_set_active_player_profile(0,10,&disk_profiles[10]);
    expect_mask(2);

    /* Reproduce the user's route: change the real menu spinner, then open
       the overlay before saving. Gameplay continues to use the active copy. */
    player_ui_begin_editing_profile(10);
    choose(_joystick_preset_south_paw);
    assert(runtime_preset(0)==_joystick_preset_standard);
    expect_mask(1);
    assert(save_count==0&&disk_profiles[10].controller_settings.joystick_preset==0);
    assert(player_ui_save_profile());
    assert(player_ui_globals.edit_profile_index==NONE);
    assert(disk_profiles[10].controller_settings.joystick_preset==1);
    publish();
#ifdef HALO_ANDROID
    assert(runtime_preset(0)==1);
    expect_mask(1);
#else
    assert(runtime_preset(0)==0); /* Keep original non-Android save behavior. */
#endif
    player_ui_set_active_player_profile(0,10,&disk_profiles[10]);

    /* Cancelling restores eligibility without changing disk or gameplay. */
    for(preset=0;preset<4;preset++) {
        int saves=save_count;
        player_ui_begin_editing_profile(10);choose((short)preset);
        expect_mask(masks[preset]);assert(runtime_preset(0)==1);
        player_ui_end_editing_profile();publish();expect_mask(1);
        assert(runtime_preset(0)==1&&save_count==saves);
    }
    /* All four saved layouts notify the mapped primary controller and also
       refresh another local player sharing the edited profile. */
    player_ui_globals.single_player_controller[0]=2;
    player_ui_globals.single_player_controller[1]=3;
    player_ui_set_active_player_profile(0,10,&disk_profiles[10]);
    player_ui_set_active_player_profile(1,10,&disk_profiles[10]);
    player_ui_globals.single_player_controller[2]=1;
    player_ui_set_active_player_profile(2,12,&disk_profiles[12]);
    for(preset=0;preset<4;preset++) {
        player_ui_begin_editing_profile(10);choose((short)preset);expect_mask(masks[preset]);
        assert(player_ui_save_profile());publish();
#ifdef HALO_ANDROID
        assert(runtime_preset(2)==preset&&runtime_preset(3)==preset);
        assert(player_ui_globals.local_players[0].profile.controller_settings.joystick_preset==preset);
        expect_mask(masks[preset]);
#endif
        assert(player_ui_globals.local_players[2].profile.controller_settings.joystick_preset==0);
    }
    /* Editing a different profile in the main menu previews that profile,
       while an unrelated draft during gameplay cannot mask active controls. */
    player_ui_set_active_player_profile(0,12,&disk_profiles[12]);
    at_main_menu=1;player_ui_begin_editing_profile(11);choose(1);expect_mask(1);
    at_main_menu=0;publish();expect_mask(2);
    assert(player_ui_save_profile());publish();expect_mask(2);
    assert(runtime_preset(2)==0&&disk_profiles[11].controller_settings.joystick_preset==1);
    /* A game-variant draft is never interpreted as controller settings. */
    at_main_menu=1;player_ui_begin_editing_profile(100);publish();expect_mask(2);
    player_ui_end_editing_profile();
    /* No active controller mapping yet: the editor still has a meaningful
       layout, and cancelling returns to slot zero's existing preferences. */
    player_ui_globals.single_player_controller[0]=NONE;
    player_ui_set_active_player_profile(0,12,&disk_profiles[12]);
    player_ui_begin_editing_profile(11);choose(1);expect_mask(1);
    player_ui_end_editing_profile();publish();expect_mask(1); /* Original saved layout of profile 11. */
    /* The main-menu editor also saves profiles which have not been activated
       by starting a game. Closing that editor must retain its saved layout. */
    player_ui_begin_editing_profile(11);choose(1);
    assert(player_ui_save_profile());publish();expect_mask(1);
    assert(runtime_preset(0)==0);
    /* Actual startup has no active profile. All saved main-menu choices must
       survive closing the editor while gameplay preferences remain untouched. */
    player_ui_initialize();memset(&input_abstraction_globals,0,sizeof(input_abstraction_globals));
    publish();expect_mask(2);
    for(preset=0;preset<4;preset++) {
        player_ui_begin_editing_profile(13);choose((short)preset);expect_mask(masks[preset]);
        assert(player_ui_globals.local_players[0].active_profile_index==NONE);
        assert(player_ui_save_profile());publish();expect_mask(masks[preset]);
        assert(runtime_preset(0)==0);
    }
    player_ui_begin_editing_profile(13);choose(1);expect_mask(1);
    player_ui_end_editing_profile();publish();
#ifdef HALO_ANDROID
    expect_mask(3); /* Cancel restores profile 13's saved Legacy Southpaw. */
#endif
    player_ui_begin_editing_profile(13);choose(1);assert(player_ui_save_profile());publish();expect_mask(1);
    at_main_menu=0;player_ui_set_active_player_profile(0,13,&disk_profiles[13]);publish();expect_mask(1);
    assert(runtime_preset(0)==1);
    at_main_menu=1;publish();expect_mask(1);
#ifdef HALO_ANDROID
    puts("Android profile controls: inactive main-menu save, real startup, all four layouts, editor cancel, game activation, primary/shared profiles and variants passed.");
#else
    puts("Non-Android profile controls: original save behavior preserved.");
#endif
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="halo-profile-controls-") as directory:
        source = Path(directory) / "profile_controls.c"
        source.write_text(fixture)
        for android in (True, False):
            binary = Path(directory) / ("android" if android else "original")
            command = [os.environ.get("CC", "cc"), "-std=c99", "-idirafter", str(ROOT / "port/linux/include")]
            if android:
                command.append("-DHALO_ANDROID")
            subprocess.run(command + [str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
