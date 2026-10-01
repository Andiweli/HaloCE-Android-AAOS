"""Validate generated caption geometry, RGBA states and glyph isolation."""
from pathlib import Path
import re
import numpy as np
p=Path(__file__).resolve().parents[1]/'source/interface/android_caption_masks.h'
s=p.read_text();images=[]
for w,h,index in re.findall(r'\{(\d+),(\d+),av_caption_pixels_(\d+)\}',s):
 values=list(map(int,re.search(r'av_caption_pixels_'+index+r'\[\]=\{([^}]+)',s)[1].split(',')))
 assert len(values)%5==0
 pixels=[]
 for k in range(0,len(values),5):pixels.extend([values[k+1:k+5]]*values[k])
 assert len(pixels)==int(w)*int(h)
 images.append(np.array(pixels,dtype=np.uint8).reshape(int(h),int(w),4))
assert len(images)==15
# V's bottom-right region must not contain the neighbouring A from ADVANCED.
assert not images[0][25:28,16:23,3].any()
for normal,focus in zip(images[5:10],images[10:]):
 assert normal.shape==focus.shape and normal.shape[0]==33
 yy,xx=np.where(normal[:,:,3]>0)
 assert (yy.min(),yy.max())==(6,26)
 assert normal[:,:,3].max()==119
 assert (normal[normal[:,:,3]>0,:3]==[35,150,255]).all()
 assert focus[:,:,3].max()==255
 assert ((normal[:,:,3]==0)&(focus[:,:,3]>0)).any(), 'missing hover halo'
 assert not focus[[0,-1],:,3].any(), 'clipped vertical halo'
print('15 caption states: glyph isolation, cap height, normal colour/opacity and hover halo OK')
