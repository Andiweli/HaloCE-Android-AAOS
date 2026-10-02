/* Final game-image correction. Runs only on the rendering thread. */
#include "host.h"
#include <GLES3/gl3.h>
#include <EGL/egl.h>
extern void host_settings_display(float *brightness,float *gamma);

static GLuint program, vao;
static EGLContext context;
static int failed;
static GLuint shader(GLenum kind,const char *source) {
    GLuint s=glCreateShader(kind); GLint ok;
    glShaderSource(s,1,&source,NULL); glCompileShader(s); glGetShaderiv(s,GL_COMPILE_STATUS,&ok);
    if(!ok) {glDeleteShader(s);return 0;} return s;
}
int host_settings_present(unsigned int texture,int width,int height) {
    float brightness,gamma; host_settings_display(&brightness,&gamma);
    if(brightness==0.0f && gamma==1.0f) return 0; /* original path at defaults */
    if(context!=eglGetCurrentContext()) {context=eglGetCurrentContext();program=vao=0;failed=0;}
    if(failed) return 0;
    if(!program) {
        const char *vs="#version 300 es\nprecision highp float;out vec2 uv;void main(){vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));uv=vec2(p.x,1.0-p.y);gl_Position=vec4(p*2.0-1.0,0,1);}";
        const char *fs="#version 300 es\nprecision highp float;in vec2 uv;uniform sampler2D frame;uniform vec2 correction;out vec4 color;void main(){vec3 c=clamp(texture(frame,uv).rgb+correction.x,0.0,1.0);color=vec4(pow(c,vec3(1.0/correction.y)),1.0);}";
        GLuint v=shader(GL_VERTEX_SHADER,vs),f=shader(GL_FRAGMENT_SHADER,fs);GLint ok=0;
        if(v&&f) {program=glCreateProgram();glAttachShader(program,v);glAttachShader(program,f);glLinkProgram(program);glGetProgramiv(program,GL_LINK_STATUS,&ok);}
        if(v)glDeleteShader(v);if(f)glDeleteShader(f);
        if(!ok) {if(program)glDeleteProgram(program);program=0;failed=1;host_logf(HOST_LOG_ERROR,"Settings display shader failed; using original presentation");return 0;}
        glGenVertexArrays(1,&vao);
    }
    GLint old_program,old_vao,viewport[4],active,tex,sampler;
    const GLenum caps[]={GL_BLEND,GL_DEPTH_TEST,GL_STENCIL_TEST,GL_CULL_FACE,GL_RASTERIZER_DISCARD};
    GLboolean enabled[5];
    glGetIntegerv(GL_CURRENT_PROGRAM,&old_program);glGetIntegerv(GL_VERTEX_ARRAY_BINDING,&old_vao);
    glGetIntegerv(GL_VIEWPORT,viewport);glGetIntegerv(GL_ACTIVE_TEXTURE,&active);
    glActiveTexture(GL_TEXTURE0);glGetIntegerv(GL_TEXTURE_BINDING_2D,&tex);glGetIntegerv(GL_SAMPLER_BINDING,&sampler);
    for(int i=0;i<5;i++){enabled[i]=glIsEnabled(caps[i]);glDisable(caps[i]);}
    glUseProgram(program);glBindVertexArray(vao);glViewport(0,0,width,height);
    glBindTexture(GL_TEXTURE_2D,texture);glBindSampler(0,0);
    glUniform1i(glGetUniformLocation(program,"frame"),0);
    glUniform2f(glGetUniformLocation(program,"correction"),brightness,gamma);
    glDrawArrays(GL_TRIANGLES,0,3);
    glBindTexture(GL_TEXTURE_2D,tex);glBindSampler(0,sampler);glActiveTexture(active);
    glUseProgram(old_program);glBindVertexArray(old_vao);glViewport(viewport[0],viewport[1],viewport[2],viewport[3]);
    for(int i=0;i<5;i++)if(enabled[i])glEnable(caps[i]);
    return 1;
}
