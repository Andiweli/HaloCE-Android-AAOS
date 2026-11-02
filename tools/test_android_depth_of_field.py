#!/usr/bin/env python3
"""Run the in-game menu's depth of field and FXAA (port/linux/src/d3d8_gl.c) on made-up frames.

The production shaders (dof_vertex, dof_common, dof_mask, dof_focus,
dof_blur), formatted as xgpu_post_process formats them, compile and run
as GLSL ES 3.00 in Chromium's WebGL2 (the OpenGL ES 3.0 of the phones),
through Playwright (tools/test_android_depth_of_field.js). On a frame with
a near block in the middle of a far checkerboard and a stripe of the
first-person weapon:
- the autofocus finds the block's distance at once, and moves a tenth of
  the way (in log distance) toward a new one each frame;
- the far checkerboard is blurred to nearly flat grey; the block, in
  focus, stays exact to the pixel;
- the weapon's colour hardly reaches the world beside it.
FXAA (dof_fxaa) smooths a hard diagonal staircase, leaves flat areas and
the alpha as they were.
Requires a C compiler, Node and Playwright with Chromium.
"""
from pathlib import Path
import json
import math
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'port/linux/src/d3d8_gl.c').read_text()
part = source[source.index('#define DOF_LOW_LOG2'):source.index('static GLuint dof_program(')]
part = re.sub(r'static struct\n\{.*?\} dof;\n', '', part, flags=re.S)
emit = '#include <stdio.h>\n' + part + r'''
int main(void)
{
	char focus[4096], blur[4096];
	FILE *f;
	snprintf(focus, sizeof focus, dof_focus, DOF_LOW_LOG2, DOF_RANGE_LOG2);
	snprintf(blur, sizeof blur, dof_blur, DOF_RANGE_LOG2, DOF_LOW_LOG2);
	f = fopen("vertex.glsl", "w"); fprintf(f, "#version 300 es\n%s", dof_vertex); fclose(f);
	f = fopen("mask.glsl", "w"); fprintf(f, "#version 300 es\n%s%s", dof_common, dof_mask); fclose(f);
	f = fopen("focus.glsl", "w"); fprintf(f, "#version 300 es\n%s%s", dof_common, focus); fclose(f);
	f = fopen("blur.glsl", "w"); fprintf(f, "#version 300 es\n%s%s", dof_common, blur); fclose(f);
	f = fopen("fxaa.glsl", "w"); fprintf(f, "#version 300 es\n%s%s", dof_common, dof_fxaa); fclose(f);
	return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='halo-dof-') as name:
    folder = Path(name)
    (folder / 'emit.c').write_text(emit)
    subprocess.run(['cc', '-Wall', '-o', str(folder / 'emit'), str(folder / 'emit.c')], check=True)
    subprocess.run([str(folder / 'emit')], cwd=folder, check=True)
    npm_root = subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True).stdout.strip()
    output = subprocess.run(['node', str(ROOT / 'tools/test_android_depth_of_field.js'), str(folder)],
                            capture_output=True, text=True, check=True,
                            env={**__import__('os').environ, 'NODE_PATH': npm_root}).stdout
result = json.loads(output.strip().splitlines()[-1])
assert not result.get('logs') and not result.get('error'), result
assert abs(result['focus1'] - 10.0) < 0.05 and abs(result['focus2'] - 10.0) < 0.05, result
expected = 2 ** (math.log2(10) + 0.1 * (math.log2(500) - math.log2(10)))
assert abs(result['focus3'] - expected) / expected < 0.01, (result, expected)
assert result['farSpread'] <= 20, result      # 0/255 checkers within 20 of grey
assert result['nearSame'], result
assert result['redNear'] <= 8, result         # the weapon's red beside it, of 255
assert result['fxaaEdge'] >= 2, result        # a staircase: pixels between black and white
assert result['fxaaFlat'], result             # flat areas as they were
assert result['fxaaAlpha'], result            # alpha kept
print(f"FXAA: {result['fxaaEdge']} pixels of a hard staircase smoothed, flat areas and alpha unchanged.")
print(f"Depth of field: focus {result['focus1']:.2f} (10), then {result['focus3']:.2f} toward 500; far checkers "
      f"within {result['farSpread']} of grey, the block in focus exact, the weapon's red {result['redNear']}/255 beside it.")
