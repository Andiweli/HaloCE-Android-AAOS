#!/usr/bin/env python3
"""Exercise the production checkpoint, visibility and cache code with fixtures.

Run from the project root: python3 tools/test_upstream_optimizations.py
No APK, GPU, game assets or external Python packages are required.
"""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def block(source, marker, declaration=False):
    start = source.index(marker)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + (";" if declaration else "")


def function(source, name):
    # Skip prototypes and historical symbol lists.
    pattern = r"^(?:static )?(?:__inline )?[\w *]+\b" + re.escape(name) + r"\s*\([^;{}]*\)\s*\{"
    match = re.search(pattern, source, re.M)
    if not match:
        raise ValueError(f"Function not found: {name}")
    return block(source[match.start():], match.group())


def run_fixture(name, replacements, flags=()):
    source = (ROOT / "tools/upstream_tests" / (name + ".c")).read_text()
    for marker, code in replacements.items():
        token = "/* PRODUCTION_" + marker + " */"
        assert source.count(token) == 1, token
        source = source.replace(token, code)
    assert "/* PRODUCTION_" not in source
    with tempfile.TemporaryDirectory(prefix="halo-upstream-") as directory:
        cfile = Path(directory) / (name + ".c")
        binary = Path(directory) / name
        cfile.write_text(source)
        compiler = shlex.split(os.environ.get("CC", "cc"))
        command = compiler + ["-std=c11", "-D_POSIX_C_SOURCE=200809L", "-O1", "-g",
                              "-Wno-multichar", *flags, str(cfile), "-pthread", "-lm", "-o", str(binary)]
        compiled = subprocess.run(command, text=True, capture_output=True, timeout=30)
        if compiled.returncode:
            print(compiled.stdout + compiled.stderr)
            compiled.check_returncode()
        subprocess.run([str(binary)], check=True, timeout=20)


def main():
    saved = (ROOT / "source/saved games/game_state_xbox.c").read_text()
    state = (ROOT / "source/saved games/game_state.c").read_text()
    checkpoint_names = ["game_state_writer_main", "game_state_writer_ready", "game_state_writer_wait",
                        "game_state_writer_dispose", "game_state_free_buffer", "game_state_create_or_open_file",
                        "game_state_close_file", "game_state_write_to_file", "game_state_read_from_file"]
    run_fixture("checkpoints", {
        "GLOBALS": block(saved, "struct xbox_game_state_globals_prefix\n", True)
        + "\nstatic struct xbox_game_state_globals_prefix xbox_game_state_globals;\n"
        + block(saved[saved.index("All writer state is outside"):], "static struct\n", True).removesuffix(";")
        + " game_state_writer;\n",
        "FUNCTIONS": "\n".join(function(saved, name) for name in checkpoint_names)
        + "\n" + function(state, "game_state_dispose"),
    })

    renderer = (ROOT / "port/linux/src/d3d8_gl.c").read_text()
    globals_start = renderer.index("static unsigned long long constant_serials[")
    globals_end = renderer.index("static void constants_store", globals_start)
    program = block(renderer, "struct program_entry\n", True)
    serial_field = re.search(r"\tunsigned long long constants_serial;", program).group()
    code = {
        "SERIAL_FIELD": serial_field,
        "CONSTANT_GLOBALS": renderer[globals_start:globals_end],
        "CONSTANT_STORE": function(renderer, "constants_store"),
        "CONSTANT_UPLOAD": block(renderer, "if (entry->constants >= 0 && entry->constants_serial != constants_serial)"),
        "VISIBILITY": "\n".join(function(renderer, name) for name in (
            "D3DDevice_BeginVisibilityTest", "D3DDevice_EndVisibilityTest", "visibility_unscaled",
            "visibility_test_result", "D3DDevice_GetVisibilityTestResult")),
    }
    run_fixture("renderer", code, ("-DHALO_ANDROID=1",))
    run_fixture("renderer", code)

    partitions = (ROOT / "source/structures/cluster_partitions.c").read_text()
    part_header = (ROOT / "source/structures/cluster_partitions.h").read_text()
    data = (ROOT / "source/memory/data.c").read_text()
    data_header = (ROOT / "source/memory/data.h").read_text()
    references = (ROOT / "source/objects/reference_lists.h").read_text()
    lights = (ROOT / "source/objects/object_lights.c").read_text()
    objects = (ROOT / "source/objects/objects.c").read_text()
    profile = (ROOT / "source/cseries/profile.c").read_text()
    light_cache_start = lights.index("enum\n", lights.index("/* port: the clusters' lights kept"))
    light_cache_end = lights.index("struct lights_game_globals *", light_cache_start)
    run_fixture("caches", {
        "STRUCTURES": "\n".join(block(text, marker, True) for text, marker in (
            (data_header, "struct data_array\n"), (data_header, "struct datum_header\n"),
            (references, "struct data_reference\n"), (part_header, "struct cluster_partition\n"))),
        "DATA": "\n".join(function(data, name) for name in (
            "datum_initialize", "datum_try_and_get", "datum_get", "datum_new", "datum_delete")),
        "REFERENCES": "\n".join(function(references, name).replace("__inline", "static inline")
                                    for name in ("reference_list_new", "reference_list_get_next_datum_index")),
        "PARTITIONS": partitions[partitions.index("/* ---------- prototypes */"):],
        "LIGHT_CACHE": lights[light_cache_start:light_cache_end],
        "LIGHT_FUNCTIONS": "\n".join(function(lights, name) for name in (
            "find_point_light_for_object", "lights_port_cluster", "find_point_lights_for_object_in_cluster")),
        "GARBAGE": function(objects, "objects_garbage_cooperative")
        + "\n" + function(objects, "objects_garbage_active_due"),
        "PROFILE": re.search(r"^#define PROFILE_TEXTURE_TIMED.*\n[^\n]+", profile, re.M).group()
        + "\n" + function(profile, "profile_texture_start") + "\n" + function(profile, "profile_texture_end"),
    })

    textures = (ROOT / "port/linux/src/xbox_textures.c").read_text()
    xgpu = (ROOT / "port/linux/src/xgpu.h").read_text()
    run_fixture("textures", {
        "DESCRIPTION": block(xgpu, "struct xgpu_texture_description\n", True),
        "CACHE": textures[textures.index("struct texture_entry\n"):],
    })


if __name__ == "__main__":
    main()
