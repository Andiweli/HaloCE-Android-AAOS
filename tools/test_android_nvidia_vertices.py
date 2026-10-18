"""Exercise production vertex setup with strict, recorded GL calls.

This is a CPU regression test, not a reproduction of the Shield driver.
It checks the NVIDIA selector and both paths with multiple streams, packed
normals, bone indices, normalized weights and changed draw offsets.
"""
from pathlib import Path
import re
import subprocess
import tempfile

from test_upstream_optimizations import block, function

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "port/linux/src/d3d8_gl.c").read_text()
assert "vertex_bindings_supported = android_use_vertex_bindings(major, minor, vendor, renderer);" in source
types = sorted(set(re.findall(r"\bD3DVSDT_\w+", function(source, "attribute_format"))))
types = ["D3DVSDT_NONE", "D3DVSDT_NORMPACKED3"] + [name for name in types if name != "D3DVSDT_NONE"]
prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef unsigned GLuint, GLenum;
typedef int GLint, GLsizei, BOOL;
typedef unsigned char GLboolean;
typedef intptr_t GLintptr;
#define TRUE 1
#define FALSE 0
#define GL_TRUE 1
#define GL_FALSE 0
#define GL_FLOAT 1
#define GL_UNSIGNED_BYTE 2
#define GL_SHORT 3
#define GL_UNSIGNED_INT 4
#define HALO_ANDROID 1
#define XGPU_VERTEX_ATTRIBUTE_COUNT 16
#define VERTEX_BINDING_COUNT 16
#define PLATFORM_PHYSICAL_TO_VIRTUAL(x) ((void *)(uintptr_t)(x))
'''
prefix += "enum { " + ", ".join(types) + " };\n"
for name in ("attribute_format", "vertex_binding", "attribute_pointer"):
    prefix += block(source, "struct " + name + "\n", True) + "\n"
prefix += r'''
static struct {
 struct vertex_binding vertex_bindings[16];
 struct attribute_format attribute_formats[16];
 struct attribute_pointer attribute_pointers[16];
 unsigned char attribute_enabled[16], attribute_value_kind[16];
 float attribute_values[16][4];
} gl_state;
struct vertex_element { unsigned long stream, reg, type, offset; };
struct vertex_shader_object { unsigned long element_count, packed_mask; struct vertex_element elements[16]; };
static struct {
 struct vertex_shader_object *vertex_shader;
 struct { unsigned long data, stride; } streams[16];
 GLuint stream_buffer;
 float attributes[16][4];
} device;
static struct { unsigned long streamed_bytes; } stats;
static BOOL vertex_bindings_supported;
static unsigned char gpu_bytes[4096];
static unsigned long upload_offset;
static int binding_calls, pointer_calls, upload_calls;
static GLuint current_buffer;
static struct {
 struct vertex_binding bindings[16];
 struct attribute_format formats[16];
 struct attribute_pointer pointers[16];
 unsigned char enabled[16];
} actual;
static void state_array_buffer(GLuint buffer) { current_buffer = buffer; }
static void glBindVertexBuffer(GLuint i, GLuint b, GLintptr o, GLsizei s) {
 assert(i < 16 && b == device.stream_buffer && o >= 0 && s >= 0);
 actual.bindings[i] = (struct vertex_binding){b, (unsigned long)o, s}; binding_calls++;
}
static void glEnableVertexAttribArray(GLuint i) { assert(i < 16); actual.enabled[i] = 1; }
static void glDisableVertexAttribArray(GLuint i) { assert(i < 16); actual.enabled[i] = 0; }
static void glVertexAttribFormat(GLuint i, GLint s, GLenum t, GLboolean n, GLuint o) {
 actual.formats[i].size=s; actual.formats[i].type=t; actual.formats[i].normalized=n;
 actual.formats[i].relative_offset=o; actual.formats[i].integer=FALSE;
}
static void glVertexAttribIFormat(GLuint i, GLint s, GLenum t, GLuint o) {
 glVertexAttribFormat(i,s,t,FALSE,o); actual.formats[i].integer=TRUE;
}
static void glVertexAttribBinding(GLuint i, GLuint b) { assert(b < 16); actual.formats[i].binding=b; }
static void glVertexAttribPointer(GLuint i, GLint s, GLenum t, GLboolean n, GLsizei stride, const void *p) {
 assert(current_buffer == device.stream_buffer);
 actual.pointers[i]=(struct attribute_pointer){current_buffer,s,t,n,FALSE,stride,(uintptr_t)p}; pointer_calls++;
}
static void glVertexAttribIPointer(GLuint i, GLint s, GLenum t, GLsizei stride, const void *p) {
 glVertexAttribPointer(i,s,t,FALSE,stride,p); actual.pointers[i].integer=TRUE;
}
static void glVertexAttrib4fv(GLuint i, const float *v) { (void)i; (void)v; }
static void glVertexAttribI4ui(GLuint i, GLuint a, GLuint b, GLuint c, GLuint d) {
 (void)i; assert(!a && !b && !c && !d);
}
static BOOL mirror_range(unsigned long a, unsigned long n, GLuint *b, unsigned long *o, void *p) {
 (void)a; (void)n; (void)b; (void)o; (void)p; return FALSE;
}
static void stream_reserve(unsigned long bytes) { assert(upload_offset + bytes <= sizeof(gpu_bytes)); }
static unsigned long stream_upload_swizzled(const struct vertex_shader_object *d, unsigned long s,
 const unsigned char *bytes, unsigned long size, unsigned long stride) {
 (void)d; (void)s; (void)stride; unsigned long offset=upload_offset;
 assert(offset + size <= sizeof(gpu_bytes)); memcpy(gpu_bytes + offset, bytes, size);
 upload_offset += (size + 15) & ~15UL; upload_calls++; return offset;
}
'''
production = "\n".join(function(source, name) for name in (
    "android_is_nvidia", "android_use_vertex_bindings", "state_vertex_buffer",
    "state_attribute_format", "state_attribute_pointer", "state_attribute_value",
    "attribute_format", "stream_has_colors", "setup_streams",
))
suffix = r'''
static const unsigned char *fetch(unsigned a, unsigned v) {
 assert(actual.enabled[a]); unsigned long offset;
 if (vertex_bindings_supported) {
  struct attribute_format *f=&actual.formats[a]; struct vertex_binding *b=&actual.bindings[f->binding];
  offset=b->offset+f->relative_offset+v*b->stride;
 } else {
  struct attribute_pointer *p=&actual.pointers[a]; offset=p->offset+v*p->stride;
 }
 assert(offset < sizeof(gpu_bytes)); return gpu_bytes+offset;
}
static void check_path(const char *vendor, const char *renderer, int minor, BOOL bindings) {
 struct { float position[3]; uint32_t normal; } vertices[10];
 struct { int16_t bones[2]; unsigned char weights[2], padding[2]; } skin[10];
 for (unsigned i=0;i<10;i++) {
  vertices[i].position[0]=i+0.25f; vertices[i].position[1]=i+10.5f; vertices[i].position[2]=i+30.75f;
  vertices[i].normal=0xf0123400+i;
  skin[i].bones[0]=i+2; skin[i].bones[1]=i+3;
  skin[i].weights[0]=128+i; skin[i].weights[1]=127-i;
 }
 struct vertex_shader_object declaration={0}; declaration.element_count=4; declaration.packed_mask=2;
 declaration.elements[0]=(struct vertex_element){0,0,D3DVSDT_FLOAT3,0};
 declaration.elements[1]=(struct vertex_element){0,1,D3DVSDT_NORMPACKED3,12};
 declaration.elements[2]=(struct vertex_element){1,2,D3DVSDT_SHORT2,0};
 declaration.elements[3]=(struct vertex_element){1,3,D3DVSDT_PBYTE2,4};
 memset(&device,0,sizeof(device)); memset(&actual,0,sizeof(actual)); memset(&gl_state,255,sizeof(gl_state));
 device.vertex_shader=&declaration; device.stream_buffer=17;
 device.streams[0].data=(uintptr_t)vertices; device.streams[0].stride=sizeof(vertices[0]);
 device.streams[1].data=(uintptr_t)skin; device.streams[1].stride=sizeof(skin[0]);
 for (unsigned i=0;i<16;i++) device.attributes[i][3]=1.0f;
 upload_offset=0; binding_calls=pointer_calls=upload_calls=0;
 vertex_bindings_supported=android_use_vertex_bindings(3,minor,vendor,renderer);
 assert(vertex_bindings_supported==bindings);
 for (unsigned first=2;first<=3;first++) {
  setup_streams(first,4);
  for (unsigned v=0;v<4;v++) {
   assert(!memcmp(fetch(0,v),vertices[first+v].position,12));
   assert(!memcmp(fetch(1,v),&vertices[first+v].normal,4));
   assert(!memcmp(fetch(2,v),skin[first+v].bones,4));
   assert(!memcmp(fetch(3,v),skin[first+v].weights,2));
  }
  for (unsigned i=4;i<16;i++) assert(!actual.enabled[i]);
 }
 assert(upload_calls==4);
 if (bindings) {
  assert(binding_calls==4 && pointer_calls==0);
  assert(actual.formats[1].integer && actual.formats[3].normalized);
 } else {
  assert(binding_calls==0 && pointer_calls==8);
  assert(actual.pointers[1].integer && actual.pointers[3].normalized);
 }
}
int main(void) {
 check_path("NVIDIA Corporation","NVIDIA Tegra",2,FALSE);
 check_path(NULL,"NVIDIA Tegra",2,FALSE);
 check_path("NVIDIA",NULL,1,FALSE);
 check_path("Qualcomm","Adreno (TM) 650",2,TRUE);
 check_path("ARM","Mali-G78",1,TRUE);
 check_path("Qualcomm","Adreno",0,FALSE);
 check_path(NULL,NULL,2,TRUE);
 assert(!android_use_vertex_bindings(2,0,NULL,NULL));
 assert(android_use_vertex_bindings(4,0,"Qualcomm",NULL));
 puts("NVIDIA vertex compatibility: seven production stream cases passed; packed normals, bone indices, weights and draw offsets preserved.");
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="halo-nvidia-vertices-") as temp:
    folder = Path(temp)
    cfile, binary = folder / "vertices.c", folder / "vertices"
    cfile.write_text(prefix + production + suffix)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(cfile), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
