/* On-demand, one-frame GLES capture. All GL inspection runs on the render
 * thread. JNI only queues a directory and reads completion state. No guest
 * memory writes, shader overrides, or changes to game data. */
#include "host.h"
#include <GLES3/gl32.h>
#include <jni.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

#define MAX_DRAWS 2048
#define MAX_PROGRAMS 128
#define MAX_TEXTURES 96
#define IMAGE_BUDGET (32u * 1024u * 1024u)
#define REPORT_BUDGET (8L * 1024L * 1024L)
static atomic_int state; /* 0 idle, 1 requested, 2 capturing, 3 done, -1 failed */
static pthread_mutex_t request_lock = PTHREAD_MUTEX_INITIALIZER;
static char directory[1024];
static FILE *report;
static unsigned draws, program_count, texture_count, image_bytes;
static GLuint programs[MAX_PROGRAMS], textures[MAX_TEXTURES], read_fbo;
static int report_failed, timed_out;
static int detailed_draw;
static unsigned detailed_draws;
static long report_bytes;
static unsigned geometry_bytes;
static struct timespec started;
static int capture_expired(void) {
    struct timespec now;clock_gettime(CLOCK_MONOTONIC,&now);
    return (now.tv_sec-started.tv_sec)+(now.tv_nsec-started.tv_nsec)/1e9 > 12.0;
}

static void note(const char *format, ...) __attribute__((format(printf,1,2)));
static void note(const char *format, ...)
{
    if (!report || report_bytes > REPORT_BUDGET) return;
    va_list args; va_start(args,format);
    int written=vfprintf(report,format,args);
    if (written<0) report_failed=1; else report_bytes+=written;
    va_end(args);
}
static void errors(const char *where)
{
    GLenum error; int n=0;
    while (n++<16 && (error=glGetError())!=GL_NO_ERROR)
        note("GL_ERROR %s 0x%x\n",where,error);
}
JNIEXPORT jboolean JNICALL Java_com_halo_decomp_GraphicsDiagnostics_nativeRequest(
    JNIEnv *env,jclass cls,jstring folder)
{
    (void)cls;
    if (!folder) return JNI_FALSE;
    const char *path=(*env)->GetStringUTFChars(env,folder,NULL);
    if (!path) return JNI_FALSE;
    jboolean accepted=JNI_FALSE;
    pthread_mutex_lock(&request_lock);
    int s=atomic_load(&state);
    if (s!=1 && s!=2 && strlen(path)<sizeof(directory)) {
        snprintf(directory,sizeof(directory),"%s",path);
        atomic_store(&state,1); accepted=JNI_TRUE;
    }
    pthread_mutex_unlock(&request_lock);
    (*env)->ReleaseStringUTFChars(env,folder,path);
    return accepted;
}
JNIEXPORT jint JNICALL Java_com_halo_decomp_GraphicsDiagnostics_nativeState(JNIEnv *env,jclass cls)
{ (void)env;(void)cls;return atomic_load(&state); }

/* Preserve read FBO and its read-buffer selector, plus every pack state that
 * could redirect or stride a read into client memory. DRAW framebuffer is
 * never changed by diagnostics. */
struct read_state { GLint fbo,buffer,target_buffer,pbo,align,row,skip_rows,skip_pixels; };
static void read_begin(struct read_state *s,GLuint fbo,GLenum buffer)
{
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING,&s->fbo);
    glGetIntegerv(GL_READ_BUFFER,&s->buffer);
    glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING,&s->pbo);
    glGetIntegerv(GL_PACK_ALIGNMENT,&s->align);
    glGetIntegerv(GL_PACK_ROW_LENGTH,&s->row);
    glGetIntegerv(GL_PACK_SKIP_ROWS,&s->skip_rows);
    glGetIntegerv(GL_PACK_SKIP_PIXELS,&s->skip_pixels);
    glBindBuffer(GL_PIXEL_PACK_BUFFER,0);
    glPixelStorei(GL_PACK_ALIGNMENT,1);glPixelStorei(GL_PACK_ROW_LENGTH,0);
    glPixelStorei(GL_PACK_SKIP_ROWS,0);glPixelStorei(GL_PACK_SKIP_PIXELS,0);
    glBindFramebuffer(GL_READ_FRAMEBUFFER,fbo);
    glGetIntegerv(GL_READ_BUFFER,&s->target_buffer);glReadBuffer(buffer);
}
static void read_end(const struct read_state *s)
{
    glReadBuffer((GLenum)s->target_buffer);
    glBindFramebuffer(GL_READ_FRAMEBUFFER,(GLuint)s->fbo);glReadBuffer((GLenum)s->buffer);
    glBindBuffer(GL_PIXEL_PACK_BUFFER,(GLuint)s->pbo);
    glPixelStorei(GL_PACK_ALIGNMENT,s->align);glPixelStorei(GL_PACK_ROW_LENGTH,s->row);
    glPixelStorei(GL_PACK_SKIP_ROWS,s->skip_rows);glPixelStorei(GL_PACK_SKIP_PIXELS,s->skip_pixels);
}
static void save_image(const char *name,GLuint fbo,int width,int height)
{
    size_t bytes;
    if (width<=0 || height<=0 || width>4096 || height>4096) {note("IMAGE skipped size %dx%d\n",width,height);return;}
    bytes=(size_t)width*height*4;
    if (bytes>IMAGE_BUDGET-image_bytes) {note("IMAGE skipped budget %s\n",name);return;}
    unsigned char *pixels=malloc(bytes);
    if (!pixels) {note("IMAGE allocation failed\n");return;}
    struct read_state saved;
    read_begin(&saved,fbo,fbo?GL_COLOR_ATTACHMENT0:GL_BACK);
    glReadPixels(0,0,width,height,GL_RGBA,GL_UNSIGNED_BYTE,pixels);
    GLenum error=glGetError();read_end(&saved);
    if (error) {note("IMAGE read failed %s 0x%x\n",name,error);free(pixels);return;}
    char path[1200];snprintf(path,sizeof(path),"%s/%s",directory,name);
    FILE *file=fopen(path,"wb");
    if (!file) {note("IMAGE open failed %s\n",name);free(pixels);return;}
    int alpha=strstr(name,".pam")!=NULL;
    if(alpha)fprintf(file,"P7\nWIDTH %d\nHEIGHT %d\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n",width,height);
    else fprintf(file,"P6\n%d %d\n255\n",width,height);
    unsigned char *row=malloc((size_t)width*3);
    int failed=!row;
    if (row) {
        for (int y=height-1;y>=0;y--) {
            for(int x=0;x<width;x++) memcpy(row+x*3,pixels+((size_t)y*width+x)*4,3);
            size_t written=alpha?fwrite(pixels+(size_t)y*width*4,4,(size_t)width,file):fwrite(row,3,(size_t)width,file);
            if(written!=(size_t)width) {failed=1;break;}
        }
        free(row);
    }
    if (fclose(file)) failed=1;
    free(pixels);image_bytes+=(unsigned)bytes;
    note("IMAGE %s %dx%d %s\n",name,width,height,failed?"WRITE_FAILED":"saved");
    if (failed) report_failed=1;
}
static GLint value(GLenum name) {GLint v=0;glGetIntegerv(name,&v);return v;}
static void program_details(GLuint program)
{
    if (!program) return;
    int seen=0;for(unsigned i=0;i<program_count;i++)if(programs[i]==program)seen=1;
    if (!seen && program_count<MAX_PROGRAMS) {
        programs[program_count++]=program;
        GLint linked=0;GLuint shaders[8];GLsizei count=0;
        glGetProgramiv(program,GL_LINK_STATUS,&linked);
        glGetAttachedShaders(program,8,&count,shaders);
        note("PROGRAM %u linked=%d attached=%d\n",program,linked,count);
        for(int i=0;i<count;i++) {
            GLint length=0,type=0;glGetShaderiv(shaders[i],GL_SHADER_SOURCE_LENGTH,&length);
            glGetShaderiv(shaders[i],GL_SHADER_TYPE,&type);
            if (length<=0 || length>131072) {note("SHADER source skipped size=%d\n",length);continue;}
            char *source=malloc((size_t)length);if(!source)continue;
            GLsizei actual=0;glGetShaderSource(shaders[i],length,&actual,source);
            char path[1200];snprintf(path,sizeof(path),"%s/program-%u-shader-%u-%x.glsl",directory,program,shaders[i],type);
            FILE *file=fopen(path,"wb");
            if(file){if(fwrite(source,1,(size_t)actual,file)!=(size_t)actual)report_failed=1;if(fclose(file))report_failed=1;}
            else report_failed=1;
            free(source);
        }
    }
    if (!detailed_draw) return;
    GLint count=0;glGetProgramiv(program,GL_ACTIVE_UNIFORMS,&count);
    for(GLint i=0;i<count && i<512;i++) {
        char name[256];GLint size=0;GLenum type=0;
        glGetActiveUniform(program,(GLuint)i,sizeof(name),NULL,&size,&type,name);
        /* Every draw records values, including matrices/constant arrays. */
        char *array=strstr(name,"[0]");if(array)*array=0;
        for(int j=0;j<size && j<256;j++) {
            /* Position transform and alpha/combiner controls suffice for this
             * geometry investigation. Avoid 192 driver queries per draw. */
            if (!detailed_draw) break;
            if (!strcmp(name,"c") && !(j<4 || j==58 || j==59)) continue;
            if (strcmp(name,"c") && strcmp(name,"viewport_scale") && strcmp(name,"viewport_offset")
                && strcmp(name,"screen_offset") && strcmp(name,"alpha_reference")
                && strcmp(name,"ps_final_c0") && strcmp(name,"ps_final_c1")) continue;
            char element[280];snprintf(element,sizeof(element),array?"%s[%d]":"%s",name,j);
            GLint loc=glGetUniformLocation(program,element);if(loc<0)continue;
            GLfloat data[16]={0};int n=1;
            switch(type) {
                case GL_FLOAT_VEC2:n=2;break;case GL_FLOAT_VEC3:n=3;break;case GL_FLOAT_VEC4:n=4;break;
                case GL_FLOAT_MAT2:n=4;break;case GL_FLOAT_MAT3:n=9;break;case GL_FLOAT_MAT4:n=16;break;
                case GL_FLOAT_MAT2x3:case GL_FLOAT_MAT3x2:n=6;break;
                case GL_FLOAT_MAT2x4:case GL_FLOAT_MAT4x2:n=8;break;
                case GL_FLOAT_MAT3x4:case GL_FLOAT_MAT4x3:n=12;break;
                case GL_INT_VEC2:case GL_BOOL_VEC2:case GL_UNSIGNED_INT_VEC2:n=2;break;
                case GL_INT_VEC3:case GL_BOOL_VEC3:case GL_UNSIGNED_INT_VEC3:n=3;break;
                case GL_INT_VEC4:case GL_BOOL_VEC4:case GL_UNSIGNED_INT_VEC4:n=4;break;
            }
            glGetUniformfv(program,loc,data);
            note("  U %s type=0x%x",element,type);
            for(int k=0;k<n;k++) note(" %.9g",data[k]);
            note("\n");
        }
    }
}
static void texture_details(void)
{
    GLint active=value(GL_ACTIVE_TEXTURE);
    for(unsigned unit=0;unit<4;unit++) {
        glActiveTexture(GL_TEXTURE0+unit);
        GLuint tex=(GLuint)value(GL_TEXTURE_BINDING_2D);
        GLuint cube=(GLuint)value(GL_TEXTURE_BINDING_CUBE_MAP);
        GLuint three=(GLuint)value(GL_TEXTURE_BINDING_3D);
        note("  TEX unit=%u 2d=%u cube=%u 3d=%u sampler=%d\n",unit,tex,cube,three,value(GL_SAMPLER_BINDING));
        if (!detailed_draw) continue;
        GLuint sampler=(GLuint)value(GL_SAMPLER_BINDING);
        if(sampler) {
            GLint min=0,mag=0,s=0,t=0;GLfloat minlod=0,maxlod=0;
            glGetSamplerParameteriv(sampler,GL_TEXTURE_MIN_FILTER,&min);glGetSamplerParameteriv(sampler,GL_TEXTURE_MAG_FILTER,&mag);
            glGetSamplerParameteriv(sampler,GL_TEXTURE_WRAP_S,&s);glGetSamplerParameteriv(sampler,GL_TEXTURE_WRAP_T,&t);
            glGetSamplerParameterfv(sampler,GL_TEXTURE_MIN_LOD,&minlod);glGetSamplerParameterfv(sampler,GL_TEXTURE_MAX_LOD,&maxlod);
            note("    SAMPLER filter=%x/%x wrap=%x/%x lod=%g..%g\n",min,mag,s,t,minlod,maxlod);
        }
        if(!tex)continue;
        GLint base=0,max=0,min=0,mag=0,wraps=0,wrapt=0;
        glGetTexParameteriv(GL_TEXTURE_2D,GL_TEXTURE_BASE_LEVEL,&base);glGetTexParameteriv(GL_TEXTURE_2D,GL_TEXTURE_MAX_LEVEL,&max);
        glGetTexParameteriv(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,&min);glGetTexParameteriv(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,&mag);
        glGetTexParameteriv(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,&wraps);glGetTexParameteriv(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,&wrapt);
        note("    base=%d max=%d filter=%x/%x wrap=%x/%x\n",base,max,min,mag,wraps,wrapt);
        int seen=0;for(unsigned i=0;i<texture_count;i++)if(textures[i]==tex)seen=1;
        if(seen || texture_count>=MAX_TEXTURES)continue;
        textures[texture_count++]=tex;
        for(int level=0;level<=12;level++) {
            GLint w=0,h=0,format=0,compressed=0;
            glGetTexLevelParameteriv(GL_TEXTURE_2D,level,GL_TEXTURE_WIDTH,&w);glGetTexLevelParameteriv(GL_TEXTURE_2D,level,GL_TEXTURE_HEIGHT,&h);
            glGetTexLevelParameteriv(GL_TEXTURE_2D,level,GL_TEXTURE_INTERNAL_FORMAT,&format);
            glGetTexLevelParameteriv(GL_TEXTURE_2D,level,GL_TEXTURE_COMPRESSED,&compressed);
            note("    LEVEL %d %dx%d fmt=0x%x compressed=%d\n",level,w,h,format,compressed);
            if(!w || !h)break;
            if(w==1 && h==1)break;
        }
    }
    glActiveTexture((GLenum)active);
}

/* Only persistent 4 MiB mirror buffers are tracked. Never retain pointers
 * into transient upload allocations. Metadata is render-thread owned. */
#define MIRROR_BYTES 0x400000u
struct source_buffer {
    GLuint id;
    uintptr_t base;
    uint32_t generation[1024];
    unsigned char uploaded[1024];
};
static struct source_buffer sources[32];
static unsigned upload_unmap_failures;
uint32_t host_memory_watch_generation(uint32_t address, uint32_t size);
static struct source_buffer *source_find(GLuint id) {
    for(unsigned i=0;i<32;i++)if(sources[i].id==id && id)return &sources[i];
    return NULL;
}
static void source_forget(GLuint id) {
    struct source_buffer *s=source_find(id);if(s)memset(s,0,sizeof(*s));
}
void host_gfx_upload(uint32_t target,uint32_t offset,uint32_t size,const void *data) {
    if(target!=GL_COPY_WRITE_BUFFER || !size || offset%4096 || size%4096 ||
       offset>=MIRROR_BYTES || size>MIRROR_BYTES-offset)return;
    uintptr_t address=(uintptr_t)data,window=host_memory_window_base();
    if(!window || address<window || address-window>=0x8000000u ||
       size>0x8000000u-(address-window) || address<offset)return;
    uintptr_t base=address-offset;
    if(base<window || (base-window)%MIRROR_BYTES)return;
    GLuint id=(GLuint)value(GL_COPY_WRITE_BUFFER_BINDING);
    struct source_buffer *s=source_find(id);
    if(!s)for(unsigned i=0;i<32;i++)if(!sources[i].id){s=&sources[i];break;}
    if(!s || !id)return;
    if(s->base!=base){memset(s,0,sizeof(*s));s->id=id;s->base=base;}
    for(unsigned p=offset/4096;p<(offset+size)/4096;p++) {
        s->generation[p]=host_memory_watch_generation((uint32_t)(base+p*4096),4096);
        s->uploaded[p]=1;
    }
}
void host_gfx_upload_result(int success) {if(!success)upload_unmap_failures++;}
static void compare_source(GLuint id,uint64_t offset,uint64_t length,const unsigned char *gpu,const char *name) {
    struct source_buffer *s=source_find(id);
    if(!s || offset>=MIRROR_BYTES || length>MIRROR_BYTES-offset) {
        note("  CPU_COMPARE unavailable: buffer=%u is not a tracked persistent mirror\n",id);return;
    }
    /* Copy only our validated mirror range through an anonymous nonblocking
     * pipe. Kernel copy_from_user returns EFAULT for inaccessible source
     * pages; no procfs access or signal-handler changes are needed.
     * Each transfer is at most PIPE_BUF (4096 on Android/Linux), with an
     * empty pipe, so a full write is atomic and cannot block the renderer. */
    int transfer[2];
    if(pipe2(transfer,O_CLOEXEC|O_NONBLOCK)<0) {
        note("  CPU_COMPARE unavailable: pipe errno=%d\n",errno);return;
    }
    unsigned char *cpu=malloc((size_t)length);
    if(!cpu){close(transfer[0]);close(transfer[1]);return;}
    int complete=1;
    for(uint64_t pos=0;pos<length;) {
        uint64_t off=offset+pos;unsigned page=(unsigned)(off/4096);
        size_t n=4096-(size_t)(off%4096);if(n>length-pos)n=(size_t)(length-pos);
        uint32_t before=host_memory_watch_generation((uint32_t)(s->base+page*4096),4096);
        ssize_t sent;
        do {sent=write(transfer[1],(const void *)(s->base+off),n);} while(sent<0 && errno==EINTR);
        ssize_t got=sent;
        if(sent==(ssize_t)n) {
            do {got=read(transfer[0],cpu+pos,n);} while(got<0 && errno==EINTR);
        }
        uint32_t after=host_memory_watch_generation((uint32_t)(s->base+page*4096),4096);
        if(got!=(ssize_t)n){note("  CPU_PAGE unreadable offset=%llu got=%lld errno=%d\n",(unsigned long long)off,(long long)got,errno);complete=0;break;}
        size_t different=0,cz=0,gz=0,first=n;
        for(size_t j=0;j<n;j++){
            cz+=cpu[pos+j]==0;gz+=gpu[pos+j]==0;
            if(cpu[pos+j]!=gpu[pos+j]){different++;if(first==n)first=j;}
        }
        note("  CPU_PAGE buffer=%u offset=%llu source=%llx bytes=%zu uploaded=%u generation_upload=%u generation_before=%u generation_after=%u different=%zu first_difference=%lld cpu_zero=%zu gpu_zero=%zu\n",
            id,(unsigned long long)off,(unsigned long long)(s->base+off),n,s->uploaded[page],s->generation[page],before,after,different,first==n?-1LL:(long long)(off+first),cz,gz);
        pos+=n;
    }
    close(transfer[0]);close(transfer[1]);
    if(complete) {
        char path[1200];snprintf(path,sizeof(path),"%s/cpu-%s",directory,name);
        FILE *f=fopen(path,"wb");if(!f)report_failed=1;
        else{if(fwrite(cpu,1,(size_t)length,f)!=(size_t)length)report_failed=1;if(fclose(f))report_failed=1;}
        note("  CPU_BUFFER file=cpu-%s source=%llx bytes=%llu\n",name,(unsigned long long)(s->base+offset),(unsigned long long)length);
    }
    free(cpu);
}
static void (*real_buffer_data)(GLenum,GLsizeiptr,const void*,GLenum);
static void (*real_buffer_sub_data)(GLenum,GLintptr,GLsizeiptr,const void*);
static void (*real_delete_buffers)(GLsizei,const GLuint*);
static void buffer_data(GLenum t,GLsizeiptr n,const void *p,GLenum usage) {
    /* BufferData replaces storage even if a name is reused. */
    GLenum binding=t==GL_ARRAY_BUFFER?GL_ARRAY_BUFFER_BINDING:t==GL_ELEMENT_ARRAY_BUFFER?GL_ELEMENT_ARRAY_BUFFER_BINDING:t==GL_COPY_WRITE_BUFFER?GL_COPY_WRITE_BUFFER_BINDING:0;
    if(binding)source_forget((GLuint)value(binding));
    real_buffer_data(t,n,p,usage);
}
static void buffer_sub_data(GLenum t,GLintptr off,GLsizeiptr n,const void *p) {
    if(off>=0 && n>0 && (uint64_t)off<=UINT32_MAX && (uint64_t)n<=UINT32_MAX)host_gfx_upload(t,(uint32_t)off,(uint32_t)n,p);
    real_buffer_sub_data(t,off,n,p);
}
static void delete_buffers(GLsizei n,const GLuint *ids) {
    for(GLsizei i=0;i<n;i++)source_forget(ids[i]);real_delete_buffers(n,ids);
}
/* Copy only the byte ranges referenced by this draw, through COPY_READ so
 * neither the VAO nor the game's ARRAY/ELEMENT bindings are disturbed. */
static unsigned char *buffer_range(GLuint buffer,uint64_t offset,uint64_t length,const char *name)
{
    if(!buffer || !length || length>262144 || geometry_bytes+length>16u*1024u*1024u) {
        note("  BUFFER skipped id=%u offset=%llu bytes=%llu (capture bounds)\n",buffer,(unsigned long long)offset,(unsigned long long)length);return NULL;
    }
    GLint previous=value(GL_COPY_READ_BUFFER_BINDING),mapped=0;GLint64 size=0;
    glBindBuffer(GL_COPY_READ_BUFFER,buffer);
    glGetBufferParameteri64v(GL_COPY_READ_BUFFER,GL_BUFFER_SIZE,&size);
    glGetBufferParameteriv(GL_COPY_READ_BUFFER,GL_BUFFER_MAPPED,&mapped);
    unsigned char *copy=NULL;
    if(mapped || size<0 || offset>(uint64_t)size || length>(uint64_t)size-offset) {
        note("  BUFFER invalid/unavailable id=%u size=%lld mapped=%d offset=%llu bytes=%llu\n",buffer,(long long)size,mapped,(unsigned long long)offset,(unsigned long long)length);
    } else {
        copy=malloc((size_t)length);
        if(copy) {
            const void *ptr=glMapBufferRange(GL_COPY_READ_BUFFER,(GLintptr)offset,(GLsizeiptr)length,GL_MAP_READ_BIT);
            if(ptr) {
                memcpy(copy,ptr,(size_t)length);
                if(!glUnmapBuffer(GL_COPY_READ_BUFFER)){free(copy);copy=NULL;note("  BUFFER unmap failed id=%u\n",buffer);}
            } else {free(copy);copy=NULL;note("  BUFFER read mapping unavailable id=%u\n",buffer);}
        }
    }
    glBindBuffer(GL_COPY_READ_BUFFER,(GLuint)previous);
    if(copy) {
        geometry_bytes+=(unsigned)length;
        compare_source(buffer,offset,length,copy,name);
        char path[1200];snprintf(path,sizeof(path),"%s/%s",directory,name);
        FILE *file=fopen(path,"wb");
        if(file){if(fwrite(copy,1,(size_t)length,file)!=(size_t)length)report_failed=1;if(fclose(file))report_failed=1;}
        else report_failed=1;
        note("  BUFFER file=%s id=%u offset=%llu bytes=%llu\n",name,buffer,(unsigned long long)offset,(unsigned long long)length);
    }
    return copy;
}
/* ES 3.1 separates an attribute's format from its stream binding. Query
 * the binding's actual offset and stride so optional geometry dumps keep
 * describing the uploaded bytes. ES 3.0 retains the pointer query. */
static int attribute_layout(GLuint attribute, GLint *buffer, GLint *size,
                            GLint *stride, GLint *format, uint64_t *offset)
{
    GLint major=0,minor=0;
    glGetVertexAttribiv(attribute,GL_VERTEX_ATTRIB_ARRAY_SIZE,size);
    glGetVertexAttribiv(attribute,GL_VERTEX_ATTRIB_ARRAY_TYPE,format);
    glGetIntegerv(GL_MAJOR_VERSION,&major);
    glGetIntegerv(GL_MINOR_VERSION,&minor);
    if(major>3 || (major==3 && minor>=1)) {
        GLint binding=0,relative=0;
        GLint64 base=0;
        glGetVertexAttribiv(attribute,GL_VERTEX_ATTRIB_BINDING,&binding);
        glGetVertexAttribiv(attribute,GL_VERTEX_ATTRIB_RELATIVE_OFFSET,&relative);
        glGetIntegeri_v(GL_VERTEX_BINDING_BUFFER,(GLuint)binding,buffer);
        glGetIntegeri_v(GL_VERTEX_BINDING_STRIDE,(GLuint)binding,stride);
        glGetInteger64i_v(GL_VERTEX_BINDING_OFFSET,(GLuint)binding,&base);
        *offset=(uint64_t)base+(unsigned)relative;
        return 1;
    }
    void *pointer=NULL;
    glGetVertexAttribiv(attribute,GL_VERTEX_ATTRIB_ARRAY_BUFFER_BINDING,buffer);
    glGetVertexAttribiv(attribute,GL_VERTEX_ATTRIB_ARRAY_STRIDE,stride);
    glGetVertexAttribPointerv(attribute,GL_VERTEX_ATTRIB_ARRAY_POINTER,&pointer);
    *offset=(uintptr_t)pointer;
    return 0;
}

static void geometry(GLsizei count,GLenum type,const void *indices,GLint base)
{
    if(count<=0)return;
    int64_t low=base,high=(int64_t)base+count-1;
    if(type) {
        unsigned step=type==GL_UNSIGNED_SHORT?2:type==GL_UNSIGNED_INT?4:type==GL_UNSIGNED_BYTE?1:0;
        if(!step)return;
        char name[80];snprintf(name,sizeof(name),"draw-%04u-indices.bin",draws);
        unsigned char *data=buffer_range((GLuint)value(GL_ELEMENT_ARRAY_BUFFER_BINDING),(uintptr_t)indices,(uint64_t)count*step,name);
        if(!data)return;
        uint32_t min=UINT32_MAX,max=0;
        GLboolean restart=glIsEnabled(GL_PRIMITIVE_RESTART_FIXED_INDEX);
        for(GLsizei i=0;i<count;i++) {
            uint32_t index=0;memcpy(&index,data+(size_t)i*step,step);
            if(restart && index==(step==1?255u:step==2?65535u:UINT32_MAX))continue;
            if(index<min)min=index;
            if(index>max)max=index;
        }
        free(data);if(min==UINT32_MAX)return;
        low=(int64_t)min+base;high=(int64_t)max+base;
    }
    note("  VERTEX_RANGE %lld..%lld\n",(long long)low,(long long)high);
    if(low<0 || high<low)return;
    for(GLuint a=0;a<1;a++) {
        GLint enabled=0,buffer=0,size=0,stride=0,format=0;uint64_t offset=0;
        glGetVertexAttribiv(a,GL_VERTEX_ATTRIB_ARRAY_ENABLED,&enabled);if(!enabled)continue;
        int bindings=attribute_layout(a,&buffer,&size,&stride,&format,&offset);
        unsigned component=format==GL_FLOAT || format==GL_INT || format==GL_UNSIGNED_INT || format==GL_FIXED?4:
            format==GL_SHORT || format==GL_UNSIGNED_SHORT || format==GL_HALF_FLOAT?2:1;
        unsigned bytes=(unsigned)size*component;
        if(format==GL_INT_2_10_10_10_REV || format==GL_UNSIGNED_INT_2_10_10_10_REV)bytes=4;
        if(!stride && !bindings)stride=(GLint)bytes;
        char name[80];snprintf(name,sizeof(name),"draw-%04u-attr-%u.bin",draws,a);
        free(buffer_range((GLuint)buffer,offset+(uint64_t)low*stride,(uint64_t)(high-low)*stride+bytes,name));
    }
}
static int before_draw(const char *kind,GLenum mode,GLsizei count,GLenum type,const void *indices,GLint base)
{
    if(atomic_load(&state)!=2)return 0;
    draws++;if(draws>MAX_DRAWS || report_bytes>REPORT_BUDGET)return 0;
    if (capture_expired() && !timed_out) {
        note("DETAIL_BUDGET reached: brief trace continues for all remaining draws.\n");timed_out=1;
    }
    detailed_draw=!timed_out && mode==GL_TRIANGLES;
    if(detailed_draw)detailed_draws++;
    errors("before-draw");
    GLint vp[4];GLboolean mask[4];glGetIntegerv(GL_VIEWPORT,vp);glGetBooleanv(GL_COLOR_WRITEMASK,mask);
    GLuint program=(GLuint)value(GL_CURRENT_PROGRAM);
    note("DRAW %u %s mode=0x%x count=%d type=0x%x offset=%llu base=%d program=%u fbo=%d vao=%d indexbuffer=%d\n",
         draws,kind,mode,count,type,(unsigned long long)(uintptr_t)indices,base,program,value(GL_DRAW_FRAMEBUFFER_BINDING),value(GL_VERTEX_ARRAY_BINDING),value(GL_ELEMENT_ARRAY_BUFFER_BINDING));
    note("  vp=%d,%d,%d,%d depth=%u/%x write=%d cull=%u/%x front=%x blend=%u rgb=%x/%x equation=%x color=%u%u%u%u stencil=%u scissor=%u\n",
         vp[0],vp[1],vp[2],vp[3],glIsEnabled(GL_DEPTH_TEST),value(GL_DEPTH_FUNC),value(GL_DEPTH_WRITEMASK),glIsEnabled(GL_CULL_FACE),value(GL_CULL_FACE_MODE),value(GL_FRONT_FACE),glIsEnabled(GL_BLEND),value(GL_BLEND_SRC_RGB),value(GL_BLEND_DST_RGB),value(GL_BLEND_EQUATION_RGB),mask[0],mask[1],mask[2],mask[3],glIsEnabled(GL_STENCIL_TEST),glIsEnabled(GL_SCISSOR_TEST));
    GLint scissor[4];GLfloat depth_range[2],offset_factor=0,offset_units=0;
    glGetIntegerv(GL_SCISSOR_BOX,scissor);glGetFloatv(GL_DEPTH_RANGE,depth_range);
    glGetFloatv(GL_POLYGON_OFFSET_FACTOR,&offset_factor);glGetFloatv(GL_POLYGON_OFFSET_UNITS,&offset_units);
    note("  TESTS scissor=%d,%d,%d,%d depth_range=%g,%g stencil_func=%x ref=%d mask=%x write=%x ops=%x/%x/%x offset=%u,%g,%g detail=%d\n",
        scissor[0],scissor[1],scissor[2],scissor[3],depth_range[0],depth_range[1],
        value(GL_STENCIL_FUNC),value(GL_STENCIL_REF),value(GL_STENCIL_VALUE_MASK),value(GL_STENCIL_WRITEMASK),
        value(GL_STENCIL_FAIL),value(GL_STENCIL_PASS_DEPTH_FAIL),value(GL_STENCIL_PASS_DEPTH_PASS),
        glIsEnabled(GL_POLYGON_OFFSET_FILL),offset_factor,offset_units,detailed_draw);
    for(GLuint a=0;a<1;a++) {
        GLint enabled=0;glGetVertexAttribiv(a,GL_VERTEX_ATTRIB_ARRAY_ENABLED,&enabled);if(!enabled)continue;
        GLint buffer=0,size=0,stride=0,format=0;uint64_t offset=0;
        attribute_layout(a,&buffer,&size,&stride,&format,&offset);
        note("  ATTR %u buffer=%d size=%d stride=%d type=0x%x offset=%llu\n",a,buffer,size,stride,format,(unsigned long long)offset);
    }
    if (detailed_draw) geometry(count,type,indices,base);
    program_details(program);texture_details();errors("diagnostic-state");return 1;
}
static void (*real_clear)(GLbitfield);
static void (*real_blit)(GLint,GLint,GLint,GLint,GLint,GLint,GLint,GLint,GLbitfield,GLenum);
static void clear_frame(GLbitfield mask) {
    if(atomic_load(&state)==2)note("CLEAR fbo=%d mask=0x%x\n",value(GL_DRAW_FRAMEBUFFER_BINDING),mask);
    real_clear(mask);
}
static void blit_frame(GLint x0,GLint y0,GLint x1,GLint y1,GLint a0,GLint b0,GLint a1,GLint b1,GLbitfield mask,GLenum filter) {
    if(atomic_load(&state)==2)note("BLIT read=%d draw=%d src=%d,%d,%d,%d dst=%d,%d,%d,%d mask=%x filter=%x\n",value(GL_READ_FRAMEBUFFER_BINDING),value(GL_DRAW_FRAMEBUFFER_BINDING),x0,y0,x1,y1,a0,b0,a1,b1,mask,filter);
    real_blit(x0,y0,x1,y1,a0,b0,a1,b1,mask,filter);
}
static void (*real_arrays)(GLenum,GLint,GLsizei);
static void (*real_elements)(GLenum,GLsizei,GLenum,const void *);
static void (*real_base)(GLenum,GLsizei,GLenum,const void *,GLint);
static void arrays(GLenum m,GLint first,GLsizei count)
{int cap=before_draw("arrays",m,count,0,NULL,first);real_arrays(m,first,count);if(cap){errors("draw-arrays");}}
static void elements(GLenum m,GLsizei count,GLenum type,const void *p)
{int cap=before_draw("elements",m,count,type,p,0);real_elements(m,count,type,p);if(cap){errors("draw-elements");}}
static void base_elements(GLenum m,GLsizei count,GLenum type,const void *p,GLint base)
{int cap=before_draw("base-elements",m,count,type,p,base);real_base(m,count,type,p,base);if(cap){errors("draw-base-elements");}}
void *host_gfx_wrap(const char *name,void *function)
{
    if(!function)return NULL;
    if(!strcmp(name,"glBufferData")){real_buffer_data=function;return buffer_data;}
    if(!strcmp(name,"glBufferSubData")){real_buffer_sub_data=function;return buffer_sub_data;}
    if(!strcmp(name,"glDeleteBuffers")){real_delete_buffers=function;return delete_buffers;}
    if(!strcmp(name,"glClear")){real_clear=function;return clear_frame;}
    if(!strcmp(name,"glBlitFramebuffer")){real_blit=function;return blit_frame;}
    if(!strcmp(name,"glDrawArrays")){real_arrays=function;return arrays;}
    if(!strcmp(name,"glDrawElements")){real_elements=function;return elements;}
    if(!strcmp(name,"glDrawElementsBaseVertex")){real_base=function;return base_elements;}
    return function;
}
void host_gfx_swap(int width,int height)
{
    if(atomic_load(&state)==2) {
        /* Read final output before SDL swaps it away. Reserve screenshot
         * space independently of texture budget. */
        image_bytes=0;save_image("frame.ppm",0,width,height);
        errors("diagnostic-end");
        if(read_fbo){glDeleteFramebuffers(1,&read_fbo);read_fbo=0;}
        note("END draws=%u programs=%u textures=%u draw_limit=%d report_limit=%ld\n",draws,program_count,texture_count,MAX_DRAWS,REPORT_BUDGET);
        fprintf(report,"CAPTURE_STATUS detail_timed_out=%d detailed_draws=%u draw_limit_hit=%d report_limit_hit=%d\n",timed_out,detailed_draws,draws>MAX_DRAWS,ftell(report)>REPORT_BUDGET);
        if(fflush(report))report_failed=1;
        if(fclose(report))report_failed=1;
        report=NULL;
        host_logf(HOST_LOG_INFO,"GFX capture %s: %s; %u draws",report_failed?"incomplete":"finished",directory,draws);
        atomic_store(&state,report_failed?-1:3);
        return;
    }
    if(atomic_load(&state)!=1)return;
    char path[1200];snprintf(path,sizeof(path),"%s/report.txt",directory);
    report=fopen(path,"w");
    if(!report){atomic_store(&state,-1);return;}
    draws=program_count=texture_count=image_bytes=geometry_bytes=0;report_bytes=0;report_failed=timed_out=0;detailed_draws=0;detailed_draw=0;
    clock_gettime(CLOCK_MONOTONIC,&started);
    note("Halo GFX Patch23 Android/AAOS: CPU/GPU mirror comparison\nGL_VENDOR=%s\nGL_RENDERER=%s\nGL_VERSION=%s\nGLSL=%s\nSurface=%dx%d guest=%08x-%08x\n",
         glGetString(GL_VENDOR),glGetString(GL_RENDERER),glGetString(GL_VERSION),glGetString(GL_SHADING_LANGUAGE_VERSION),width,height,host_image.base,host_image.end);
    note("No per-draw pixel reads or texture images: use Patch15 images as reference.\nAll draws get a brief trace; triangle draws get position/index bytes and selected uniforms until the detail budget.\nTriangle topology is a selection heuristic, not a material classification. No CPU visibility/material-name trace.\n");
    note("UPLOAD_UNMAP_FAILURES lifetime=%u\n",upload_unmap_failures);
    note("CPU_READ_METHOD=anonymous-pipe\nMIRROR_UPLOAD_POLICY=ordered-buffer-sub-data\nFRAME_POLICY=original-30fps-no-interpolation\nCPU comparison is a live observation, not an atomic snapshot. Equal generations do not exclude a concurrent write to an already writable page.\n");
    errors("pending-before-capture");
    atomic_store(&state,2);
}
