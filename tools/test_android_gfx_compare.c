#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <EGL/egl.h>
#include <assert.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include "../port/android/host/host_gfx.c"
#include "../port/android/host/host_gl.c"
struct host_guest_image host_image;
uint32_t host_memory_window_base(void){return 0x50000000;}
uint32_t host_memory_watch_generation(uint32_t a,uint32_t n){(void)a;(void)n;return 42;}
void host_logf(int priority,const char *format,...) {(void)priority;(void)format;}
static GLuint shader(GLenum type,const char *src) {
 GLuint s=glCreateShader(type);glShaderSource(s,1,&src,NULL);glCompileShader(s);GLint good=0;glGetShaderiv(s,GL_COMPILE_STATUS,&good);assert(good);return s;
}
int main(void) {
 EGLDisplay d=eglGetPlatformDisplay(0x31DD,EGL_DEFAULT_DISPLAY,NULL);EGLint major,minor;
 assert(eglInitialize(d,&major,&minor));assert(eglBindAPI(EGL_OPENGL_ES_API));
 EGLint attr[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};
 EGLConfig cfg;EGLint count;assert(eglChooseConfig(d,attr,&cfg,1,&count)&&count);
 EGLint dims[]={EGL_WIDTH,64,EGL_HEIGHT,64,EGL_NONE};EGLSurface surface=eglCreatePbufferSurface(d,cfg,dims);
 EGLint version[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_NONE};EGLContext ctx=eglCreateContext(d,cfg,EGL_NO_CONTEXT,version);
 assert(eglMakeCurrent(d,surface,surface,ctx));printf("%s\n",glGetString(GL_VERSION));
 GLuint vs=shader(GL_VERTEX_SHADER,"#version 300 es\nlayout(location=0) in vec2 pos;uniform vec2 offset;void main(){gl_Position=vec4(pos+offset,0,1);}");
 GLuint fs=shader(GL_FRAGMENT_SHADER,"#version 300 es\nprecision highp float;uniform sampler2D tex0;uniform vec4 gain;out vec4 color;void main(){color=texture(tex0,vec2(0.5))*gain;}");
 GLuint prog=glCreateProgram();glAttachShader(prog,vs);glAttachShader(prog,fs);glLinkProgram(prog);GLint linked;glGetProgramiv(prog,GL_LINK_STATUS,&linked);assert(linked);glUseProgram(prog);
 glUniform1i(glGetUniformLocation(prog,"tex0"),0);glUniform4f(glGetUniformLocation(prog,"gain"),1,1,1,1);glUniform2f(glGetUniformLocation(prog,"offset"),0,0);
 GLuint tex;glGenTextures(1,&tex);glBindTexture(GL_TEXTURE_2D,tex);unsigned char pixels[]={255,0,0,128};glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,1,1,0,GL_RGBA,GL_UNSIGNED_BYTE,pixels);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
 GLuint vao,buffer;glGenVertexArrays(1,&vao);glBindVertexArray(vao);glGenBuffers(1,&buffer);glBindBuffer(GL_ARRAY_BUFFER,buffer);
 float vertices[]={-1,-1,3,-1,-1,3};glBufferData(GL_ARRAY_BUFFER,sizeof(vertices),vertices,GL_STATIC_DRAW);glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,0);glEnableVertexAttribArray(0);
 GLuint ib;glGenBuffers(1,&ib);glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,ib);unsigned short indices[]={0,1,2};glBufferData(GL_ELEMENT_ARRAY_BUFFER,sizeof(indices),indices,GL_STATIC_DRAW);
 glBindBuffer(GL_COPY_READ_BUFFER,buffer);

 /* Reuse the same buffers over 32 updates, checking actual raster output. */
 glViewport(0,0,64,64);
 for(unsigned step=0;step<32;step++) {
  float collapsed[6]={0};
  host_gl_wait_frame(step%8);
  host_gl_buffer_write(GL_ARRAY_BUFFER,0,sizeof(vertices),step%2?collapsed:vertices);
  host_gl_buffer_write(GL_ELEMENT_ARRAY_BUFFER,0,sizeof(indices),indices);
  glClearColor(0,0,0,1);glClear(GL_COLOR_BUFFER_BIT);
  glDrawElements(GL_TRIANGLES,3,GL_UNSIGNED_SHORT,0);
  host_gl_fence_frame(step%8);
  unsigned char pixel[4];glReadPixels(32,32,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel);
  assert(pixel[0]==(step%2?0:255));assert(glGetError()==GL_NO_ERROR);
 }
 for(unsigned slot=0;slot<8;slot++)host_gl_wait_frame(slot);
 host_gl_buffer_write(GL_ARRAY_BUFFER,0,sizeof(vertices),vertices);
 puts("PASS: 32 synchronized vertex/index updates and frame-slot reuse, pixels verified.");

 unsigned char *cpu=mmap((void*)0x50000000,0x400000,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);assert(cpu==(void*)0x50000000);
 memset(cpu,0x5a,8192);
 GLuint mirrored;glGenBuffers(1,&mirrored);glBindBuffer(GL_COPY_WRITE_BUFFER,mirrored);
 void (*allocate)(GLenum,GLsizeiptr,const void*,GLenum)=host_gfx_wrap("glBufferData",glBufferData);
 void (*update)(GLenum,GLintptr,GLsizeiptr,const void*)=host_gfx_wrap("glBufferSubData",glBufferSubData);
 allocate(GL_COPY_WRITE_BUFFER,0x400000,NULL,GL_DYNAMIC_DRAW);
 host_gl_buffer_write(GL_COPY_WRITE_BUFFER,0,4096,cpu);
 update(GL_COPY_WRITE_BUFFER,4096,4096,cpu+4096);
 assert(source_find(mirrored) && source_find(mirrored)->uploaded[1]);
 snprintf(directory,sizeof(directory),"/tmp/halo-gfx21-compare");mkdir(directory,0700);
 report=fopen("/tmp/halo-gfx21-compare/report.txt","w");assert(report);
 free(buffer_range(mirrored,0,8192,"equal.bin"));
 unsigned char zeros[4096]={0};glBufferSubData(GL_COPY_WRITE_BUFFER,4096,4096,zeros);
 free(buffer_range(mirrored,0,8192,"different.bin"));
 assert(value(GL_COPY_READ_BUFFER_BINDING)==(GLint)buffer);

 /* Exercise incremental mirror updates while draws using earlier ranges
  * are queued. Verify the entire initialized region, not just new bytes. */
 unsigned char expected[32*4096];memset(expected,0x35,sizeof(expected));
 memcpy(expected,vertices,sizeof(vertices));memcpy(cpu,expected,sizeof(expected));
 host_gl_buffer_write(GL_COPY_WRITE_BUFFER,0,sizeof(expected),cpu);
 glBindBuffer(GL_ARRAY_BUFFER,mirrored);
 glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,0);
 for(unsigned page=1;page<32;page++) {
     glDrawArrays(GL_TRIANGLES,0,3);
     memset(expected+page*4096,(int)(0x40+page),4096);
     memcpy(cpu+page*4096,expected+page*4096,4096);
     host_gl_buffer_write(GL_COPY_WRITE_BUFFER,page*4096,4096,cpu+page*4096);
 }
 for(unsigned page=1;page<32;page++) {
     glDrawArrays(GL_TRIANGLES,0,3);
     memset(expected+page*4096+128,(int)(0x70+page),511);
     memcpy(cpu+page*4096+128,expected+page*4096+128,511);
     host_gl_buffer_write(GL_COPY_WRITE_BUFFER,page*4096+128,511,cpu+page*4096+128);
 }
 glBindBuffer(GL_COPY_READ_BUFFER,mirrored);
 const void *observed=glMapBufferRange(GL_COPY_READ_BUFFER,0,sizeof(expected),GL_MAP_READ_BIT);
 assert(observed && !memcmp(observed,expected,sizeof(expected)));
 assert(glUnmapBuffer(GL_COPY_READ_BUFFER));
 unsigned char mirror_pixel[4];glReadPixels(32,32,1,1,GL_RGBA,GL_UNSIGNED_BYTE,mirror_pixel);
 assert(mirror_pixel[0]==255);assert(glGetError()==GL_NO_ERROR);
 glBindBuffer(GL_COPY_READ_BUFFER,buffer);glBindBuffer(GL_ARRAY_BUFFER,buffer);
 glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,0);
 puts("PASS: 62 ordered mirror updates with queued draws; 128 KiB preserved byte-for-byte and rendered pixel correct.");
 assert(munmap(cpu,0x400000)==0);
 free(buffer_range(mirrored,0,8192,"unmapped.bin"));
 fclose(report);report=NULL;
 allocate(GL_COPY_WRITE_BUFFER,0x400000,NULL,GL_DYNAMIC_DRAW);assert(!source_find(mirrored));
 assert(glGetError()==GL_NO_ERROR);
 puts("PASS: mirror uploads, CPU/GPU match, mismatch, inaccessible CPU memory, storage replacement.");
 GLuint saved_fbo;glGenFramebuffers(1,&saved_fbo);glBindFramebuffer(GL_READ_FRAMEBUFFER,saved_fbo);glReadBuffer(GL_NONE);
 GLuint pbo;glGenBuffers(1,&pbo);glBindBuffer(GL_PIXEL_PACK_BUFFER,pbo);glBufferData(GL_PIXEL_PACK_BUFFER,256,NULL,GL_STREAM_READ);
 glPixelStorei(GL_PACK_ALIGNMENT,8);glPixelStorei(GL_PACK_ROW_LENGTH,8);glPixelStorei(GL_PACK_SKIP_ROWS,2);glPixelStorei(GL_PACK_SKIP_PIXELS,1);
 glActiveTexture(GL_TEXTURE2);glViewport(0,0,64,64);assert(glGetError()==GL_NO_ERROR);
 void (*draw)(GLenum,GLint,GLsizei)=host_gfx_wrap("glDrawArrays",glDrawArrays);
 void (*indexed)(GLenum,GLsizei,GLenum,const void*)=host_gfx_wrap("glDrawElements",glDrawElements);
 void (*base_draw)(GLenum,GLsizei,GLenum,const void*,GLint)=host_gfx_wrap("glDrawElementsBaseVertex",glDrawElementsBaseVertex);
 void (*clear)(GLbitfield)=host_gfx_wrap("glClear",glClear);
 for(int i=0;i<3;i++) {
  snprintf(directory,sizeof(directory),"/tmp/halo-gfx21-smoke-%d",i);mkdir(directory,0700);
  atomic_store(&state,1);host_gfx_swap(64,64);assert(atomic_load(&state)==2);if(i==2)started.tv_sec-=13;
  glClearColor(0,0,0,1);clear(GL_COLOR_BUFFER_BIT);draw(GL_TRIANGLES,0,3);indexed(GL_TRIANGLES,3,GL_UNSIGNED_SHORT,0);base_draw(GL_TRIANGLES,3,GL_UNSIGNED_SHORT,0,0);
  assert(value(GL_READ_FRAMEBUFFER_BINDING)==(GLint)saved_fbo);assert(value(GL_READ_BUFFER)==GL_NONE);
  assert(value(GL_DRAW_FRAMEBUFFER_BINDING)==0);assert(value(GL_PIXEL_PACK_BUFFER_BINDING)==(GLint)pbo);
  assert(value(GL_PACK_ALIGNMENT)==8);assert(value(GL_PACK_ROW_LENGTH)==8);assert(value(GL_PACK_SKIP_ROWS)==2);assert(value(GL_PACK_SKIP_PIXELS)==1);
  assert(value(GL_COPY_READ_BUFFER_BINDING)==(GLint)buffer);assert(value(GL_ELEMENT_ARRAY_BUFFER_BINDING)==(GLint)ib);
  assert(value(GL_ACTIVE_TEXTURE)==GL_TEXTURE2);assert(value(GL_CURRENT_PROGRAM)==(GLint)prog);
  assert(value(GL_VERTEX_ARRAY_BINDING)==(GLint)vao);assert(glGetError()==GL_NO_ERROR);
  host_gfx_swap(64,64);assert(atomic_load(&state)==3);
  assert(value(GL_READ_FRAMEBUFFER_BINDING)==(GLint)saved_fbo);assert(value(GL_READ_BUFFER)==GL_NONE);
  assert(value(GL_PIXEL_PACK_BUFFER_BINDING)==(GLint)pbo);assert(glGetError()==GL_NO_ERROR);
 }
 draw(GL_TRIANGLES,0,3);assert(glGetError()==GL_NO_ERROR);
 puts("PASS: three complete captures (including expired detail budget); idle draw; FBO/read buffer/pack/texture/program/VAO state restored.");return 0;
}
