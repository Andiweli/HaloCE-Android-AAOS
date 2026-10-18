"""Exercise actual CPU skeletal stream setup and switching to ordinary draws.

Strict recorded GL state, production attribute decoder and NV2A executor.
Covers draw offsets, multiple streams, stride zero, current attributes,
changed constants, immediate inputs, and oversized draws. No game assets.
Attributes the program never writes are constant values (Shield performance
test v1); tools/test_android_cpu_parallel.py covers the worker threads.
"""
from pathlib import Path
import contextlib, io, os, re, runpy, shutil, subprocess, tempfile
from test_upstream_optimizations import function

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT/'port/linux/src/d3d8_gl.c').read_text()
with contextlib.redirect_stdout(io.StringIO()):
    existing = runpy.run_path(str(ROOT/'tools/test_android_nvidia_vertices.py'))
prefix = re.sub(r'enum \{ .*? \};\n', '', existing['prefix'], count=1)
prefix = '#include "xgpu.h"\n#include "halo_android_perf.h"\n#include <math.h>\n#include <time.h>\n#include <pthread.h>\n#include <unistd.h>\n' + prefix
# the attributes' current values, which unwritten CPU outputs read
prefix = prefix.replace('static void glVertexAttrib4fv(GLuint i, const float *v) { (void)i; (void)v; }',
    'static float current_values[16][4];\nstatic void glVertexAttrib4fv(GLuint i, const float *v) { memcpy(current_values[i], v, 16); }')
assert 'current_values' in prefix
prefix = prefix.replace('float attributes[16][4];', 'float attributes[16][4]; float constants[192][4];')
prefix = prefix.replace('struct vertex_shader_object { unsigned long element_count, packed_mask; struct vertex_element elements[16]; };',
    'struct vertex_shader_object { unsigned long element_count,packed_mask; struct vertex_element elements[16]; '
    'unsigned long id,instruction_count; DWORD *instructions; GLuint shader[2]; BOOL cpu_checked; struct nv2a_cpu_program *cpu_program; '
    'GLuint block_shader[2]; BOOL block_attempted[2]; };')
prefix += r'''
#define STREAM_BUFFER_SIZE 4096
static struct nv2a_cpu_program *android_active_cpu_program;
static BOOL android_cpu_skeletal_vertices;
static GLuint android_cpu_vertex_shader;
static BOOL android_cpu_vertex_shader_attempted;
static double android_cpu_frame_ms;
static double android_cpu_frame_parts[3];
static unsigned long android_cpu_frame_fixed_vertices;
static unsigned long android_cpu_frame_vertices, android_cpu_frame_draws;
static unsigned int android_perf_settings;
static BOOL android_full_constants_draw;
static struct { float viewport_scale[4],viewport_offset[4],screen_offset,point_size; } draw_uniforms;
static unsigned rejected;
static void platform_log(const char *format,...){(void)format;rejected++;}
static unsigned long stream_upload(const void *data,unsigned long size){
 return stream_upload_swizzled(NULL,0,data,size,0);
}
struct xgpu_capabilities xgpu_capabilities={"300 es"};
#include <stdarg.h>
void xgpu_text_append(struct xgpu_text *t,const char *f,...){
 va_list a,b;va_start(a,f);va_copy(b,a);int n=vsnprintf(NULL,0,f,a);va_end(a);
 if(t->length+n+1>t->capacity){t->capacity=(t->length+n+1)*2;t->buffer=realloc(t->buffer,t->capacity);}
 vsnprintf(t->buffer+t->length,t->capacity-t->length,f,b);va_end(b);t->length+=n;
}
#define GL_VERTEX_SHADER 5
static struct { const char *dump_shaders; } debug_settings;
static unsigned cpu_compiles,gpu_compiles;
static BOOL fail_cpu_compile;
static char last_source[65536];
static GLuint compile_shader(GLenum type,const char *text,const char *label){
 static GLuint id=100;(void)label;assert(type==GL_VERTEX_SHADER);
 snprintf(last_source,sizeof(last_source),"%s",text);
 if(strstr(text,"NVIDIA CPU skeletal vertex path")){cpu_compiles++;if(fail_cpu_compile)return 0;}else gpu_compiles++;
 return ++id;
}
char *nv2a_vertex_shader_to_glsl(const DWORD *,unsigned long,unsigned long);
'''
start = source.index('/* ---------- NVIDIA CPU skeletal vertices')
cpu = source[start:source.index('static GLenum primitive_mode')].rstrip()
assert cpu.endswith('#endif')
production = existing['production'] + '\n' + function(source,'android_skinning_mode') + '\n' + cpu[:-len('#endif')]
production += '\n' + function(source,'vertex_type_bytes') + '\n' + function(source,'android_constant_block_shader')
production += '\n' + function(source,'vertex_shader_get')
fixture = r'''
struct operand { unsigned mux,index,swizzle,negate; };
#define V(i,s) ((struct operand){2,i,s,0})
#define R(i,s) ((struct operand){1,i,s,0})
#define K(i,s) ((struct operand){3,i,s,0})
#define Z ((struct operand){0,0,0x1b,0})
static void operand(DWORD *w,unsigned which,struct operand o){
 if(o.mux==2)w[1]|=o.index<<9;
 if(o.mux==3)w[1]|=o.index<<13;
 unsigned reg=o.mux==1?o.index:0;
 if(which==0){w[1]|=o.swizzle | o.negate<<8;w[2]|=reg<<28 | o.mux<<26;}
 if(which==1){w[2]|=o.swizzle<<17 | o.negate<<25 | reg<<13 | o.mux<<11;}
 if(which==2){w[2]|=o.swizzle<<2 | o.negate<<10 | reg>>2;w[3]|=(reg&3)<<30 | o.mux<<28;}
}
static void emit(DWORD *w,unsigned op,struct operand a,struct operand b,struct operand c,
 unsigned temporary,unsigned mask,unsigned out,unsigned omask,unsigned relative){
 memset(w,0,16);w[1]=op<<21;w[3]=temporary<<20 | mask<<24 | omask<<12 | (omask?1U<<11:0) | out<<3 | relative<<1;
 operand(w,0,a);operand(w,1,b);operand(w,2,c);
}
static struct nv2a_cpu_program *program(void){
 DWORD w[17][4];
 emit(w[0],2,V(5,0x1b),K(7,0xff),Z,0,12,0,0,0);
 emit(w[1],13,R(0,0),Z,Z,15,0,0,0,0); // Unused temporary field is not a register write.
 for(unsigned k=0;k<3;k++)emit(w[2+k],2,V(6,0),K(60+k,0x1b),Z,1+k,15,0,0,1);
 emit(w[5],13,R(0,0x55),Z,Z,0,0,0,0,0);
 emit(w[6],3,V(6,0xff),Z,(struct operand){2,6,0,1},4,8,0,0,0);
 for(unsigned k=0;k<3;k++)emit(w[7+k],4,R(4,0),K(60+k,0x1b),R(1+k,0x1b),1+k,15,0,0,1);
 for(unsigned k=0;k<3;k++)emit(w[10+k],6,V(0,0x1b),R(1+k,0x1b),Z,0,0,0,8>>k,0);
 emit(w[13],1,V(0,0xff),Z,Z,0,0,0,1,0);
 emit(w[14],1,V(9,0x1b),Z,Z,0,0,3,15,0);
 emit(w[15],1,V(1,0x1b),Z,Z,0,0,4,15,0);
 emit(w[16],1,V(4,0x1b),Z,Z,0,0,9,15,0);w[16][3]|=1;
 static DWORD saved[17][4];memcpy(saved,w,sizeof(w));
 // Keep a copy available for the actual production shader-routing test.
 extern DWORD *shader_words;shader_words=&saved[0][0];
 return nv2a_cpu_program_create(&w[0][0],17);
}
DWORD *shader_words;
static struct nv2a_cpu_vertex *output(unsigned vertex){
 static struct nv2a_cpu_vertex v;
 for(unsigned a=0;a<9;a++){
  if(actual.enabled[a])memcpy(v.value[a],gpu_bytes+actual.pointers[a].offset+vertex*actual.pointers[a].stride,16);
  else memcpy(v.value[a],current_values[a],16);
 }
 if(actual.enabled[9])memcpy(&v.fog,gpu_bytes+actual.pointers[9].offset+vertex*actual.pointers[9].stride,8);
 else memcpy(&v.fog,current_values[9],8);
 return &v;
}
static void near(float a,float b){assert(fabsf(a-b)<0.0001f);}
static void check(struct nv2a_cpu_vertex *v,const float *p,float weight,float tx,float ty,float tz){
 near(v->value[0][0],p[0]+weight*tx+(1-weight)*100.0f+0.5f);
 near(v->value[0][1],-(p[1]+weight*ty+(1-weight)*200.0f+0.5f));
 near(v->value[0][2],2*(p[2]+weight*tz+(1-weight)*300.0f)-1);
 near(v->value[0][3],1);near(v->fog,1);near(v->point_size,3);
 for(unsigned c=0;c<4;c++)near(v->value[1][c],device.attributes[9][c]);
 near(v->value[2][0],0);near(v->value[2][1],0);near(v->value[2][2],0);near(v->value[2][3],1);
 near(v->value[5][0],16384.0f/32767);near(v->value[5][1],-1);near(v->value[5][3],1);
}
int main(void){
 float p[6][3];struct { unsigned char indices[2];short weight; } bone[6];short uv[32]={16384,-32768};
 for(unsigned i=0;i<6;i++){p[i][0]=i+1;p[i][1]=i+2;p[i][2]=i+3;bone[i].indices[0]=0;bone[i].indices[1]=3;bone[i].weight=16384;}
 struct vertex_shader_object declaration={0};declaration.element_count=4;declaration.packed_mask=2;
 declaration.elements[0]=(struct vertex_element){0,0,D3DVSDT_FLOAT3,0};
 declaration.elements[1]=(struct vertex_element){1,5,D3DVSDT_PBYTE2,0};
 declaration.elements[2]=(struct vertex_element){1,6,D3DVSDT_NORMSHORT1,2};
 declaration.elements[3]=(struct vertex_element){2,4,D3DVSDT_NORMSHORT2,0};
 memset(&device,0,sizeof(device));memset(&actual,0,sizeof(actual));memset(&gl_state,255,sizeof(gl_state));
 device.vertex_shader=&declaration;device.stream_buffer=17;vertex_bindings_supported=FALSE;
 device.streams[0].data=(uintptr_t)p;device.streams[0].stride=12;
 device.streams[1].data=(uintptr_t)bone;device.streams[1].stride=4;
 device.streams[2].data=(uintptr_t)uv;device.streams[2].stride=0;
 for(unsigned i=0;i<16;i++)device.attributes[i][3]=1;
 device.attributes[9][0]=0.25f;device.attributes[9][1]=0.5f;device.attributes[9][2]=0.75f;
 device.attributes[1][0]=123;device.attributes[1][1]=456;device.attributes[1][2]=789;
 for(unsigned node=0;node<2;node++)for(unsigned k=0;k<3;k++){
  device.constants[60+node*3+k][k]=1;device.constants[60+node*3+k][3]=(node?100:10)*(k+1);
 }
 device.constants[7][3]=255;draw_uniforms.viewport_scale[0]=draw_uniforms.viewport_scale[1]=draw_uniforms.viewport_scale[2]=1;
 draw_uniforms.point_size=3;android_active_cpu_program=program();assert(android_active_cpu_program);
 float weight=16384.0f/32767;
 assert(android_cpu_setup_vertices(1,2,NULL));
 for(unsigned i=0;i<2;i++)check(output(i),p[1+i],weight,10,20,30);
 // Written: position, oD0, oD1, oT0. The rest, fog and point size are constants.
 for(unsigned a=0;a<10;a++)assert(actual.enabled[a]==(a==0 || a==1 || a==2 || a==5));
 for(unsigned a=0;a<10;a++)assert(!actual.enabled[a] || (!actual.pointers[a].integer && actual.pointers[a].stride==16));
 for(unsigned a=10;a<16;a++)assert(!actual.enabled[a]);
 device.constants[60][3]=20;device.attributes[9][0]=0.125f;
 assert(android_cpu_setup_vertices(2,2,NULL));
 for(unsigned i=0;i<2;i++)check(output(i),p[2+i],weight,20,20,30);
 // Switching through an ordinary GPU stream setup must clear CPU attributes.
 assert(android_cpu_setup_vertices(2,2,NULL));
 for(unsigned i=0;i<2;i++)check(output(i),p[2+i],weight,20,20,30);
 setup_streams(1,2);assert(actual.enabled[0] && actual.enabled[4] && actual.enabled[5] && actual.enabled[6]);
 assert(!actual.enabled[1] && !actual.enabled[2] && !actual.enabled[3] && !actual.enabled[7] && !actual.enabled[8] && !actual.enabled[9]);
 assert(android_cpu_setup_vertices(3,2,NULL));
 for(unsigned i=0;i<2;i++)check(output(i),p[3+i],weight,20,20,30);
 float immediate[2][16][4];
 for(unsigned i=0;i<2;i++){
  memcpy(immediate[i],device.attributes,sizeof(device.attributes));memcpy(immediate[i][0],p[i],12);
  immediate[i][1][0]=immediate[i][1][1]=immediate[i][1][2]=0;
  immediate[i][5][0]=0;immediate[i][5][1]=3.0f/255;immediate[i][6][0]=weight;
  immediate[i][4][0]=weight;immediate[i][4][1]=-1;
 }
 assert(android_cpu_setup_vertices(0,2,&immediate[0][0][0]));
 for(unsigned i=0;i<2;i++)check(output(i),p[i],weight,20,20,30);
 unsigned calls=upload_calls;assert(!android_cpu_setup_vertices(0,100000,NULL));assert(upload_calls==calls && rejected==1);
 assert(android_cpu_frame_vertices==10 && android_cpu_frame_draws==5 && android_cpu_frame_ms>0);
 double parts=0;for(unsigned i=0;i<3;i++){assert(android_cpu_frame_parts[i]>=0);parts+=android_cpu_frame_parts[i];}
 assert(fabs(parts-android_cpu_frame_ms)<1e-9 && !android_cpu_frame_fixed_vertices);
 free(android_active_cpu_program);
 // Other vendors retain their original shader/cache. NVIDIA uses one shared
 // passthrough and can switch back without overwriting that original cache.
 struct vertex_shader_object object={0},other={0};
 object.instructions=other.instructions=shader_words;object.instruction_count=other.instruction_count=17;
 android_cpu_skeletal_vertices=FALSE;
 GLuint original=vertex_shader_get(&object,FALSE);assert(original && !object.cpu_checked && !android_active_cpu_program);
 assert(vertex_shader_get(&object,FALSE)==original && gpu_compiles==1 && !cpu_compiles);
 android_cpu_skeletal_vertices=TRUE;
 GLuint cpu=vertex_shader_get(&object,FALSE);assert(cpu!=original && android_active_cpu_program && cpu_compiles==1);
 assert(vertex_shader_get(&other,FALSE)==cpu && cpu_compiles==1 && other.cpu_program);
 android_cpu_skeletal_vertices=FALSE;
 assert(vertex_shader_get(&object,FALSE)==original && !android_active_cpu_program && gpu_compiles==1);
 android_cpu_skeletal_vertices=TRUE;
 declaration.elements[0].type=0xff;
 assert(vertex_shader_get(&object,FALSE)==original && !android_active_cpu_program);
 assert(vertex_shader_get(&object,TRUE)==cpu && android_active_cpu_program);
 declaration.elements[0].type=D3DVSDT_FLOAT3;
 DWORD static_words[4]={0,0,0,1};struct vertex_shader_object ordinary={0};ordinary.instructions=static_words;ordinary.instruction_count=1;
 assert(vertex_shader_get(&ordinary,FALSE)!=cpu && !ordinary.cpu_program && !android_active_cpu_program);
 android_cpu_vertex_shader=0;android_cpu_vertex_shader_attempted=FALSE;fail_cpu_compile=TRUE;
 assert(vertex_shader_get(&object,FALSE)==original && !android_active_cpu_program);
 unsigned compiled=cpu_compiles;
 assert(vertex_shader_get(&object,FALSE)==original && cpu_compiles==compiled && !android_active_cpu_program);
 // The Shield test's GPU variants (halo_android_perf.h), NVIDIA skeletal programs only.
 fail_cpu_compile=FALSE;android_cpu_vertex_shader_attempted=FALSE;
 android_perf_settings=HALO_PERF_GPU_ORIGINAL;
 assert(vertex_shader_get(&object,FALSE)==original && !android_active_cpu_program && !android_full_constants_draw);
 android_perf_settings=HALO_PERF_GPU_FULL_CONSTANTS;
 assert(vertex_shader_get(&object,FALSE)==original && !android_active_cpu_program && android_full_constants_draw);
 vertex_shader_get(&ordinary,FALSE);assert(!android_full_constants_draw && !android_active_cpu_program);
 android_perf_settings=HALO_PERF_GPU_UNIFORM_BLOCK;unsigned before=gpu_compiles;
 GLuint block=vertex_shader_get(&object,FALSE);
 assert(block && block!=original && object.block_shader[0]==block && gpu_compiles==before+1 && !android_active_cpu_program);
 assert(strstr(last_source,"layout(std140) uniform nv2a_constant_block") && !strstr(last_source,"uniform vec4 c[192];"));
 assert(strstr(last_source,"c[clamp(a0 + 60, 0, 191)]"));
 assert(vertex_shader_get(&object,FALSE)==block && gpu_compiles==before+1);
 assert(vertex_shader_get(&ordinary,FALSE)!=block && !ordinary.block_attempted[0]);
 android_perf_settings=HALO_PERF_CPU_SINGLE;
 GLuint passthrough=vertex_shader_get(&object,FALSE);
 assert(android_active_cpu_program && passthrough!=original && passthrough!=block);
 android_cpu_skeletal_vertices=FALSE;android_perf_settings=HALO_PERF_GPU_UNIFORM_BLOCK;
 assert(vertex_shader_get(&object,FALSE)==original && !android_active_cpu_program && !android_full_constants_draw);
 free(object.cpu_program);free(other.cpu_program);
 puts("PASS: production CPU/GPU stream switching, first/base range, multiple/constant streams, changed uniforms/current attributes, immediate mode and buffer bounds.");
 puts("PASS: NVIDIA-only shader routing, shared passthrough, original cache preservation, unsupported/static fallback and no repeated failed compilations.");
 puts("PASS: Shield test variants: GPU original, full constants and uniform block only for NVIDIA skeletal programs; one compile each.");
}
'''
header = (ROOT/'port/linux/src/xgpu.h').read_text()
api = header[header.index('struct nv2a_cpu_program;'):header.index('#endif',header.index('struct nv2a_cpu_program;'))]
xdk = (ROOT/'port/include/xdk/xdk_d3d8.h').read_text()
formats='\n'.join(re.findall(r'^#define D3DVSDT_\w+ .*$',xdk,re.M))
with tempfile.TemporaryDirectory(prefix='halo-cpu-streams-') as name:
    tmp=Path(name)
    shutil.copyfile(ROOT/'port/android/include/halo_android_perf.h',tmp/'halo_android_perf.h')
    (tmp/'xgpu.h').write_text('#include <stdint.h>\n#include <stdlib.h>\n'
        '#define HALO_ANDROID 1\n#define TRUE 1\n#define FALSE 0\ntypedef uint32_t DWORD;\ntypedef int BOOL;\n'
        '#define XGPU_VERTEX_ATTRIBUTE_COUNT 16\n#define XGPU_VERTEX_CONSTANT_COUNT 192\n#define XGPU_VERTEX_CONSTANT_BIAS 96\n'
        'struct xgpu_capabilities { const char *shading_language; };\nextern struct xgpu_capabilities xgpu_capabilities;\n'
        'struct xgpu_text { char *buffer; unsigned long length,capacity; };\nvoid xgpu_text_append(struct xgpu_text *,const char *,...);\n'
        +formats+'\n'+api)
    shutil.copyfile(ROOT/'port/linux/src/nv2a_vsh.c',tmp/'nv2a_vsh.c')
    shutil.copyfile(ROOT/'port/linux/src/nv2a_cpu_shaders.inc',tmp/'nv2a_cpu_shaders.inc')
    (tmp/'test.c').write_text(prefix+production+fixture)
    binary=tmp/'test'
    subprocess.run(['cc','-std=gnu11','-O2','-ffp-contract=off','-g','-fsanitize=address,undefined',
                    str(tmp/'test.c'),str(tmp/'nv2a_vsh.c'),'-pthread','-lm','-o',str(binary)],check=True)
    # LeakSanitizer cannot enumerate threads in the traced Work runtime;
    # keep AddressSanitizer bounds checks and UBSan enabled.
    env=dict(os.environ,ASAN_OPTIONS=os.environ.get('ASAN_OPTIONS','')+':detect_leaks=0')
    subprocess.run([str(binary)],check=True,timeout=20,env=env)
