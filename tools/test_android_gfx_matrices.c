/* Real surfaceless GLES capture regression, including unchanged raster output.
 * Run via tools/test_android_gfx_matrices.py with the NDK header directory. */
#define _GNU_SOURCE
#include <EGL/egl.h>
#include <assert.h>
#include <sys/stat.h>
#include "../port/android/host/host_gfx.c"

struct host_guest_image host_image;
uint32_t host_memory_window_base(void) { return 0x50000000; }
uint32_t host_memory_watch_generation(uint32_t address,uint32_t size) { (void)address;(void)size;return 1; }
void host_logf(int priority,const char *format,...) { (void)priority;(void)format; }
static GLuint compile(GLenum type,const char *source) {
 GLuint result=glCreateShader(type);glShaderSource(result,1,&source,NULL);glCompileShader(result);
 GLint good=0;glGetShaderiv(result,GL_COMPILE_STATUS,&good);
 if(!good){char log[2048];glGetShaderInfoLog(result,sizeof(log),NULL,log);fputs(log,stderr);} assert(good);return result;
}
int main(int argc,char **argv) {
 assert(argc==2);
 EGLDisplay display=eglGetPlatformDisplay(0x31DD,EGL_DEFAULT_DISPLAY,NULL);EGLint major,minor;
 assert(eglInitialize(display,&major,&minor));assert(eglBindAPI(EGL_OPENGL_ES_API));
 EGLint attributes[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT,
  EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};
 EGLConfig config;EGLint configs=0;assert(eglChooseConfig(display,attributes,&config,1,&configs)&&configs);
 EGLint dimensions[]={EGL_WIDTH,64,EGL_HEIGHT,64,EGL_NONE};
 EGLSurface surface=eglCreatePbufferSurface(display,config,dimensions);
 EGLint version[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_NONE};
 EGLContext context=eglCreateContext(display,config,EGL_NO_CONTEXT,version);
 assert(eglMakeCurrent(display,surface,surface,context));
 printf("GLES matrix diagnostic backend: %s / %s\n",glGetString(GL_VERSION),glGetString(GL_RENDERER));
 const char *vertex="#version 310 es\nprecision highp float;precision highp int;"
  "layout(location=0) in vec3 position;layout(location=1) in uint normal;"
  "layout(location=5) in vec2 weights;layout(location=6) in vec2 bones;"
  "uniform vec4 c[192];void main(){int a0=int(bones.x);vec4 m=c[clamp(a0 + 60,0,191)];"
  "gl_Position=vec4(position+vec3((m.x+float(normal&1u)+weights.x)*0.001,0,0),1);}";
 GLuint vs=compile(GL_VERTEX_SHADER,vertex);
 GLuint fs=compile(GL_FRAGMENT_SHADER,"#version 310 es\nprecision highp float;out vec4 color;void main(){color=vec4(1,0.5,0.25,1);}");
 GLuint program=glCreateProgram();glAttachShader(program,vs);glAttachShader(program,fs);glLinkProgram(program);
 GLint linked=0;glGetProgramiv(program,GL_LINK_STATUS,&linked);assert(linked);glUseProgram(program);
 GLuint vao,buffer,indices;glGenVertexArrays(1,&vao);glBindVertexArray(vao);glGenBuffers(1,&buffer);
 struct vertex { float position[3];uint32_t normal;float weights[2],bones[2]; } vertices[]={
  {{-0.8f,-0.8f,0},0xf0123457,{0.25f,0.75f},{0,1}},
  {{ 0.8f,-0.8f,0},0xf0123457,{0.25f,0.75f},{0,1}},
  {{ 0.0f, 0.8f,0},0xf0123457,{0.25f,0.75f},{0,1}},
 };
 glBindBuffer(GL_ARRAY_BUFFER,buffer);glBufferData(GL_ARRAY_BUFFER,sizeof(vertices),vertices,GL_STATIC_DRAW);
 glEnableVertexAttribArray(0);glVertexAttribPointer(0,3,GL_FLOAT,GL_FALSE,sizeof(vertices[0]),0);
 glEnableVertexAttribArray(1);glVertexAttribIPointer(1,1,GL_UNSIGNED_INT,sizeof(vertices[0]),(void *)12);
 glEnableVertexAttribArray(5);glVertexAttribPointer(5,2,GL_FLOAT,GL_FALSE,sizeof(vertices[0]),(void *)16);
 glEnableVertexAttribArray(6);glVertexAttribPointer(6,2,GL_FLOAT,GL_FALSE,sizeof(vertices[0]),(void *)24);
 unsigned short triangle[]={0,1,2};glGenBuffers(1,&indices);glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,indices);
 glBufferData(GL_ELEMENT_ARRAY_BUFFER,sizeof(triangle),triangle,GL_STATIC_DRAW);
 GLfloat constants[192][4];
 for(int i=0;i<192;i++)for(int j=0;j<4;j++)constants[i][j]=i*0.125f+j*0.25f;
 GLint base=glGetUniformLocation(program,"c[0]");assert(base>=0);
 void (*upload)(GLint,GLsizei,const GLfloat *)=host_gfx_wrap("glUniform4fv",glUniform4fv);
 void (*draw)(GLenum,GLsizei,GLenum,const void *)=host_gfx_wrap("glDrawElements",glDrawElements);
 glViewport(0,0,64,64);glClearColor(0,0,0,1);glClear(GL_COLOR_BUFFER_BIT);
 upload(base,192,&constants[0][0]);draw(GL_TRIANGLE_STRIP,3,GL_UNSIGNED_SHORT,0);
 unsigned char reference[4],observed[4];glReadPixels(32,32,1,1,GL_RGBA,GL_UNSIGNED_BYTE,reference);
 assert(reference[0]==255 && reference[1]>=127 && reference[2]>=63);
 assert(atomic_load(&state)==0 && uniform_uploads==0); /* no idle capture */
 assert(strlen(argv[1])<sizeof(directory));snprintf(directory,sizeof(directory),"%s",argv[1]);
 atomic_store(&state,1);host_gfx_swap(64,64);assert(atomic_load(&state)==2);
 /* Consume the entire generic detail allowance before the model: its
  * independent budget must still capture matrices and all model streams. */
 generic_details=MAX_GENERIC_DETAILS;
 upload(base,192,&constants[0][0]);
 GLfloat one[4]={9.5f,0.5f,0.25f,1};
 GLint node=glGetUniformLocation(program,"c[61]");assert(node>=0);upload(node,1,one);
 glClear(GL_COLOR_BUFFER_BIT);draw(GL_TRIANGLE_STRIP,3,GL_UNSIGNED_SHORT,0);
 glReadPixels(32,32,1,1,GL_RGBA,GL_UNSIGNED_BYTE,observed);assert(!memcmp(reference,observed,4));
 GLfloat actual_node[4];glGetUniformfv(program,node,actual_node);assert(!memcmp(one,actual_node,sizeof(one)));
 assert(value(GL_VERTEX_ARRAY_BINDING)==(GLint)vao && value(GL_ARRAY_BUFFER_BINDING)==(GLint)buffer);
 assert(value(GL_ELEMENT_ARRAY_BUFFER_BINDING)==(GLint)indices && glGetError()==GL_NO_ERROR);
 assert(model_details==1 && uniform_uploads==2);
 host_gfx_swap(64,64);assert(atomic_load(&state)==3);
 puts("PASS: actual GLES matrix/CPU-upload readback, triangle-strip model priority, all enabled streams and unchanged raster output.");
 return 0;
}
