#!/usr/bin/env python3
"""Compare every fixed CPU executor with the retained interpreter.

The four-vertex executors (NEON lanes) must give the same bits as the
one-vertex executors, for every group of four and a remainder.

Uses the complete original microcode payload, randomized inputs/constants,
changed draw constants and addressing boundaries. --gles additionally creates
a synthetic capture and runs the existing real GLES transform-feedback check.
The benchmark is a host comparison, not a Shield FPS measurement.
"""
from pathlib import Path
import argparse
import ctypes as C
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile, ZIP_DEFLATED
import numpy as np
from android_cpu_shader_generate import programs, supported

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--gles', action='store_true')
parser.add_argument('--output', type=Path)
parser.add_argument('--native-images', type=Path, nargs='+',
                    help='Additionally execute the built arm64_32 CPU path with Unicorn and pyelftools.')
args = parser.parse_args()


class NativeExecutor:
    """Run the actual linked guest function, including its viewport conversion."""
    def __init__(self, path):
        import io
        from elftools.elf.elffile import ELFFile
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
        from unicorn import arm64_const as regs
        self.regs = regs
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        elf = ELFFile(io.BytesIO(path.read_bytes()))
        self.symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        low = min(s['p_vaddr'] for s in segments) & ~4095
        high = (max(s['p_vaddr'] + s['p_memsz'] for s in segments) + 4095) & ~4095
        assert high - low <= 0x01000000 and high < 0x100000000, path
        self.uc.mem_map(low, high - low)
        for s in segments:
            self.uc.mem_write(s['p_vaddr'], s.data())
        self.uc.mem_map(0x01000000, 0x20000)
        self.uc.mem_map(0x10000000, 0x20000)

    def execute(self, ordinal, count, inputs, constants, scale, offset, screen, size, quad=False):
        """One vertex (inputs [16][4]), or four at once (inputs [4][16][4])."""
        import struct
        r, uc = self.regs, self.uc
        # The arm64_32 program starts with count, prepared, the executor and
        # the four-vertex executor: four 32-bit fields. Their fixed branches
        # do not read the interpreter array.
        uc.mem_write(0x01000000, struct.pack('<IIII', count, 0, self.symbols[f'cpu_fast_{ordinal}'],
                                             self.symbols[f'cpu_fast4_{ordinal}']))
        for address, data in [(0x01000100, inputs), (0x01001000, constants),
                              (0x01002000, scale), (0x01002010, offset)]:
            uc.mem_write(address, data.tobytes())
        for reg, address in [(r.UC_ARM64_REG_X0, 0x01000000), (r.UC_ARM64_REG_X1, 0x01000100),
                             (r.UC_ARM64_REG_X2, 0x01001000), (r.UC_ARM64_REG_X3, 0x01002000),
                             (r.UC_ARM64_REG_X4, 0x01002010), (r.UC_ARM64_REG_X5, 0x01003000),
                             (r.UC_ARM64_REG_SP, 0x1001f000), (r.UC_ARM64_REG_LR, 0x70000000)]:
            uc.reg_write(reg, address)
        uc.reg_write(r.UC_ARM64_REG_S0, struct.unpack('<I', struct.pack('<f', screen))[0])
        uc.reg_write(r.UC_ARM64_REG_S1, struct.unpack('<I', struct.pack('<f', size))[0])
        uc.emu_start(self.symbols['nv2a_cpu_vertex_execute4' if quad else 'nv2a_cpu_vertex_execute'],
                     0x70000000, count=200000)
        assert uc.reg_read(r.UC_ARM64_REG_PC) == 0x70000000
        return np.frombuffer(bytes(uc.mem_read(0x01003000, 640 if quad else 160)),
                             dtype='<f4').reshape(4 if quad else 1, 40).squeeze()


def bits(values):
    """the bits of each float, every NaN alike (whichever NaN two NaNs give)"""
    result = values.view(np.uint32).copy()
    result[np.isnan(values)] = 0x7fc00000
    return result

header = (ROOT / 'port/linux/src/xgpu.h').read_text()
api = header[header.index('struct nv2a_cpu_program;'):header.index('#endif', header.index('struct nv2a_cpu_program;'))]
xdk = (ROOT / 'port/include/xdk/xdk_d3d8.h').read_text()
formats = '\n'.join(re.findall(r'^#define D3DVSDT_\w+ .*$', xdk, re.M))
prefix = ('#include <stdint.h>\n#include <stdlib.h>\n#include <stdarg.h>\n'
          '#define HALO_ANDROID 1\n#define TRUE 1\n#define FALSE 0\n'
          'typedef uint32_t DWORD; typedef int BOOL;\n'
          '#define XGPU_VERTEX_ATTRIBUTE_COUNT 16\n#define XGPU_VERTEX_CONSTANT_COUNT 192\n'
          '#define XGPU_VERTEX_CONSTANT_BIAS 96\n'
          'struct xgpu_capabilities { const char *shading_language; };\n'
          'extern struct xgpu_capabilities xgpu_capabilities;\n'
          'struct xgpu_text { char *buffer; unsigned long length, capacity; };\n'
          'void xgpu_text_append(struct xgpu_text *,const char *,...);\n' + formats + '\n' + api)
bridge = r'''
#include <stdio.h>
#include "nv2a_vsh.c"
struct xgpu_capabilities xgpu_capabilities={"310 es"};
void xgpu_text_append(struct xgpu_text *t,const char *f,...){
 va_list a,b;va_start(a,f);va_copy(b,a);int n=vsnprintf(NULL,0,f,a);va_end(a);
 if(t->length+n+1>t->capacity){t->capacity=(t->length+n+1)*2;t->buffer=realloc(t->buffer,t->capacity);}
 vsnprintf(t->buffer+t->length,t->capacity-t->length,f,b);va_end(b);t->length+=n;
}
void *make(const DWORD *w,unsigned long n,int fixed){
 struct nv2a_cpu_program *p=nv2a_cpu_program_create(w,n);
 if(p && !fixed)p->execute=NULL,p->execute4=NULL;
 return p;
}
/* groups of four as the renderer runs them, then the remainder one by one */
void batch4(struct nv2a_cpu_program *p,const float (*v)[16][4],const float c[192][4],
 const float s[4],const float o[4],float x,float size,unsigned n,struct nv2a_cpu_vertex *out){
 unsigned i=0;
 nv2a_cpu_program_prepare_constants(p,c);
 for(;i+4<=n;i+=4)nv2a_cpu_vertex_execute4(p,v+i,c,s,o,x,size,out+i);
 for(;i<n;i++)nv2a_cpu_vertex_execute(p,v[i],c,s,o,x,size,&out[i]);
}
void batch(struct nv2a_cpu_program *p,const float (*v)[16][4],const float c[192][4],
 const float s[4],const float o[4],float x,float size,unsigned n,struct nv2a_cpu_vertex *out){
 nv2a_cpu_program_prepare_constants(p,c);
 for(unsigned i=0;i<n;i++)nv2a_cpu_vertex_execute(p,v[i],c,s,o,x,size,&out[i]);
}
'''

with tempfile.TemporaryDirectory(prefix='halo-cpu-fixed-') as name:
    folder = Path(name)
    (folder / 'xgpu.h').write_text(prefix)
    (folder / 'test.c').write_text(bridge)
    for fn in ('nv2a_vsh.c', 'nv2a_cpu_shaders.inc'):
        shutil.copyfile(ROOT / 'port/linux/src' / fn, folder / fn)
    lib = folder / 'test.so'
    # (gcc may swap fminf/fmaxf arguments in one path; see test_android_cpu_parallel.py)
    subprocess.run(['cc', '-std=gnu11', '-O2', '-ffp-contract=off', '-fno-builtin-fminf', '-fno-builtin-fmaxf',
                    '-fPIC', '-shared',
                    str(folder / 'test.c'), '-lm', '-o', str(lib)], check=True)
    production = C.CDLL(str(lib))
    P, F, U = C.c_void_p, C.c_float, C.c_uint
    production.make.argtypes = [P, C.c_ulong, C.c_int]
    production.make.restype = P
    production.nv2a_cpu_program_is_specialized.argtypes = [P]
    production.batch.argtypes = [P, P, P, P, P, F, F, U, P]
    production.batch4.argtypes = [P, P, P, P, P, F, F, U, P]
    production.nv2a_cpu_program_is_quad.argtypes = [P]
    production.nv2a_vertex_shader_to_glsl.argtypes = [P, C.c_ulong, C.c_ulong]
    production.nv2a_vertex_shader_to_glsl.restype = P
    libc = C.CDLL(None)
    libc.free.argtypes = [P]
    rng = np.random.default_rng(0x534849454c44)
    summary = {'programs': 0, 'vertices': 0, 'host_interpreter_ms': 0.0, 'host_fixed_ms': 0.0, 'host_quad_ms': 0.0,
               'unknown_fallbacks': 0, 'scalar_outputs_per_vertex': 40}
    native = [NativeExecutor(p) for p in args.native_images or []]
    if native:
        summary['native_images'] = len(native)
        summary['native_vertices'] = 0
    report, captured = [], []

    def batch(p, v, c, scale, offset, screen, size, quad=False):
        out = np.zeros((len(v), 40), dtype=np.float32)
        (production.batch4 if quad else production.batch)(
            p, v.ctypes.data, c.ctypes.data, scale.ctypes.data, offset.ctypes.data,
            screen, size, len(v), out.ctypes.data)
        return out

    for ordinal, code in programs():
        words = np.asarray(code, dtype=np.uint32)
        fast = production.make(words.ctypes.data, len(code) // 4, 1)
        if not supported(code):
            assert not fast, ('non-skeletal accepted', ordinal)
            continue
        assert fast and production.nv2a_cpu_program_is_specialized(fast), ordinal
        assert production.nv2a_cpu_program_is_quad(fast), ordinal
        slow = production.make(words.ctypes.data, len(code) // 4, 0)
        assert slow and not production.nv2a_cpu_program_is_specialized(slow)
        assert not production.nv2a_cpu_program_is_quad(slow)
        # word 0 is ignored by the interpreter but still part of the exact
        # match. An unfamiliar equivalent program must safely fall back.
        unknown_words = words.copy()
        unknown_words[0] ^= np.uint32(0x100)
        unknown = production.make(unknown_words.ctypes.data, len(code) // 4, 1)
        assert unknown and not production.nv2a_cpu_program_is_specialized(unknown)
        for trial in range(4):
            v = rng.uniform(-1, 1, (512, 16, 4)).astype(np.float32)
            v[:, :, 3] = 1
            v[:, 5, :2] = rng.integers(0, 40, (512, 2)) * np.float32(3 / 255)
            v[:, 6, 0] = rng.uniform(0, 1, 512)
            c = rng.uniform(-2, 2, (192, 4)).astype(np.float32)
            c[7, 3] = 255
            c[58] = [320, -240, 1, 1]
            c[59] = [320, 240, 0, 0]
            scale = np.asarray([320, -240, 1, 1] if trial % 2 else [640, -360, 2, 1], dtype=np.float32)
            offset = np.asarray([320, 240, 0, 0], dtype=np.float32)
            screen, size = (0.25 if trial % 2 else 0.0), (3 if trial % 2 else 1)
            if trial == 2:
                # Address-rounding boundaries and saturation, including
                # nonfinite node input. No undefined C float-to-int cast.
                v[:8, 5, 0] = [-4, -0.001, 0, 0.001, 191, 255, np.inf, np.nan]
                scale[:3] = 0
            if trial == 1:
                # different bones in each lane, beyond both ends of c[] too
                v[:, 5, 0] = rng.integers(-8, 70, 512) * np.float32(3)
            expected = batch(slow, v, c, scale, offset, screen, size)
            actual = batch(fast, v, c, scale, offset, screen, size)
            fallback = batch(unknown, v, c, scale, offset, screen, size)
            # 511: 127 groups of four and a remainder of three
            quad = batch(fast, v[:511], c, scale, offset, screen, size, quad=True)
            quad_fallback = batch(slow, v[:511], c, scale, offset, screen, size, quad=True)
            assert np.array_equal(actual, expected, equal_nan=True), (ordinal, trial, 'fixed differs')
            assert np.array_equal(fallback, expected, equal_nan=True), (ordinal, trial, 'fallback differs')
            assert np.array_equal(quad.view(np.uint32), actual[:511].view(np.uint32)), (ordinal, trial, 'four lanes differ')
            assert np.array_equal(quad_fallback, expected[:511], equal_nan=True), (ordinal, trial, 'interpreter by four differs')
            summary['quad_vertices'] = summary.get('quad_vertices', 0) + 511
            summary['vertices'] += len(v)
            if trial == 0:
                for image in native:
                    for vi in range(8):
                        native_result = image.execute(ordinal, len(code) // 4, v[vi], c, scale, offset, screen, size)
                        assert np.array_equal(native_result, expected[vi], equal_nan=True), (ordinal, vi, 'native ELF differs')
                        summary['native_vertices'] += 1
                    # four at once in the NEON lanes: the bits of the one-vertex
                    # native executor, signed zeros included
                    # a third of the inputs +0 or -0: max(+0, -0) and the like
                    zeros = np.where(rng.random((32, 16, 4)) < 0.5, np.float32(0.0), np.float32(-0.0))
                    vz = np.where(rng.random((32, 16, 4)) < 0.3, zeros, v[:32]).astype(np.float32)
                    for vi in range(0, 32, 4):
                        lanes = image.execute(ordinal, len(code) // 4, vz[vi:vi + 4], c, scale, offset, screen, size, True)
                        for lane in range(4):
                            single = image.execute(ordinal, len(code) // 4, vz[vi + lane], c, scale, offset, screen, size)
                            assert np.array_equal(bits(lanes[lane]), bits(single)), (ordinal, vi + lane, 'native NEON lanes differ')
                        summary['native_quad_vertices'] = summary.get('native_quad_vertices', 0) + 4
                # A deterministic shader/data capture for the independent
                # existing real-GLES test; these are synthetic, not Shield dumps.
                pointer = production.nv2a_vertex_shader_to_glsl(words.ctypes.data, len(code) // 4, 0)
                text = C.string_at(pointer).decode()
                libc.free(pointer)
                report += [f'DRAW {ordinal} program={ordinal}', '  VERTEX_RANGE 0..511']
                for a in range(16):
                    report.append(f'  ATTR {a} enabled=1 size=4 type=0x1406 normalized=0 integer=0 stride=16')
                    captured.append((f'draw-{ordinal:04d}-attr-{a}.bin', v[:, a].copy().tobytes()))
                for k in range(192):
                    report.append(f'  U c[{k}] location={k} type=0x8b52 ' + ' '.join(map(str, c[k])) + ' nonfinite=0')
                for key, values in [('viewport_scale', scale), ('viewport_offset', offset), ('screen_offset', [screen]), ('point_size', [size])]:
                    report.append(f'  U {key} location=200 type=0x8b52 ' + ' '.join(map(str, values)) + ' nonfinite=0')
                captured.append((f'program-{ordinal}-shader-8b31.glsl', text.encode()))
            if trial == 3:
                times = []
                for executor, by_four in ((slow, False), (fast, False), (fast, True)):
                    samples = []
                    for _ in range(5):
                        start = time.perf_counter()
                        batch(executor, v, c, scale, offset, screen, size, by_four)
                        samples.append((time.perf_counter() - start) * 1000)
                    times.append(statistics.median(samples))
                summary['host_interpreter_ms'] += times[0]
                summary['host_fixed_ms'] += times[1]
                summary['host_quad_ms'] += times[2]
        for p in (fast, slow, unknown):
            libc.free(p)
        summary['programs'] += 1
        summary['unknown_fallbacks'] += 1
    assert summary['programs'] == 21
    summary['host_speedup'] = summary['host_interpreter_ms'] / summary['host_fixed_ms']
    if args.gles:
        capture = folder / 'synthetic-original-shaders.zip'
        with ZipFile(capture, 'w', ZIP_DEFLATED) as z:
            z.writestr('report.txt', '\n'.join(report))
            for filename, data in captured:
                z.writestr(filename, data)
        result = folder / 'gles.json'
        subprocess.run([sys.executable, str(ROOT / 'tools/test_android_cpu_skeletal.py'),
                        '--dumps', str(capture), '--output', str(result)], check=True)
        summary['gles'] = json.loads(result.read_text())
    print('PASS: all 21 skeletal programs match the interpreter across', summary['vertices'], 'vertices; all 40 outputs match.')
    print('PASS: exact matching, changed constants, address limits and 21 unknown-program fallbacks.')
    print('PASS: four-vertex executors give the bits of the one-vertex executors for',
          summary['quad_vertices'], 'vertices (groups of four and remainders), bones differing per lane.')
    print('Host-only CPU execution speedup:', round(summary['host_speedup'], 2),
          '; four at once against one at a time:', round(summary['host_fixed_ms'] / summary['host_quad_ms'], 2),
          '(not Shield FPS)')
    if native:
        print('PASS:', summary['native_vertices'], 'actual AArch64 vertices across', len(native), 'linked images match all 40 outputs exactly; Unicorn control.')
        print('PASS:', summary['native_quad_vertices'], 'AArch64 vertices four at once give the bits of one at a time (signed zeros too).')
    if args.output:
        args.output.write_text(json.dumps(summary, indent=2) + '\n')
