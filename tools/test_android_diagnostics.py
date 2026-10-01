"""Exercise the real native diagnostic writer/fatal formatter on the host."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'port/android/host/host_main.c').read_text()
code=s[s.index('static void diagnostic_write('):s.index('\nvoid host_abort(')]
pre=r'''
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#include <assert.h>
#include <setjmp.h>
#define ANDROID_LOG_ERROR 6
#define ANDROID_LOG_FATAL 7
#define SDL_MESSAGEBOX_ERROR 1
static FILE *diagnostic_file;
static char diagnostic_path[1024]="/Android/media/com.halo.decomp/halo-diagnostic.txt",diagnostic_error[1024];
static pthread_mutex_t diagnostic_mutex=PTHREAD_MUTEX_INITIALIZER;
static char dialog[3200];static jmp_buf fatal;
static void __android_log_write(int p,const char *tag,const char *text){(void)p;(void)tag;(void)text;}
static void SDL_ShowSimpleMessageBox(int flags,const char *title,const char *message,void *window){(void)flags;(void)title;(void)window;snprintf(dialog,sizeof(dialog),"%s",message);}
#define _exit(code) longjmp(fatal,code)
'''
post=r'''
int main(void){
 diagnostic_file=tmpfile();assert(diagnostic_file);
 errno=EEXIST;diagnostic_write(6,"cannot reserve: File exists");assert(errno==EEXIST);
 host_logf(4,"informational %d",42);
 if(!setjmp(fatal))host_fatal("cannot load the game image");
 assert(strstr(dialog,"cannot reserve: File exists"));
 assert(strstr(dialog,"/Android/media/com.halo.decomp/halo-diagnostic.txt"));
 rewind(diagnostic_file);char data[8192];size_t n=fread(data,1,sizeof(data)-1,diagnostic_file);data[n]=0;
 assert(strstr(data,"informational 42"));assert(strstr(data,"cannot load the game image"));
 fclose(diagnostic_file);return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'test.c').write_text(pre+code+post)
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-pthread',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('Native diagnostic: file output, errno preservation, last error and fatal dialog passed')
