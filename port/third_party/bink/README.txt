FFmpeg 7.1.1 - Bink movie decoding
Copyright (c) the FFmpeg developers. https://ffmpeg.org/

This build uses the LGPL 2.1-or-later configuration (no GPL/nonfree options),
limited to the Bink demuxer, Bink video/audio decoders, file input and swscale.
FFmpeg is statically linked into libmain.so. The exact unmodified source archive
is supplied in port/third_party/bink/ffmpeg-7.1.1.tar.xz; the reproducible build
recipe is tools/android_bink_build.py. Full port sources and link rules permit
rebuilding/relinking with a modified FFmpeg. No Bink SDK or game movies are bundled.
See FFmpeg-LGPL-2.1.txt for the license.
