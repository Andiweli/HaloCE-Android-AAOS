"""Exercise the real runtime menu builder against a small, asset-free widget graph."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'source/interface/ui_widget.c').read_text()
names = ['ui_widget_event_handler_reference', 'ui_widget_child_reference',
         'ui_widget_definition', 'widget_animation_data', 'widget_instance']
structs = '\n'.join(source[source.index('struct '+name+'\n{'):source.index('\n};', source.index('struct '+name+'\n{'))+3] for name in names)
prelude = r'''
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>
typedef unsigned char byte,boolean;typedef unsigned short word;typedef float real;
typedef struct {short y0,x0,y1,x1;} rectangle2d;
typedef struct {float alpha,red,green,blue;} real_argb_color;
struct tag_reference {long group;char *name;long name_length;long index;};
struct tag_block {long count;void *address;void *definition;};
#define NONE (-1)
#define TRUE 1
#define FALSE 0
#define FLAG(x) (1L<<(x))
#define TEST_FLAG(v,b) ((v)&FLAG(b))
#define TAG_BLOCK_ADDRESS(b) ((b).address)
#define PIN(v,a,b) ((v)<(a)?(a):((v)>(b)?(b):(v)))
#define UI_WIDGET_DEFINITION_TAG 1
#define _ui_widget_type_text_box 1
#define _ui_widget_type_spinner_list 2
#define _ui_widget_type_column_list 3
#define _ui_widget_type_container 0
#define _list_items_generated_from_string_list_tag 1
#define match_assert(f,l,c) assert(c)
#define match_vassert(f,l,c,m) assert(c)
struct event_record;
struct player_profile {wchar_t player_name[32];};
static struct player_profile test_profile={L"Andreas"};
static struct player_profile *player_ui_get_edit_player_profile(void) {return &test_profile;}
#define _widget_dpad_leftright_tabs_thru_list_items_bit 6
#define _widget_dpad_updown_tabs_thru_children_bit 3
#define _widget_pass_unhandled_events_to_children_bit 0
#define _event_handler_open_widget_bit 3
#define _event_handler_run_function_bit 7
#define _event_handler_go_back_to_previous_widget_bit 9
#define _gamepad_analog_button_a 0
#define _widget_event_b_button 1
#define _widget_event_back_button 9
#define _error_silent 0
#define XC_LANGUAGE_GERMAN 2
#define XC_LANGUAGE_FRENCH 3
#define XC_LANGUAGE_SPANISH 4
#define XC_LANGUAGE_ITALIAN 5
#define XC_LANGUAGE_JAPANESE 6
#define _interface_font_system 0
static long tag_loaded(long group,char const *name){return 1;}
static long interface_get_tag_index(int index){return 1;}
static int language;
static int XGetLanguage(void) {return language;}
static void *widget_memory_pool;
static void *pool_new_pointer(void *p,unsigned long n,char const *f,int l) {return calloc(1,n);}
static unsigned long ustrlen(wchar_t const *s) {unsigned long n=0;while(s[n])n++;return n;}
#define csmemcpy memcpy
static int string_has_icons_to_draw(wchar_t *s) {return s[0]==L'%';}
static void error(int level,char const *message,...) {assert(!message);}
'''
harness = r'''
static struct ui_widget_definition fixture[32];
static struct ui_widget_child_reference refs[32][8];
static struct ui_widget_event_handler_reference events[32];
static int levels[3]={10,8,6};
static void *tag_get(int group,long tag) {assert(tag>=0&&tag<32);return &fixture[tag];}
static char const *tag_get_name(long tag) {assert(tag>=0&&tag<32);return tag==16?"ui\\shell\\=accept_new":"fixture";}
#define ui_widget_definition_get(tag) ((struct ui_widget_definition *)tag_get(1,tag))
static wchar_t *unicode_string_list_get_string(long tag,short index) {
    if(tag==2)return L"ADVANCED CONTROLS";
    if(tag==3)return L"%b BACK";
    return L"LOOK SENSITIVITY";
}
int android_ui_profile_handler_kind(short f) {return f;}
int host_audio_level(int c) {return levels[c];}
int host_audio_set_level(int c,int v) {levels[c]=v;return 1;}
static struct widget_instance *widget_instance_get_topmost_parent(struct widget_instance *w) {while(w->parent)w=w->parent;return w;}
static struct widget_instance *ui_widget_load_by_name_or_tag(char const *,long,struct widget_instance *,short,long,long,short);
'''
# The block following these two functions also contains public functions; isolate by braces.
def function_text(name):
    start=source.index('boolean '+name+'('); brace=source.index('{',start); depth=1; end=brace+1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[start:end]
navigation='\n'.join(function_text(n) for n in ['widget_event_function_list_widget_goto_next_item','widget_event_function_list_widget_goto_previous_item'])
start=source.index('static boolean android_ui_label_follows_button(struct widget_instance *widget)');brace=source.index('{',start);depth=1;end=brace+1
while depth:
    if source[end]=='{':depth+=1
    elif source[end]=='}':depth-=1
    end+=1
label_helper=source[start:end]
helpers=r'''
static struct widget_instance *widget_instance_get_nth_child(struct widget_instance *w,long n) {w=w->child;while(w&&n--)w=w->next;return w;}
static void widget_instance_give_focus_by_tag(struct widget_instance *w,long tag,short player) {for(struct widget_instance *c=w->child;c;c=c->next)if(c->definition_tag_index==tag){w->focused_child=c;return;}assert(0);}
static void widget_instance_give_focus_directly(struct widget_instance *w,struct widget_instance *c) {w->focused_child=c;}
'''
body = r'''
static struct widget_instance *ui_widget_load_by_name_or_tag(char const *name,long tag,struct widget_instance *parent,short player,long a,long b,short c) {
    struct widget_instance *w=calloc(1,sizeof(*w)),*last=NULL;
    struct ui_widget_definition *d=ui_widget_definition_get(tag);
    w->visible=TRUE;w->definition_tag_index=tag;w->parent=parent;w->type=d->type;w->local_player_index=player;
    for(int i=0;i<d->child_widgets.count;i++) {
        struct ui_widget_child_reference *ref=(struct ui_widget_child_reference *)d->child_widgets.address+i;
        struct widget_instance *child=ui_widget_load_by_name_or_tag(NULL,ref->widget_tag.index,w,player,0,0,0);
        child->horizontal_offset=ref->horizontal_offset;child->vertical_offset=ref->vertical_offset;
        if(last)last->next=child;else w->child=child;child->previous=last;last=child;
    }
    av_initialize(w);return w;
}
static void child(int parent,int slot,int tag) {
    fixture[parent].child_widgets.address=refs[parent];
    fixture[parent].child_widgets.count=slot+1;refs[parent][slot].widget_tag.index=tag;
}
static void launch(int tag,int target) {
    events[tag].flags=FLAG(_event_handler_open_widget_bit);events[tag].widget_tag.index=target;
    fixture[tag].event_handlers.count=1;fixture[tag].event_handlers.address=&events[tag];
}
static void kind(int tag,int value) {
    events[tag].flags=FLAG(_event_handler_run_function_bit);events[tag].function=value;events[tag].widget_tag.index=NONE;
    fixture[tag].event_handlers.count=1;fixture[tag].event_handlers.address=&events[tag];
}
int main(void) {
    for(int i=0;i<32;i++) {
        fixture[i].bounds.x0=0;fixture[i].bounds.x1=200;
        fixture[i].type=0;fixture[i].text_label_string_list.index=NONE;
        fixture[i].text_font.index=1;fixture[i].bounds.y0=100;fixture[i].bounds.y1=120;
        fixture[i].background_bitmap.index=NONE;fixture[i].extended_description_widget.index=NONE;
    }
    child(0,0,1);fixture[1].type=3;child(1,0,2);child(1,1,3);child(1,2,19);child(0,1,22);
    fixture[19].type=1;fixture[19].bounds.y0=180;fixture[19].bounds.y1=200;
    fixture[22].type=0;fixture[22].background_bitmap.index=1;fixture[22].bounds.y0=170;fixture[22].bounds.y1=172;
    fixture[2].type=fixture[3].type=1;fixture[3].bounds.y0=140;fixture[3].bounds.y1=160;
    launch(2,4);launch(3,17);child(4,0,5);launch(5,6);
    child(6,0,7);child(6,1,15);child(6,2,16);fixture[7].type=3;kind(7,2);
    for(int i=0;i<5;i++){child(7,i,8+i);fixture[8+i].bounds.y0=140+i*40;fixture[8+i].bounds.y1=160+i*40;}
    child(9,0,13);child(9,1,14);fixture[13].type=1;fixture[13].bounds.y0=180;fixture[13].text_label_string_list.index=1;
    fixture[14].type=2;fixture[14].bounds.y0=180;fixture[14].text_label_string_list.index=1;
    child(8,0,23);child(8,1,24);child(10,0,25);child(10,1,26);
    for(int j=23;j<=26;j++) {fixture[j].type=j%2?1:2;fixture[j].bounds.y0=j<25?140:220;fixture[j].text_label_string_list.index=1;}
    for(int j=8;j<=10;j++)fixture[j].background_bitmap.index=42;
    refs[8][1].horizontal_offset=366;refs[9][1].horizontal_offset=373;refs[10][1].horizontal_offset=366;
    refs[8][1].vertical_offset=refs[9][1].vertical_offset=refs[10][1].vertical_offset=1;
    fixture[24].list_header_bounds.x0=120;fixture[24].list_header_bounds.x1=140;
    fixture[24].list_footer_bounds.x0=180;fixture[24].list_footer_bounds.x1=200;
    fixture[14].list_footer_bounds.x0=160;fixture[14].list_footer_bounds.x1=170;
    fixture[15].type=0;fixture[15].bounds.y0=40;fixture[15].bounds.y1=70;fixture[15].background_bitmap.index=2;
    fixture[16].type=1;fixture[16].bounds.y0=400;fixture[16].text_label_string_list.index=3;
    child(17,0,18);kind(18,1);
    struct ui_widget_definition before[32];memcpy(before,fixture,sizeof(before));
    struct widget_instance *root=ui_widget_load_by_name_or_tag(NULL,0,NULL,0,0,0,0);
    struct widget_instance *entry=root->child->child->next->next;
    assert(entry && entry->next && entry->previous->definition_tag_index==3);
    assert(root->child->parameters.list.number_of_items==4);
    root->child->focused_child=root->child->child;
    for(int k=0;k<4;k++){assert(widget_event_function_list_widget_goto_next_item(root->child,NULL,NULL));}
    assert(root->child->focused_child==root->child->child);
    assert(widget_event_function_list_widget_goto_previous_item(root->child,NULL,NULL));
    assert(root->child->focused_child==entry->next);
    av_finish_layout(root,root);assert(root->child->next->vertical_offset==40);
    struct widget_instance description={0},text={0},picture={0};
    description.child=&text;text.type=1;text.next=&picture;picture.type=5;
    root->child->parameters.list.extended_description=&description;
    assert(android_volume_description_index(root->child,3)==2);
    root->child->focused_child=entry;assert(android_volume_description_index(root->child,2)==0);
    wchar_t buffer[512];assert(av_description(&text,buffer,512));
    assert(buffer[0]==L'C');
    {unsigned long len=ustrlen(buffer);assert(buffer[len-1]==L's' && buffer[len-7]==L'A');}
    for(int lang=0;lang<=6;lang++) {
        language=lang;assert(av_description(&text,buffer,512));
        unsigned long len=ustrlen(buffer);assert(len>7 && buffer[len-7]==L'A' && buffer[len-1]==L's');
        wchar_t small[8];assert(av_description(&text,small,8));assert(small[7]==0);
    }
    language=0;
    root->child->focused_child=entry->next;assert(android_volume_description_index(root->child,3)==2);
    assert(!av_description(&text,buffer,512));
    assert(entry->vertical_offset==40);
    assert(memcmp(before,fixture,sizeof(before))==0);
    long screen=av_nodes[av_index(entry->definition_tag_index)].events[0].widget_tag.index;
    struct widget_instance *menu=ui_widget_load_by_name_or_tag(NULL,screen,NULL,0,0,0,0);
    struct widget_instance *row=menu->child->child;
    for(int i=0;i<3;i++) {
        assert(row);assert(ui_widget_definition_get(row->definition_tag_index)->event_handlers.count==1);
        struct widget_instance *spinner=row->child->next;
        assert(av_nodes[av_index(spinner->definition_tag_index)].category==i);
        assert(spinner->horizontal_offset==366 && spinner->vertical_offset==1);
        assert(spinner->parameters.list.number_of_items==11);
        assert(ui_widget_definition_get(spinner->definition_tag_index)->list_header_bounds.x0==120);
        assert(ui_widget_definition_get(spinner->definition_tag_index)->list_footer_bounds.x0==180);
        assert(ui_widget_definition_get(spinner->definition_tag_index)->list_footer_bounds.x1==200);
        assert(ui_widget_definition_get(spinner->definition_tag_index)->bounds.y0==140);
        av_spinner_text(spinner);assert(spinner->parameters.list.item_text[0]);
        assert(av_adjust(spinner,-1));assert(levels[i]==(i==0?9:i==1?7:5));
        levels[i]=0;av_adjust(spinner,-1);assert(levels[i]==10);
        av_adjust(spinner,1);assert(levels[i]==0);
        for(int n=0;n<11;n++)av_adjust(spinner,1);assert(levels[i]==0);
        assert(ui_widget_definition_get(row->definition_tag_index)->background_bitmap.index==42);
        row=row->next;
    }
    assert(!row);
    assert(av_nodes[av_index(screen)].events[0].flags==FLAG(_event_handler_go_back_to_previous_widget_bit));
    assert(av_nodes[av_index(menu->child->next->definition_tag_index)].label==1);
    assert(ui_widget_definition_get(menu->child->next->definition_tag_index)->background_bitmap.index==NONE);
    assert(menu->child->next->type==1);
    assert(android_ui_label_follows_button(menu->child->next->next));
    assert(strstr(av_tag_name(menu->child->next->next->definition_tag_index),"=accept_new"));
    assert(av_label(2)[0]==L'V');language=XC_LANGUAGE_GERMAN;assert(av_label(2)[0]==L'L');
    puts("Native volume menu: real next/previous navigation, wraparound, separator, original description indices, six languages/profile text, bounds and volume controls passed.");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='halo-volume-menu-') as tmp:
    test = Path(tmp) / 'test.c'
    test.write_text(prelude + structs + harness + '\n#include "' + str(root / 'source/interface/android_volume_menu.inc') + '"\n' + helpers + '\nstatic short ui_mouse_key_button(struct widget_instance *w){return NONE;}\n' + label_helper + navigation + body)
    binary = Path(tmp) / 'test'
    subprocess.run(['cc', '-DHALO_ANDROID', '-std=gnu11', '-fshort-wchar', '-Werror=implicit-function-declaration', str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
