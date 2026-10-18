"""Compare production CPU skeletal execution with real GLES transform feedback.

Run with --dumps halo-gfx-*.zip to use recorded NVIDIA inputs/uniforms.
Reconstruct instruction fields from the emitted GLSL and require byte-identical
retranslation before testing. Compare every varying, fog and point size, not
only positions. Software GLES is a control, not a test on Shield hardware.
"""
from pathlib import Path
import argparse, ctypes as C, io, json, os, re, shutil, struct, subprocess, tempfile, time
from zipfile import ZipFile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dumps', type=Path, nargs='+', required=True)
parser.add_argument('--output', type=Path)
args = parser.parse_args()

MAC = {'A': 1, 'A * B': 2, 'A + C': 3, 'A * B + C': 4,
       'vec4(dot(A.xyz, B.xyz))': 5, 'vec4(dot(A.xyz, B.xyz) + B.w)': 6,
       'vec4(dot(A, B))': 7, 'vec4(1.0, A.y * B.y, A.z, B.w)': 8,
       'min(A, B)': 9, 'max(A, B)': 10, 'vec4(lessThan(A, B))': 11,
       'vec4(greaterThanEqual(A, B))': 12}
ILU = {'C': 1, 'vec4(1.0 / C.x)': 2, 'nv2a_rcc(C.x)': 3,
       'vec4(inversesqrt(abs(C.x)))': 4, 'nv2a_exp(C.x)': 5,
       'nv2a_log(C.x)': 6, 'nv2a_lit(C)': 7}
OUT = {'oPos': 0, 'oD0': 3, 'oD1': 4, 'oFog': 5, 'oPts': 6,
       'oB0': 7, 'oB1': 8, 'oT0': 9, 'oT1': 10, 'oT2': 11, 'oT3': 12, 'oUnused': 13}

def instructions_from_glsl(text):
    blocks = re.findall(r'/\* (\d+) \*/\n(.*?)(?=\s*/\* \d+ \*/|\s*/\* undo)', text, re.S)
    words = []
    for ordinal, body in blocks:
        w = [0, 0, 0, 0]
        inputs, constants, relative = set(), set(), set()
        for which, word, low, negword, negbit, idxword, idxlow, muxword, muxlow in (
                ('A', 1, 6, 1, 8, 2, 28, 2, 26), ('B', 2, 23, 2, 25, 2, 13, 2, 11),
                ('C', 2, 8, 2, 10, None, None, 3, 28)):
            operand = re.search(r'\b' + which + r' = (.*?);', body)[1]
            m = re.fullmatch(r'(-?)(.*)\.([xyzw]{4})', operand)
            assert m, operand
            negate, source, swizzle = m.groups()
            w[negword] |= bool(negate) << negbit
            for i, letter in enumerate(swizzle): w[word] |= 'xyzw'.index(letter) << (low - i * 2)
            index, mux = 0, 0
            if source.startswith('v'):
                mux = 2; inputs.add(int(source[1:]))
            elif source.startswith('r') or source == 'oPos':
                mux = 1; index = 12 if source == 'oPos' else int(source[1:])
            elif source.startswith('c['):
                mux = 3
                m = re.fullmatch(r'c\[clamp\(a0 \+ (\d+), 0, 191\)\]', source)
                if m: constants.add(int(m[1])); relative.add(True)
                else: constants.add(int(re.fullmatch(r'c\[(\d+)\]', source)[1])); relative.add(False)
            else: assert source == 'vec4(0.0)', source
            w[muxword] |= mux << muxlow
            if which == 'C':
                w[2] |= (index >> 2) & 3; w[3] |= (index & 3) << 30
            else: w[idxword] |= index << idxlow
        assert len(inputs) <= 1 and len(constants) <= 1 and len(relative) <= 1, body
        if inputs: w[1] |= next(iter(inputs)) << 9
        if constants: w[1] |= next(iter(constants)) << 13
        if relative: w[3] |= next(iter(relative)) << 1
        mac_expr = re.search(r'\bmac = (.*?);', body)
        ilu_expr = re.search(r'\bilu = (.*?);', body)
        mac = 13 if 'a0 = int(floor' in body else MAC[mac_expr[1]] if mac_expr else 0
        ilu = ILU[ilu_expr[1]] if ilu_expr else 0
        w[1] |= mac << 21 | ilu << 25
        writes = re.findall(r'\b(r\d+|o\w+)\.([xyzw]+) = (mac|ilu)\.([xyzw]+);', body)
        output_writes = [p for p in writes if p[0].startswith('o')]
        temporary = None
        for dest, mask, unit, rhs in writes:
            assert mask == rhs
            bits = sum(8 >> 'xyzw'.index(letter) for letter in mask)
            if dest.startswith('r') or (dest == 'oPos' and len(output_writes) > 1 and dest == output_writes[0][0]):
                reg = 12 if dest == 'oPos' else int(dest[1:])
                if unit == 'mac':
                    w[3] |= bits << 24; temporary = reg
                else:
                    w[3] |= bits << 16
                    if mac: assert reg == 1, body
                    else: temporary = reg
            else:
                w[3] |= bits << 12 | 1 << 11 | OUT[dest] << 3 | (unit == 'ilu') << 2
        if temporary is not None: w[3] |= temporary << 20
        words.extend(w)
    assert words
    words[-1] |= 1
    return (C.c_uint32 * len(words))(*words)

def parse_draws(report):
    draws = []; draw = None
    for line in report.splitlines():
        if line.startswith('DRAW '):
            draw = {'id': int(line.split()[1]), 'program': int(re.search(r'program=(\d+)', line)[1]),
                    'attributes': {}, 'current': {}, 'uniforms': {}}
            draws.append(draw)
        elif draw:
            m = re.match(r'  ATTR (\d+) enabled=1 (.*)', line)
            if m: draw['attributes'][int(m[1])] = {k: int(v, 0) for k,v in re.findall(r'(\w+)=(0x[\da-f]+|\d+)', m[2])}
            m = re.match(r'  ATTR (\d+) enabled=0 current_float=([^ ]+)', line)
            if m: draw['current'][int(m[1])] = tuple(map(float, m[2].split(',')))
            m = re.match(r'  U (\S+) location=\d+ type=\S+ (.*?) nonfinite=', line)
            if m: draw['uniforms'][m[1]] = tuple(map(float, m[2].split()))
            m = re.match(r'  VERTEX_RANGE (\d+)\.\.(\d+)', line)
            if m: draw['range'] = int(m[1]), int(m[2])
    return draws

P = C.c_void_p; I = C.c_int; U = C.c_uint; F = C.c_float
class Vertex(C.Structure):
    _fields_ = [('value', (F*4)*9), ('fog', F), ('point_size', F), ('padding',F*2)]

# Compile the actual translator/executor with a minimal platform header.
temporary = tempfile.TemporaryDirectory(prefix='halo-cpu-skeletal-')
folder = Path(temporary.name)
header = (ROOT/'port/linux/src/xgpu.h').read_text()
cpu_api = header[header.index('struct nv2a_cpu_program;'):header.index('#endif', header.index('struct nv2a_cpu_program;'))]
xdk = (ROOT/'port/include/xdk/xdk_d3d8.h').read_text()
formats = '\n'.join(re.findall(r'^#define D3DVSDT_\w+ .*$', xdk, re.M))
(folder/'xgpu.h').write_text('#include <stdint.h>\n#include <stdlib.h>\n#include <stdarg.h>\n'
    '#define HALO_ANDROID 1\n#define TRUE 1\n#define FALSE 0\ntypedef uint32_t DWORD;\ntypedef int BOOL;\n'
    '#define XGPU_VERTEX_ATTRIBUTE_COUNT 16\n#define XGPU_VERTEX_CONSTANT_COUNT 192\n#define XGPU_VERTEX_CONSTANT_BIAS 96\n'
    'struct xgpu_capabilities { const char *shading_language; };\nextern struct xgpu_capabilities xgpu_capabilities;\n'
    'struct xgpu_text { char *buffer; unsigned long length, capacity; };\n'
    'void xgpu_text_append(struct xgpu_text *,const char *,...);\n' + formats + '\n' + cpu_api)
shutil.copyfile(ROOT/'port/linux/src/nv2a_vsh.c', folder/'nv2a_vsh.c')
shutil.copyfile(ROOT/'port/linux/src/nv2a_cpu_shaders.inc', folder/'nv2a_cpu_shaders.inc')
(folder/'bridge.c').write_text(r'''
#include "xgpu.h"
#include <stdio.h>
#include <string.h>
struct xgpu_capabilities xgpu_capabilities={"310 es"};
void set_language(const char *v){static char language[16];snprintf(language,sizeof(language),"%s",v);xgpu_capabilities.shading_language=language;}
void xgpu_text_append(struct xgpu_text *t,const char *f,...){
 va_list a,b;va_start(a,f);va_copy(b,a);int n=vsnprintf(NULL,0,f,a);va_end(a);
 if(t->length+n+1>t->capacity){t->capacity=(t->length+n+1)*2;t->buffer=realloc(t->buffer,t->capacity);}
 vsnprintf(t->buffer+t->length,t->capacity-t->length,f,b);va_end(b);t->length+=n;
}
void execute_batch(const struct nv2a_cpu_program *p,const float (*v)[16][4],const float c[192][4],
 const float s[4],const float o[4],float x,float size,unsigned count,struct nv2a_cpu_vertex *out){
 nv2a_cpu_program_prepare_constants((struct nv2a_cpu_program *)p,c);
 for(unsigned i=0;i<count;i++)nv2a_cpu_vertex_execute(p,v[i],c,s,o,x,size,&out[i]);
}
''')
library = folder/'production.so'
subprocess.run(['cc','-std=gnu11','-O2','-ffp-contract=off','-fPIC','-shared',str(folder/'bridge.c'),
                str(folder/'nv2a_vsh.c'),'-lm','-o',str(library)],check=True)
production = C.CDLL(str(library))
production.nv2a_cpu_program_create.argtypes = [P,C.c_ulong]; production.nv2a_cpu_program_create.restype = P
production.nv2a_vertex_shader_to_glsl.argtypes = [P,C.c_ulong,C.c_ulong]; production.nv2a_vertex_shader_to_glsl.restype = P
production.nv2a_cpu_vertex_glsl.restype = P
production.nv2a_cpu_attribute_decode.argtypes = [C.c_ulong,P,P]
production.execute_batch.argtypes = [P,P,P,P,P,F,F,U,P]
production.set_language.argtypes = [C.c_char_p]
libc = C.CDLL(None); libc.free.argtypes = [P]
def generated(function, *arguments):
    p = function(*arguments); text = C.string_at(p).decode(); libc.free(p); return text

# Real GLES 3.1 via surfaceless Mesa; all eleven transform-feedback outputs.
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'; os.environ['EGL_PLATFORM'] = 'surfaceless'
egl = C.CDLL('libEGL.so.1')
def bind(lib, name, ret, params):
    f = getattr(lib, name); f.restype = ret; f.argtypes = params; return f
display = bind(egl,'eglGetPlatformDisplay',P,[U,P,P])(0x31DD,None,None)
major=I(); minor=I()
assert bind(egl,'eglInitialize',U,[P,P,P])(display,C.byref(major),C.byref(minor))
assert bind(egl,'eglBindAPI',U,[U])(0x30A0)
cfg=P(); count=I()
attributes=(I*13)(0x3033,1,0x3040,0x40,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3038)
assert bind(egl,'eglChooseConfig',U,[P,P,P,I,P])(display,attributes,C.byref(cfg),1,C.byref(count))
surface=bind(egl,'eglCreatePbufferSurface',P,[P,P,P])(display,cfg,(I*5)(0x3057,16,0x3056,16,0x3038))
ctx=bind(egl,'eglCreateContext',P,[P,P,P,P])(display,cfg,None,(I*3)(0x3098,3,0x3038))
assert bind(egl,'eglMakeCurrent',U,[P,P,P,P])(display,surface,surface,ctx)
proc=bind(egl,'eglGetProcAddress',P,[C.c_char_p])
def gl(name,ret,params): return C.CFUNCTYPE(ret,*params)(proc(name.encode()))
get_string=gl('glGetString',C.c_char_p,[U]); get_error=gl('glGetError',U,[])
new_shader=gl('glCreateShader',U,[U]); shader_source=gl('glShaderSource',None,[U,I,P,P])
compile_shader=gl('glCompileShader',None,[U]); shader_iv=gl('glGetShaderiv',None,[U,U,P]); shader_log=gl('glGetShaderInfoLog',None,[U,I,P,P])
new_program=gl('glCreateProgram',U,[]); attach=gl('glAttachShader',None,[U,U]); link=gl('glLinkProgram',None,[U])
program_iv=gl('glGetProgramiv',None,[U,U,P]); program_log=gl('glGetProgramInfoLog',None,[U,I,P,P]); use=gl('glUseProgram',None,[U])
varyings=gl('glTransformFeedbackVaryings',None,[U,I,P,U]); gen_vao=gl('glGenVertexArrays',None,[I,P]); vao=gl('glBindVertexArray',None,[U])
gen_buffer=gl('glGenBuffers',None,[I,P]); buffer=gl('glBindBuffer',None,[U,U]); buffer_data=gl('glBufferData',None,[U,C.c_ssize_t,P,U])
pointer=gl('glVertexAttribPointer',None,[U,I,U,C.c_ubyte,I,P]); ipointer=gl('glVertexAttribIPointer',None,[U,I,U,I,P])
enable_attr=gl('glEnableVertexAttribArray',None,[U]); current_attr=gl('glVertexAttrib4fv',None,[U,P]); current_int=gl('glVertexAttribI4ui',None,[U,U,U,U,U])
uniform_loc=gl('glGetUniformLocation',I,[U,C.c_char_p]); uniform4=gl('glUniform4fv',None,[I,I,P]); uniform1=gl('glUniform1f',None,[I,F])
bind_base=gl('glBindBufferBase',None,[U,U,U]); enable=gl('glEnable',None,[U]); disable=gl('glDisable',None,[U])
begin=gl('glBeginTransformFeedback',None,[U]); end=gl('glEndTransformFeedback',None,[]); draw_arrays=gl('glDrawArrays',None,[U,I,I])
map_range=gl('glMapBufferRange',P,[U,C.c_ssize_t,C.c_ssize_t,U]); unmap=gl('glUnmapBuffer',U,[U])
delete_buffers=gl('glDeleteBuffers',None,[I,P]); delete_vaos=gl('glDeleteVertexArrays',None,[I,P])
delete_shader=gl('glDeleteShader',None,[U]); delete_program=gl('glDeleteProgram',None,[U])
print('BACKEND:',get_string(0x1F02).decode(),get_string(0x1F01).decode())

def shader(kind,text):
    s=new_shader(kind); encoded=(C.c_char_p*1)(text.encode()); shader_source(s,1,encoded,None); compile_shader(s)
    good=I(); shader_iv(s,0x8B81,C.byref(good))
    if not good.value:
        message=C.create_string_buffer(8192); shader_log(s,8192,None,message); raise AssertionError(message.value.decode())
    return s
def program(text):
    version=text.splitlines()[0]
    vs=shader(0x8B31,text); fs=shader(0x8B30,version+'\nprecision highp float;out vec4 color;void main(){color=vec4(1);}')
    p=new_program(); attach(p,vs); attach(p,fs)
    names=(C.c_char_p*11)(*[n.encode() for n in ['gl_Position','xD0','xD1','xB0','xB1','xT0','xT1','xT2','xT3','xFog','gl_PointSize']])
    varyings(p,11,names,0x8C8C); link(p)
    good=I(); program_iv(p,0x8B82,C.byref(good))
    if not good.value:
        message=C.create_string_buffer(8192); program_log(p,8192,None,message); raise AssertionError(message.value.decode())
    delete_shader(vs); delete_shader(fs); return p
def feedback(p, count):
    use(p); bid=U(); gen_buffer(1,C.byref(bid)); buffer(0x8C8E,bid); buffer_data(0x8C8E,count*152,None,0x88E4)
    bind_base(0x8C8E,0,bid); enable(0x8C89); begin(0); draw_arrays(0,0,count); end(); disable(0x8C89)
    ptr=map_range(0x8C8E,0,count*152,1); assert ptr
    result=np.frombuffer(C.string_at(ptr,count*152),dtype='<f4').reshape(count,38).copy(); assert unmap(0x8C8E)
    bind_base(0x8C8E,0,0); delete_buffers(1,C.byref(bid)); assert get_error()==0
    return result

# Decoder boundary tests use the actual XDK constants (not sequential enums).
for type_, raw, expected in [(0x24,bytes([0,255]),[0,1,0,1]),(0x11,struct.pack('<h',-32768),[-1,0,0,1]),
                             (0x41,struct.pack('<hhhh',0,32767,-32768,16384),[0,1,-1,16384/32767]),
                             (0x45,struct.pack('<hhhh',1,-2,3,-4),[1,-2,3,-4]),
                             (0x40,bytes([10,20,30,40]),[30/255,20/255,10/255,40/255]),
                             (0x16,struct.pack('<I',0x80000400),[-1024/1023,0,-512/511,1])]:
    memory=C.create_string_buffer(b'X'+raw); value=(F*4)()
    production.nv2a_cpu_attribute_decode(type_,C.byref(memory,1),value)
    assert np.allclose(list(value),expected,rtol=1e-6,atol=1e-7),(type_,list(value),expected)

summary={'draws':0,'vertices':0,'additional_shader_cases':0,'additional_vertices':0,'unique_shaders':0,'max_absolute_error':[0.0]*38,'max_scaled_error':0.0,
         'passthrough_max_error':0.0,'captures':[],'backend':get_string(0x1F01).decode()}
cache={}; passthrough={}
for language in (b'300 es',b'310 es'):
    production.set_language(language)
    passthrough[language.decode()]=program(generated(production.nv2a_cpu_vertex_glsl))
for zip_path in args.dumps:
    cpu_time=0.0; tested=0; total=0
    with ZipFile(zip_path) as z:
        assert z.testzip() is None
        sources={}
        for name in z.namelist():
            m=re.match(r'program-(\d+)-.*-8b31\.glsl$',name)
            if m: sources[int(m[1])]=z.read(name).decode()
        draws=parse_draws(z.read('report.txt').decode())
        recorded_programs={d['program'] for d in draws if 'range' in d}
        base=next((d for d in draws if 'range' in d and 5 in d['attributes'] and 6 in d['attributes'] and
                   len([n for n in d['uniforms'] if n.startswith('c[')])==192),None)
        # Also cover recorded shader variants without a detailed draw. They
        # reuse one real input set but count separately from captured draws.
        if base:
            for pid,text in sources.items():
                if pid not in recorded_programs and ('c[clamp(a0' in text or 'halo_nvidia_constant' in text):
                    extra=dict(base,program=pid,supplemental=True)
                    extra['range']=(base['range'][0],min(base['range'][1],base['range'][0]+31))
                    draws.append(extra)
        for draw in draws:
            if 'range' not in draw: continue
            text=sources.get(draw['program'],'')
            if 'halo_nvidia_constant' in text:
                start=text.index('/* Shield matrix test 2: literal-index constant selection */')
                finish=text.index('layout(location',start)
                text=text[:start]+text[finish:]
                text=re.sub(r'halo_nvidia_constant\(a0 \+ (\d+)\)',r'c[clamp(a0 + \1, 0, 191)]',text)
            if 'c[clamp(a0' not in text: continue
            version=text.splitlines()[0].removeprefix('#version ')
            production.set_language(version.encode())
            packed=sum(1<<int(m) for m in re.findall(r'layout\(location = (\d+)\) in uint',text))
            if text not in cache:
                words=instructions_from_glsl(text)
                generated_text=generated(production.nv2a_vertex_shader_to_glsl,words,len(words)//4,packed)
                if generated_text!=text:
                    import difflib
                    print(''.join(difflib.unified_diff(text.splitlines(True),generated_text.splitlines(True)))[:5000])
                    raise AssertionError('Reconstructed instruction retranslation differs: '+zip_path.name+' '+str(draw['program']))
                cpu=production.nv2a_cpu_program_create(words,len(words)//4); assert cpu
                cache[text]=(cpu,program(text)); summary['unique_shaders']+=1
            cpu,p=cache[text]
            if version not in passthrough: passthrough[version]=program(generated(production.nv2a_cpu_vertex_glsl))
            low,high=draw['range']; count=high-low+1
            inputs=np.zeros((count,16,4),dtype='<f4'); inputs[:,:,3]=1
            constants=np.zeros((192,4),dtype='<f4')
            for name,values in draw['uniforms'].items():
                m=re.fullmatch(r'c\[(\d+)\]',name)
                if m: constants[int(m[1])]=values
            assert len([n for n in draw['uniforms'] if n.startswith('c[')])==192
            value=U(); gen_vao(1,C.byref(value)); vao(value); use(p)
            gpu_buffers=[]
            for a in range(16):
                attr=draw['attributes'].get(a)
                if attr:
                    raw=z.read(f"draw-{draw['id']:04d}-attr-{a}.bin"); memory=C.create_string_buffer(raw)
                    bid=U(); gen_buffer(1,C.byref(bid)); buffer(0x8892,bid); buffer_data(0x8892,len(raw),memory,0x88E4); gpu_buffers.append(bid.value)
                    if attr['integer']: ipointer(a,attr['size'],attr['type'],attr['stride'],None)
                    else: pointer(a,attr['size'],attr['type'],attr['normalized'],attr['stride'],None)
                    enable_attr(a)
                    type_ = 0x16 if packed & (1<<a) else (attr['size']<<4) | {0x1406:2,0x1402:1 if attr['normalized'] else 5,0x1401:4}[attr['type']]
                    for v in range(count):
                        out=(F*4)(); production.nv2a_cpu_attribute_decode(type_,C.byref(memory,v*attr['stride']),out); inputs[v,a]=out
                elif packed & (1<<a): current_int(a,0,0,0,0)
                else:
                    values=draw['current'].get(a,(0,0,0,1)); inputs[:,a]=values; current_attr(a,(F*4)(*values))
            for name,values in draw['uniforms'].items():
                loc=uniform_loc(p,name.encode())
                if loc<0: continue
                if len(values)==4: uniform4(loc,1,(F*4)(*values))
                elif len(values)==1: uniform1(loc,values[0])
            # The old recorder announces point_size but omits its scalar
            # readback. Set the same explicit value in both controls.
            size=draw['uniforms'].get('point_size',(1,))[0]
            uniform1(uniform_loc(p,b'point_size'),size)
            reference=feedback(p,count)
            cpu_vertices=(Vertex*count)()
            scale=(F*4)(*draw['uniforms']['viewport_scale']); off=(F*4)(*draw['uniforms']['viewport_offset'])
            screen=draw['uniforms'].get('screen_offset',(0,))[0]; size=draw['uniforms'].get('point_size',(1,))[0]
            began=time.perf_counter()
            production.execute_batch(cpu,inputs.ctypes.data,constants.ctypes.data,scale,off,screen,size,count,cpu_vertices)
            cpu_time+=time.perf_counter()-began
            result=np.frombuffer(cpu_vertices,dtype='<f4').reshape(count,40)[:,:38]
            assert np.isfinite(reference).all() and np.isfinite(result).all(),(zip_path.name,draw['id'],'nonfinite')
            delta=np.abs(reference-result); scaled=delta/(1+np.abs(reference))
            summary['max_absolute_error']=np.maximum(summary['max_absolute_error'],delta.max(axis=0)).tolist()
            summary['max_scaled_error']=max(summary['max_scaled_error'],float(scaled.max()))
            assert scaled.max()<3e-5,(zip_path.name,draw['id'],'CPU differs',float(scaled.max()),np.unravel_index(scaled.argmax(),scaled.shape))
            # Execute the actual GPU passthrough against the CPU output buffer.
            cpu_vao=U(); gen_vao(1,C.byref(cpu_vao)); vao(cpu_vao)
            planar=np.concatenate([result[:,a*4:(a+1)*4].ravel() for a in range(9)]+[result[:,36:38].ravel()]).astype('<f4')
            cpu_buffer=U(); gen_buffer(1,C.byref(cpu_buffer)); buffer(0x8892,cpu_buffer); buffer_data(0x8892,planar.nbytes,planar.ctypes.data,0x88E4)
            for a in range(10):
                pointer(a,4 if a<9 else 2,0x1406,0,16 if a<9 else 8,P(a*count*16 if a<9 else count*144)); enable_attr(a)
            actual=feedback(passthrough[version],count)
            assert np.array_equal(actual,result),'GPU passthrough changed CPU results'
            delete_buffers(1,C.byref(cpu_buffer)); delete_vaos(1,C.byref(cpu_vao)); delete_vaos(1,C.byref(value))
            delete_buffers(len(gpu_buffers),(U*len(gpu_buffers))(*gpu_buffers))
            if draw.get('supplemental'):
                summary['additional_shader_cases']+=1; summary['additional_vertices']+=count
            else:
                tested+=1; total+=count
    summary['draws']+=tested; summary['vertices']+=total
    capture={'file':zip_path.name,'draws':tested,'vertices':total,'cpu_execution_ms':cpu_time*1000}
    summary['captures'].append(capture); print(json.dumps(capture),flush=True)
for cpu,p in cache.values(): libc.free(cpu); delete_program(p)
for p in passthrough.values(): delete_program(p)
assert summary['vertices']>0
if args.output: args.output.write_text(json.dumps(summary,indent=2)+'\n')
print('PASS:',summary['draws'],'draws,',summary['vertices'],'vertices,',summary['unique_shaders'],'shader variants; every output compared; max scaled error',summary['max_scaled_error'])
temporary.cleanup()
