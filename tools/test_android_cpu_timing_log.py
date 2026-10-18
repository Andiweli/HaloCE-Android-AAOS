#!/usr/bin/env python3
"""Exercise the production guest-log bridge and diagnostic writer.

No Android device or Logcat permission is needed for this host-side test.
The Android log sink is a stub; line buffering, writev handling and the
bounded file writer are extracted unchanged from the production sources.
With a JDK or --ecj, also execute the production GFX copy/ZIP export on the JVM.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--javac", help="Optional path to a JDK javac executable")
parser.add_argument("--ecj", help="Optional Eclipse Java compiler JAR (a JRE suffices)")
args = parser.parse_args()
syscalls = (ROOT / "port/android/host/host_syscall.c").read_text()
main = (ROOT / "port/android/host/host_main.c").read_text()
graphics = (ROOT / "port/android/app/src/main/java/com/halo/decomp/GraphicsDiagnostics.java").read_text()
writer = main[main.index("static void diagnostic_write("):main.index("\nvoid host_fatal(")]
bridge = syscalls[syscalls.index("struct log_stream\n"):syscalls.index("\nstatic long guest_readv(")]
assert "case SYS_write:" in syscalls and "log_bytes((int)a," in syscalls
assert "return guest_writev((int)a," in syscalls
assert 'copy(log,new File(folder,"halo-diagnostic.txt"))' in graphics
assert "guest-log bridge v1" in graphics
assert "setFocusable(false)" in graphics and "RelativeLayout.CENTER_HORIZONTAL" in graphics

PRE = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/uio.h>
#include <time.h>
#include <unistd.h>
#define ANDROID_LOG_INFO 4
#define ANDROID_LOG_WARN 5
#define ANDROID_LOG_ERROR 6
static FILE *diagnostic_file;
static char diagnostic_error[1024];
static pthread_mutex_t diagnostic_mutex = PTHREAD_MUTEX_INITIALIZER;
static unsigned logcat_count, info_count, warn_count;
static void __android_log_write(int priority, const char *tag, const char *text)
{
    assert(!strcmp(tag, "halo") && text);
    ++logcat_count;
    if (priority == ANDROID_LOG_INFO) ++info_count;
    if (priority == ANDROID_LOG_WARN) ++warn_count;
    errno = EPERM; /* Check that the bridge does not leak logging errno. */
}
struct guest_iovec { uint32_t base, length; };
static union { uint64_t alignment; unsigned char bytes[4096]; } arena;
static void *guest_address(uint32_t address)
{
    assert(address < sizeof(arena.bytes));
    return arena.bytes + address;
}
#define GUEST(type, value) ((type)guest_address((uint32_t)(value)))
static long result_of(long value) { return value == -1 ? -errno : value; }
'''
POST = r'''
static void send_line(int fd, const char *text)
{
    errno = E2BIG;
    log_bytes(fd, text, strlen(text));
    assert(errno == E2BIG);
}
static void *worker(void *argument)
{
    unsigned long id = (unsigned long)(uintptr_t)argument;
    char line[180];
    for (unsigned i = 0; i < 20; ++i) {
        snprintf(line, sizeof(line),
            "halo-linux: NVIDIA CPU skeletal timing: thread %lu sample %u\n", id, i);
        /* An entire line per write, as the guest log lock serializes bytes. */
        send_line(2, line);
    }
    return NULL;
}
int main(int argc, char **argv)
{
    assert(argc == 2);
    diagnostic_file = fopen(argv[1], "w+");
    assert(diagnostic_file);
    assert(setvbuf(diagnostic_file, NULL, _IONBF, 0) == 0);
    send_line(2, "halo-linux: NVIDIA CPU ske");
    assert(ftell(diagnostic_file) == 0 && logcat_count == 0);
    send_line(1, "ordinary stdout remains Logcat only\n");
    assert(ftell(diagnostic_file) == 0 && logcat_count == 1 && info_count == 1);
    send_line(2, "letal timing: 300 active frames, 42 vertices/frame, 1.25 ms/frame, worst 2.50 ms (includes stream upload)\n");
    assert(ftell(diagnostic_file) > 0 && logcat_count == 2 && warn_count == 1);

    /* Real writev code must assemble one line across separate vectors. */
    struct guest_iovec *v = (struct guest_iovec *)(arena.bytes + 8);
    const char *parts[] = {
        "halo-linux: NVIDIA ", "CPU skeletal timing: ",
        "writev sample 3.75 ms/frame\nordinary stderr remains Logcat only\n"
    };
    uint32_t offset = 512;
    long total = 0;
    for (unsigned i = 0; i < 3; ++i) {
        size_t length = strlen(parts[i]);
        memcpy(arena.bytes + offset, parts[i], length);
        v[i].base = offset; v[i].length = (uint32_t)length;
        offset += (uint32_t)length; total += (long)length;
    }
    errno = EBUSY;
    assert(guest_writev(2, 8, 3, 0, 0) == total && errno == EBUSY);
    assert(logcat_count == 4);
    assert(guest_writev(2, 8, -1, 0, 0) == -EINVAL);
    assert(guest_writev(2, 8, 65, 0, 0) == -EINVAL);
    assert(guest_writev(2, 8, 0, 0, 0) == 0);

    send_line(2, "halo-linux: NVIDIA CPU skeletal shader 7: 61 original instructions\n");
    send_line(2, "halo-linux: NVIDIA CPU skeletal breakdown v1: input/setup 0.100, execute 0.500, pack 0.050, upload/bind 0.200 ms/active frame; fixed 42/42 vertices\n");
    send_line(2, "halo-linux: NVIDIA CPU skeletal passthrough unavailable; retaining original GPU shaders\n");
    /* The Shield test's other low-rate families also reach the file. */
    send_line(2, "halo-linux: gamepad port 1: controller 7\n");
    send_line(2, "halo-linux: NVIDIA performance test v1: skinning mode 0, visibility async\n");
    send_line(2, "halo-linux: NVIDIA skinning test A: shader 9 with a uniform block compiled\n");
    /* A lookalike must not match the bounded diagnostic family. */
    send_line(2, "halo-linux: NVIDIA CPU skeletalX timing: not a sample\n");
    send_line(2, "halo-linux: ordinary guest warning\n");
    send_line(1, "NVIDIA CPU skeletal timing: missing platform prefix\n");
    /* Overflow fragments and empty writes preserve the original behaviour. */
    char long_line[2051];
    memset(long_line, 'x', sizeof(long_line));
    long_line[2050] = 0;
    send_line(1, long_line); send_line(1, "\n");
    send_line(1, "");
    unsigned before_threads = logcat_count;
    pthread_t threads[4];
    for (unsigned i = 0; i < 4; ++i)
        assert(!pthread_create(&threads[i], NULL, worker, (void *)(uintptr_t)i));
    for (unsigned i = 0; i < 4; ++i) assert(!pthread_join(threads[i], NULL));
    assert(logcat_count == before_threads + 80);
    rewind(diagnostic_file);
    char data[32768];
    size_t size = fread(data, 1, sizeof(data)-1, diagnostic_file);
    data[size] = 0;
    assert(strstr(data, "1.25 ms/frame") && strstr(data, "writev sample 3.75 ms/frame"));
    assert(strstr(data, "shader 7: 61 original instructions"));
    assert(strstr(data, "passthrough unavailable"));
    assert(strstr(data, "gamepad port 1: controller 7") && strstr(data, "performance test v1") &&
        strstr(data, "skinning test A"));
    assert(!strstr(data, "ordinary") && !strstr(data, "skeletalX"));
    assert(!strstr(data, "missing platform prefix"));
    unsigned samples = 0;
    for (char *at = data; (at = strstr(at, "NVIDIA CPU skeletal timing:")); ++at) ++samples;
    assert(samples == 82);
    assert(!fclose(diagnostic_file));
    /* Keep the pre-existing diagnostic size cap; Logcat still receives it. */
    diagnostic_file = tmpfile(); assert(diagnostic_file);
    assert(!fseek(diagnostic_file, 2*1024*1024, SEEK_SET));
    long limit = ftell(diagnostic_file);
    unsigned before_cap = logcat_count;
    send_line(2, "halo-linux: NVIDIA CPU skeletal timing: capped\n");
    assert(ftell(diagnostic_file) == limit && logcat_count == before_cap + 1);
    fclose(diagnostic_file);
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="halo-cpu-timing-") as temporary:
    directory = Path(temporary)
    c = directory / "test.c"
    c.write_text(PRE + writer + bridge + POST)
    exe = directory / "test"
    subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-pthread",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    str(c), "-o", str(exe)], check=True)
    log = directory / "halo-diagnostic.txt"
    subprocess.run([str(exe), str(log)], check=True)
    recorded = log.read_text()
    assert recorded.count("NVIDIA CPU skeletal timing:") == 82
    assert recorded.count("NVIDIA CPU skeletal breakdown v1:") == 1
    assert "fixed 42/42 vertices" in recorded
    assert all(recorded.count(f"thread {t} sample {i}\n") == 1
               for t in range(4) for i in range(20))
    print("PASS: production guest stderr/stdout buffering, fragmented writev,")
    print("      82 timing samples, shader/fallback diagnostics, no duplicate Logcat,")
    print("      unchanged ordinary output, concurrency, errno and 2 MiB cap; UBSan.")

    javac = args.javac or shutil.which("javac")
    if javac or args.ecj:
        # Execute the exporter body verbatim, with only the Activity lookup
        # supplied by a test fixture. No Android classes are needed here.
        start = graphics.index("                    File log = StartDiagnostics.log(activity);")
        end = graphics.index("\n                } catch (IOException", start)
        export = graphics[start:end]
        start = graphics.index("    private static void copy(")
        end = graphics.index("\n    private void message(", start)
        copy = graphics[start:end]
        java = (
            "import java.io.*; import java.util.*; import java.util.zip.*;\n"
            "public final class GfxExportTest {\n"
            "static final class StartDiagnostics { static File log(Object activity) { return (File)activity; } }\n"
            + copy + "\n"
            "public static void main(String[] args) throws Exception {\n"
            "Object activity = new File(args[0]); File folder = new File(args[1]);\n"
            "if (!folder.mkdir()) throw new IOException(\"mkdir\");\n"
            "boolean complete = true; String result;\n"
            + export + "\nSystem.out.println(result); } }\n"
        )
        j = directory / "GfxExportTest.java"
        j.write_text(java)
        compiler = ([javac] if javac else
                    [shutil.which("java"), "-jar", args.ecj, "-17"])
        subprocess.run(compiler + ["-d", str(directory), str(j)], check=True)
        java_exe = Path(javac).resolve().with_name("java") if javac else shutil.which("java")
        folder = directory / "halo-gfx-test"
        subprocess.run([str(java_exe), "-cp", str(directory), "GfxExportTest",
                        str(log), str(folder)], check=True)
        with zipfile.ZipFile(str(folder) + ".zip") as archive:
            assert archive.testzip() is None
            assert archive.read("halo-diagnostic.txt") == log.read_bytes()
        print("PASS: production Java GFX log copy/ZIP export retains all timing samples.")
    else:
        print("SKIP: Java execution (provide a JDK or --ecj); export wiring checked.")
