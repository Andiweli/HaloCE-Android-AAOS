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
#include "../../linux/include/halo_android_controls.h"
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static unsigned int held;
static unsigned long long until[20];
static float move_x, move_y, look_x, look_y;
static int mode;
static int aiming, motion_enabled, settings_open;
static float motion_yaw, motion_pitch;
static Uint64 mode_updated, motion_updated;
static uint32_t motion_consumed;
extern int host_bink_active(void);
static float volumes[3] = {1, 1, 1};
static float default_volumes[3] = {1, 1, 1};
static char audio_profile[512], audio_file[1024];
extern void host_android_path(int which, char *buffer, unsigned int size);
static void reset(void) {
    held = 0; move_x = move_y = look_x = look_y = 0;
    motion_yaw = motion_pitch = 0;
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
    int next_mode = value & HALO_ANDROID_TOUCH_MODE_MASK;
    int next_aiming = next_mode == 2 && (value & HALO_ANDROID_TOUCH_AIMING);
    pthread_mutex_lock(&lock);
    if(mode!=next_mode) {reset();mode=next_mode;}
    if(aiming!=next_aiming) motion_yaw=motion_pitch=0;
    aiming=next_aiming; mode_updated=SDL_GetTicks();
    pthread_mutex_unlock(&lock);
}
/* Called with lock held. A loading/pause stall must never retain an old
   gameplay status or sensor delta that would jump the view on the next frame. */
static int motion_allowed(void) {
    return motion_enabled && mode==2 && aiming && !settings_open &&
        !host_bink_active() && SDL_GetTicks()-mode_updated<=200;
}
JNIEXPORT void JNICALL Java_com_halo_decomp_MotionAim_nativeEnabled(JNIEnv *e,jclass c,jboolean enabled) {
    pthread_mutex_lock(&lock);motion_enabled=enabled;motion_yaw=motion_pitch=0;pthread_mutex_unlock(&lock);
}
JNIEXPORT jboolean JNICALL Java_com_halo_decomp_MotionAim_nativeAiming(JNIEnv *e,jclass c) {
    pthread_mutex_lock(&lock);int allowed=motion_allowed();pthread_mutex_unlock(&lock);
    return allowed ? JNI_TRUE : JNI_FALSE;
}
/* Small Logcat status snapshot: UI can verify registration -> accepted
   input -> game consumption without opening the file/GFX diagnostics. */
JNIEXPORT jlong JNICALL Java_com_halo_decomp_MotionAim_nativeState(JNIEnv *e,jclass c) {
    pthread_mutex_lock(&lock);
    uint32_t state=(motion_enabled?1u:0u)|(mode==2?2u:0u)|(aiming?4u:0u)|
        (settings_open?8u:0u)|(host_bink_active()?16u:0u)|
        (SDL_GetTicks()-mode_updated<=200?32u:0u);
    uint64_t result=((uint64_t)motion_consumed<<32)|state;
    pthread_mutex_unlock(&lock);return (jlong)result;
}
JNIEXPORT void JNICALL Java_com_halo_decomp_MotionAim_nativeDelta(JNIEnv *e,jclass c,jfloat yaw,jfloat pitch) {
    if(!isfinite(yaw)||!isfinite(pitch)||fabsf(yaw)>.15f||fabsf(pitch)>.15f)return;
    pthread_mutex_lock(&lock);
    if(motion_allowed()) {
        motion_yaw=fmaxf(-.2f,fminf(.2f,motion_yaw+yaw));
        motion_pitch=fmaxf(-.2f,fminf(.2f,motion_pitch+pitch));
        motion_updated=SDL_GetTicks();
    }
    pthread_mutex_unlock(&lock);
}
void host_motion_look(float *yaw,float *pitch) {
    pthread_mutex_lock(&lock);
    int fresh=motion_allowed() && SDL_GetTicks()-motion_updated<=100;
    *yaw=fresh?motion_yaw:0;*pitch=fresh?motion_pitch:0;
    if(*yaw!=0 || *pitch!=0)motion_consumed++;
    motion_yaw=motion_pitch=0;
    pthread_mutex_unlock(&lock);
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
static float settings_brightness=0.0f, settings_gamma=1.0f;
static float settings_left_stick=1.0f, settings_right_stick=1.0f;
static unsigned int settings_stick_look_mask=HALO_ANDROID_RIGHT_STICK_LOOK;
JNIEXPORT void JNICALL Java_com_halo_decomp_SettingsOverlay_nativeOpen(JNIEnv *e,jclass c,jboolean open) {
    pthread_mutex_lock(&lock); settings_open=open; reset(); pthread_mutex_unlock(&lock);
}
JNIEXPORT void JNICALL Java_com_halo_decomp_SettingsOverlay_nativeDisplay(JNIEnv *e,jclass c,jint brightness,jint gamma) {
    pthread_mutex_lock(&lock);
    settings_brightness=(fmaxf(50,fminf(150,brightness))-100.f)/100.f;
    settings_gamma=fmaxf(50,fminf(200,gamma))/100.f;
    pthread_mutex_unlock(&lock);
}
JNIEXPORT void JNICALL Java_com_halo_decomp_SettingsOverlay_nativeSticks(JNIEnv *e,jclass c,jint left,jint right) {
    pthread_mutex_lock(&lock);
    settings_left_stick=fmaxf(50,fminf(150,left))/100.f;
    settings_right_stick=fmaxf(50,fminf(150,right))/100.f;
    pthread_mutex_unlock(&lock);
}
void host_settings_sticks(float *left,float *right) {
    pthread_mutex_lock(&lock);*left=settings_left_stick;*right=settings_right_stick;pthread_mutex_unlock(&lock);
}
/* Publish the applied Halo profile, even in menus/overlays where axes are blocked. */
void host_settings_stick_look_mask(unsigned int mask) {
    pthread_mutex_lock(&lock);
    settings_stick_look_mask=mask&(HALO_ANDROID_LEFT_STICK_LOOK|HALO_ANDROID_RIGHT_STICK_LOOK);
    pthread_mutex_unlock(&lock);
}
JNIEXPORT jint JNICALL Java_com_halo_decomp_SettingsOverlay_nativeLookSticks(JNIEnv *e,jclass c) {
    pthread_mutex_lock(&lock);unsigned int mask=settings_stick_look_mask;pthread_mutex_unlock(&lock);return (jint)mask;
}
int host_settings_active(void) {
    pthread_mutex_lock(&lock); int open=settings_open; pthread_mutex_unlock(&lock); return open;
}
void host_settings_display(float *brightness,float *gamma) {
    pthread_mutex_lock(&lock); *brightness=settings_brightness; *gamma=settings_gamma; pthread_mutex_unlock(&lock);
}
