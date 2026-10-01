"""Load real guest ELFs through the real host loader with deliberate collisions.
Runs on Linux; validates mapping and linked pointers, not AArch64 execution.
"""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
memory=(root/'port/android/host/host_memory.c').read_text()
# Exclude the architecture-specific signal handler and write-watch routines.
memory=memory[:memory.index('#define WATCH_PAGE_COUNT')]
code=r'''
#include "host.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
void host_logf(int priority,const char *format,...){(void)priority;(void)format;}
void host_fatal(const char *format,...){(void)format;abort();}
static void imported(void){}
void *host_resolve_import(const char *name){(void)name;return imported;}
void *host_gl_resolve(const char *name){(void)name;return imported;}
int main(int argc,char **argv){
 assert(argc==6);int blocked=atoi(argv[1]);
 unsigned long bases[]={0x40000000,0x20000000,0x60000000,0xa0000000};
 for(int i=0;i<blocked;i++){
  void *p=mmap((void *)bases[i],4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
  assert(p==(void *)bases[i]);*(unsigned *)p=0x12345678;
 }
 for(int i=0;i<4;i++){
  FILE *f=fopen(argv[2+i],"rb");assert(f);fseek(f,0,SEEK_END);size_t n=ftell(f);rewind(f);
  void *bytes=malloc(n);assert(fread(bytes,1,n,f)==n);fclose(f);
  int result=host_load_image(bytes,n);free(bytes);
  for(int j=0;j<blocked;j++)assert(*(unsigned *)bases[j]==0x12345678);
  if(i<blocked){assert(result==-2);continue;}
  assert(result==0 && host_image.base==bases[i]);
  assert(host_image.header->import_table>=host_image.base && host_image.header->import_table<host_image.end);
  assert(host_image.cache_file_globals>=host_image.base && host_image.cache_file_globals<host_image.end);
  assert(host_image.global_tag_instances>=host_image.base && host_image.global_tag_instances<host_image.end);
  return 0;
 }
 assert(blocked==4);return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);(p/'memory.c').write_text(memory);(p/'test.c').write_text(code)
 subprocess.run(['cc','-D_GNU_SOURCE','-std=gnu11','-pthread','-I'+str(root/'port/android/host'),'-I'+str(root/'port/android/include'),str(p/'test.c'),str(p/'memory.c'),str(root/'port/android/host/host_loader.c'),'-o',str(p/'test')],check=True)
 images=[root/'build/android'/name for name in ['halo_guest.elf','halo_guest_20000000.elf','halo_guest_60000000.elf','halo_guest_a0000000.elf']]
 for blocked in range(5):subprocess.run([str(p/'test'),str(blocked)]+list(map(str,images)),check=True)
print('Actual loader: preferred base, three fallbacks and all-addresses-occupied passed; existing mappings preserved.')
