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
activity. The AAOS variant has no update button.

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
Without the NDK, run the build workflow by hand with **Commit the rebuilt
native payload**: it commits that directory, built from the branch's
sources, to the branch (never main).

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
The other controllers are players 2 to 4 (split screen). The buttons agree
with the positions on the Xbox controller:

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

Hold SELECT (Create, back) for half a second to open the in-game menu of
the app; SELECT, Start or B on its first page close it again. A short press is the back button of the Xbox controller. Controllers
without SELECT (the NVIDIA Shield controller, TV remotes) use their Back
button the same way. At the main menu, B (and the back gesture of Android)
quits the app; the back button does not, so a press of SELECT too short to
open the settings never quits (`source/interface/ui_widget.c`).

The controller gets the rumble. The back gesture of Android is the B
button.

A Bluetooth or USB keyboard and mouse play as on Linux (the keys of
`port/linux/src/xinput_sdl.c`: W A S D move, the mouse aims, the left
button fires, the right button throws a grenade, Escape pauses). While
the game plays, the mouse is captured (Android's pointer capture, Android
8 and later), so the aim never stops at the screen's edge; F12 frees it
and captures it again. In the game's menus the mouse moves a pointer
instead: a click chooses, the right button goes back, the wheel scrolls
(`halo_ui_pointer_update` in `port/linux/src/d3d8_gl.c`). The in-game
menu takes the mouse as any app does. F1 is SELECT: a short press Halo's
Back, held the in-game menu, again its close. A physical keyboard with
letters or a mouse hides the touch controls, as a controller does
(`ControllerPresence.java`); the screen's keyboard and a handheld's own
buttons do not. In the in-game menu, **Controls → Touch buttons** chooses
**Auto** (the default: the input used last decides; a finger on the screen
shows them, a controller's button or stick, a key or the mouse hides them,
and connecting one hides them too; a fingerprint sensor that says it is a
gamepad does not count), **Force** (always shown, whatever is connected) or
**Suppress** (always hidden, for a Chromebook, say).

Without a controller, the screen shows touch controls (RetroTouch
1.0.0-beta.13). The buttons show symbols for what they do, as the RE
style of CubeEvil4-Android, in the in-game menu's blues: one skin, the
ICONS style, nothing to switch (`HaloTouchStyle.java`). The triggers
(Fire, Grenade), the bumpers (Light, Type), Pause and SELECT are
rectangles, not round; a button shows its symbol alone, centred. RetroTouch's own symbols are used
where one fits (the crosshair, the cartridge, pause, the menu, the
arrows); Jump, Crouch, Melee, Switch weapon, Grenade, Switch grenade,
Flashlight and Zoom have simple line drawings of the port's own. The
menus' buttons keep their words (OK, Back, X, Y). The touch controls
hide while a controller is connected: a physical device with a gamepad or
joystick source that also has a stick or a D-pad on axes
(`ControllerPresence.java`). Phones list more devices as gamepads, such as
the fingerprint sensors of Xiaomi, Redmi and Poco phones (`uinput-fpc`,
`uinput-goodix`), which have only keys and leave the touch controls shown.
Logcat and the diagnostic file name each gamepad device and the choice.

Some handhelds (Anbernic's among them) have L2 and R2 keys instead of
analog triggers. SDL maps them to no trigger when it does not know the
controller. The game then reads the keys as fully pulled triggers
(`host_sdl_gamepad_digital_triggers` in `host/host_sdl.c`). The diagnostic
file gets the mapping of each controller and the first presses of its
buttons and axes.

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
| `display.direct_camera` | `true` (the default): in first person, on foot, the view points where the player aims in each frame, not where the last tick left it, a tick less behind the stick. `false`: as before. |
| `debug.sample_seconds` | Refer to "Find problems". |

### In-game menu

The in-game menu (`SettingsOverlay.java`, laid out like CubeEvil4's in
Halo's colours) shows the version, an update button and **Back to the
game**, four pages: **Display** (brightness, gamma, 60 FPS, FPS display, resolution,
upscaling, MSAA, texture filtering, FXAA, depth of field), **Controls** (touch buttons, gyroscope, stick sensitivity,
keyboard & mouse), **Volume** and **Cheats**, and at the bottom a button to this port's page on
GitHub. Every change applies and is saved at once. The D-pad or the
left stick moves, A presses, L1 / R1 (Q / E, Page up / Page down) change the
value of the focused arrow or slider cell, B goes back a page, Start closes. Its texts
are in English, German, French and Italian (`res/values*/strings_menu.xml`).

Its look follows CubeEvil4-Android's 1.1.0 menu, in Halo's blues: every
sub-page has side labels on the left and the settings on the right, in
pairs where they fit; every cell is 64 dp high; headings carry a faint
line. Choices of more than two values (resolution, upscaling, MSAA) are arrow
cells (`ArrowSelector.java`: ‹ › on the sides, the value big, a dot per
step, lit while not off); sliders are cells too (`SliderCell.java`: name,
value, bar; ‹ › step, the bar still drags); the gyroscope's sensitivity, the
master volume and the texture filtering span both columns. With a mouse,
a pressed cell lights up (no hover look, as CubeEvil4's). Narrow
windows stack the label above its settings and fold the pairs.

**Keyboard & mouse** (Controls): the mouse's sensitivity (25 to 300 %,
100 % by default, in per cent of `input.mouse_sensitivity`) and **Invert
mouse Y**, sent to the game through `host_settings_mouse_look`
(`host/host_touch.c`) and applied in `halo_linux_mouse_look`
(`port/linux/src/xinput_sdl.c`) to the mouse's motion only, not to the
touch look. Below them a read-only overview of the keys
(`keyboard_gamepad`): W A S D move, the mouse aims, left button fires,
right button or G throws a grenade, Space / Enter jump, E / R reload or
use, Tab or the wheel switch weapons, X switches grenades, F / Backspace /
mouse button 4 melee, left Ctrl / C crouch, Z or the middle button zoom,
Q the flashlight, Esc the pause menu, F1 back (held: this menu), F12 frees
or captures the mouse, the arrow keys are the D-pad. The keys cannot be
changed yet.

The update button asks GitHub for the releases of
`Andiweli/HaloCE-Android-AAOS` (`AppUpdate.java`) and takes the one with the
highest version (its tag `1.0.16`; drafts, pre-releases and the CI's
`build-N` releases do not count): green when the app is up to date, red
with a newer release (one with an `.apk` without `aaos` in its name). It
opens the releases page in the browser; the app downloads and installs
nothing itself. Android Automotive builds have no button.

**Resolution** (Original 480p, 720p, 1080p, Native; 1080p by default,
prefs `resolution`): the lines the game draws its picture in. The game
still works in its 480 lines; the screen's render targets get lines / 480
pixels per unit (`screen_scale`, as fullscreen on the desktop), and
viewports, clears, scissors and visibility counts follow (`target_scale`),
so the HUD, the menus, MSAA's renderbuffers, the depth of field's copy,
FXAA, the screenshot and the FPS display's size all take the new size.
Never more lines than the screen has, never fewer than 480; Native is the
screen's own, and no target wider than the GPU's largest texture. It
applies at once, between two frames (`halo_screen_commit`, logged as
`screen: ...`). The targets of an earlier size are kept, not freed
(`render_target_get` never frees), ready for a change back: at most one set
per choice. The screen's height is taken when the choice changes, so a
surface that changes its size while it stays (AAOS split screen) does not
make a new set at every size (`screen_mode_choose` in
`port/linux/src/d3d8_gl.c`, `host_settings_resolution` in
`host/host_touch.c`).

**Upscaling** (Linear, SGSR, FSR; Linear by default, prefs `upscaler`): how
a picture smaller than the screen is brought to it at Present
(`host_settings_present` in `host/host_settings.c`, `host/host_upscale.c`),
as CubeEvil4's 1.1.0. Linear is the plain stretch; SGSR is Qualcomm's
Snapdragon Game Super Resolution 1 (one pass); FSR is AMD's FidelityFX
Super Resolution 1 (EASU, then RCAS's sharpening at 0.2 stops). The
third-party files stay unchanged in `port/third_party/` and are embedded
at build time (`tools/android_embed.py`); FSR's constants are made on the
processor. Brightness and gamma are applied after the upscaler. Offered
only while the picture is smaller than the screen; it needs GLSL ES 3.10
(`textureGather`), else, or when a shader fails, the plain stretch stays.

**Texture filtering** (a slider: Off, 2x, 4x, 8x, 16x) replaces `display.anisotropic_filtering`
at once (`anisotropic_filtering` in `port/linux/src/d3d8_gl.c`, asked once a
frame), at most the GPU's maximum. 4x is the default.

**MSAA** (Off, 2x, 4x; off by default) draws the screen's render targets
into multisampled renderbuffers (OpenGL ES 3.0), the color's and the
depth's, which keep their samples from one framebuffer to the next: Halo
draws its walls in several passes over the same depth, with its other
targets drawn in between. A color target is resolved into its texture when
something reads it: a draw that samples it, the screenshot, Present
(`msaa_framebuffer`, `msaa_resolve` and `bind_targets` in
`port/linux/src/d3d8_gl.c`). The first try,
`GL_EXT_multisampled_render_to_texture`, lost the depth whenever the
framebuffer changed: the walls turned bright and see-through. Where the
GPU has no samples, or a renderbuffer cannot be made, the menu offers Off
only.

**FPS display top left** (off by default; `FpsCounter.java`, as
CubeEvil4's): the frames the game advanced in each second
(`game_time_update`), with 60 FPS also the pictures shown (Present), the
screen's refresh rate and the size the pictures are drawn at, as
"30 FPS (Game) · 60 Hz · 2400×1080". Hidden while the menu is open.

**FXAA** (off by default; CubeEvil4's shader) smooths the edges once more
on the world and the weapon, with or without MSAA, before the HUD.

**Depth of field** (off by default) is an autofocus of this port's own
(`xgpu_post_process` in `d3d8_gl.c`, called by `render_window` in
`source/render/render.c` after the world, its effects and fog, before the
lens flares, the HUD and the menus): the distance at the crosshair is in
focus, followed over about a third of a second; what lies behind it blurs
more the farther it is, never what is in front. The first-person weapon,
which the game marks in bit 0 of the stencil, stays sharp and is not
blurred into the world. Only with one player on the screen. A slider
beside the switch sets its strength, 10 to 200 % (50 % by default; 100 %
was the first build's): the blur widens with it, and where it starts and
where it is full come nearer.
`tools/test_android_depth_of_field.py` runs its shaders and FXAA's in
Chromium's WebGL2 (the GLSL ES of the phones) on made-up frames.

**Cheats**: the switches *Infinite health*, *Infinite ammo*, *Never
reload* and *One-hit kill* set the original game's `cheat_deathless_player`,
`cheat_infinite_ammo`, `cheat_bottomless_clip` and `cheat_omnipotent`; they
stay on, also after a restart, until switched off. *All weapons* lays the
level's weapons around the player (`cheat_all_weapons`), *Spawn Warthog*
puts the level's Warthog in front of the player, if the level has one (The
Pillar of Autumn has none). In another player's network game the host's
rules apply and the cheats are off (`android_cheats_update` in
`source/game/cheats.c`). `tools/test_android_ingame_menu.py` checks the
texts, the keys and the cheats from the menu to the game.

The game shows 30 frames each second, as on the Xbox: the host starts it
with `display.interpolation` false (`host/host_main.c`), whatever
`config.toml` says. The switch **60 FPS (experimental)** in the display
page of the in-game menu turns on the interpolation of the Linux
port instead (refer to "Frame rate" in
[port/linux/README.md](../linux/README.md#frame-rate)): one frame for each
refresh of the display. It takes effect at once, between two frames
(`halo_interpolation_update` in `port/linux/src/sdl_platform.c`, asked by
`main_loop`), and is saved at once. The interpolation is not perfect: the
spaceship in the first level hops, which is why 30 is the default. `tools/test_android_frame_rate.py` checks the switch.

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

The app does not update itself. When a newer release is on GitHub, the
update button of the in-game menu turns red; it opens the releases page
(https://github.com/Andiweli/HaloCE-Android-AAOS/releases). Download the
`.apk` there and install it.

To install over the previous version, each build must have the same
signature. GitHub Actions signs each build with the key in the
`ANDROID_KEYSTORE_BASE64` and `ANDROID_KEYSTORE_PASSWORD` secrets of the
repository. If you installed a build that has a different signature, remove
that build before you install a new build. Removing the app deletes its data
folder: first make a copy of `maps/` and `save/`.

### Changes in 1.1.2

- Touch controls missing on some phones (a Galaxy A36 with 1.1.1): the
  phone lists a built-in device as a keyboard with letters, which hid the
  touch controls. Now only a connected keyboard or mouse (Bluetooth, USB;
  Android 10 and later) hides them at once; a built-in one (a Chromebook's
  keyboard and touchpad too) hides them when it is used. A finger on the
  screen always brings them back, until a key or the mouse is used again.
- In-game menu, Controls: **Touch buttons** Auto / Force / Suppress, as
  CubeEvil4's. Auto follows the input used last: a finger shows them (with
  a controller there too), a controller's button or stick, a key or the
  mouse hides them; Force always shows them (with a controller, a keyboard
  or a mouse there too); Suppress always hides them.
- In-game menu: the side label "Keys" stands beside the first key line.

### Changes in 1.1.1

- Keyboard and mouse, in the game and in its menus (see Controls); a
  keyboard or a mouse hides the touch controls, F1 opens the in-game menu.
- The in-game menu takes CubeEvil4's 1.1.0 look: side labels, settings in
  pairs, 64 dp cells, arrow cells for MSAA, slider cells (texture
  filtering now up to 16x); L1 / R1 change a value. New in Controls: **Keyboard & mouse** with
  the mouse's sensitivity, its Y axis and an overview of the keys.
- Display: **Resolution** (Original 480p, 720p, 1080p, Native; 1080p by
  default) and **Upscaling** (Linear, SGSR, FSR) as CubeEvil4's 1.1.0;
  both apply at once.
- Licences of AMD FidelityFX FSR 1 (MIT) and Qualcomm Snapdragon GSR 1
  (BSD-3-Clause) in `assets/licenses`.
- The mouse in the game: Android sends the captured mouse's moves and
  buttons in events that SDL 3.4 does not pass on, so the aim did not move.
  `HaloSurface` passes them on (moves as relative motion, each button as a
  press or a release). The in-game menu lets the mouse go when it opens, so
  its pointer shows and clicks work, and the game takes it back when the
  menu closes (`org.libsdl.app.HaloPointer`).
- The in-game menu and the mouse: a pressed cell lights up (no hover look,
  as CubeEvil4's); the mouse no longer moves the controller's focus (its axes
  are the pointer's place, `SettingsOverlay.motion` now takes only a
  controller's).
- Lens flares behind a pillar or a wall no longer shine through it: the
  GPU's count of a flare's visible pixels (on GPUs with atomic counters) is
  now in the game's pixels, as the game reads it; at 1080p it was some five
  times too high, so a flare all but hidden shone in full.
- The FPS display shows again: since it moved into a frame of its own
  (02.11.2026) its line stayed hidden. It keeps clear of the system's
  caption bar (ChromeOS), a camera cutout and bars that show.

### Changes in 1.1.0

- RetroTouch 1.0.0-beta.13: the touch buttons show symbols (as CubeEvil4's
  RE style, in Halo's blues), one skin, nothing to switch. The menus'
  touch layout is new; the gameplay layout a player made stays.
- The in-game menu shows the version small left of its buttons, as
  CubeEvil4's.
- From upstream: crash fixes (scripts and objects that no longer exist, a
  player leaving split screen, a sound without a listener, a looping sound
  fading out, a projectile without its owner, negative periodic
  functions), at 60 FPS the first-person animations, camera shake,
  contrails, flags, lightning and shadows per tick, widescreen chapter
  titles, riders thrown from a vehicle landing on its side, a cheaper
  sound occlusion test, a wait for the GPU when a frame fence fails.

### Changes in 1.0.18

- License: AGPL-3.0-or-later (releases up to 1.0.17 stay CC0).
- Save & Quit saves the game at the moment it is chosen, not the last
  checkpoint (the last checkpoint while dead, falling or in a cinematic).
- No grey veil after the in-game menu or a return from the background
  (Android's focus highlight on the game's surface is off).
- No self-update: the update button opens the releases page.
- From upstream: particles drawn after a tick's update (60 FPS), shorter
  sound start and stop, no level flashing at portal edges, NaN-safe
  particles, fog screen per split-screen window, faster LRU caches, a Theater
  menu crash, the network port asked once.
- The first-person view turns in the frame the stick moves.
- Lens flares hold over a single occlusion test of 0.

## Widescreen

The game shows 480 lines in the shape of the display, not the 640x480 of
the Xbox (drawn at the menu's resolution, see **Resolution** above):

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
- The NVIDIA driver (Tegra X1 of the Shield TV) computes the skinned vertex
  shaders (characters, weapons) incorrectly. On NVIDIA, the CPU runs these
  shaders (`nv2a_cpu_program` in `nv2a_vsh.c`; the fixed code in
  `nv2a_cpu_shaders.inc` comes from `tools/android_cpu_shader_generate.py`)
  and the GPU gets the finished vertices. Large draws are divided among the
  render thread and up to three worker threads (the number of processors
  minus two).
- On NVIDIA, the visibility tests do not wait for the GPU. The game reads the
  last finished result. Waiting halved the frame rate in large fights.

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

## Find problems

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
  A saved game (checkpoint, Save and Quit) loads only where the window lay
  when it was written, so the host keeps the window's address in
  `save/memory_window.txt` and takes it first the next time. When that
  address is taken, the log says so, and such a saved game starts the
  level again.
- Save and Quit in the pause menu keeps the game as it is at that moment,
  not the last checkpoint as on the Xbox. While the player is dead or
  falling, or a cinematic plays, it keeps the last checkpoint.
  Existing Android mappings are never overwritten; startup fails with a
  diagnostic if no suitable address is available.
- Kernels with 16 KB pages (a developer option of Android 15) do not
  operate. The Xbox memory uses 4 KB pages.
