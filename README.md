# Halo: Combat Evolved - Android & AAOS

![Android](https://img.shields.io/badge/up%20to-Android%2015%20-green)
![Architecture](https://img.shields.io/badge/architecture-ARM64%20%2864--bit%29-orange)
![AI](https://img.shields.io/badge/AI-assisted%20coding-6e7781)
![Controls](https://img.shields.io/badge/Controls-Gamepad%20%2F%20RetroTouch%20%2F%20Keyboard-blueviolet)
![Multiplayer](https://img.shields.io/badge/Multiplayer-System%20Link%20%2F%20Online-blueviolet)

## 🎮 Introduction

An unofficial **Halo: Combat Evolved** port for Android phones, handhelds and
**Android Automotive OS (AAOS)**. Based on
[thelinkin3000/halo-ce-universal](https://github.com/thelinkin3000/halo-ce-universal)
and the Halo Xbox decompilation projects credited upstream. [Take a short preview](https://github.com/user-attachments/assets/f327569b-4370-45c4-a937-2cc7ec899b11).

<p align=center>
<img width="854" height="480" alt="image" src="https://github.com/user-attachments/assets/7a56c91c-f4c2-4c7e-84ee-76058461b73c" />
<img width="854" height="480" alt="image" src="https://github.com/user-attachments/assets/5699972f-36bb-4524-8aa8-006063af9982" />
</p>

This fork adds controller-aware [RetroTouch](https://github.com/Andiweli/RetroTouch),
profile volume controls, cleaned-up menus, immersive mobile display and an AAOS
build that respects the vehicle's available screen area. AAOS audio buffering
and Android memory-layout fallbacks are included. The game uses the original
**30 FPS mode**, with a corrected geometry-upload path tested on Retroid.
Use the AAOS build while parked.

<p align=center>
<img width="854" height="480" alt="image" src="https://github.com/user-attachments/assets/b8a476e3-f6a5-40bf-98e1-138493be4c47" />
</p>

Requires **ARM64**, Android **9+** for mobile or **10+** for AAOS, and a compatible
OpenGL ES 3 GPU. The Android badge describes the current build target (API 35),
not device-wide certification; the recent rendering fixes were tested on
Android 13. This is not Android Auto phone projection.

Open the **repository root in Android Studio**. Choose `mobileDebug` /
`mobileRelease` or `aaosDebug` / `aaosRelease`. Matching native binaries are
included. See [Android build instructions](port/android/README.md) for native
rebuilds. Keep your signing key and increase `versionCode` for published updates.

## 🚗 What is AAOS?

**Android Automotive OS (AAOS)** is Android running directly on a vehicle's
infotainment system. Apps are installed on the vehicle itself. It is different
from **Android Auto**, which projects supported phone apps onto the car's screen.
This project's AAOS build is intended for compatible vehicles while parked to be playable with a connected Bluetooth Controller.

In most cases, AAOS builds can only be installed via the Play Store, unless you have root access to your vehicle (you do this at your own risk).

<img width="1080" height="810" alt="image" src="https://github.com/user-attachments/assets/c8a02b2f-5525-433e-afe7-2f4446cf64d2" />

> [!NOTE]
> If you are interested in testing the AAOS version, contact me.

## 💾 Game data

**No commercial game data is included.** Supply an Xbox Halo: Combat Evolved
`.iso` / `.xiso` image from your own legally obtained copy; PC and Custom Edition
data are not substitutes for the Xbox maps.

1. Copy the disc image to your Android device.
2. Start the app and select the image in the installer.
3. Let the app extract the game data, then start Halo.

The imported maps determine the available localized text and speech. For German
menus and voices, use a compatible German-language Xbox release. The port
supports PAL map timing conversion. The installer uses app-specific storage;
you do not need to modify `ui.map` manually. Diagnostic exports, when requested,
are written to `Android/media/com.halo.decomp/`.

## 🌐 Multiplayer

The upstream port provides **System Link over LAN** and **online play through
invite links**, including cross-platform sessions with compatible Linux,
Windows and Android builds. For LAN play, connect devices to the same network
and avoid Wi-Fi client isolation. Use matching port versions and compatible
game data on all participants.

Online connectivity depends on the network and upstream networking support;
it is not an official Xbox Live service. See the
[multiplayer documentation](port/linux/README.md) and
[netcode notes](port/linux/NETCODE.md). Multiplayer has not been revalidated by
the recent single-player rendering tests.

## ⚖️ Legal

Halo, Halo: Combat Evolved, Xbox and their associated assets and trademarks
belong to their respective owners, including Microsoft. This community project
is not affiliated with or endorsed by Microsoft or Bungie.

See [LICENSE.md](LICENSE.md) for the repository's license notice. Third-party
components retain their own licenses, including
[SDL](port/android/native/SDL-LICENSE.txt) and
[musl](port/android/native/MUSL-COPYRIGHT.txt). These notices do not grant rights
to the original game's commercial assets. You must supply your own game data.
