"""Compile the actual root BACK handler and verify that submenus never exit."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'source/interface/ui_widget.c').read_text()
a=s.index('    /* Only the active main-menu root may exit.')
block=s[a:s.index('#endif',a)]
assert 'av_install_exit' not in s
h='''#include <assert.h>
#define FALSE 0
#define _event_type_button 1
#define _widget_event_b_button 2
#define _widget_event_back_button 3
struct widget {void *parent;};
struct definition {int kind;};
struct event {int type;struct {struct {int value,index;} button;} data;};
int calls;
int av_kind(struct definition *d,int kind){return d->kind==kind;}
void main_android_request_exit(void){calls++;}
void dispatch(struct widget *widget,struct definition *definition,struct event *event,int event_for_this_widget,int *return_widget_deleted){
'''+block+'''}
int main(void){
 struct widget w={0};struct definition d={3};struct event e={1,{{1,2}}};int deleted=9;
 dispatch(&w,&d,&e,1,&deleted);assert(calls==1 && deleted==0);
 e.data.button.index=3;dispatch(&w,&d,&e,1,&deleted);assert(calls==2);
 for(int kind=0;kind<3;kind++){d.kind=kind;dispatch(&w,&d,&e,1,&deleted);}assert(calls==2);
 d.kind=3;w.parent=&w;dispatch(&w,&d,&e,1,&deleted);assert(calls==2);w.parent=0;
 for(int value=0;value<4;value++){if(value==1)continue;e.data.button.value=value;dispatch(&w,&d,&e,1,&deleted);}assert(calls==2);
 e.data.button.value=1;dispatch(&w,&d,&e,0,&deleted);assert(calls==2);
 e.type=0;dispatch(&w,&d,&e,1,&deleted);assert(calls==2);
 e.type=1;e.data.button.index=0;dispatch(&w,&d,&e,1,&deleted);assert(calls==2);
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'test.c').write_text(h)
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('Main-menu B/BACK exits; submenus, child widgets, other buttons, held/released buttons and unrelated events do not.')
