"""Run the real footer scanner/UV renderer against an original Xbox ui.map.
Usage: python tools/test_android_keyboard_bitmap.py /path/to/ui.map
The input map is read-only; no copyrighted map data is distributed by this test.
"""
import pathlib,struct,zlib,subprocess,tempfile,sys
root=pathlib.Path(__file__).resolve().parents[1]
data=pathlib.Path(sys.argv[1]).read_bytes()
if len(data)<struct.unpack_from('<I',data,8)[0]:data=data[:2048]+zlib.decompress(data[2048:])
toff=struct.unpack_from('<I',data,16)[0];base=0x803a6000
u=lambda p:struct.unpack_from('<I',data,p)[0]
ptr=lambda p:p-base+toff
for i in range(u(toff+12)):
 p=toff+36+i*32;n=ptr(u(p+16));name=data[n:data.index(0,n)]
 if data[p:p+4]==b'mtib' and name==b'ui\\bkd_virtual_keyboard':
  d=ptr(u(p+20));b=ptr(u(d+100));break
else:raise SystemExit('keyboard bitmap missing')
w,h=struct.unpack_from('<2h',data,b+4);fmt=struct.unpack_from('<h',data,b+12)[0];off,size=struct.unpack_from('<2I',data,b+24)
c=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
typedef float real;
#define TRUE 1
#define FALSE 0
struct bitmap_data {short width,height,format;long pixels_offset;void *base_address;};
typedef struct {short y0,x0,y1,x1;} rectangle2d;
struct vec {float i,j;};
struct rasterizer_dynamic_screen_geometry_parameters {struct bitmap_data *map[3];struct vec map_scale[3],map_texture_scale[3];};
struct dynamic_screen_vertex {unsigned long color;struct {float x,y;}position,texture_coordinates;};
static int strips;
static void rasterizer_psuedo_dynamic_screen_quad_draw(void *p,struct dynamic_screen_vertex *v) {
 strips++;printf("%.0f %.0f %.0f %.0f %.0f %.0f\n",v[0].position.x,v[0].position.y,v[2].position.x,v[2].position.y,v[0].texture_coordinates.x*1024,v[2].texture_coordinates.x*1024);
}
static void *_texture_cache_bitmap_get_hardware_format(void *p,int a,int b){return p;}
static void draw_bitmap_in_rect(void *a,void *b,void *c,void *d,unsigned long e,void *f,int g){assert(!"scanner did not find bitmap equals");}
'''
with tempfile.TemporaryDirectory() as td:
 t=pathlib.Path(td);(t/'pixels').write_bytes(data[off:off+size])
 c+='\n#include "'+str(root/'source/interface/android_keyboard_background.inc')+'"\n'
 c+=f'''int main(int argc,char **argv){{struct bitmap_data b={{{w},{h},{fmt},{off},NULL}};
 b.base_address=malloc({size});FILE *f=fopen(argv[1],"rb");assert(fread(b.base_address,1,{size},f)=={size});fclose(f);
 android_draw_keyboard_background(&b);assert(strips==7);return 0;}}'''
 (t/'test.c').write_text(c);subprocess.run(['cc','-Wall','-Wextra','-Wno-unused-parameter',str(t/'test.c'),'-o',str(t/'test')],check=True)
 result=subprocess.check_output([str(t/'test'),str(t/'pixels')],text=True)
 strips=[list(map(int,l.split())) for l in result.splitlines()]
 holes=[s for s in strips if s[4:]==[20,21]]
 assert len(holes)==2 and all(s[1]==412 and s[3]==442 for s in holes),holes
 assert 392<=holes[0][0]<=395 and 402<=holes[0][2]<=406,holes
 assert 493<=holes[1][0]<=496 and 503<=holes[1][2]<=507,holes
 print('Real-map keyboard test passed; only equals strips resampled:',holes)
