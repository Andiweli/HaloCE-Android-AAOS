/* Host-side input/audio bridge tests with a deterministic clock. */
#include <assert.h>
#include <stdio.h>
#include <math.h>
#include "../port/android/host/host_touch.c"
static char test_root[256];
void host_android_path(int which,char *buffer,unsigned int size) { (void)which;snprintf(buffer,size,"%s",test_root); }
static Uint64 clock_ms = 1000;
Uint64 SDL_GetTicks(void) { return clock_ms; }
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
    puts("Android bridge: tap/hold/release, mode/lifecycle reset, move/look and audio checks passed.");
    return 0;
}
