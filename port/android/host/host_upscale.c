/* The in-game menu's upscaling (Display: "Upscaling"): the game's picture, rendered below the
screen's size ("Resolution", d3d8_gl.c screen_mode_choose), brought to the screen by SGSR
(Qualcomm's Snapdragon Game Super Resolution 1, one pass) or FSR (AMD's FidelityFX Super
Resolution 1: EASU, then RCAS's sharpening), as in CubeEvil4-Android (gx_upscale.cpp, gx_gl.cpp).
The third-party files stay unchanged in port/third_party (their licences there and in the app's
assets/licenses); their text is embedded at build time (tools/android_embed.py) and adapted here
for GLSL ES 3.10. FSR's constants are made on the processor with the header's own CPU code.

Runs on the rendering thread (host_settings_present). The result is a texture of the screen's
size in the picture's own orientation (row 0 the top, as the back buffer's), which the caller
shows. A GPU without GLSL ES 3.10 (or a failing shader) keeps the plain linear stretch. */
#include "host.h"
#include <GLES3/gl3.h>
#include <EGL/egl.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* FSR's constants on the processor (A_CPU); its many helpers unused here */
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Weverything"
#define A_CPU 1
#include "fidelityfx-fsr/ffx_a.h"
#include "fidelityfx-fsr/ffx_fsr1.h"
#pragma clang diagnostic pop

static const char ffx_a_text[] =
#include "ffx_a.inc"
;
static const char ffx_fsr1_text[] =
#include "ffx_fsr1.inc"
;
static const char sgsr1_text[] =
#include "sgsr1.inc"
;

enum { UPSCALE_SGSR = 1, UPSCALE_FSR = 2 };
enum { PROGRAM_SGSR, PROGRAM_EASU, PROGRAM_RCAS, PROGRAM_COUNT };

static EGLContext context;
static GLuint programs[PROGRAM_COUNT], vao, framebuffer, textures[2], linear;
static GLint uniforms[PROGRAM_COUNT][4];
static int failed[PROGRAM_COUNT], width, height;

/* ---------- text */

/* a copy of `text` with each `from` (or only the first) replaced by `to` */
static char *replaced(char *text, const char *from, const char *to, int all)
{
	size_t from_length = strlen(from), to_length = strlen(to), count = 0, length = strlen(text);
	char *at, *result, *out;
	const char *in;

	for (at = strstr(text, from); at; at = strstr(at + from_length, from))
	{
		count++;
		if (!all)
			break;
	}
	if (!count)
		return text;
	result = malloc(length + count * (to_length + 1) + 1);
	if (!result)
		return text;
	out = result;
	in = text;
	while ((at = strstr(in, from)) && count)
	{
		memcpy(out, in, (size_t)(at - in));
		out += at - in;
		memcpy(out, to, to_length);
		out += to_length;
		in = at + from_length;
		count--;
	}
	strcpy(out, in);
	free(text);
	return result;
}

/* `text` without the part from `from` up to (not including) `until` */
static char *cut(char *text, const char *from, const char *until)
{
	char *a = strstr(text, from), *b = a ? strstr(a, until) : NULL;

	if (a && b)
		memmove(a, b, strlen(b) + 1);
	return text;
}

static char *joined(const char *const *parts, int count)
{
	size_t length = 1;
	char *text;
	int i;

	for (i = 0; i < count; i++)
		length += strlen(parts[i]);
	text = malloc(length);
	if (!text)
		return NULL;
	text[0] = 0;
	for (i = 0; i < count; i++)
		strcat(text, parts[i]);
	return text;
}

/* ffx_fsr1.h for the shaders: without its constant setup (made on the processor), whose
int-to-uint assignments GLSL ES does not allow */
static char *fsr_gpu(void)
{
	char *text = strdup(ffx_fsr1_text);

	if (!text)
		return NULL;
	text = cut(text, "A_STATIC void FsrEasuCon(", "#if defined(A_GPU)&&defined(FSR_EASU_F)");
	text = cut(text, "A_STATIC void FsrRcasCon(", "#if defined(A_GPU)&&defined(FSR_RCAS_F)");
	return text;
}

/* ---------- programs */

static const char vertex_source[] =
	"#version 310 es\n"
	"layout(location = 0) out highp vec4 in_TEXCOORD0;\n"
	"void main() {\n"
	"  vec2 p = vec2(float(gl_VertexID & 1), float(gl_VertexID >> 1));\n"
	"  in_TEXCOORD0 = vec4(p, 0.0, 0.0);\n"
	"  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);\n"
	"}\n";

static char *fragment_source(int program)
{
	static const char common[] =
		"#version 310 es\nprecision highp float;\nprecision highp int;\n"
		"uniform highp sampler2D src;\n";
	char *gpu, *text;

	if (program == PROGRAM_SGSR)
	{
		text = strdup(sgsr1_text);
		if (!text)
			return NULL;
		text = replaced(text, "#version 300 es", "#version 310 es", 0);
		text = replaced(text, "int mode = OperationMode;", "const int mode = OperationMode;", 0);
		/* a precision on a constructor, which Qualcomm's compiler takes and GLSL does not */
		text = replaced(text, "highp vec2(", "vec2(", 1);
		return text;
	}
	gpu = fsr_gpu();
	if (!gpu)
		return NULL;
	if (program == PROGRAM_EASU)
	{
		const char *parts[] = {
			common,
			"uniform highp uvec4 con0;\nuniform highp uvec4 con1;\nuniform highp uvec4 con2;\nuniform highp uvec4 con3;\n"
			"layout(location = 0) out vec4 o;\n#define A_GPU 1\n#define A_GLSL 1\n",
			ffx_a_text,
			"\n#define FSR_EASU_F 1\n"
			"AF4 FsrEasuRF(AF2 p) { return textureGather(src, p, 0); }\n"
			"AF4 FsrEasuGF(AF2 p) { return textureGather(src, p, 1); }\n"
			"AF4 FsrEasuBF(AF2 p) { return textureGather(src, p, 2); }\n",
			gpu,
			"\nvoid main() {\n  AF3 c;\n  FsrEasuF(c, AU2(gl_FragCoord.xy), con0, con1, con2, con3);\n"
			"  o = vec4(c, 1.0);\n}\n",
		};
		text = joined(parts, 6);
	}
	else
	{
		const char *parts[] = {
			common,
			"uniform highp uvec4 con;\nlayout(location = 0) out vec4 o;\n#define A_GPU 1\n#define A_GLSL 1\n",
			ffx_a_text,
			"\n#define FSR_RCAS_F 1\n"
			"AF4 FsrRcasLoadF(ASU2 p) { return texelFetch(src, ASU2(p), 0); }\n"
			"void FsrRcasInputF(inout AF1 r, inout AF1 g, inout AF1 b) {}\n",
			gpu,
			"\nvoid main() {\n  AF3 c;\n  FsrRcasF(c.r, c.g, c.b, AU2(gl_FragCoord.xy), con);\n"
			"  o = vec4(c, 1.0);\n}\n",
		};
		text = joined(parts, 6);
	}
	free(gpu);
	return text;
}

static GLuint shader(GLenum kind, const char *source, const char *what)
{
	GLuint s = glCreateShader(kind);
	GLint ok = 0;

	glShaderSource(s, 1, &source, NULL);
	glCompileShader(s);
	glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
	if (!ok)
	{
		char log[1024];

		glGetShaderInfoLog(s, sizeof(log), NULL, log);
		host_logf(HOST_LOG_ERROR, "upscaler: the %s shader failed (the plain stretch instead): %s", what, log);
		glDeleteShader(s);
		return 0;
	}
	return s;
}

static int program_ready(int program)
{
	static const char *const names[PROGRAM_COUNT] = { "SGSR", "FSR EASU", "FSR RCAS" };
	GLuint v, f;
	GLint ok = 0;
	char *source;

	if (programs[program])
		return 1;
	if (failed[program])
		return 0;
	failed[program] = 1;
	source = fragment_source(program);
	if (!source)
		return 0;
	v = shader(GL_VERTEX_SHADER, vertex_source, names[program]);
	f = shader(GL_FRAGMENT_SHADER, source, names[program]);
	free(source);
	if (v && f)
	{
		programs[program] = glCreateProgram();
		glAttachShader(programs[program], v);
		glAttachShader(programs[program], f);
		glLinkProgram(programs[program]);
		glGetProgramiv(programs[program], GL_LINK_STATUS, &ok);
	}
	if (v)
		glDeleteShader(v);
	if (f)
		glDeleteShader(f);
	if (!ok)
	{
		if (programs[program])
			glDeleteProgram(programs[program]);
		programs[program] = 0;
		host_logf(HOST_LOG_ERROR, "upscaler: the %s program did not link (the plain stretch instead)", names[program]);
		return 0;
	}
	glUseProgram(programs[program]);
	glUniform1i(glGetUniformLocation(programs[program], program == PROGRAM_SGSR ? "ps0" : "src"), 0);
	if (program == PROGRAM_SGSR)
	{
		uniforms[program][0] = glGetUniformLocation(programs[program], "ViewportInfo");
	}
	else if (program == PROGRAM_EASU)
	{
		uniforms[program][0] = glGetUniformLocation(programs[program], "con0");
		uniforms[program][1] = glGetUniformLocation(programs[program], "con1");
		uniforms[program][2] = glGetUniformLocation(programs[program], "con2");
		uniforms[program][3] = glGetUniformLocation(programs[program], "con3");
	}
	else
	{
		uniforms[program][0] = glGetUniformLocation(programs[program], "con");
	}
	failed[program] = 0;
	host_logf(HOST_LOG_INFO, "upscaler: %s ready", names[program]);
	return 1;
}

/* the two textures of the screen's size (EASU's, RCAS's or SGSR's result) */
static int targets(int w, int h)
{
	int i;

	if (!framebuffer)
		glGenFramebuffers(1, &framebuffer);
	if (!linear)
	{
		glGenSamplers(1, &linear);
		glSamplerParameteri(linear, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
		glSamplerParameteri(linear, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
		glSamplerParameteri(linear, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
		glSamplerParameteri(linear, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	}
	if (!vao)
		glGenVertexArrays(1, &vao);
	if (width == w && height == h && textures[0])
		return 1;
	for (i = 0; i < 2; i++)
	{
		if (textures[i])
			glDeleteTextures(1, &textures[i]);
		glGenTextures(1, &textures[i]);
		glBindTexture(GL_TEXTURE_2D, textures[i]);
		glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, w, h);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	}
	width = w;
	height = h;
	return 1;
}

/* ---------- the pass */

int host_upscale(unsigned int texture, int src_w, int src_h, int dst_w, int dst_h, int upscaler,
	unsigned int *result, unsigned int *result_framebuffer)
{
	int fsr = upscaler == UPSCALE_FSR, first = fsr ? PROGRAM_EASU : PROGRAM_SGSR;
	GLboolean scissor, blend, depth, stencil, cull;

	if (upscaler != UPSCALE_SGSR && upscaler != UPSCALE_FSR)
		return 0;
	if (!texture || src_w < 16 || src_h < 16 || dst_w < 16 || dst_h < 16)
		return 0;
	/* only to enlarge: at the screen's size (or larger) the plain blit */
	if ((float)dst_w <= src_w * 1.02f && (float)dst_h <= src_h * 1.02f)
		return 0;
	if (context != eglGetCurrentContext())
	{
		/* a new context: everything made anew */
		context = eglGetCurrentContext();
		memset(programs, 0, sizeof(programs));
		memset(failed, 0, sizeof(failed));
		vao = framebuffer = linear = 0;
		textures[0] = textures[1] = 0;
		width = height = 0;
	}
	if (!program_ready(first) || (fsr && !program_ready(PROGRAM_RCAS)))
		return 0;
	if (!targets(dst_w, dst_h))
		return 0;
	scissor = glIsEnabled(GL_SCISSOR_TEST);
	blend = glIsEnabled(GL_BLEND);
	depth = glIsEnabled(GL_DEPTH_TEST);
	stencil = glIsEnabled(GL_STENCIL_TEST);
	cull = glIsEnabled(GL_CULL_FACE);
	glDisable(GL_SCISSOR_TEST);
	glDisable(GL_BLEND);
	glDisable(GL_DEPTH_TEST);
	glDisable(GL_STENCIL_TEST);
	glDisable(GL_CULL_FACE);
	glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
	glBindFramebuffer(GL_DRAW_FRAMEBUFFER, framebuffer);
	glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, textures[0], 0);
	glViewport(0, 0, dst_w, dst_h);
	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, texture);
	/* SGSR and EASU gather the source's texels; SGSR also samples it filtered */
	glBindSampler(0, linear);
	glBindVertexArray(vao);
	glUseProgram(programs[first]);
	if (!fsr)
	{
		const float info[4] = { 1.0f / (float)src_w, 1.0f / (float)src_h, (float)src_w, (float)src_h };

		glUniform4fv(uniforms[PROGRAM_SGSR][0], 1, info);
	}
	else
	{
		varAU4(c0);
		varAU4(c1);
		varAU4(c2);
		varAU4(c3);

		FsrEasuCon(c0, c1, c2, c3, (AF1)src_w, (AF1)src_h, (AF1)src_w, (AF1)src_h, (AF1)dst_w, (AF1)dst_h);
		glUniform4uiv(uniforms[PROGRAM_EASU][0], 1, (const GLuint *)c0);
		glUniform4uiv(uniforms[PROGRAM_EASU][1], 1, (const GLuint *)c1);
		glUniform4uiv(uniforms[PROGRAM_EASU][2], 1, (const GLuint *)c2);
		glUniform4uiv(uniforms[PROGRAM_EASU][3], 1, (const GLuint *)c3);
	}
	glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
	*result = textures[0];
	if (fsr)
	{
		varAU4(con);

		/* RCAS: the enlarged picture sharpened (AMD's 0.2 stops) */
		glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, textures[1], 0);
		glBindTexture(GL_TEXTURE_2D, textures[0]);
		glBindSampler(0, 0);
		glUseProgram(programs[PROGRAM_RCAS]);
		FsrRcasCon(con, 0.2f);
		glUniform4uiv(uniforms[PROGRAM_RCAS][0], 1, (const GLuint *)con);
		glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
		*result = textures[1];
	}
	/* the result as the framebuffer's attachment, for the caller's blit */
	glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, *result, 0);
	*result_framebuffer = framebuffer;
	glBindSampler(0, 0);
	glBindVertexArray(0);
	if (scissor) glEnable(GL_SCISSOR_TEST);
	if (blend) glEnable(GL_BLEND);
	if (depth) glEnable(GL_DEPTH_TEST);
	if (stencil) glEnable(GL_STENCIL_TEST);
	if (cull) glEnable(GL_CULL_FACE);
	return 1;
}
