/* Android Bink 1 adapter. FFmpeg owns decoding; SDL owns a separate audio stream.
 * All decoder calls run on the game thread. Only pause/skip come from Java.
 * No decoder pointers cross the 32-bit guest / 64-bit host ABI. */
#include "host.h"
#include <SDL3/SDL.h>
#include <jni.h>
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
#include <strings.h>
#include <math.h>
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libswscale/swscale.h>
#include <libavutil/samplefmt.h>

static AVFormatContext *format;
static AVCodecContext *video, *audio;
static AVPacket *packet;
static AVFrame *picture, *samples;
static struct SwsContext *scaler;
static SDL_AudioStream *sound;
static int vi, ai, pending, failed;
static double fps;
static Uint64 origin, pause_start;
static atomic_int active, skip;
static int paused;
static pthread_mutex_t audio_lock = PTHREAD_MUTEX_INITIALIZER;
extern float host_audio_gain(int category);

int host_bink_active(void) { return atomic_load(&active); }
int host_bink_skip(void) { return atomic_load(&skip); }

static void set_pause(int value) {
    pthread_mutex_lock(&audio_lock);
    Uint64 now=SDL_GetTicksNS();
    if (value && !paused) { pause_start=now; if(sound) SDL_PauseAudioStreamDevice(sound); }
    if (!value && paused) {
        if(origin) origin+=now-pause_start;
        if(sound && origin) SDL_ResumeAudioStreamDevice(sound);
    }
    paused=value;
    pthread_mutex_unlock(&audio_lock);
}
JNIEXPORT void JNICALL Java_com_halo_decomp_HaloActivity_nativeMoviePause(JNIEnv *e,jclass c,jboolean p) {set_pause(p);}
JNIEXPORT jboolean JNICALL Java_com_halo_decomp_HaloActivity_nativeMovieSkip(JNIEnv *e,jclass c) {
    if(!atomic_load(&active)) return JNI_FALSE;
    atomic_store(&skip,1);return JNI_TRUE;
}

void host_bink_close(void) {
    atomic_store(&active,0);
    pthread_mutex_lock(&audio_lock);
    if(sound) SDL_DestroyAudioStream(sound);
    sound=NULL; origin=0;
    pthread_mutex_unlock(&audio_lock);
    sws_freeContext(scaler);scaler=NULL;
    av_frame_free(&picture);av_frame_free(&samples);av_packet_free(&packet);
    avcodec_free_context(&video);avcodec_free_context(&audio);avformat_close_input(&format);
    pending=failed=0;
}
static AVCodecContext *open_decoder(int stream) {
    const AVCodec *codec=avcodec_find_decoder(format->streams[stream]->codecpar->codec_id);
    if(!codec) return NULL;
    AVCodecContext *ctx=avcodec_alloc_context3(codec);
    if(!ctx) return NULL;
    if(avcodec_parameters_to_context(ctx,format->streams[stream]->codecpar)<0 || avcodec_open2(ctx,codec,NULL)<0)
        avcodec_free_context(&ctx);
    return ctx;
}
int host_bink_open(const char *name, uint32_t *info) {
    char path[1024]; const char *base=name;
    host_bink_close(); atomic_store(&skip,0);
    if(!name || !info) return 0;
    for(const char *p=name;*p;p++) if(*p=='/' || *p=='\\') base=p+1;
    const char *movie=!strcasecmp(base,"intro.bik")?"intro.bik":!strcasecmp(base,"credits.bik")?"credits.bik":NULL;
    const char *root=SDL_GetAndroidExternalStoragePath();
    if(!movie || !root || snprintf(path,sizeof(path),"%s/bink/%s",root,movie)>=(int)sizeof(path)) return 0;
    if(avformat_open_input(&format,path,av_find_input_format("bink"),NULL)<0) goto error;
    if(avformat_find_stream_info(format,NULL)<0) goto error;
    vi=av_find_best_stream(format,AVMEDIA_TYPE_VIDEO,-1,-1,NULL,0);
    ai=av_find_best_stream(format,AVMEDIA_TYPE_AUDIO,-1,-1,NULL,0);
    if(vi<0 || !(video=open_decoder(vi))) goto error;
    if(video->width<=0 || video->height<=0 || video->width>1920 || video->height>1080 || video->width%32 || (int64_t)video->width*video->height*4>3*1024*1024) goto error;
    AVRational rate=format->streams[vi]->avg_frame_rate;
    if(!rate.num) rate=format->streams[vi]->r_frame_rate;
    fps=av_q2d(rate);
    if(!isfinite(fps) || fps<1 || fps>120) goto error;
    int64_t frames=format->streams[vi]->nb_frames;
    if(frames<=0 && format->streams[vi]->duration>0)
        frames=av_rescale_q(format->streams[vi]->duration,format->streams[vi]->time_base,av_inv_q(rate));
    if(frames<=0 || frames>1000000) goto error;
    if(ai>=0) {
        audio=open_decoder(ai);
        if(!audio || audio->ch_layout.nb_channels<1 || audio->ch_layout.nb_channels>2) goto error;
        SDL_AudioSpec spec={.format=SDL_AUDIO_F32,.channels=audio->ch_layout.nb_channels,.freq=audio->sample_rate};
        pthread_mutex_lock(&audio_lock);
        sound=SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK,&spec,NULL,NULL);
        pthread_mutex_unlock(&audio_lock);
        if(!sound) goto error;
    }
    packet=av_packet_alloc();picture=av_frame_alloc();samples=av_frame_alloc();
    if(!packet || !picture || !samples) goto error;
    info[0]=video->width; info[1]=video->height;info[2]=(uint32_t)frames;info[3]=0;info[4]=0;
    atomic_store(&active,1);
    host_logf(HOST_LOG_INFO,"Bink: %s %dx%d %.3f fps, %lld frames, audio=%d",movie,video->width,video->height,fps,(long long)frames,ai>=0);
    return 1;
error:
    host_logf(HOST_LOG_WARN,"Bink: could not open %s; skipping",path);
    host_bink_close();return 0;
}
static int queue_audio(void) {
    if(avcodec_send_packet(audio,packet)<0) return 0;
    int result;
    while((result=avcodec_receive_frame(audio,samples))>=0) {
        int channels=audio->ch_layout.nb_channels, count=samples->nb_samples;
        if(samples->format!=AV_SAMPLE_FMT_FLT && samples->format!=AV_SAMPLE_FMT_FLTP) return 0;
        float *pcm=av_malloc_array((size_t)count*channels,sizeof(float));
        if(!pcm) return 0;
        for(int i=0;i<count;i++) for(int c=0;c<channels;c++)
            pcm[i*channels+c]=samples->format==AV_SAMPLE_FMT_FLT ? ((float*)samples->data[0])[i*channels+c] : ((float*)samples->extended_data[c])[i];
        pthread_mutex_lock(&audio_lock);
        SDL_SetAudioStreamGain(sound,host_audio_gain(0));
        bool ok=SDL_PutAudioStreamData(sound,pcm,count*channels*sizeof(float));
        pthread_mutex_unlock(&audio_lock);
        av_free(pcm);av_frame_unref(samples);
        if(!ok) return 0;
    }
    return result==AVERROR(EAGAIN) || result==AVERROR_EOF;
}
int host_bink_frame(void) {
    if(!atomic_load(&active) || failed) return 0;
    int got=0;
    for(;;) {
        if(!pending) {
            int result=av_read_frame(format,packet);
            if(result<0) {
                if(result!=AVERROR_EOF) goto error;
                if(sound) SDL_FlushAudioStream(sound);
                break;
            }
        }
        pending=0;
        if(packet->stream_index==vi) {
            if(got) {pending=1;break;}
            if(avcodec_send_packet(video,packet)<0 || avcodec_receive_frame(video,picture)<0) goto error;
            got=1;
        } else if(packet->stream_index==ai && audio) {
            if(!queue_audio()) goto error;
        }
        av_packet_unref(packet);
    }
    if(!got) goto error;
    return 1;
error:
    failed=1;atomic_store(&skip,1);
    host_logf(HOST_LOG_WARN,"Bink decode failed; returning to game");return 0;
}
int host_bink_wait(uint32_t next_frame) {
    pthread_mutex_lock(&audio_lock);
    if(!origin) {
        origin=SDL_GetTicksNS();
        if(paused) pause_start=origin;
        if(sound && !paused) SDL_ResumeAudioStreamDevice(sound);
    }
    pthread_mutex_unlock(&audio_lock);
    pthread_mutex_lock(&audio_lock);
    int wait=paused || (origin && (double)(SDL_GetTicksNS()-origin)/1e9 < next_frame/fps);
    pthread_mutex_unlock(&audio_lock);
    return wait;
}
int host_bink_copy(void *destination, int32_t pitch, uint32_t height) {
    if(!picture || !picture->data[0] || !destination || pitch<video->width*4 || height<(uint32_t)video->height) return 0;
    scaler=sws_getCachedContext(scaler,video->width,video->height,picture->format,
        video->width,video->height,AV_PIX_FMT_BGRA,SWS_BILINEAR,NULL,NULL,NULL);
    if(!scaler) {atomic_store(&skip,1);return 0;}
    uint8_t *out[4]={destination,NULL,NULL,NULL};int lines[4]={pitch,0,0,0};
    return sws_scale(scaler,(const uint8_t *const*)picture->data,picture->linesize,0,video->height,out,lines)==video->height;
}
