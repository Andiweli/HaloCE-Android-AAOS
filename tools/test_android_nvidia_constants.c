/* Real GLES selector regression. Run through test_android_nvidia_constants.py. */
#include <EGL/egl.h>
#include <GLES3/gl32.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

static GLuint compile(GLenum kind, const char *a, const char *b, const char *c) {
    GLuint shader=glCreateShader(kind);const char *parts[]={a,b,c};
    glShaderSource(shader,3,parts,NULL);glCompileShader(shader);
    GLint good=0;glGetShaderiv(shader,GL_COMPILE_STATUS,&good);
    if(!good){char log[4096];glGetShaderInfoLog(shader,sizeof(log),NULL,log);fputs(log,stderr);}assert(good);return shader;
}
int main(int argc, char **argv) {
    assert(argc==2);FILE *file=fopen(argv[1],"rb");assert(file);
    assert(!fseek(file,0,SEEK_END));long bytes=ftell(file);assert(bytes>0&&bytes<65536);rewind(file);
    char *helper=calloc((size_t)bytes+1,1);assert(helper);assert(fread(helper,1,bytes,file)==(size_t)bytes);fclose(file);
    EGLDisplay display=eglGetPlatformDisplay(0x31DD,EGL_DEFAULT_DISPLAY,NULL);EGLint major,minor;
    assert(eglInitialize(display,&major,&minor)&&eglBindAPI(EGL_OPENGL_ES_API));
    EGLint attributes[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT,
        EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_NONE};EGLConfig config;EGLint count=0;
    assert(eglChooseConfig(display,attributes,&config,1,&count)&&count);
    EGLint dimensions[]={EGL_WIDTH,16,EGL_HEIGHT,16,EGL_NONE};EGLSurface surface=eglCreatePbufferSurface(display,config,dimensions);
    EGLint version[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_NONE};EGLContext context=eglCreateContext(display,config,EGL_NO_CONTEXT,version);
    assert(eglMakeCurrent(display,surface,surface,context));printf("Selector GLES backend: %s / %s\n",glGetString(GL_VERSION),glGetString(GL_RENDERER));
    GLint inputs[390];unsigned n=0;
    for(int i=-64;i<320;i++)inputs[n++]=i;
    inputs[n++]=INT_MIN;inputs[n++]=INT_MAX;
    GLfloat constants[192][4];for(unsigned i=0;i<192;i++)for(unsigned j=0;j<4;j++)constants[i][j]=i*0.125f+j*0.25f;
    for(int language=300;language<=310;language+=10) {
        char prologue[256];snprintf(prologue,sizeof(prologue),"#version %d es\nprecision highp float;precision highp int;uniform vec4 c[192];\n",language);
        GLuint vertex=compile(GL_VERTEX_SHADER,prologue,helper,"layout(location=0) in int index;out vec4 selected;void main(){selected=halo_nvidia_constant(index);gl_Position=vec4(0,0,0,1);}");
        snprintf(prologue,sizeof(prologue),"#version %d es\nprecision highp float;",language);
        GLuint fragment=compile(GL_FRAGMENT_SHADER,prologue,"","out vec4 color;void main(){color=vec4(1);}");
        GLuint program=glCreateProgram();glAttachShader(program,vertex);glAttachShader(program,fragment);
        const char *varying="selected";glTransformFeedbackVaryings(program,1,&varying,GL_INTERLEAVED_ATTRIBS);glLinkProgram(program);
        GLint linked=0;glGetProgramiv(program,GL_LINK_STATUS,&linked);assert(linked);glUseProgram(program);
        glUniform4fv(glGetUniformLocation(program,"c[0]"),192,&constants[0][0]);
        for(unsigned i=0;i<192;i++) {
            char name[16];snprintf(name,sizeof(name),"c[%u]",i);GLfloat value[4];
            GLint location=glGetUniformLocation(program,name);assert(location>=0);
            glGetUniformfv(program,location,value);assert(!memcmp(value,constants[i],sizeof(value)));
        }
        GLuint vao,input,output;glGenVertexArrays(1,&vao);glBindVertexArray(vao);
        glGenBuffers(1,&input);glBindBuffer(GL_ARRAY_BUFFER,input);glBufferData(GL_ARRAY_BUFFER,n*sizeof(inputs[0]),inputs,GL_STATIC_DRAW);
        glEnableVertexAttribArray(0);glVertexAttribIPointer(0,1,GL_INT,0,0);
        glGenBuffers(1,&output);glBindBuffer(GL_TRANSFORM_FEEDBACK_BUFFER,output);glBufferData(GL_TRANSFORM_FEEDBACK_BUFFER,n*4*sizeof(GLfloat),NULL,GL_STREAM_READ);
        glBindBufferBase(GL_TRANSFORM_FEEDBACK_BUFFER,0,output);glEnable(GL_RASTERIZER_DISCARD);
        glBeginTransformFeedback(GL_POINTS);glDrawArrays(GL_POINTS,0,n);glEndTransformFeedback();glDisable(GL_RASTERIZER_DISCARD);
        const GLfloat *values=glMapBufferRange(GL_TRANSFORM_FEEDBACK_BUFFER,0,n*4*sizeof(GLfloat),GL_MAP_READ_BIT);assert(values);
        for(unsigned i=0;i<n;i++){
            int slot=inputs[i]<0?0:inputs[i]>191?191:inputs[i];
            if(memcmp(values+i*4,constants[slot],4*sizeof(GLfloat)))
                fprintf(stderr,"GLSL %d index %d slot %d: expected %g,%g,%g,%g; observed %g,%g,%g,%g; error=%x\n",language,inputs[i],slot,
                    constants[slot][0],constants[slot][1],constants[slot][2],constants[slot][3],values[i*4],values[i*4+1],values[i*4+2],values[i*4+3],glGetError());
            assert(!memcmp(values+i*4,constants[slot],4*sizeof(GLfloat)));
        }
        assert(glUnmapBuffer(GL_TRANSFORM_FEEDBACK_BUFFER));assert(glGetError()==GL_NO_ERROR);
        printf("PASS: GLSL %d selector, %u index/clamp cases, exact GPU vec4 values.\n",language,n);
        glDeleteProgram(program);glDeleteShader(vertex);glDeleteShader(fragment);glDeleteVertexArrays(1,&vao);glDeleteBuffers(1,&input);glDeleteBuffers(1,&output);
    }
    free(helper);return 0;
}
