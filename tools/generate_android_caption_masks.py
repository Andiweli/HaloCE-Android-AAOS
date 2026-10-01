"""Rebuild graphic captions from the verified user-supplied English Xbox UI map.
Usage: python tools/generate_android_caption_masks.py ui.map [preview.png]
Requires Pillow, NumPy and SciPy. Does not write to the input map.
Latin glyph bowls/stems come from original headings; B/Q/X and diacritics are
completed in the same graphic style for the added translated captions.
"""
import struct,json
from pathlib import Path
import sys,zlib,hashlib
raw=Path(sys.argv[1]).read_bytes()
if hashlib.sha256(raw).hexdigest()!='d0fe49936eab99892a3c938372b29f126336795d7a2ea9e7647de3be89f84d67':
 raise SystemExit('Use the verified English Xbox UI map for reproducible caption artwork.')
D=raw[:2048]+zlib.decompress(raw[2048:]) if len(raw)<struct.unpack_from('<I',raw,8)[0] else raw
T=struct.unpack_from('<I',D,16)[0];BASE=0x803a6000
u=lambda off:struct.unpack_from('<I',D,off)[0]
i=lambda off:struct.unpack_from('<i',D,off)[0]
s=lambda off:struct.unpack_from('<h',D,off)[0]
def ptr(p):return p-BASE+T
def st(p):p=ptr(p);return D[p:D.index(0,p)].decode('latin1')
def block(p):return u(p),ptr(u(p+4))
tags=[]
for k in range(u(T+12)):
 o=T+36+k*32;tags.append(dict(id=u(o+12),group=D[o:o+4][::-1].decode('latin1'),name=st(u(o+16)),p=ptr(u(o+20))))
def tag(n):return None if n==0xffffffff else tags[n&65535]
def ref(o):t=tag(u(o+12));return t['name'] if t else None
def rect(o):return struct.unpack_from('<4h',D,o)
def widget(t):
 p=t['p'];count,cs=block(p+0x3e0);return dict(name=t['name'],type=s(p),bounds=rect(p+0x24),background=ref(p+0x38),font=ref(p+0xfc),offset=(s(p+0x130),s(p+0x132)),header=(ref(p+0x154),rect(p+0x174)),footer=(ref(p+0x164),rect(p+0x17c)),children=[(ref(cs+x*0x50),struct.unpack_from('<2h',D,cs+x*0x50+0x4c)) for x in range(count)])
from PIL import Image,ImageDraw
import io,numpy as np

def bitmap(t,idx=0):
 c,b=block(t['p']+96);b+=idx*48;w,h=s(b+4),s(b+6);offset,size=u(b+24),u(b+28)
 head=struct.pack('<7I',124,0x81007,h,w,w*h,0,0)+bytes(44)+struct.pack('<II4s5I',32,4,b'DXT3',0,0,0,0,0)+struct.pack('<5I',0x1000,0,0,0,0)
 return Image.open(io.BytesIO(b'DDS '+head+D[offset:offset+w*h])).convert('RGBA')
bs=[t for t in tags if t['group']=='bitm' and 'header_' in t['name']]
texts={0:'CHOOSE DIFFICULTY',1:'LOAD LEVEL',2:'SELECT PROFILE',3:'MULTIPLAYER',4:'EDIT PROFILE SETTINGS',5:'PROFILE NAME',6:'CONTROLLER SETUP',7:'ADVANCED CONTROLS',15:'SYSTEM LINK GAMES'}
glyphs={}
for idx,txt in texts.items():
 arr=np.array(bitmap(bs[idx]));m=np.where((arr[:,:,2]>100)&(arr[:,:,1]>70),arr[:,:,3],0).astype('uint8');m[:32]=0;m[56:]=0
 # Original text occupies y=33..55. Ignore the dark heading panel.
 from scipy.ndimage import label,find_objects,distance_transform_edt,gaussian_filter
 labs,n=label(m>80);runs=[]
 for lab,sl in enumerate(find_objects(labs),1):
  if (labs[sl]==lab).sum()>15 and sl[0].stop-sl[0].start>10:runs.append((sl[1].start,sl[1].stop,lab))
 runs.sort(key=lambda r:r[0])
 letters=txt.replace(' ','');print(idx,len(runs),len(letters))
 if len(runs)!=len(letters):continue
 for ch,run in zip(letters,runs):
  if ch not in glyphs:
   # Assign antialias pixels to their nearest connected glyph, rather than
   # copying neighbouring diagonals that overlap the glyph's bounding box.
   nearest=distance_transform_edt(labs==0,return_distances=False,return_indices=True)
   owner=labs[tuple(nearest)]
   isolated=np.where(owner==run[2],m,0).astype('uint8')
   glyphs[ch]=Image.fromarray(isolated[33:56,run[0]:run[1]])
glyphs['K']=Image.fromarray(m[33:56,223:242])
print('glyphs',''.join(sorted(glyphs)))
# The added captions need three letters absent from the English heading set.
# Keep the same cap height/stroke widths; form B/Q from original P/O bowls.
p=np.array(glyphs['P']);b=p.copy();b[11:]=p[:12];glyphs['B']=Image.fromarray(b)
q=glyphs['O'].copy();d=ImageDraw.Draw(q);d.line((q.width-8,16,q.width-2,22),fill=255,width=3);glyphs['Q']=q
x=Image.new('L',(19*4,23*4));d=ImageDraw.Draw(x);d.line((2,0,73,91),fill=255,width=13);d.line((73,0,2,91),fill=255,width=13);glyphs['X']=x.resize((19,23),Image.Resampling.LANCZOS)
def caption(text):
 widths=[glyphs.get(c,glyphs.get({'Ä':'A','Ú':'U'}.get(c,''))).width for c in text];im=Image.new('L',(sum(widths)+3*(len(text)-1),28));at=0
 for c,w in zip(text,widths):
  base={'Ä':'A','Ú':'U'}.get(c,c);im.paste(glyphs[base],(at,5));d=ImageDraw.Draw(im)
  if c=='Ä':d.rectangle((at+w//2-5,0,at+w//2-3,2),fill=255);d.rectangle((at+w//2+2,0,at+w//2+4,2),fill=255)
  if c=='Ú':d.line((at+w//2,3,at+w//2+3,0),fill=255,width=2)
  at+=w+3
 return im
labels=['VOLUMES','LAUTSTÄRKE','VOLUMES','VOLÚMENES','VOLUMI','EXIT','BEENDEN','QUITTER','SALIR','ESCI']
# Main-menu labels have a 21px cap height, versus 23px for headings.
# Preserve the original SETTINGS RGB and 119/255 normal opacity. Its focused
# frame has a white core and a blue halo reaching five pixels past the ink.
settings=next(t for t in tags if t['group']=='bitm' and t['name'].endswith('menu_settings'))
normal=np.array(bitmap(settings,0));selected=np.array(bitmap(settings,1))
normal_color=tuple(int(v) for v in normal[normal[:,:,3]==normal[:,:,3].max()][0,:3])
normal_alpha=int(normal[:,:,3].max())
y,x=np.where(normal[:,:,3]>0);cap_height=int(y.max()-y.min()+1)
assert cap_height==21 and normal_alpha==119
header=['/* Original-UI-derived caption artwork. No map is edited/distributed.',
        '   RLE records: count, R, G, B, A. Main-menu states are separate. */',
        'struct av_caption_mask {unsigned short width,height; unsigned char const *rle;};']
images=[]
for idx,text in enumerate(labels):
 im=caption(text)
 if idx<5:
  rgba=Image.new('RGBA',im.size,(33,148,255));rgba.putalpha(im);images.append(rgba)
 else:
  # Crop the reserved accent band before scaling Latin menu lettering.
  im=im.crop((0,5,im.width,28))
  im=im.resize((round(im.width*cap_height/23),cap_height),Image.Resampling.LANCZOS)
  padded=Image.new('L',(im.width+12,33));padded.paste(im,(6,6))
  coverage=np.array(padded,dtype=float)/255
  rgba=np.zeros((*coverage.shape,4),dtype=np.uint8);rgba[:,:,:3]=normal_color
  rgba[:,:,3]=np.rint(coverage*normal_alpha).astype('uint8');images.append(Image.fromarray(rgba))
# Focused state: the same ink position/size, plus the original five-pixel halo.
for normal_im in images[5:10]:
 coverage=np.array(normal_im)[:,:,3].astype(float)/normal_alpha
 halo=np.clip(gaussian_filter(coverage,1.6)*2.0,0,1)
 core=coverage
 alpha=core+(1-core)*halo*.6
 rgb=np.zeros((*core.shape,3),dtype=float)
 for channel,value in enumerate((41,150,255)):
  rgb[:,:,channel]=np.divide(core*255+(1-core)*halo*.6*value,alpha,out=np.zeros_like(alpha),where=alpha>0)
 rgba=np.zeros((*core.shape,4),dtype=np.uint8);rgba[:,:,:3]=np.rint(rgb).astype('uint8');rgba[:,:,3]=np.rint(alpha*255).astype('uint8')
 images.append(Image.fromarray(rgba))
preview=Image.new('RGBA',(450,len(images)*44),(0,20,38,255))
for idx,im in enumerate(images):
 rle=[]
 for pixel in im.getdata():
  pixel=list(pixel)
  if rle and rle[-4:]==pixel and rle[-5]<255:rle[-5]+=1
  else:rle += [1]+pixel
 header.append('static unsigned char const av_caption_pixels_%d[]={%s};'%(idx,','.join(map(str,rle))))
 preview.alpha_composite(im,(8,idx*44))
header.append('static struct av_caption_mask const av_caption_masks[]={'+','.join('{%d,%d,av_caption_pixels_%d}'%(im.width,im.height,idx) for idx,im in enumerate(images))+'};')
(Path(__file__).resolve().parents[1]/'source/interface/android_caption_masks.h').write_text('\n'.join(header)+'\n')
preview.save(Path(sys.argv[2]) if len(sys.argv)>2 else Path('caption-preview.png'))
