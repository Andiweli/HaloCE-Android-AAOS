#!/usr/bin/env python3
"""Build the pinned LGPL-only Bink decoder subset for Android arm64."""
import hashlib, os, pathlib, subprocess, sys, tarfile
root=pathlib.Path(__file__).resolve().parents[1]
ndk=pathlib.Path(sys.argv[1]).resolve()
archive=root/'port/third_party/bink/ffmpeg-7.1.1.tar.xz'
if hashlib.sha256(archive.read_bytes()).hexdigest() != '733984395e0dbbe5c046abda2dc49a5544e7e0e1e2366bba849222ae9e3a03b1':
 raise SystemExit('Unexpected FFmpeg archive checksum')
build=root/'build/android/bink' 
build.mkdir(parents=True,exist_ok=True)
source=build/'ffmpeg-7.1.1'
if not source.exists():
 with tarfile.open(archive) as t:t.extractall(build,filter='data')
out=build/'install'
cc=ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin'
args=['./configure','--target-os=android','--arch=aarch64','--enable-cross-compile',
 '--cc='+str(cc/'aarch64-linux-android28-clang'),'--ar='+str(cc/'llvm-ar'),
 '--ranlib='+str(cc/'llvm-ranlib'),'--strip='+str(cc/'llvm-strip'),
 '--prefix='+str(out),'--disable-everything','--disable-autodetect','--disable-programs',
 '--disable-doc','--disable-debug','--disable-network','--disable-avdevice','--disable-avfilter',
 '--disable-swresample','--enable-swscale','--enable-avformat','--enable-avcodec','--enable-avutil',
 '--enable-demuxer=bink','--enable-decoder=bink,binkaudio_rdft,binkaudio_dct',
 '--enable-protocol=file','--enable-pic','--enable-static','--disable-shared',
 '--extra-cflags=-O2 -fPIC','--extra-ldflags=-Wl,-z,max-page-size=16384']
if not (source/'config.h').exists():subprocess.run(args,cwd=source,check=True)
subprocess.run(['make','-j4'],cwd=source,check=True)
subprocess.run(['make','install'],cwd=source,check=True)
