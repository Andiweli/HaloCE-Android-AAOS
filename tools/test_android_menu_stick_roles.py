#!/usr/bin/env python3
"""Exercise real next/previous spinner events before Halo's exit/save callback.

Menu identity uses the real callback classifier, independent of map language.
Run from the project root: python3 tools/test_android_menu_stick_roles.py
"""
from pathlib import Path
import os
import subprocess
import tempfile

from test_android_gamepad_integration import block, enclosing_enum

ROOT = Path(__file__).resolve().parents[1]


def main():
    widgets = (ROOT / "source/interface/ui_widget.c").read_text()
    callbacks = (ROOT / "source/interface/ui_widget_event_handler_functions.c").read_text()
    profile = (ROOT / "source/saved games/player_profile.h").read_text()
    fixture = r'''
#include <assert.h>
#include <stdio.h>
#include <stddef.h>
typedef unsigned char byte,boolean;
typedef unsigned short word;
#define TRUE 1
#define FALSE 0
#define NONE -1
#define FLAG(b) (1u<<(b))
#define TEST_FLAG(f,b) (((f)&FLAG(b))!=0)
#define TAG_BLOCK_ADDRESS(b) ((b).address)
#define match_assert(file,line,c) assert(c)
#define match_vassert(file,line,c,...) assert(c)
#define _error_silent 0
static void error(int kind,const char *message,...) { (void)kind;(void)message;assert(0); }
'''
    for name in ("_ui_widget_type_spinner_list", "_event_handler_run_function_bit",
                 "_list_items_generated_from_string_list_tag"):
        fixture += enclosing_enum(widgets, name)
    for name in ("MAXIMUM_PLAYER_PROFILE_NAME_LENGTH", "_joystick_preset_standard = 0"):
        fixture += enclosing_enum(profile, name)
    for name in ("struct player_profile_controller_settings\n", "struct player_profile\n"):
        fixture += block(profile, name, True)
    fixture += r'''
struct event_record { short controller_index; };
struct widget_instance {
    short type,local_player_index;
    long definition_tag_index;
    struct widget_instance *parent,*child,*next,*previous,*focused_child;
    struct { struct { short selected_index,last_list_tab_direction;void *list_items;word number_of_items; } list; } parameters;
};
struct ui_widget_event_handler_reference { unsigned int flags;short function; };
struct test_block { long count;void *address; };
struct ui_widget_definition { struct test_block event_handlers,child_widgets;unsigned int list_flags; };
static struct ui_widget_definition definitions[8];
static struct player_profile edited;
static int editing=1,callback_invocations;
static struct player_profile *player_ui_get_edit_player_profile(void) { return editing?&edited:NULL; }
static struct ui_widget_definition *ui_widget_definition_get(long i) { assert(i>=0&&i<8);return &definitions[i]; }
static struct widget_instance *widget_instance_get_nth_child(struct widget_instance *w,long i)
{ struct widget_instance *child=w->child;while(child&&i--)child=child->next;return child; }
static void widget_instance_give_focus_by_tag(struct widget_instance *w,long tag,short local)
{ (void)w;(void)tag;(void)local; }
static void widget_instance_give_focus_directly(struct widget_instance *w,struct widget_instance *child)
{ w->focused_child=child; }
typedef boolean (*handler)(struct widget_instance *,struct event_record *,boolean *);
static struct { handler functions[102]; } event_handler_function_list;
#define STUB_HANDLER(name) static boolean name(struct widget_instance *w,struct event_record *e,boolean *d) { (void)w;(void)e;(void)d;callback_invocations++;return TRUE; }
STUB_HANDLER(main_menu_initialize)
STUB_HANDLER(player_profile_color_picker_menu_initialize)
STUB_HANDLER(player_profile_initialize_advanced_controller_settings)
STUB_HANDLER(player_profile_initialize_controller_settings)
STUB_HANDLER(player_profile_change_controller_settings)
'''
    fixture += "\n#ifdef HALO_ANDROID\n"
    fixture += block(callbacks, "int android_ui_profile_handler_kind(")
    fixture += block(widgets, "static void android_update_joystick_spinner(")
    fixture += "\n#endif\n"
    for name in ("boolean widget_event_function_list_widget_goto_next_item(",
                 "boolean widget_event_function_list_widget_goto_previous_item("):
        fixture += block(widgets, name)
    fixture += r'''
static void expect_profile(short preset)
{
#ifdef HALO_ANDROID
    assert(edited.controller_settings.joystick_preset==preset);
#else
    (void)preset;assert(edited.controller_settings.joystick_preset==0);
#endif
    assert(callback_invocations==0); /* No screen-exit/save callback has run. */
}
int main(void)
{
    struct widget_instance list={0},item={0},label={0},stick={0},button_item={0},button={0};
    struct ui_widget_event_handler_reference event={FLAG(_event_handler_run_function_bit),10};
    short old;
    int kind;
    event_handler_function_list.functions[10]=player_profile_initialize_controller_settings;
    event_handler_function_list.functions[11]=player_profile_change_controller_settings;
    event_handler_function_list.functions[12]=player_profile_initialize_advanced_controller_settings;
    event_handler_function_list.functions[13]=main_menu_initialize;
    event_handler_function_list.functions[14]=player_profile_color_picker_menu_initialize;
#ifdef HALO_ANDROID
    assert(android_ui_profile_handler_kind(-1)==0&&android_ui_profile_handler_kind(102)==0);
    assert(android_ui_profile_handler_kind(10)==4&&android_ui_profile_handler_kind(11)==4);
    assert(android_ui_profile_handler_kind(12)==2&&android_ui_profile_handler_kind(13)==3&&android_ui_profile_handler_kind(14)==1);
#endif
    definitions[0].event_handlers.count=1;definitions[0].event_handlers.address=&event;
    list.type=_ui_widget_type_column_list;list.child=&item;
    item.parent=&list;item.child=&label;item.next=&button_item;
    label.type=_ui_widget_type_text_box;label.next=&stick;
    stick.type=_ui_widget_type_spinner_list;stick.parent=&item;stick.definition_tag_index=1;
    stick.parameters.list.list_items=&stick;stick.parameters.list.number_of_items=4;
    button_item.parent=&list;button_item.child=&button;
    button.type=_ui_widget_type_spinner_list;button.parent=&button_item;button.definition_tag_index=2;
    button.parameters.list.list_items=&button;button.parameters.list.number_of_items=5;
    edited.controller_settings.button_preset=2;edited.controller_settings.look_sensitivity=5;
    /* Both callback identities recognize the same localized controls menu. */
    for(kind=10;kind<=11;kind++) {
        event.function=kind;
        stick.parameters.list.selected_index=0;edited.controller_settings.joystick_preset=0;
        assert(widget_event_function_list_widget_goto_next_item(&stick,NULL,NULL));
        assert(stick.parameters.list.selected_index==1);expect_profile(1);
        assert(widget_event_function_list_widget_goto_next_item(&stick,NULL,NULL));expect_profile(2);
        assert(widget_event_function_list_widget_goto_next_item(&stick,NULL,NULL));expect_profile(3);
        assert(widget_event_function_list_widget_goto_next_item(&stick,NULL,NULL));expect_profile(0);
        assert(widget_event_function_list_widget_goto_previous_item(&stick,NULL,NULL));expect_profile(3);
        assert(widget_event_function_list_widget_goto_previous_item(&stick,NULL,NULL));expect_profile(2);
        assert(widget_event_function_list_widget_goto_previous_item(&stick,NULL,NULL));expect_profile(1);
        old=edited.controller_settings.joystick_preset;
        assert(widget_event_function_list_widget_goto_next_item(&button,NULL,NULL));
        assert(edited.controller_settings.joystick_preset==old);
    }
    /* String-list spinners use a different branch from generated list items. */
    definitions[1].list_flags=FLAG(_list_items_generated_from_string_list_tag);
    stick.parameters.list.list_items=NULL;stick.parameters.list.selected_index=0;
    edited.controller_settings.joystick_preset=0;
    assert(widget_event_function_list_widget_goto_next_item(&stick,NULL,NULL));expect_profile(1);
    assert(widget_event_function_list_widget_goto_previous_item(&stick,NULL,NULL));expect_profile(0);
    assert(widget_event_function_list_widget_goto_previous_item(&stick,NULL,NULL));expect_profile(3);
    assert(widget_event_function_list_widget_goto_next_item(&stick,NULL,NULL));expect_profile(0);
    /* Advanced settings, non-function handlers and missing edit data must not
       turn arbitrary numeric spinners into the joystick preset. */
    event.function=12;
    assert(widget_event_function_list_widget_goto_next_item(&stick,NULL,NULL));expect_profile(0);
    event.function=10;event.flags=0;
    assert(widget_event_function_list_widget_goto_next_item(&stick,NULL,NULL));expect_profile(0);
    event.flags=FLAG(_event_handler_run_function_bit);editing=0;
    assert(widget_event_function_list_widget_goto_next_item(&stick,NULL,NULL));expect_profile(0);
    editing=1;stick.parent=NULL;
    assert(widget_event_function_list_widget_goto_previous_item(&stick,NULL,NULL));expect_profile(0);
    assert(edited.controller_settings.button_preset==2&&edited.controller_settings.look_sensitivity==5);
#ifdef HALO_ANDROID
    puts("Live Halo menu: real next/previous events update all four layouts before exit/save, both spinner branches, callback-based identity and unrelated controls passed.");
#else
    puts("Non-Android menu: original spinner/profile behavior preserved.");
#endif
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="halo-menu-sticks-") as directory:
        source = Path(directory) / "menu_sticks.c"
        source.write_text(fixture)
        for android in (True, False):
            binary = Path(directory) / ("android" if android else "original")
            command = [os.environ.get("CC", "cc"), "-std=c99"]
            if android:
                command.append("-DHALO_ANDROID")
            subprocess.run(command + [str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
