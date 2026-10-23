#!/usr/bin/env python3
"""Check the NVIDIA CPU skinning path (port/linux/src/d3d8_gl.c).

The production android_cpu_setup_vertices (port/linux/src/d3d8_gl.c) runs
with its worker pool on real threads, every skeletal program of the game's
vertex shader payload and randomized declarations: element types, strides,
offsets, constant (stride 0) streams, registers without a stream, immediate
mode and draws on both sides of the chunk and parallel limits. Whatever a
GPU attribute reads - its uploaded plane, or the constant value an unwritten
attribute keeps - must be bit for bit what the reference gives: every input
register decoded per vertex and the same nv2a_cpu_vertex_execute, as the
earlier single-threaded path did.

Built three times: optimized, with AddressSanitizer/UBSan, and with
ThreadSanitizer for the pool's synchronisation. No device, no game assets.
HALO_TEST_KEEP=<directory> keeps the generated harness there.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from android_cpu_shader_generate import programs  # noqa: E402
from test_upstream_optimizations import function  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'port/linux/src/d3d8_gl.c').read_text()
start = source.index('/* ---------- NVIDIA CPU skeletal vertices')
end = source.index('static GLenum primitive_mode')
region = source[start:end]
assert region.rstrip().endswith('#endif')
region = region.rstrip()[:-len('#endif')]
production = '\n'.join([
    function(source, 'state_array_buffer'),
    function(source, 'state_attribute_pointer'),
    function(source, 'state_attribute_value'),
    region,
])
header = (ROOT / 'port/linux/src/xgpu.h').read_text()
api = header[header.index('struct nv2a_cpu_program;'):header.index('#endif', header.index('struct nv2a_cpu_program;'))]
xdk = (ROOT / 'port/include/xdk/xdk_d3d8.h').read_text()
formats = '\n'.join(re.findall(r'^#define D3DVSDT_\w+ .*$', xdk, re.M))

shaders = [code for _, code in programs()]
words = ',\n'.join('{%d,{%s}}' % (len(code) // 4, ','.join('0x%08xU' % w for w in code)) for code in shaders)

PREFIX = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "xgpu.h"
/* the runs to compare: the workers' and the render thread's alone */
enum { MODE_THREADS, MODE_SINGLE };
typedef unsigned GLuint, GLenum;
typedef int GLint, GLsizei;
typedef unsigned char GLboolean;
#define GL_TRUE 1
#define GL_FALSE 0
#define GL_FLOAT 0x1406
#define STREAM_BUFFER_SIZE (16 * 1024 * 1024)
#define PLATFORM_PHYSICAL_TO_VIRTUAL(x) ((void *)(uintptr_t)(x))
struct attribute_pointer { GLuint buffer; GLint size; GLenum type; GLboolean normalized, integer; GLsizei stride; unsigned long offset; };
static struct {
 GLuint array_buffer;
 struct attribute_pointer attribute_pointers[16];
 unsigned char attribute_enabled[16], attribute_value_kind[16];
 float attribute_values[16][4];
} gl_state;
struct vertex_element { unsigned char reg, stream, type, bytes; unsigned short offset; };
struct vertex_shader_object { unsigned long element_count, packed_mask; struct vertex_element elements[16]; };
static struct {
 struct vertex_shader_object *vertex_shader;
 struct { unsigned long data, stride; } streams[16];
 GLuint stream_buffer;
 float attributes[16][4];
 float constants[192][4];
} device;
static struct { float viewport_scale[4], viewport_offset[4], screen_offset, point_size; } draw_uniforms;
static struct { unsigned long streamed_bytes; } stats;
static struct nv2a_cpu_program *android_active_cpu_program;
static unsigned rejected;
static void platform_log(const char *format, ...) { if (strstr(format, "rejected")) rejected++; }
/* the GL the draw leaves behind: enabled arrays, their pointers, current values */
static unsigned char *gpu; static unsigned long gpu_size, gpu_used;
static unsigned char enabled[16]; static struct attribute_pointer pointers[16]; static float current[16][4];
static GLuint bound;
static void glBindBuffer(GLenum t, GLuint b) { (void)t; bound = b; }
#define GL_ARRAY_BUFFER 1
static void glEnableVertexAttribArray(GLuint i) { enabled[i] = 1; }
static void glDisableVertexAttribArray(GLuint i) { enabled[i] = 0; }
static void glVertexAttribPointer(GLuint i, GLint s, GLenum t, GLboolean n, GLsizei stride, const void *p) {
 assert(bound == device.stream_buffer);
 pointers[i] = (struct attribute_pointer){bound, s, t, n, 0, stride, (unsigned long)(uintptr_t)p};
}
static void glVertexAttribIPointer(GLuint i, GLint s, GLenum t, GLsizei stride, const void *p) { (void)i;(void)s;(void)t;(void)stride;(void)p; assert(0); }
static void glVertexAttrib4fv(GLuint i, const float *v) { memcpy(current[i], v, 16); }
static void glVertexAttribI4ui(GLuint i, GLuint a, GLuint b, GLuint c, GLuint d) { (void)i;(void)a;(void)b;(void)c;(void)d; assert(0); }
static unsigned long stream_upload(const void *data, unsigned long size) {
 unsigned long offset = gpu_used;
 if (offset + size > gpu_size) { gpu_size = (offset + size) * 2; gpu = realloc(gpu, gpu_size); }
 memcpy(gpu + offset, data, size); gpu_used += (size + 15) & ~15UL; return offset;
}
'''

SUFFIX = r'''
static const struct { unsigned long count; DWORD words[400]; } shaders[] = {
''' + words + r'''
};
static unsigned long long rng = 0x5348494c45445046ULL;
static unsigned random32(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return (unsigned)(rng >> 16); }
static float random_float(float scale) { return ((int)(random32() % 20001) - 10000) / 10000.0f * scale; }
static const unsigned long types[] = { D3DVSDT_FLOAT1, D3DVSDT_FLOAT2, D3DVSDT_FLOAT3, D3DVSDT_FLOAT4,
 D3DVSDT_D3DCOLOR, D3DVSDT_NORMPACKED3, D3DVSDT_SHORT2, D3DVSDT_SHORT4, D3DVSDT_NORMSHORT1,
 D3DVSDT_NORMSHORT2, D3DVSDT_NORMSHORT3, D3DVSDT_PBYTE1, D3DVSDT_PBYTE2, D3DVSDT_PBYTE4, D3DVSDT_FLOAT2H };
/* what the GPU's passthrough shader reads for one vertex: nine float4,
then fog and point size */
static void gpu_vertex(unsigned long vertex, float out[38]) {
 for (unsigned a = 0; a < 10; a++) {
  unsigned n = a < 9 ? 4 : 2;
  if (enabled[a]) {
   assert(pointers[a].size == (GLint)n && pointers[a].type == GL_FLOAT && pointers[a].stride == (GLsizei)(n * 4));
   memcpy(out + a * 4, gpu + pointers[a].offset + vertex * n * 4, n * 4);
  } else memcpy(out + a * 4, current[a], n * 4);
 }
}
static unsigned long checked_vertices, parallel_draws, single_draws, immediate_draws, written_planes, constant_attributes;
static void draw(struct nv2a_cpu_program *program, BOOL immediate_mode, unsigned long count, unsigned mode) {
 static unsigned char memory[8][320 * 1024];
 static BOOL filled;
 static float immediate[8192][16][4];
 struct vertex_shader_object declaration = { 0 };
 unsigned long first = random32() % 37, vertex, index;
 for (index = 0; index < 16; index++)
  for (unsigned c = 0; c < 4; c++) device.attributes[index][c] = random_float(4.0f);
 for (index = 0; index < 192; index++)
  for (unsigned c = 0; c < 4; c++) device.constants[index][c] = random_float(2.0f);
 /* node indices: sensible rows usually, out of range sometimes */
 for (index = 0; index < 4; index++) device.constants[index + 4][3] = (random32() % 8) ? 3.0f : 300.0f;
 for (unsigned c = 0; c < 3; c++) { draw_uniforms.viewport_scale[c] = random_float(300.0f); draw_uniforms.viewport_offset[c] = random_float(300.0f); }
 draw_uniforms.screen_offset = random_float(80.0f); draw_uniforms.point_size = random_float(5.0f);
 /* vertex memory: random once, then a fresh window per draw */
 if (!filled) { for (index = 0; index < 8; index++) for (vertex = 0; vertex < sizeof(memory[0]); vertex++) memory[index][vertex] = (unsigned char)random32(); filled = TRUE; }
 for (index = 0; index < 8; index++) { unsigned long at = random32() % (sizeof(memory[0]) - 4096); for (vertex = 0; vertex < 4096; vertex++) memory[index][at + vertex] = (unsigned char)random32(); }
 declaration.packed_mask = random32() & 0xffffU;
 declaration.element_count = 0;
 for (index = 0; index < 16 && declaration.element_count < 15; index++) {
  if (random32() % 5 == 0) continue; /* no stream: the current value */
  struct vertex_element *e = &declaration.elements[declaration.element_count++];
  e->reg = (unsigned char)index; e->stream = (unsigned char)(random32() % 8);
  e->type = (unsigned char)types[random32() % (sizeof(types) / sizeof(types[0]))];
  e->offset = (unsigned short)(random32() % 32);
  if (random32() % 7 == 0) { /* a later element for the same register wins */
   struct vertex_element *again = &declaration.elements[declaration.element_count++];
   *again = *e; again->type = D3DVSDT_FLOAT3; again->offset = (unsigned short)(random32() % 16);
  }
 }
 for (index = 0; index < 8; index++) {
  device.streams[index].data = (random32() % 9) ? (unsigned long)(uintptr_t)memory[index] : 0;
  device.streams[index].stride = (random32() % 6) ? 48 + random32() % 3 * 4 : 0;
 }
 device.vertex_shader = &declaration;
 for (vertex = 0; vertex < count; vertex++)
  for (index = 0; index < 16; index++) for (unsigned c = 0; c < 4; c++) immediate[vertex][index][c] = random_float(3.0f);
 android_active_cpu_program = program;
 gpu_used = 0;
 /* the render thread alone: the started workers, hidden for this draw */
 unsigned long workers = android_cpu_workers();
 if (mode == MODE_SINGLE) android_cpu_pool.workers = 0;
 assert(android_cpu_setup_vertices(first, count, immediate_mode ? &immediate[0][0][0] : NULL));
 android_cpu_pool.workers = workers;
 if (immediate_mode) immediate_draws++;
 else if (mode == MODE_THREADS && count >= ANDROID_CPU_PARALLEL_MINIMUM) parallel_draws++;
 else single_draws++;
 for (index = 0; index < 10; index++) { if (enabled[index]) written_planes++; else constant_attributes++; }
 /* the reference: every register decoded for every vertex */
 float defaults[16][4];
 const struct vertex_element *last[16] = { NULL };
 memcpy(defaults, device.attributes, sizeof(defaults));
 for (index = 0; index < 16; index++)
  if (declaration.packed_mask & (1UL << index)) { defaults[index][0] = defaults[index][1] = defaults[index][2] = 0; defaults[index][3] = 1; }
 for (index = 0; index < declaration.element_count; index++)
  if (device.streams[declaration.elements[index].stream].data) last[declaration.elements[index].reg] = &declaration.elements[index];
 for (index = 0; index < 16; index++)
  if (last[index] && !device.streams[last[index]->stream].stride)
   nv2a_cpu_attribute_decode(last[index]->type, (unsigned char *)(uintptr_t)device.streams[last[index]->stream].data + first * 0 + last[index]->offset, defaults[index]);
 nv2a_cpu_program_prepare_constants(program, device.constants);
 for (vertex = 0; vertex < count; vertex++) {
  float inputs[16][4], expected[38], actual[38];
  struct nv2a_cpu_vertex reference;
  if (immediate_mode) memcpy(inputs, immediate[vertex], sizeof(inputs));
  else {
   memcpy(inputs, defaults, sizeof(inputs));
   for (index = 0; index < 16; index++) {
    const struct vertex_element *e = last[index];
    unsigned long stride;
    if (!e || !(stride = device.streams[e->stream].stride)) continue;
    nv2a_cpu_attribute_decode(e->type, (unsigned char *)(uintptr_t)device.streams[e->stream].data + (first + vertex) * stride + e->offset, inputs[index]);
   }
  }
  nv2a_cpu_vertex_execute(program, inputs, device.constants, draw_uniforms.viewport_scale, draw_uniforms.viewport_offset,
   draw_uniforms.screen_offset, draw_uniforms.point_size, &reference);
  memcpy(expected, reference.value, sizeof(reference.value)); expected[36] = reference.fog; expected[37] = reference.point_size;
  gpu_vertex(vertex, actual);
  if (memcmp(expected, actual, sizeof(expected))) {
   for (index = 0; index < 38; index++) if (memcmp(&expected[index], &actual[index], 4))
    fprintf(stderr, "vertex %lu of %lu (first %lu, mode %u, immediate %d) value %lu: expected %.9g, got %.9g (written %03x)\n",
     vertex, count, first, mode, immediate_mode, index, expected[index], actual[index], nv2a_cpu_program_outputs(program));
   abort();
  }
  checked_vertices++;
 }
}
int main(int argc, char **argv) {
 unsigned long rounds = argc > 1 ? strtoul(argv[1], NULL, 10) : 4, programs_used = 0, interpreters = 0;
 static const unsigned long counts[] = { 1, 2, 63, 64, 65, 127, 191, 192, 193, 255, 640, 2049, 5000 };
 memset(&gl_state, 255, sizeof(gl_state)); device.stream_buffer = 17;
 for (unsigned long s = 0; s < sizeof(shaders) / sizeof(shaders[0]); s++) {
  for (int interpreter = 0; interpreter < 2; interpreter++) {
   DWORD copy[400]; memcpy(copy, shaders[s].words, sizeof(copy));
   /* a trailing, never-executed difference keeps the interpreter */
   if (interpreter) copy[shaders[s].count * 4 - 4] ^= 1;
   struct nv2a_cpu_program *program = nv2a_cpu_program_create(copy, shaders[s].count);
   if (!program) break;
   if (interpreter) { if (nv2a_cpu_program_is_specialized(program)) { free(program); continue; } interpreters++; }
   else programs_used++;
   for (unsigned long round = 0; round < rounds; round++)
    for (unsigned long c = 0; c < sizeof(counts) / sizeof(counts[0]); c++) {
     draw(program, FALSE, counts[c], MODE_THREADS);
     draw(program, FALSE, counts[c], MODE_SINGLE);
     if (c % 4 == 0) draw(program, TRUE, counts[c], MODE_THREADS);
    }
   free(program);
  }
 }
 assert(programs_used == 21 && interpreters > 0);
 assert(android_cpu_pool.workers >= 1 && parallel_draws && single_draws && immediate_draws);
 assert(written_planes && constant_attributes);
 /* the streaming limit still rejects without uploading */
 android_active_cpu_program = NULL;
 for (unsigned long s = 0; !android_active_cpu_program; s++) android_active_cpu_program = nv2a_cpu_program_create(shaders[s].words, shaders[s].count);
 struct vertex_shader_object empty = { 0 }; device.vertex_shader = &empty; gpu_used = 0;
 assert(!android_cpu_setup_vertices(0, STREAM_BUFFER_SIZE / ANDROID_CPU_VERTEX_BYTES + 1, NULL) && rejected == 1 && !gpu_used);
 printf("PASS: %lu vertices bit-identical to the reference across %lu skeletal programs and %lu interpreter fallbacks; "
  "%lu parallel draws on %lu workers, %lu single-thread, %lu immediate; %lu attribute planes, %lu constant attributes\n",
  checked_vertices, programs_used, interpreters, parallel_draws, android_cpu_pool.workers, single_draws, immediate_draws,
  written_planes, constant_attributes);
 return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='halo-cpu-parallel-') as name:
    tmp = Path(os.environ.get('HALO_TEST_KEEP') or name)
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / 'xgpu.h').write_text(
        '#include <stdint.h>\n#include <stdlib.h>\n'
        '#define HALO_ANDROID 1\n#define TRUE 1\n#define FALSE 0\ntypedef uint32_t DWORD;\ntypedef int BOOL;\n'
        '#define XGPU_VERTEX_ATTRIBUTE_COUNT 16\n#define XGPU_VERTEX_CONSTANT_COUNT 192\n#define XGPU_VERTEX_CONSTANT_BIAS 96\n'
        'struct xgpu_capabilities { const char *shading_language; };\nextern struct xgpu_capabilities xgpu_capabilities;\n'
        'struct xgpu_text { char *buffer; unsigned long length,capacity; };\nvoid xgpu_text_append(struct xgpu_text *,const char *,...);\n'
        + formats + '\n' + api)
    shutil.copyfile(ROOT / 'port/linux/src/nv2a_vsh.c', tmp / 'nv2a_vsh.c')
    shutil.copyfile(ROOT / 'port/linux/src/nv2a_cpu_shaders.inc', tmp / 'nv2a_cpu_shaders.inc')
    (tmp / 'text.c').write_text(r'''#include <stdarg.h>
#include <stdio.h>
#include "xgpu.h"
struct xgpu_capabilities xgpu_capabilities = { "310 es" };
void xgpu_text_append(struct xgpu_text *t, const char *f, ...) { (void)t; (void)f; }
''')
    (tmp / 'test.c').write_text(PREFIX + production + SUFFIX)
    builds = [
        ('optimized', ['-O2'], '6'),
        ('address/undefined sanitizers', ['-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all'], '1'),
        ('thread sanitizer', ['-O1', '-g', '-fsanitize=thread'], '1'),
    ]
    for label, flags, rounds in builds:
        binary = tmp / ('test-' + label.split()[0].replace('/', '-'))
        subprocess.run(['cc', '-std=gnu11', '-ffp-contract=off', '-Wall', '-Wno-unused-function',
                        '-Wno-unused-variable', *flags, '-I', str(tmp), str(tmp / 'test.c'), str(tmp / 'nv2a_vsh.c'),
                        str(tmp / 'text.c'), '-pthread', '-lm', '-o', str(binary)], check=True)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0', TSAN_OPTIONS='halt_on_error=1')
        result = subprocess.run([str(binary), rounds], timeout=600, env=env, text=True, capture_output=True)
        if result.returncode:
            print(result.stdout + result.stderr[-6000:])
            raise SystemExit(f"FAIL: {label}")
        print(f'{label}: {result.stdout.strip()}')
