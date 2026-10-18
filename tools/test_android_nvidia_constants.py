"""Exercise the production translator, NVIDIA selector and compiler fallback.

Optional --ndk runs the real GLES selector against Linux Mesa. --baseline-vsh
compares the non-NVIDIA output byte-for-byte with a previous translator file.
These checks do not reproduce an NVIDIA driver or validate a Shield device.
"""
from pathlib import Path
import argparse
import ctypes
import os
import re
import subprocess
import tempfile

from test_upstream_optimizations import block, function

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--ndk", type=Path)
parser.add_argument("--baseline-vsh", type=Path)
parser.add_argument("--selector-out", type=Path)
args = parser.parse_args()
header = (ROOT / "port/linux/src/xgpu.h").read_text()
mock = "#pragma once\n#include <stdint.h>\n#include <stdlib.h>\n"
mock += "typedef int BOOL; typedef uint32_t DWORD;\n#define TRUE 1\n#define FALSE 0\n"
for name in ("XGPU_VERTEX_ATTRIBUTE_COUNT", "XGPU_VERTEX_CONSTANT_COUNT", "XGPU_VERTEX_CONSTANT_BIAS"):
    mock += re.search(r"^#define " + name + r" .*", header, re.M)[0] + "\n"
mock += block(header, "struct xgpu_text\n", True) + "\n"
mock += block(header, "struct xgpu_capabilities\n", True) + "\n"
mock += "extern struct xgpu_capabilities xgpu_capabilities;\n"
mock += 'void xgpu_text_append(struct xgpu_text *, const char *, ...) __attribute__((format(printf,2,3)));\n'
wrapper = '#include "xgpu.h"\nstruct xgpu_capabilities xgpu_capabilities;\n'
wrapper += "void test_configure(int enabled) {xgpu_capabilities.static_relative_constants=enabled;xgpu_capabilities.shading_language=\"310 es\";}\n"
with tempfile.TemporaryDirectory(prefix="halo-nvidia-constants-") as temporary:
    folder = Path(temporary)
    (folder / "xgpu.h").write_text(mock)
    (folder / "wrapper.c").write_text(wrapper)
    (folder / "xgpu_text.c").write_text((ROOT / "port/linux/src/xgpu_text.c").read_text())
    (folder / "nv2a_vsh.c").write_text((ROOT / "port/linux/src/nv2a_vsh.c").read_text())
    def build(file, name):
        output = folder / name
        subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-DHALO_ANDROID",
                        "-shared", "-fPIC", "-I" + str(folder), str(file), str(folder / "xgpu_text.c"),
                        str(folder / "wrapper.c"), "-o", str(output)], check=True)
        library = ctypes.CDLL(str(output))
        library.nv2a_vertex_shader_to_glsl.restype = ctypes.c_void_p
        library.nv2a_vertex_shader_to_glsl.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_ulong, ctypes.c_ulong]
        return library
    current = build(folder / "nv2a_vsh.c", "current.so")
    baseline = build(args.baseline_vsh, "baseline.so") if args.baseline_vsh else None
    libc = ctypes.CDLL(None)
    libc.free.argtypes = [ctypes.c_void_p]
    def generate(lib, words, enabled):
        lib.test_configure(enabled)
        array = (ctypes.c_uint32 * len(words))(*words)
        address = lib.nv2a_vertex_shader_to_glsl(array, len(words) // 4, 14)
        try:
            return ctypes.string_at(address).decode()
        finally:
            libc.free(address)
    selector = None
    cases = 0
    for relative in (0, 1):
        for operand in ("A", "B", "C", "none"):
            for offset in (0, 60, 61, 62, 191):
                words = [0, (1 << 21) | (offset << 13), 0, (15 << 24) | (relative << 1)]
                if operand == "A": words[2] |= 3 << 26
                if operand == "B": words[2] |= 3 << 11
                if operand == "C": words[3] |= 3 << 28
                original = generate(current, words, 0)
                revised = generate(current, words, 1)
                if baseline: assert original == generate(baseline, words, 0)
                if not relative or operand == "none":
                    assert revised == original
                else:
                    begin = revised.index("/* Shield matrix test 2:")
                    end = revised.index("layout(location", begin)
                    helper = revised[begin:end]
                    if selector is None: selector = helper
                    assert selector == helper
                    assert "c[clamp(a0" not in revised
                    expected = re.sub(r"c\[clamp\(a0 \+ (\d+), 0, 191\)\]", r"halo_nvidia_constant(a0 + \1)", original)
                    assert revised[:begin] + revised[end:] == expected
                    indices = re.findall(r"return c\[(\d+)\]", helper)
                    assert list(map(int, indices)) == list(range(192))
                cases += 1
    assert selector
    if args.selector_out:
        args.selector_out.parent.mkdir(parents=True, exist_ok=True)
        args.selector_out.write_text(selector)
    helper = folder / "selector.glsl"
    helper.write_text(selector)

    production = function((ROOT / "port/linux/src/d3d8_gl.c").read_text(), "vertex_shader_get")
    fixture = r'''
#define _GNU_SOURCE
#define HALO_ANDROID 1
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <stdarg.h>
typedef unsigned GLuint; typedef unsigned DWORD; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define GL_VERTEX_SHADER 0x8b31
static struct {BOOL static_relative_constants;} xgpu_capabilities;
struct vertex_shader_object {GLuint shader[2];DWORD *instructions;unsigned long instruction_count,packed_mask,id;};
static struct {struct vertex_shader_object *vertex_shader;} device;
static struct {const char *dump_shaders;} debug_settings;
static int source_calls,compile_calls,fail_first,relative_program;
static unsigned long seen_masks[2];static BOOL seen_flags[2];
static char *nv2a_vertex_shader_to_glsl(const DWORD *i,unsigned long n,unsigned long mask) {
 (void)i;(void)n;seen_masks[source_calls]=mask;seen_flags[source_calls]=xgpu_capabilities.static_relative_constants;source_calls++;
 return strdup(relative_program && xgpu_capabilities.static_relative_constants?"halo_nvidia_constant(a0 + 60)":"original");
}
static GLuint compile_shader(unsigned kind,const char *source,const char *label) {
 (void)source;(void)label;assert(kind==GL_VERTEX_SHADER);compile_calls++;
 return fail_first&&compile_calls==1?0:37;
}
static void platform_log(const char *s,...) {(void)s;}
'''
    fixture += production + r'''
int main(void) {
 struct vertex_shader_object declaration={.packed_mask=14},program={.id=2};device.vertex_shader=&declaration;
 for(int enabled=0;enabled<=1;enabled++)for(int relative=0;relative<=1;relative++)for(int fail=0;fail<=1;fail++)for(int immediate=0;immediate<=1;immediate++) {
  memset(program.shader,0,sizeof(program.shader));source_calls=compile_calls=0;fail_first=fail;relative_program=relative;
  xgpu_capabilities.static_relative_constants=enabled;
  GLuint result=vertex_shader_get(&program,immediate);
  int fallback=enabled&&relative&&fail;
  assert(source_calls==1+fallback&&compile_calls==1+fallback);
  assert(xgpu_capabilities.static_relative_constants==enabled);
  assert(result==(fail&&!fallback?0:37));assert(seen_masks[0]==(immediate?0:14));
  if(fallback)assert(!seen_flags[1]&&seen_masks[1]==seen_masks[0]);
  if(result){vertex_shader_get(&program,immediate);assert(compile_calls==1+fallback);}
 }
 puts("PASS: 16 production shader-cache/fallback cases; original packed mask and capability restored.");
}
'''
    (folder / "fallback.c").write_text(fixture)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(folder / "fallback.c"), "-o", str(folder / "fallback")], check=True)
    subprocess.run([str(folder / "fallback")], check=True)
    if args.ndk:
        headers = args.ndk / "toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include"
        binary = folder / "gles"
        subprocess.run(["cc", "-std=gnu11", "-O2", "-DUSE_OZONE", "-idirafter", str(headers),
                        str(ROOT / "tools/test_android_nvidia_constants.c"), "-Wl,-l:libEGL.so.1", "-Wl,-l:libGL.so.1", "-o", str(binary)], check=True)
        env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE="1", EGL_PLATFORM="surfaceless")
        subprocess.run([str(binary), str(helper)], env=env, check=True, timeout=45)
print(f"PASS: {cases} production translator cases; literal indices 0..191, original clamp and unchanged other-GPU output checked.")
