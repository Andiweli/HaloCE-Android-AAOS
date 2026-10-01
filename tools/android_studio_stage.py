#!/usr/bin/env python3
"""Stage a freshly built Android engine for the portable Studio project."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/android"
DEST = ROOT / "port/android/native"


def patch_automotive_surface(path):
    """Keep the AAOS aspect fix when regenerating staged SDL Java sources."""
    source = path.read_text(encoding="utf-8")
    marker = "// Halo AAOS: its render aspect must follow the inset-safe surface,"
    if marker in source:
        return
    anchor = "        synchronized(SDLActivity.getContext()) {"
    if source.count(anchor) != 1:
        raise SystemExit("SDL SDLSurface changed; review the AAOS surface-size patch before staging.")
    patch = "        // Halo AAOS: its render aspect must follow the inset-safe surface,\n        // not the physical display including the vehicle's system bars.\n        // This is sent before handleNativeState starts the game thread.\n        if (width > 0 && height > 0 && getContext().getPackageManager().hasSystemFeature(\n                android.content.pm.PackageManager.FEATURE_AUTOMOTIVE)) {\n            nDeviceWidth = width;\n            nDeviceHeight = height;\n        }\n\n"
    path.write_text(source.replace(anchor, patch + anchor, 1), encoding="utf-8")


def main():
    files = ["assets/halo_guest.elf", "jniLibs/arm64-v8a/libmain.so",
             "jniLibs/arm64-v8a/libSDL3.so"]
    files += [f"assets/halo_guest_{address}.elf" for address in ("20000000", "60000000", "a0000000")]
    java = BUILD / "third_party/SDL3/android-project/app/src/main/java"
    for name in files:
        if not (BUILD / name).is_file():
            raise SystemExit(f"Missing {BUILD / name}; run ninja android first.")
    if not (java / "org/libsdl/app/SDLActivity.java").is_file():
        raise SystemExit("SDL Java sources are missing; run configure.py first.")
    for name in files:
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BUILD / name, target)
    target = DEST / "sdl-java"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(java, target)
    patch_automotive_surface(target / "org/libsdl/app/SDLSurface.java")
    shutil.copy2(BUILD / "third_party/SDL3/LICENSE.txt", DEST / "SDL-LICENSE.txt")
    shutil.copy2(BUILD / "third_party/musl-1.2.5/COPYRIGHT", DEST / "MUSL-COPYRIGHT.txt")
    hashes = {str(p.relative_to(DEST)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(DEST.rglob("*")) if p.is_file() and p.name != "SHA256.json"}
    (DEST / "SHA256.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
    print(f"Staged {len(hashes)} files in {DEST}")


if __name__ == "__main__":
    main()
