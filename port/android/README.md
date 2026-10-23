## Android Studio variants

Select `mobileDebug` / `mobileRelease` for phones and handhelds, or
`aaosDebug` / `aaosRelease` for Android Automotive OS (parked game).
Both variants keep the existing application ID and version, and therefore
replace each other when installed with the same signing key.

AAOS uses the available window area with dynamic system-bar, cutout and
keyboard insets shared by SDL and RetroTouch. System bars remain accessible.
The adaptive launcher icon stays within its safe zone and is also used as the
round icon. The AAOS activities are resizable and do not request rotation.
Native rendering/audio is paused at onPause, including when AAOS blocks the
activity. The mobile self-updater is disabled in the AAOS variant.

Build commands from this directory:

```sh
./gradlew :app:assembleAaosDebug
./gradlew :app:assembleAaosRelease
./gradlew :app:bundleAaosRelease
```

APK output: `app/build/outputs/apk/aaos/debug/app-aaos-debug.apk` (or release).
AAB output: `app/build/outputs/bundle/aaosRelease/app-aaos-release.aab`.
The native payload remains arm64-v8a only; x86_64 AAOS emulators are unsupported.
Test on an ARM64 AAOS device, including side/bottom bars, resizing, portrait,
controller/touch input, keyboard, and audio suspension when the OS blocks play.
This variant targets native Android Automotive OS, not phone-projected Android Auto.

# Android

## Android Studio 2025 distribution (Android UI patch 01)

Open the **repository root** (the folder with `settings.gradle`) in Android
Studio 2025. The distribution includes a matching ARM64 engine payload in
`port/android/native`, so building the APK needs no native compiler or WSL.
Use JDK 17 (or the compatible bundled Studio JDK), Android SDK 35 and Build
Tools 35.0.0. AGP is pinned to 8.9.2 and Gradle to 8.11.1.

See `START-HIER.txt` in the repository root for the German quick start,
validation results, signing and native-source rebuild instructions.

Android UI patch 01 makes both activities immersive, hides on-screen engine
diagnostics and build text, and removes the separator in controller labels.
It does not add touch controls or change Android/ABI requirements. Native
logging remains available. The native payload is a release engine in both
Gradle variants; a debug APK still permits Java/Android debugging.

The original command-line native build below remains available. `ninja
android` now also copies its outputs and SDL Java sources into the portable
`port/android/native` directory. Gradle always uses that directory.

`ninja android` builds the game for 64-bit ARM Android (arm64-v8a).
`ninja android_apk` makes an app from it:
`port/android/app/build/outputs/apk/mobile/debug/app-mobile-debug.apk`.

The game shows its graphics with OpenGL ES 3. It plays sound through SDL3
(AAudio). It accepts input from game controllers, for example a PlayStation
5 DualSense on Bluetooth. The app needs Android 9 (API 28) or later. It
operates on 64-bit-only devices, for example the Pixel 9 Pro XL.

The Android build uses the platform layer of the Linux build
(`port/linux/src`). Refer to [port/linux/README.md](../linux/README.md).

## Requirements

You do not need the Xbox SDK. You need the tools of the Linux build (Python,
ninja) and these items:

- A clang with the `arm64_32` target, for example the clang of the system.
  The option `--android-guest-cc` of `configure.py` selects a different
  compiler.
- The Android NDK. `configure.py` looks for it in `ANDROID_NDK_HOME`, then
  in `$ANDROID_HOME/ndk`, `~/Android/Sdk/ndk` and `/opt/android-sdk/ndk`.
  The option `--android-ndk` selects a different NDK.
- CMake, and a JDK 17 or later for Gradle.
- A network connection for the first build. `configure.py` downloads musl
  1.2.5 and SDL 3.4.16 to `build/android/third_party`. Gradle downloads the
  Android Gradle Plugin.

## Build and install the app

1. Go to the root folder of the repository.
2. Enter `python configure.py`.
3. Enter `ninja android_apk`.
4. Connect the device with adb.
5. Enter `adb install -r port/android/app/build/outputs/apk/mobile/debug/app-mobile-debug.apk`.

`ninja android` builds only the game image and the native libraries.

## Game data

The game needs the `maps/` folder from an Xbox disc image (`.xiso` or
`.iso`) of any version of the game. The app extracts `maps/` from the disc
image. The app keeps the data in `/sdcard/Android/data/com.halo.decomp/files`.

To install the data with the app:

1. Copy the disc image to the phone.
2. Start the app.
3. Push the button. The file picker of the system opens.
4. Select the disc image.
5. Wait while the app extracts the data (approximately 1.8 GB). Then the
   game starts.
6. You can delete the disc image.

To install the data from a computer:

1. Start the app one time. The app makes its folders.
2. Enter `adb push <folder>/. /sdcard/Android/data/com.halo.decomp/files/`.

| Item | Location in `/sdcard/Android/data/com.halo.decomp/files` |
| --- | --- |
| Saved games (`z:\` and `u:\`) | `save` |
| Log | `debug.txt` |
| Settings | `config.toml` |

To make a copy of the saved games, enter
`adb pull /sdcard/Android/data/com.halo.decomp/files/save`.

## Controls

The game reads controllers through the gamepad functions of SDL3. All the
controllers that Android knows operate. The first controller is player 1.
The other controllers are players 2 to 4 (split screen). Only controllers
with two analog sticks take one of the four ports, and each keeps its port
while connected: a controller switched on later, or one that wakes from
sleep under a new Android ID, takes the lowest free port. TV remotes (the
Shield lists its remote twice) and other gamepad devices without sticks
merge into the first port, so they still work the menus. The log names
each port's controller (`gamepad port`), also in `halo-diagnostic.txt`.
The buttons agree with the positions on the Xbox controller:

| DualSense | Xbox | Function in the game |
| --- | --- | --- |
| left stick, right stick | left stick, right stick | move, look |
| R2 | right trigger | fire |
| L2 | left trigger | throw a grenade |
| Cross | A | jump, accept |
| Circle | B | melee, back |
| Square | X | action, reload |
| Triangle | Y | change the weapon |
| L1 | white | flashlight |
| R1 | black | change the grenade |
| L3, R3 | left and right stick clicks | crouch, zoom |
| D-pad | D-pad | |
| Options | start | pause menu |
| Create | back | |

The controller gets the rumble. The back gesture of Android is the B
button. A Bluetooth or USB keyboard operates as on Linux. The screen does
not accept touch input.

## Settings

The settings are in `config.toml` in the data folder of the app. To change
them:

1. Enter `adb pull /sdcard/Android/data/com.halo.decomp/files/config.toml`.
2. Change the file.
3. Enter `adb push config.toml /sdcard/Android/data/com.halo.decomp/files/`.

At the first start, the game writes the file with the default values. To
get the default values again, delete the file.

The settings are the settings of Linux, without the window, the mouse and
the paths. Refer to [port/linux/README.md](../linux/README.md#settings).
These settings are only for Android:

| Setting | Function |
| --- | --- |
| `display.screen_width` | The number of columns of the 480-line picture. `0` (the default): the shape of the display (1068 on a 20:9 phone). `640`: the 4:3 shape of the Xbox. |
| `debug.sample_seconds` | Refer to "Find problems". |

## Internet play

Internet play operates as on Linux, but without Discord. When the game
hosts a system link game, it puts the invite link on the clipboard and
shows a notice.

To join a game, do one of these steps:

- Open the link. The app is the handler of `halo://join/...` links. If the
  game does not operate, the app starts it. The app writes the link to
  `files/join_link.txt`, and the game reads it.
- Copy the link and go to the game.

On the local network:

- The game uses the address of the Wi-Fi (or of the hotspot of the
  phone), not the address of the mobile data.
- The app holds a Wi-Fi multicast lock while the game operates. Some
  phones otherwise drop the broadcasts that find system link games.

Keep the game in the front during a network game. When the app goes to the
background, Android stops the game. After 15 seconds the other machines
drop it, and when it hosts, its players leave.

## Updates

The app from GitHub Actions can update itself, as on Linux (refer to
"Updates" in [port/linux/README.md](../linux/README.md#updates)). When you
select "Yes":

1. The app downloads the new version.
2. The package installer of Android opens. At the first update, Android asks
   you to let Halo install apps. Allow it.
3. Select "Update". Android replaces the app.
4. Select "Open" to start the new version.

To install over the previous version, each build must have the same
signature. GitHub Actions signs each build with the key in the
`ANDROID_KEYSTORE_BASE64` and `ANDROID_KEYSTORE_PASSWORD` secrets of the
repository. If you installed a build that has a different signature, remove
that build before you install a new build. Removing the app deletes its data
folder: first make a copy of `maps/` and `save/`.

## Widescreen

The game shows 480 lines in the shape of the display, not the 640x480 of
the Xbox:

- The 3D view is wider. The camera keeps the vertical field of view.
- The HUD stays at the edges of the screen.
- The menus, the loading bar and the screens after a game have 640
  columns, at the center of the screen.
- Black bars and fades cover all of the screen.

The changes are in `#ifdef HALO_ANDROID` in `rasterizer_xbox.c`, `render.c`,
`ui_widget.c`, `cinematics.c`, `main.c` and
`rasterizer_xbox_screen_effect.c`.

## How the port operates

### ILP32 code

The data of the game contains 32-bit pointers. The cache files have the
layout of the Xbox memory. The saved games are copies of the memory.
Direct3D resources contain 32-bit physical addresses. Current Android
devices cannot execute 32-bit ARM code. 64-bit pointers change the layout of
the structures that the game reads from its files.

Thus the game is ILP32 AArch64 code: 64-bit ARM instructions with 32-bit
`int`, `long` and pointers, in a 64-bit app.

### The guest image

The guest is the game, the platform layer and a small runtime:

1. clang compiles the guest for `arm64_32-apple-watchos`, the only ILP32
   AArch64 target of clang. The options `-U__APPLE__` and
   `-fno-define-target-os-macros` hide the Darwin environment.
2. `tools/android_asm_convert.py` changes the Mach-O assembly to ELF
   assembly.
3. The AArch64 assembler makes the objects.
4. `ld.lld` links the objects with `guest/guest.ld` to a static image,
   `build/android/halo_guest.elf`, at a fixed address above the Xbox memory
   (`include/halo_android_abi.h`).

The APK contains the image as an asset.

The C library of the guest is a part of musl for a new `arm64_32`
architecture (`guest/libc/arch/arm64_32`). It has ILP32 types and a 32-bit
`time_t`, as in the MSVC runtime of the game. Its system calls go to the
host (`syscall_arch.h`). `guest/runtime/guest_thread.c` makes the threads
and supplies the thread pointer and TLS.

### The host library

`libmain.so` is an arm64 NDK library. The activity of SDL3 starts it
(`app/.../HaloActivity.java`). The host library:

- Reserves the address space of the guest below 4 GB: the Xbox memory at
  `0x80000000`, the image, and pools for the memory of the guest
  (`host/host_memory.c`).
- Loads the image and fills its import table (`host/host_loader.c`).
- Starts the `main` of the game and each guest thread on a stack in guest
  memory, because ILP32 code keeps stack addresses in 32-bit registers
  (`host/host_thread.c`).
- Gives the audio callback of SDL to a thread with a guest stack
  (`host/host_sdl.c`).
- Does the calls of the guest: system calls (`host/host_syscall.c`), SDL
  (`host/host_sdl.c`), OpenGL ES (`host/host_gl.c`), and the file and socket
  functions of `port/linux/src/posix_*.c`.

The guest calls the host through stubs (`tools/android_imports.py`). The
two ABIs use the same registers for 32-bit integers, floats and pointers.
`tools/android_gl_stubs.py` makes the OpenGL ES stubs from
`port/linux/src/gl.h`. `tools/android_posix_stubs.py` makes the stubs of the
`posix_*` functions, which copy the `errno` of the host.

### OpenGL ES

The renderer (`port/linux/src/d3d8_gl.c`) uses OpenGL ES 3.0, and some
functions of OpenGL ES 3.2 if they are available:

- The vertex shaders flip y and change the depth range from 0..1. The front
  face winding is inverted.
- BGRA textures go to the GPU as RGBA with a swizzle. If the driver has no
  S3TC (Mali GPUs), the CPU decodes the DXT textures.
- The pixel shaders apply the LOD bias of the sampler.
- The upload changes the byte order of `D3DCOLOR` vertex attributes.
- Dynamic vertex and index data goes into a ring of three buffers, one for
  each frame. On Mali, other methods used too much memory.
- On OpenGL ES 3.2, indexed draws use a base vertex. Before 3.2, the CPU
  changes the indices.
- On OpenGL ES 3.1 and later, the visibility tests (lens flares) count
  samples with an atomic counter, as the NV2A did. OpenGL ES 3.0 tells only
  if a sample is visible.

### Calling conventions

Some files of the game declare a function differently from its definition,
or call a function without a prototype. On 32-bit x86, this has no effect.
The guest ABI passes floating-point arguments in their own registers and
variadic arguments on the stack. Thus such a call gives incorrect values.

`tools/android_abi_check.py` compares each declaration with its definition
in the LLVM IR. The problems are repaired:

- `hs.c` declared the red component of the script fades as `long`.
- Some files call `error`, `console_printf` or `terminal_printf` without a
  prototype. `include/halo_android_variadic_prototypes.h` gives the
  prototypes.

`guest/runtime/guest_misc.c` supplies the Darwin library functions that the
target calls (`__sincos_stret`, `__exp10f`). The guest compiles without
floating-point contraction, as on x86.

### Game source changes

The x86 inline assembly is replaced by C (refer to
[port/linux/README.md](../linux/README.md#game-source-changes)).
These changes are in `#ifdef HALO_ANDROID`:

- Seven `#pragma bss_seg(".bss")` lines are removed. The Darwin target does
  not accept them.
- A stack walker follows the AArch64 frame records. Thus the log of an
  assertion (`debug.txt`) shows the call sites.

The musl of the guest uses its C math, not the AArch64 assembly. The only
assembly of the port is necessary:

- The import stubs. A 32-bit guest cannot keep or go to a 64-bit host
  address.
- The symbol aliases in `guest/libc/src_include/features.h`. The Darwin
  target does not accept alias attributes.

## NVIDIA skeletal vertex compatibility

NVIDIA Android contexts execute supported Halo skeletal NV2A vertex programs
on the CPU and stream their completed clip positions, colours, texture
coordinates, fog and point size into one small GPU passthrough vertex shader.
Fragment shading, clipping, depth testing, blending and visibility queries
remain on the GPU. Other vendors and non-skeletal meshes keep their original
vertex path. This removes the driver's execution of the complex skeletal programs
from the Shield geometry path without the large selector shaders from test 2.

The original instruction stream is decoded once, including parallel MAC/ILU
reads/writes, r12 position aliasing, address-register rounding and clamping,
packed input decoding, shadow variants and viewport conversion. Static
constant operands in the interpreter are refreshed once per draw. The existing stream/index
ring, base-vertex handling and immediate-mode inputs remain in use. No
guest/host ABI changes or alternate graphics drivers are required.

The 21 skeletal programs in the original immutable microcode payload now
also have fixed CPU executors, generated by
`tools/android_cpu_shader_generate.py` into `port/linux/src/nv2a_cpu_shaders.inc`.
They perform the same parallel MAC/ILU operations without per-instruction
runtime dispatch, operand decoding, mask selection or dynamic swizzles.
Selection compares every instruction word at shader creation. Unknown or
modified programs retain the interpreter; no runtime native code is generated.
Constant streams and source addresses are resolved once per draw. This stays
inside the NVIDIA CPU path; original GPU shader generation is unchanged.

Run `python3 tools/android_cpu_shader_generate.py --check` to verify that
the checked-in include matches the source payload. Run
`python3 tools/test_android_cpu_specialized.py --gles` for randomized
interpreter comparisons and real software GLES transform feedback covering
every fixed executor. The test uses synthetic data, not the Shield captures.

The top-centre GFX button remains available. A CPU skeletal shader capture
contains completed vertex outputs rather than a GPU bone-uniform array:
attributes 0=position, 1..4=colours, 5..8=texcoords, 9=fog/point size.
Ordinary GPU captures keep their previous format. Native logs identify
selected CPU shaders and report their measured CPU/upload time once per
300 frames. CPU cost and visual behaviour still require a Shield hardware
test; software GLES comparisons cannot confirm the device's final raster.

`NVIDIA CPU skeletal breakdown v1` additionally reports input/setup,
execution, planar packing and upload/bind wall-clock milliseconds per active
frame, and the number of vertices using fixed executors versus all CPU
vertices. The four stages sum to the total in the accompanying timing line.
Upload time includes CPU/driver calls and waits encountered there, not a
separate GPU execution measurement. All lines use the existing guest-log
bridge and are copied into `halo-diagnostic.txt` in the GFX ZIP. Play for
one to two minutes, then press the top-centre GFX button; ADB is unnecessary.

`tools/test_android_cpu_skeletal.py --dumps halo-gfx-*.zip` reconstructs the
recorded microcode semantics, requires byte-identical original GLSL, then
compares all outputs against real software GLES transform feedback and
tests the GPU passthrough itself.

## NVIDIA Shield performance test v1

The frame rate on the Shield fell with the CPU skinning path. Two causes are
addressed, NVIDIA only; every other GPU keeps its path and timing:

- **Lens flare visibility without waiting.** At the start of every frame the
  game reads the previous frame's lens flare tests. On ES 3.1+ the port read
  exact sample counts from an atomic counter buffer: a synchronous buffer map
  plus `GL_QUERY_RESULT`, so the CPU waited until the GPU had finished the
  whole previous frame, every frame - CPU and GPU time added up instead of
  overlapping. NVIDIA now reads the latest finished hardware query result
  (`GL_QUERY_RESULT_AVAILABLE`, as ES 3.0 devices always did) and keeps the
  last known value until a new one is ready; no sample counter is written.
  A flare is then either visible or not, without partial dimming, and
  follows the occlusion a frame or two later.
- **Faster CPU skinning.** A draw's vertices are cut into chunks of 64 that
  the render thread and worker threads (processors minus two, at most three;
  two on the Shield) take in turn. The guest counts the processors with
  `sched_getaffinity`, which the host now passes on: without it, test 1
  counted one processor and started a single worker. Each chunk decodes only the input
  registers the program reads, column by column, runs the unchanged program
  and writes the attribute planes directly. Attributes a program never
  writes are no longer uploaded: they are constant values (0, 0, 0, 1), fog
  1 and the draw's point size, exactly what the planes held before. Draws
  below 192 vertices stay on the render thread. Results are bit-identical
  to the single-threaded path (`tools/test_android_cpu_parallel.py`).

Diagnostic builds show a section **NVIDIA Shield test** in the settings
overlay (hold SELECT for half a second, D-pad and A/B on a controller). Its
settings apply at once, live, and are saved with OK. The overlay opens on
the skinning mode. Controllers without SELECT (the Shield controller, TV
remotes) hold their Back button instead; a short Back stays Back. The
counter says so in its last line:

| Setting | Values |
|---|---|
| Skinning mode | CPU, several cores (default) - CPU, one core - GPU test A: uniform buffer - GPU test B: full constants - GPU original (known artefacts; frame-rate comparison only) |
| Visibility tests without waiting | on (default) / off: the earlier waiting read |
| Show FPS / frame time | the counter at the bottom centre (default on) |
| Save GFX diagnostic | the GFX capture, reachable with a controller |

GPU test A compiles the original GLSL of a skeletal program with `c[]` as a
std140 uniform block and gives every draw its own copy of the constants in a
per-frame uniform ring (`android_constant_block_bind`). GPU test B keeps the
original shader and uploads all of `c[]` from `c[0]`'s location for every
skeletal draw. Both test the remaining hypothesis that the Tegra driver
loses partial per-draw updates of the uniform array while earlier draws are
in flight; neither was tried before. If one of them draws the NPCs
correctly, skinning can return to the GPU at full speed.

The counter shows, averaged over about a second: FPS, frame time (and its
maximum), the game thread's own CPU time, the CPU skinning time with draws
and vertices, and the waits for visibility reads, the stream ring's fence,
the swap and Present's vertical-blank pacing. Every 300 frames a line
`halo-perf v2: ...` with the same figures, frames over 34 and 50 ms, the
mode and the GL renderer goes to Logcat and `halo-diagnostic.txt`, which the
GFX ZIP contains; its `device.txt` names the saved settings and the counter.

Test 1 showed the GPU never waited: the game thread itself took 26-40 ms
in large fights besides the skinning. Test 2 splits that time. The counter
and `halo-perf v2` add the time inside the draw calls (`D3DDevice_Draw*`,
skinning included) and of it `prepare_draw`'s state, shaders and
constants, with the constant vectors, program switches and the geometry
streamed and mirrored per frame. The CPU's generic timer
(`cntvct_el0`) times these, a register read where `clock_gettime` is a
system call through the host. A second line, `halo-profile v1`, comes
from Halo's own profiler (`source/cseries/profile.c`), switched on while
the test measures and on the same timer: the frame split into render, idle
and the rest (game update, sound, network), then the sections taking most
time per frame - `game_update` and the updates inside it (`ai_update`,
`unit_update`, `projectile_update`...), `render_objects`, `render_model`,
`render_structure_*`... - with their calls per frame.
`NVIDIA CPU skeletal breakdown v2` replaces v1: setup, compute (decoding,
program and planes on all threads) and upload/bind.

`tools/test_android_cpu_parallel.py` compares 5.7 million vertices of all
skeletal programs, interpreter fallbacks, random declarations, immediate
mode and chunk/parallel limits with the reference, also under Address-,
Undefined- and ThreadSanitizer. `tools/test_android_glsl_variants.py`
validates the original, uniform-block and passthrough GLSL with
glslangValidator. Neither replaces a test on the Shield.

The native payload in `port/android/native` is staged by the build
workflow (artifact `halo-android-native`) and must match these sources:
build the APK with the workflow, or `ninja android` with the NDK. Run the
workflow by hand with **Commit the rebuilt native payload** to commit it to
a test branch (never main), so that Android Studio builds of the branch
use it too. A diagnostic build whose libmain.so predates these sources
says so in a message at start, and its counter reads "libmain.so predates
the frame-time counter".
## Find problems

- This Shield matrix diagnostic package enables the top-centre `GFX`
  button by default (also in the settings overlay, for controllers). Click it with touch or a mouse while a stretched NPC
  is visible, wait for the saved-path message, then send
  `Android/media/com.halo.decomp/halo-gfx-<timestamp>.zip`.
  It contains shader sources, the captured frame, all enabled vertex
  attributes and indices. Ordinary GPU programs also provide their
  `c[0..191]` constants and CPU `glUniform4fv` arguments from the captured
  frame. CPU skeletal programs provide the completed vertex outputs.
  Model selection is a shader heuristic, with separate limits of 64
  model and 4 generic draws; time and byte limits and skipped data are
  recorded in `report.txt`. CPU uploads from earlier frames are not a
  complete CPU matrix snapshot. A capture alone cannot establish the
  cause of malformed geometry. Build with `-PhaloDiagnostics=false` to
  hide the diagnostic UI again. The application version stays 1.0.10.
- NVIDIA Android devices retain classic attribute-pointer bindings for
  ordinary meshes and the skeletal passthrough. Other ES 3.1/3.2 GPUs retain
  their stream-binding path. Logcat reports
  `Shield vertex compatibility: classic attribute pointers` when selected.
  Skeletal execution uses the CPU compatibility path described above.

- Enter `adb logcat -s halo` to see the log of the port and the errors of
  the game. `files/debug.txt` is the log of the game.
- If the guest code stops, the log shows the registers and the frame chain.
  To find the functions, enter
  `llvm-symbolizer --obj=build/android/halo_guest.elf <address>`.
- Set `sample_seconds = <seconds>` in `[debug]` of `config.toml`. The log
  then shows the program counter and the frame chain of each guest thread
  at this interval. This finds hangs on devices without root access.
- Set `gl_debug = true` in `[debug]` of `config.toml`. The log then shows
  the OpenGL ES errors.

## Limits

- Bink video is not available. The game skips the movies.
- The loader tries linked game images at `0x40000000`, `0x20000000`,
  `0x60000000`, and `0xa0000000` when an image address is occupied.
  The Xbox data window is separately placed in free low-address memory.
  Existing Android mappings are never overwritten; startup fails with a
  diagnostic if no suitable address is available.
- The game does not accept touch input. Use a controller or a keyboard.
- Kernels with 16 KB pages (a developer option of Android 15) do not
  operate. The Xbox memory uses 4 KB pages.
