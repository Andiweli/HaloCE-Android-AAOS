/* Android UI thread <-> guest engine. Never call guest code through JNI. */
#include <jni.h>
#include <pthread.h>
#include <math.h>
#include <SDL3/SDL.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <sys/stat.h>
#include <unistd.h>
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static unsigned int held;
static unsigned long long until[20];
static float move_x, move_y, look_x, look_y;
static int mode;
extern int host_bink_active(void);
static float volumes[3] = {1, 1, 1};
static float default_volumes[3] = {1, 1, 1};
static char audio_profile[512], audio_file[1024];
extern void host_android_path(int which, char *buffer, unsigned int size);
static void reset(void) {
    held = 0; move_x = move_y = look_x = look_y = 0;
    for (int i=0;i<20;i++) until[i]=0;
}
JNIEXPORT void JNICALL Java_com_halo_decomp_HaloPort_nativeReset(JNIEnv *e,jclass c) {
    pthread_mutex_lock(&lock); reset(); pthread_mutex_unlock(&lock);
}
JNIEXPORT void JNICALL Java_com_halo_decomp_HaloPort_nativeAction(JNIEnv *e,jclass c,jint action,jboolean down) {
    if(action<0 || action>=20) return;
    pthread_mutex_lock(&lock);
    if(down) { held |= 1u<<action; until[action]=SDL_GetTicks()+80; }
    else held &= ~(1u<<action);
    pthread_mutex_unlock(&lock);
}
JNIEXPORT void JNICALL Java_com_halo_decomp_HaloPort_nativeMove(JNIEnv *e,jclass c,jfloat x,jfloat y) {
    pthread_mutex_lock(&lock);
    move_x=isfinite(x)?fmaxf(-1,fminf(1,x)):0;
    move_y=isfinite(y)?fmaxf(-1,fminf(1,y)):0;
    pthread_mutex_unlock(&lock);
}
JNIEXPORT void JNICALL Java_com_halo_decomp_HaloPort_nativeLook(JNIEnv *e,jclass c,jfloat x,jfloat y) {
    pthread_mutex_lock(&lock);
    if(mode==2 && isfinite(x) && isfinite(y)) { look_x+=x;look_y+=y; }
    pthread_mutex_unlock(&lock);
}
JNIEXPORT jint JNICALL Java_com_halo_decomp_HaloPort_nativeMode(JNIEnv *e,jclass c) {
    pthread_mutex_lock(&lock); int result=host_bink_active()?0:mode; pthread_mutex_unlock(&lock);return result;
}
JNIEXPORT void JNICALL Java_com_halo_decomp_HaloPort_nativeVolumes(JNIEnv *e,jclass c,jint master,jint effects,jint music) {
    int v[3]={master,effects,music};pthread_mutex_lock(&lock);
    audio_profile[0]=audio_file[0]=0;
    for(int i=0;i<3;i++) default_volumes[i]=volumes[i]=fmaxf(0,fminf(100,v[i]))/100.f;
    pthread_mutex_unlock(&lock);
}
void host_touch_mode(int value) {
    pthread_mutex_lock(&lock); if(mode!=value) {reset();mode=value;} pthread_mutex_unlock(&lock);
}
void host_touch_read(unsigned int *buttons,float *x,float *y) {
    pthread_mutex_lock(&lock);unsigned int bits=held;
    unsigned long long now=SDL_GetTicks();
    for(int i=0;i<20;i++) if(now<until[i]) bits|=1u<<i;
    *buttons=bits;*x=move_x;*y=move_y;pthread_mutex_unlock(&lock);
}
void host_touch_look(float *x,float *y) {
    pthread_mutex_lock(&lock);*x=look_x;*y=look_y;look_x=look_y=0;pthread_mutex_unlock(&lock);
}
float host_audio_gain(int category) {
    pthread_mutex_lock(&lock);float value=volumes[0];
    if(category==1 || category==2) value*=volumes[category];
    pthread_mutex_unlock(&lock);return value;
}

/* Profile directory is stable across display-name changes. Store the full key
   as well as the filename hash, so a collision cannot load another profile. */
void host_audio_profile(const char *key) {
    char root[768], saved_key[512]; int a,b,c; uint64_t hash=UINT64_C(14695981039346656037);
    if(!key || !*key || strlen(key)>=sizeof(audio_profile)) return;
    pthread_mutex_lock(&lock);
    if(!strcmp(audio_profile,key)) {pthread_mutex_unlock(&lock);return;}
    snprintf(audio_profile,sizeof(audio_profile),"%s",key);
    for(const unsigned char *p=(const unsigned char *)key;*p;p++) {hash^=*p;hash*=UINT64_C(1099511628211);}
    host_android_path(1,root,sizeof(root));
    size_t len=strlen(root);snprintf(root+len,sizeof(root)-len,"/android-volumes");
    mkdir(root,0770);
    snprintf(audio_file,sizeof(audio_file),"%s/%016llx.cfg",root,(unsigned long long)hash);
    for(int i=0;i<3;i++) volumes[i]=roundf(default_volumes[i]*10.f)/10.f;
    FILE *f=fopen(audio_file,"r");
    if(f) {
        if(fgets(saved_key,sizeof(saved_key),f)) {
            saved_key[strcspn(saved_key,"\r\n")]=0;
            if(!strcmp(saved_key,key) && fscanf(f,"%d %d %d",&a,&b,&c)==3 &&
                a>=0&&a<=10&&b>=0&&b<=10&&c>=0&&c<=10) {
                volumes[0]=a/10.f;volumes[1]=b/10.f;volumes[2]=c/10.f;
            }
        }
        fclose(f);
    }
    pthread_mutex_unlock(&lock);
}
int host_audio_level(int category) {
    if(category<0||category>2)return 10;
    pthread_mutex_lock(&lock);int v=(int)lroundf(volumes[category]*10.f);pthread_mutex_unlock(&lock);return v;
}
int host_audio_set_level(int category,int value) {
    char temporary[1060];int ok=0;
    if(category<0||category>2||value<0||value>10)return 0;
    pthread_mutex_lock(&lock);
    if(!audio_file[0]) {pthread_mutex_unlock(&lock);return 0;}
    float previous=volumes[category];volumes[category]=value/10.f;
    snprintf(temporary,sizeof(temporary),"%s.tmp",audio_file);
    FILE *f=fopen(temporary,"w");
    if(f) {
        ok=fprintf(f,"%s\n%d %d %d\n",audio_profile,(int)lroundf(volumes[0]*10),
            (int)lroundf(volumes[1]*10),(int)lroundf(volumes[2]*10))>0;
        if(fflush(f)!=0)ok=0;
        if(fsync(fileno(f))!=0)ok=0;
        if(fclose(f)!=0)ok=0;
        if(ok)ok=rename(temporary,audio_file)==0;
        if(!ok)unlink(temporary);
    }
    if(!ok)volumes[category]=previous;
    pthread_mutex_unlock(&lock);return ok;
}

/* UI thread writes, render/input threads read; never enter guest code from JNI. */
static int settings_open;
static float settings_brightness=0.0f, settings_gamma=1.0f;
JNIEXPORT void JNICALL Java_com_halo_decomp_SettingsOverlay_nativeOpen(JNIEnv *e,jclass c,jboolean open) {
    pthread_mutex_lock(&lock); settings_open=open; reset(); pthread_mutex_unlock(&lock);
}
JNIEXPORT void JNICALL Java_com_halo_decomp_SettingsOverlay_nativeDisplay(JNIEnv *e,jclass c,jint brightness,jint gamma) {
    pthread_mutex_lock(&lock);
    settings_brightness=(fmaxf(50,fminf(150,brightness))-100.f)/100.f;
    settings_gamma=fmaxf(50,fminf(200,gamma))/100.f;
    pthread_mutex_unlock(&lock);
}
int host_settings_active(void) {
    pthread_mutex_lock(&lock); int open=settings_open; pthread_mutex_unlock(&lock); return open;
}
void host_settings_display(float *brightness,float *gamma) {
    pthread_mutex_lock(&lock); *brightness=settings_brightness; *gamma=settings_gamma; pthread_mutex_unlock(&lock);
}
