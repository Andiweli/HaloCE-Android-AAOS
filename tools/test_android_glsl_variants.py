#!/usr/bin/env python3
"""Validate the GLSL of the NVIDIA Shield performance test's shader variants.

For every skeletal program of the game's vertex shader payload, the
production code (port/linux/src/d3d8_gl.c android_constant_block_shader,
port/linux/src/nv2a_vsh.c) writes the original GLSL, the GPU test variant A
with c[] as a std140 uniform block, and the CPU skinning passthrough, for
OpenGL ES 3.0 and 3.1. glslangValidator (Khronos reference compiler) must
accept all of them; the variant must differ from the original only in the
declaration of c[]. Driver-specific behaviour is not tested here.

Usage: test_android_glsl_variants.py [--glslang PATH]
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from android_cpu_shader_generate import programs  # noqa: E402
from test_upstream_optimizations import function  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('--glslang', default=shutil.which('glslangValidator'))
args = parser.parse_args()
if not args.glslang:
    raise SystemExit('glslangValidator not found (pass --glslang)')

source = (ROOT / 'port/linux/src/d3d8_gl.c').read_text()
header = (ROOT / 'port/linux/src/xgpu.h').read_text()
api = header[header.index('struct nv2a_cpu_program;'):header.index('#endif', header.index('struct nv2a_cpu_program;'))]
xdk = (ROOT / 'port/include/xdk/xdk_d3d8.h').read_text()
formats = '\n'.join(re.findall(r'^#define D3DVSDT_\w+ .*$', xdk, re.M))
shaders = [code for _, code in programs()]
words = ',\n'.join('{%d,{%s}}' % (len(code) // 4, ','.join('0x%08xU' % w for w in code)) for code in shaders)

harness = r'''
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "xgpu.h"
typedef unsigned GLuint, GLenum;
#define GL_VERTEX_SHADER 1
struct xgpu_capabilities xgpu_capabilities;
void xgpu_text_append(struct xgpu_text *t, const char *f, ...) {
 va_list a, b; va_start(a, f); va_copy(b, a); int n = vsnprintf(NULL, 0, f, a); va_end(a);
 if (t->length + n + 1 > t->capacity) { t->capacity = (t->length + n + 1) * 2; t->buffer = realloc(t->buffer, t->capacity); }
 vsnprintf(t->buffer + t->length, t->capacity - t->length, f, b); va_end(b); t->length += n;
}
struct vertex_shader_object { unsigned long id, instruction_count, packed_mask; DWORD *instructions; GLuint block_shader[2]; BOOL block_attempted[2]; };
static struct { struct vertex_shader_object *vertex_shader; } device;
static const char *folder; static char name[512]; static GLuint written;
static void platform_log(const char *f, ...) { (void)f; }
static GLuint compile_shader(GLenum type, const char *text, const char *label) {
 (void)type; (void)label; FILE *file = fopen(name, "w"); fputs(text, file); fclose(file); return ++written;
}
''' + function(source, 'android_constant_block_shader') + r'''
static const struct { unsigned long count; DWORD words[400]; } shaders[] = {
''' + words + r'''
};
static void save(const char *path, char *text) { FILE *file = fopen(path, "w"); fputs(text, file); fclose(file); free(text); }
int main(int argc, char **argv) {
 folder = argv[1];
 const char *languages[] = { "300 es", "310 es" };
 unsigned skeletal = 0;
 for (unsigned l = 0; l < 2; l++) {
  xgpu_capabilities.shading_language = languages[l];
  char path[512];
  snprintf(path, sizeof(path), "%s/passthrough-%u.vert", folder, l); save(path, nv2a_cpu_vertex_glsl());
  for (unsigned s = 0; s < sizeof(shaders) / sizeof(shaders[0]); s++) {
   struct nv2a_cpu_program *p = nv2a_cpu_program_create(shaders[s].words, shaders[s].count);
   if (!p) continue;
   free(p); if (!l) skeletal++;
   /* the packed normals of a model declaration, and immediate mode (none) */
   for (unsigned v = 0; v < 2; v++) {
    unsigned long packed = v ? 0 : 0xe;
    struct vertex_shader_object object = { s, shaders[s].count, packed, (DWORD *)shaders[s].words, { 0 }, { 0 } };
    struct vertex_shader_object declaration = object;
    device.vertex_shader = &declaration;
    snprintf(path, sizeof(path), "%s/original-%u-%u-%u.vert", folder, l, s, v);
    save(path, nv2a_vertex_shader_to_glsl(shaders[s].words, shaders[s].count, packed));
    snprintf(name, sizeof(name), "%s/block-%u-%u-%u.vert", folder, l, s, v);
    if (!android_constant_block_shader(&object, (int)v, v != 0)) return 2;
   }
  }
 }
 printf("%u\n", skeletal);
 return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='halo-glsl-variants-') as name:
    tmp = Path(name)
    (tmp / 'xgpu.h').write_text(
        '#include <stdint.h>\n#include <stdlib.h>\n'
        '#define HALO_ANDROID 1\n#define TRUE 1\n#define FALSE 0\ntypedef uint32_t DWORD;\ntypedef int BOOL;\n'
        '#define XGPU_VERTEX_ATTRIBUTE_COUNT 16\n#define XGPU_VERTEX_CONSTANT_COUNT 192\n#define XGPU_VERTEX_CONSTANT_BIAS 96\n'
        'struct xgpu_capabilities { const char *shading_language; };\nextern struct xgpu_capabilities xgpu_capabilities;\n'
        'struct xgpu_text { char *buffer; unsigned long length,capacity; };\n'
        'void xgpu_text_append(struct xgpu_text *,const char *,...);\n'
        'char *nv2a_vertex_shader_to_glsl(const DWORD *, unsigned long, unsigned long);\n' + formats + '\n' + api)
    for file in ('nv2a_vsh.c', 'nv2a_cpu_shaders.inc'):
        shutil.copyfile(ROOT / 'port/linux/src' / file, tmp / file)
    (tmp / 'test.c').write_text(harness)
    out = tmp / 'glsl'
    out.mkdir()
    subprocess.run(['cc', '-std=gnu11', '-O1', '-w', '-I', str(tmp), str(tmp / 'test.c'), str(tmp / 'nv2a_vsh.c'),
                    '-lm', '-o', str(tmp / 'test')], check=True)
    skeletal = int(subprocess.run([str(tmp / 'test'), str(out)], check=True, capture_output=True, text=True).stdout)
    files = sorted(out.glob('*.vert'))
    blocks = [f for f in files if f.name.startswith('block-')]
    assert skeletal == 21 and len(blocks) == 2 * 2 * skeletal, (skeletal, len(blocks))
    for block in blocks:
        original = (out / block.name.replace('block-', 'original-')).read_text()
        text = block.read_text()
        assert 'uniform vec4 c[192];' in original and 'uniform vec4 c[192];' not in text
        assert text.replace('layout(std140) uniform nv2a_constant_block\n{\n\tvec4 c[192];\n};\n',
                            'uniform vec4 c[192];\n') == original, block.name
    failed = []
    for file in files:
        result = subprocess.run([args.glslang, '-S', 'vert', str(file)], capture_output=True, text=True)
        if result.returncode:
            failed.append(f'{file.name}: {result.stdout.strip()} {result.stderr.strip()}')
    if failed:
        print('\n'.join(failed[:20]))
        raise SystemExit(f'FAIL: {len(failed)} of {len(files)} shaders rejected')
    print(f'PASS: {len(files)} vertex shaders accepted by glslangValidator (ES 3.0 and 3.1): '
          f'{len(blocks)} uniform-block variants of {skeletal} skeletal programs differ from the original '
          'only in the declaration of c[], plus originals and the CPU passthrough.')
