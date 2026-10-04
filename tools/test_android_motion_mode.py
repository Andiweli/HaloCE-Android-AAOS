"""Run the production game-thread gyro eligibility block, without weapon zoom."""
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
source=(root/'source/interface/ui_widget.c').read_text()
start=source.index('        int input_mode =',source.index('void process_ui_widgets('))
end=source.index('        host_touch_mode(input_mode);',start)+len('        host_touch_mode(input_mode);')
block=source[start:end]
fixture=r'''
#include <assert.h>
#include <stdio.h>
#include "halo_android_controls.h"
#define NONE -1
static int menu,widgets,active=1,paused,cinematic,player=0,unit=123;
static int published;
int ui_widgets_active(void){return widgets;}
#define we_are_at_the_main_menu menu
int game_in_progress(void){return active;}
int game_time_get_paused(void){return paused;}
int cinematic_in_progress(void){return cinematic;}
int local_player_get_player_index(int index){assert(index==0);return player;}
int player_control_get_unit_index(int index){assert(index==0);return unit;}
void host_touch_mode(int mode){published=mode;}
static void publish(void){
'''
checks=r'''
}
int main(void){
    publish();assert(published==(2|HALO_ANDROID_TOUCH_AIMING)); /* No zoom function or weapon required. */
    menu=1;publish();assert(published==1);menu=0;
    widgets=1;publish();assert(published==1);widgets=0;
    active=0;publish();assert(published==2);active=1;
    paused=1;publish();assert(published==2);paused=0;
    cinematic=1;publish();assert(published==2);cinematic=0;
    player=NONE;publish();assert(published==2);player=0;
    unit=NONE;publish();assert(published==2);unit=123;
    publish();assert(published==(2|HALO_ANDROID_TOUCH_AIMING));
    puts("Production gyro eligibility: gameplay without zoom, menus, pause, cinematics and absent player/unit passed.");
}
'''
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp);(path/'test.c').write_text(fixture+block+checks)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-I'+str(root/'port/linux/include'),str(path/'test.c'),'-o',str(path/'test')],check=True)
    subprocess.run([str(path/'test')],check=True)
