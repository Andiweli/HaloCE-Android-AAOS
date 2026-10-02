/*
BINK_NULL.C

The Bink video SDK entry points bink_playback.c uses. There is no Bink
decoder in the native builds (the RAD SDK is proprietary), so BinkOpen reports that a movie cannot be
opened and the game skips it, exactly as it does for a missing movie file.

The prototypes match the declarations in bink_playback.c; the RAD SDK's
RADEXPLINK is __stdcall.
*/

#include "platform.h"

typedef void *(__stdcall *rad_memory_allocate_proc)(unsigned long size);
typedef void (__stdcall *rad_memory_free_proc)(void *memory);
typedef void *(__stdcall *bink_sound_system_open_proc)(unsigned long param);
typedef struct BINK *HBINK;

void __stdcall RADSetMemory(rad_memory_allocate_proc allocate, rad_memory_free_proc release)
{
	(void)allocate;
	(void)release;
}

#ifdef HALO_ANDROID
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
struct BINK { uint32_t Width, Height, Frames, FrameNum, LastFrameNum; };
extern int host_bink_open(const char *, uint32_t *);
extern void host_bink_close(void);
extern int host_bink_frame(void);
extern int host_bink_wait(uint32_t);
extern int host_bink_copy(void *, int32_t, uint32_t);
void *__stdcall BinkOpenDirectSound(unsigned long p) { (void)p; return (void *)1; }
long __stdcall BinkSetSoundSystem(bink_sound_system_open_proc p, unsigned long v) { (void)p;(void)v;return 1; }
void __stdcall BinkSetIOSize(unsigned long s) { (void)s; }
HBINK __stdcall BinkOpen(const char *name, unsigned long flags) {
    (void)flags; HBINK b=calloc(1,sizeof(*b));
    if(b && !host_bink_open(name,(uint32_t*)b)) {free(b);b=NULL;} return b;
}
void __stdcall BinkClose(HBINK b) {host_bink_close();free(b);}
long __stdcall BinkDoFrame(HBINK b) {
    if(!host_bink_frame()) {b->FrameNum=b->Frames;return 1;} return 0;
}
void __stdcall BinkNextFrame(HBINK b) {b->LastFrameNum=b->FrameNum;if(b->FrameNum<b->Frames)b->FrameNum++;}
long __stdcall BinkWait(HBINK b) {return host_bink_wait(b->FrameNum);}
long __stdcall BinkCopyToBuffer(HBINK b,void *d,long pitch,unsigned long h,unsigned long x,unsigned long y,unsigned long flags) {
    (void)b;(void)flags;if(x || y) return 1;return host_bink_copy(d,pitch,h)?0:1;
}
void __stdcall BinkGetSummary(HBINK b,void *s) {(void)b;memset(s,0,31*4);}
void __stdcall BinkGetRealtime(HBINK b,void *s,unsigned long n) {(void)b;(void)n;memset(s,0,14*4);}
#else
void *__stdcall BinkOpenDirectSound(unsigned long param)
{
	(void)param;
	return NULL;
}

long __stdcall BinkSetSoundSystem(bink_sound_system_open_proc open, unsigned long param)
{
	(void)open;
	(void)param;
	return 0;
}

void __stdcall BinkSetIOSize(unsigned long io_size)
{
	(void)io_size;
}

HBINK __stdcall BinkOpen(const char *name, unsigned long flags)
{
	(void)flags;
	platform_log("Bink video is not supported; skipping \"%s\"", name ? name : "");
	return NULL;
}

/* never reached without an open movie */

void __stdcall BinkClose(HBINK bink) { (void)bink; }
long __stdcall BinkDoFrame(HBINK bink) { (void)bink; return 0; }
void __stdcall BinkNextFrame(HBINK bink) { (void)bink; }
long __stdcall BinkWait(HBINK bink) { (void)bink; return 0; }

long __stdcall BinkCopyToBuffer(HBINK bink, void *destination, long destination_pitch,
	unsigned long destination_height, unsigned long destination_x, unsigned long destination_y,
	unsigned long flags)
{
	(void)bink; (void)destination; (void)destination_pitch; (void)destination_height;
	(void)destination_x; (void)destination_y; (void)flags;
	return 0;
}

void __stdcall BinkGetSummary(HBINK bink, void *summary) { (void)bink; (void)summary; }
void __stdcall BinkGetRealtime(HBINK bink, void *realtime, unsigned long frame_count) { (void)bink; (void)realtime; (void)frame_count; }

#endif
