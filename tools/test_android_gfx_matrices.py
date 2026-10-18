"""Run the real GFX recorder against software GLES and inspect its files.

Needs Linux Mesa EGL/GL and --ndk for GLES/JNI headers. Does not claim to
reproduce the NVIDIA driver bug or validate an Android device.
"""
from pathlib import Path
import argparse
import os
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--ndk", required=True, type=Path)
args = parser.parse_args()
headers = args.ndk / "toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include"
assert headers.is_dir(), headers
with tempfile.TemporaryDirectory(prefix="halo-gfx-matrices-") as temporary:
    folder = Path(temporary)
    capture = folder / "capture"
    capture.mkdir()
    binary = folder / "test"
    subprocess.run(["cc", "-std=gnu11", "-O1", "-pthread", "-DUSE_OZONE",
                    "-I" + str(ROOT / "port/android/include"),
                    "-idirafter", str(headers), str(ROOT / "tools/test_android_gfx_matrices.c"),
                    "-Wl,-l:libEGL.so.1", "-Wl,-l:libGL.so.1", "-lm", "-o", str(binary)], check=True)
    env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE="1", EGL_PLATFORM="surfaceless")
    subprocess.run([str(binary), str(capture)], env=env, check=True, timeout=45)
    report = (capture / "report.txt").read_text()
    assert "GL_ERROR" not in report, report
    assert "CPU_UNIFORM4 serial=1" in report and "count=192" in report
    assert "CPU_UNIFORM4 serial=2" in report and "CPU_U4 ordinal=0 9.5 0.5 0.25 1" in report
    assert "U c[60]" in report and "U c[191]" in report
    assert "U c[61]" in report and "9.5 0.5 0.25 1 nonfinite=0" in report
    for attribute, relative, width in ((0, 0, 12), (1, 12, 4), (5, 16, 8), (6, 24, 8)):
        assert f"ATTR {attribute} enabled=1" in report
        data = (capture / f"draw-0001-attr-{attribute}.bin").read_bytes()
        assert len(data) == 64 + width
        if attribute == 1:
            assert struct.unpack_from("<I", data)[0] == 0xF0123457
        if attribute == 5:
            assert struct.unpack_from("<ff", data) == (0.25, 0.75)
        if attribute == 6:
            assert struct.unpack_from("<ff", data) == (0, 1)
    assert (capture / "draw-0001-indices.bin").read_bytes() == struct.pack("<HHH", 0, 1, 2)
    assert (capture / "frame.ppm").is_file()
    assert list(capture.glob("*.glsl"))
    assert "model_details=1" in report and "cpu_uniform_uploads=2" in report
    assert "geometry_skips=0" in report and "detail_timed_out=0" in report
    java = (ROOT / "port/android/app/src/main/java/com/halo/decomp/GraphicsDiagnostics.java").read_text()
    assert "ALIGN_PARENT_TOP" in java and "CENTER_HORIZONTAL" in java and 'setText("GFX")' in java
    print("PASS: GPU c[60..191], CPU uploads, packed normal/weights/bone attributes, indices, shader sources and centred GFX button checked.")
