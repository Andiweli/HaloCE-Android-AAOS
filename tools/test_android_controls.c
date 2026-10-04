/* Host-side input/audio bridge tests with a deterministic clock. */
#include <assert.h>
#include <stdio.h>
#include <math.h>
#include "../port/android/host/host_touch.c"
static char test_root[256];
void host_android_path(int which,char *buffer,unsigned int size) { (void)which;snprintf(buffer,size,"%s",test_root); }
static Uint64 clock_ms = 1000;
Uint64 SDL_GetTicks(void) { return clock_ms; }
static int movie_active;
int host_bink_active(void) { return movie_active; }
#define ACTION(a,d) Java_com_halo_decomp_HaloPort_nativeAction(NULL,NULL,a,d)
#define RESET() Java_com_halo_decomp_HaloPort_nativeReset(NULL,NULL)
int main(void) {
    unsigned int b; float x,y;
    snprintf(test_root,sizeof(test_root),"/tmp/halo-audio-test-%ld",(long)getpid());
    assert(mkdir(test_root,0700)==0);
    host_touch_mode(2);
    ACTION(7,1); ACTION(7,0); host_touch_read(&b,&x,&y);assert(b==(1u<<7));
    clock_ms+=81;host_touch_read(&b,&x,&y);assert(!b);
    ACTION(2,1);clock_ms+=100;host_touch_read(&b,&x,&y);assert(b==(1u<<2));
    ACTION(2,0);host_touch_read(&b,&x,&y);assert(!b);
    ACTION(-1,1);ACTION(40,1);host_touch_read(&b,&x,&y);assert(!b);
    Java_com_halo_decomp_HaloPort_nativeMove(NULL,NULL,2,-2);
    host_touch_read(&b,&x,&y);assert(x==1 && y==-1);
    Java_com_halo_decomp_HaloPort_nativeLook(NULL,NULL,.2f,-.1f);
    host_touch_look(&x,&y);assert(x==.2f && y==-.1f);
    host_touch_look(&x,&y);assert(x==0 && y==0);
    ACTION(7,1);host_touch_mode(1);host_touch_read(&b,&x,&y);assert(!b && !x && !y);
    Java_com_halo_decomp_HaloPort_nativeLook(NULL,NULL,1,1);host_touch_look(&x,&y);assert(!x&&!y);
    Java_com_halo_decomp_HaloPort_nativeVolumes(NULL,NULL,50,20,80);
    assert(fabsf(host_audio_gain(0)-.5f)<.0001f);
    assert(fabsf(host_audio_gain(1)-.1f)<.0001f);
    assert(fabsf(host_audio_gain(2)-.4f)<.0001f);
    Java_com_halo_decomp_HaloPort_nativeVolumes(NULL,NULL,0,100,100);
    assert(host_audio_gain(0)==0 && host_audio_gain(1)==0 && host_audio_gain(2)==0);
    host_touch_mode(2);ACTION(7,1);RESET();host_touch_read(&b,&x,&y);assert(!b&&!x&&!y);
    Java_com_halo_decomp_HaloPort_nativeVolumes(NULL,NULL,100,100,100);
    host_audio_profile("profile-a");assert(host_audio_level(0)==10);
    assert(host_audio_set_level(0,0));assert(host_audio_gain(0)==0 && host_audio_gain(2)==0);
    assert(!host_audio_set_level(0,11));assert(!host_audio_set_level(-1,5));
    host_audio_profile("profile-b");assert(host_audio_level(0)==10);
    assert(host_audio_set_level(1,4));assert(fabsf(host_audio_gain(1)-.4f)<.0001f);
    host_audio_profile("profile-a");assert(host_audio_level(0)==0 && host_audio_level(1)==10);
    unlink(audio_file);
    host_audio_profile("profile-b");assert(host_audio_level(1)==4);unlink(audio_file);
    {char folder[512];snprintf(folder,sizeof(folder),"%s/android-volumes",test_root);rmdir(folder);rmdir(test_root);}
    /* Active gameplay gating, including non-zoom weapons, independent caches and lifecycle transitions. */
    host_touch_mode(2);
    Java_com_halo_decomp_MotionAim_nativeEnabled(NULL,NULL,JNI_TRUE);
    assert(!Java_com_halo_decomp_MotionAim_nativeAiming(NULL,NULL));
    Java_com_halo_decomp_MotionAim_nativeDelta(NULL,NULL,.01f,-.02f);
    host_motion_look(&x,&y);assert(!x&&!y);
    host_touch_mode(2|HALO_ANDROID_TOUCH_AIMING);
    assert(Java_com_halo_decomp_HaloPort_nativeMode(NULL,NULL)==2);
    assert(Java_com_halo_decomp_MotionAim_nativeAiming(NULL,NULL));
    ACTION(7,1);
    Java_com_halo_decomp_HaloPort_nativeLook(NULL,NULL,.2f,-.1f);
    Java_com_halo_decomp_MotionAim_nativeDelta(NULL,NULL,.01f,-.02f);
    host_touch_look(&x,&y);assert(x==.2f&&y==-.1f);
    host_motion_look(&x,&y);assert(x==.01f&&y==-.02f);
    host_motion_look(&x,&y);assert(!x&&!y);
    Java_com_halo_decomp_MotionAim_nativeDelta(NULL,NULL,.01f,.02f);
    host_touch_mode(2);
    host_motion_look(&x,&y);assert(!x&&!y);
    host_touch_read(&b,&x,&y);assert(b&(1u<<7)); /* Changing camera eligibility cannot release fire. */
    host_touch_mode(2|HALO_ANDROID_TOUCH_AIMING);
    Java_com_halo_decomp_MotionAim_nativeDelta(NULL,NULL,.02f,.03f);
    Java_com_halo_decomp_SettingsOverlay_nativeOpen(NULL,NULL,JNI_TRUE);
    assert(!Java_com_halo_decomp_MotionAim_nativeAiming(NULL,NULL));
    host_motion_look(&x,&y);assert(!x&&!y);
    Java_com_halo_decomp_SettingsOverlay_nativeOpen(NULL,NULL,JNI_FALSE);
    movie_active=1;
    assert(!Java_com_halo_decomp_MotionAim_nativeAiming(NULL,NULL));
    Java_com_halo_decomp_MotionAim_nativeDelta(NULL,NULL,.02f,.03f);
    movie_active=0;
    host_motion_look(&x,&y);assert(!x&&!y);
    Java_com_halo_decomp_MotionAim_nativeDelta(NULL,NULL,.02f,.03f);
    clock_ms+=101;host_motion_look(&x,&y);assert(!x&&!y);
    clock_ms+=100;
    assert(!Java_com_halo_decomp_MotionAim_nativeAiming(NULL,NULL));
    host_touch_mode(2|HALO_ANDROID_TOUCH_AIMING);
    Java_com_halo_decomp_MotionAim_nativeDelta(NULL,NULL,NAN,INFINITY);
    Java_com_halo_decomp_MotionAim_nativeDelta(NULL,NULL,1,1);
    host_motion_look(&x,&y);assert(!x&&!y);
    for(int i=0;i<5;i++)Java_com_halo_decomp_MotionAim_nativeDelta(NULL,NULL,.1f,-.1f);
    host_motion_look(&x,&y);assert(x==.2f&&y==-.2f);
    Java_com_halo_decomp_MotionAim_nativeDelta(NULL,NULL,.01f,.02f);RESET();
    host_motion_look(&x,&y);assert(!x&&!y);
    Java_com_halo_decomp_MotionAim_nativeEnabled(NULL,NULL,JNI_FALSE);
    assert(!Java_com_halo_decomp_MotionAim_nativeAiming(NULL,NULL));
    host_touch_mode(1);
    Java_com_halo_decomp_MotionAim_nativeEnabled(NULL,NULL,JNI_TRUE);
    assert(!Java_com_halo_decomp_MotionAim_nativeAiming(NULL,NULL));
    puts("Android bridge: tap/hold/release, mode/lifecycle reset, move/look and audio checks passed.");
    puts("Gyro bridge: general gameplay, additive look, held buttons, stale samples, movies, overlay, reset and invalid data passed.");
    return 0;
}
