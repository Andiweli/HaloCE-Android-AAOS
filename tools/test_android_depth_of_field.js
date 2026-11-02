const { chromium } = require('playwright');
const fs = require('fs');
const dir = process.argv[2];
const src = n => fs.readFileSync(dir + '/' + n, 'utf8');
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage();
  const result = await page.evaluate(({ vs, mask, focus, blur }) => {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2');
    if (!gl) return { error: 'no webgl2' };
    const out = { logs: [] };
    function program(fs, name) {
      const v = gl.createShader(gl.VERTEX_SHADER); gl.shaderSource(v, vs); gl.compileShader(v);
      if (!gl.getShaderParameter(v, gl.COMPILE_STATUS)) out.logs.push(name + ' vs: ' + gl.getShaderInfoLog(v));
      const f = gl.createShader(gl.FRAGMENT_SHADER); gl.shaderSource(f, fs); gl.compileShader(f);
      if (!gl.getShaderParameter(f, gl.COMPILE_STATUS)) out.logs.push(name + ' fs: ' + gl.getShaderInfoLog(f));
      const p = gl.createProgram(); gl.attachShader(p, v); gl.attachShader(p, f); gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) out.logs.push(name + ' link: ' + gl.getProgramInfoLog(p));
      gl.useProgram(p);
      gl.uniform1i(gl.getUniformLocation(p, 'color_texture'), 0);
      gl.uniform1i(gl.getUniformLocation(p, 'depth_texture'), 1);
      gl.uniform1i(gl.getUniformLocation(p, 'focus_texture'), 2);
      return p;
    }
    const pm = program(mask, 'mask'), pf = program(focus, 'focus'), pb = program(blur, 'blur');
    if (out.logs.length) return out;
    const W = 96, H = 48, near = 0.05, far = 1024;
    const d = z => far / (far - near) * (1 - near / z);
    // scene: far (500) everywhere, a near block (10) in the middle, a weapon stripe (alpha 0, red) at x 70..73
    const depth = new Float32Array(W * H), color = new Uint8Array(W * H * 4);
    const zAt = (x, y) => (x >= 36 && x < 60 && y >= 14 && y < 34) ? 10 : 500;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x; depth[i] = d(zAt(x, y));
      const weapon = x >= 70 && x < 74;
      const v = ((x + y) & 1) ? 255 : 0;
      color.set(weapon ? [255, 0, 0, 0] : [0, v, v, 255], i * 4);
    }
    function tex(internal, w, h, format, type, data, filter) {
      const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texImage2D(gl.TEXTURE_2D, 0, internal, w, h, 0, format, type, data); return t;
    }
    const tc = tex(gl.RGBA8, W, H, gl.RGBA, gl.UNSIGNED_BYTE, color, gl.LINEAR);
    const td = tex(gl.DEPTH_COMPONENT32F, W, H, gl.DEPTH_COMPONENT, gl.FLOAT, depth, gl.NEAREST);
    const tf = [0, 1].map(() => tex(gl.RGBA8, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4), gl.NEAREST));
    const fb = t => { const f = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, f); gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0); return f; };
    const ff = tf.map(fb);
    const to = tex(gl.RGBA8, W, H, gl.RGBA, gl.UNSIGNED_BYTE, null, gl.NEAREST), fo = fb(to);
    const vao = gl.createVertexArray(); gl.bindVertexArray(vao);
    function bind(focusTex) { [tc, td, focusTex].forEach((t, u) => { gl.activeTexture(gl.TEXTURE0 + u); gl.bindTexture(gl.TEXTURE_2D, t); }); }
    function runFocus(from, to, rate) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, ff[to]); gl.viewport(0, 0, 1, 1); gl.useProgram(pf);
      gl.uniform2f(gl.getUniformLocation(pf, 'clip'), near, far); gl.uniform1f(gl.getUniformLocation(pf, 'rate'), rate);
      bind(tf[from]); gl.drawArrays(gl.TRIANGLES, 0, 3);
      const p = new Uint8Array(4); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, p);
      return Math.pow(2, (p[0] / 255 + p[1] / 255 / 255) * 18.64 - 6.64);
    }
    out.focus1 = runFocus(0, 1, 0.1);           // first frame: the distance at once
    out.focus2 = runFocus(1, 0, 0.1);           // steady
    // blur
    gl.bindFramebuffer(gl.FRAMEBUFFER, fo); gl.viewport(0, 0, W, H); gl.useProgram(pb);
    gl.uniform2f(gl.getUniformLocation(pb, 'clip'), near, far);
    gl.uniform2f(gl.getUniformLocation(pb, 'radius'), 0.007 * 8 * H / W, 0.007 * 8);  // a larger radius on the tiny test image
    bind(tf[0]); gl.drawArrays(gl.TRIANGLES, 0, 3);
    const px = new Uint8Array(W * H * 4); gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, px);
    const g = (x, y) => px[(y * W + x) * 4 + 1], r = (x, y) => px[(y * W + x) * 4];
    let farSpread = 0, nearSame = true, redNear = 0;
    for (let y = 2; y < 10; y++) for (let x = 4; x < 30; x++) farSpread = Math.max(farSpread, Math.abs(g(x, y) - 127.5));
    for (let y = 16; y < 32; y++) for (let x = 38; x < 58; x++) if (g(x, y) !== (((x + y) & 1) ? 255 : 0)) nearSame = false;
    for (let y = 2; y < 46; y++) for (const x of [66, 67, 68, 69, 74, 75, 76, 77]) redNear = Math.max(redNear, r(x, y));
    out.farSpread = farSpread; out.nearSame = nearSame; out.redNear = redNear;
    // the focus follows: look at the far distance, a tenth of the way a frame
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) depth[y * W + x] = d(500);
    gl.bindTexture(gl.TEXTURE_2D, td); gl.texImage2D(gl.TEXTURE_2D, 0, gl.DEPTH_COMPONENT32F, W, H, 0, gl.DEPTH_COMPONENT, gl.FLOAT, depth);
    out.focus3 = runFocus(0, 1, 0.1);
    out.error = gl.getError();
    return out;
  }, { vs: src('vertex.glsl'), mask: src('mask.glsl'), focus: src('focus.glsl'), blur: src('blur.glsl') });
  console.log(JSON.stringify(result));
  await browser.close();
})();
