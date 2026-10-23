/*
NV2A_VSH.C

Translation of NV2A vertex programs (Xbox vertex shader microcode) into
GLSL.

Each instruction is four little-endian words. Word 1 to 3 hold a MAC
(vector) operation and an ILU (scalar) operation that execute in parallel
on the same three operands A, B and C, and the destinations of both; the
bit positions of every field are spelled out in operand() and in
nv2a_vertex_shader_to_glsl(). When both units run, the ILU result goes to
temporary r1, whatever the instruction's temporary register field says.

Xbox vertex programs finish by converting their clip-space position to
screen space with the viewport constants c[-38] and c[-37], which Direct3D
maintains. The generated shader inverts that transform to hand OpenGL a
clip-space position again.
*/

#include "xgpu.h"

#include <stdlib.h>
#ifdef HALO_ANDROID
#include <math.h>
#include <string.h>
#endif

/* ---------- instruction fields */

static unsigned long field(const DWORD *instruction, int word, int low_bit, int bit_count)
{
	return (instruction[word] >> low_bit) & ((1UL << bit_count) - 1);
}

enum
{
	_mac_nop, _mac_mov, _mac_mul, _mac_add, _mac_mad, _mac_dp3, _mac_dph, _mac_dp4,
	_mac_dst, _mac_min, _mac_max, _mac_slt, _mac_sge, _mac_arl,
};

enum
{
	_ilu_nop, _ilu_mov, _ilu_rcp, _ilu_rcc, _ilu_rsq, _ilu_exp, _ilu_log, _ilu_lit,
};

enum
{
	_mux_unknown, _mux_temporary, _mux_input, _mux_constant,
};

/* output register addresses (o[]) */
static const char *output_name(unsigned long address)
{
	switch (address)
	{
	case 0: return "oPos";
	case 3: return "oD0";
	case 4: return "oD1";
	case 5: return "oFog";
	case 6: return "oPts";
	case 7: return "oB0";
	case 8: return "oB1";
	case 9: return "oT0";
	case 10: return "oT1";
	case 11: return "oT2";
	case 12: return "oT3";
	default: return "oUnused";
	}
}

static void write_mask(unsigned long mask, char *out)
{
	/* bit 3 is x */
	int count = 0;

	if (mask & 8) out[count++] = 'x';
	if (mask & 4) out[count++] = 'y';
	if (mask & 2) out[count++] = 'z';
	if (mask & 1) out[count++] = 'w';
	out[count] = 0;
}

static void operand(struct xgpu_text *text, const DWORD *instruction, char which, int relative)
{
	static const char swizzle_names[] = "xyzw";
	unsigned long negate, swizzle[4], index, mux;

	switch (which)
	{
	case 'A':
		negate = field(instruction, 1, 8, 1);
		swizzle[0] = field(instruction, 1, 6, 2);
		swizzle[1] = field(instruction, 1, 4, 2);
		swizzle[2] = field(instruction, 1, 2, 2);
		swizzle[3] = field(instruction, 1, 0, 2);
		index = field(instruction, 2, 28, 4);
		mux = field(instruction, 2, 26, 2);
		break;
	case 'B':
		negate = field(instruction, 2, 25, 1);
		swizzle[0] = field(instruction, 2, 23, 2);
		swizzle[1] = field(instruction, 2, 21, 2);
		swizzle[2] = field(instruction, 2, 19, 2);
		swizzle[3] = field(instruction, 2, 17, 2);
		index = field(instruction, 2, 13, 4);
		mux = field(instruction, 2, 11, 2);
		break;
	default:
		negate = field(instruction, 2, 10, 1);
		swizzle[0] = field(instruction, 2, 8, 2);
		swizzle[1] = field(instruction, 2, 6, 2);
		swizzle[2] = field(instruction, 2, 4, 2);
		swizzle[3] = field(instruction, 2, 2, 2);
		index = (field(instruction, 2, 0, 2) << 2) | field(instruction, 3, 30, 2);
		mux = field(instruction, 3, 28, 2);
		break;
	}

	xgpu_text_append(text, "%s", negate ? "-" : "");
	switch (mux)
	{
	case _mux_temporary:
		/* r12 reads back the position output */
		if (index == 12)
			xgpu_text_append(text, "oPos");
		else
			xgpu_text_append(text, "r%lu", index);
		break;
	case _mux_input:
		xgpu_text_append(text, "v%lu", field(instruction, 1, 9, 4));
		break;
	case _mux_constant:
		if (relative)
			xgpu_text_append(text, "c[clamp(a0 + %lu, 0, %d)]", field(instruction, 1, 13, 8), XGPU_VERTEX_CONSTANT_COUNT - 1);
		else
			xgpu_text_append(text, "c[%lu]", field(instruction, 1, 13, 8));
		break;
	default:
		xgpu_text_append(text, "vec4(0.0)");
		break;
	}
	xgpu_text_append(text, ".%c%c%c%c",
		swizzle_names[swizzle[0]], swizzle_names[swizzle[1]], swizzle_names[swizzle[2]], swizzle_names[swizzle[3]]);
}

static const char shader_prologue[] =
#ifdef HALO_ANDROID
	/* the #version line comes first, from the context's capabilities */
	"precision highp float;\n"
	"precision highp int;\n"
#else
	"#version 450 core\n"
#endif
	"uniform vec4 c[192];\n"
	"uniform vec4 viewport_scale;\n"
	"uniform vec4 viewport_offset;\n"
	"uniform float point_size;\n"
	/* columns the menus shift by to center on a wide screen (d3d8_gl.c) */
	"uniform float screen_offset;\n"
	"out vec4 xD0;\n"
	"out vec4 xD1;\n"
	"out vec4 xB0;\n"
	"out vec4 xB1;\n"
	"out vec4 xT0;\n"
	"out vec4 xT1;\n"
	"out vec4 xT2;\n"
	"out vec4 xT3;\n"
	"out float xFog;\n"
	"invariant gl_Position;\n"
	"vec4 unpack_normpacked3(uint p)\n"
	"{\n"
	"	int x = int(p << 21) >> 21;\n"
	"	int y = int(p << 10) >> 21;\n"
	"	int z = int(p) >> 22;\n"
	"	return vec4(float(x) / 1023.0, float(y) / 1023.0, float(z) / 511.0, 1.0);\n"
	"}\n"
	"vec4 nv2a_rcc(float x)\n"
	"{\n"
	"	float r = 1.0 / x;\n"
	"	if (r > 0.0) r = clamp(r, 5.42101e-20, 1.884467e+19);\n"
	"	else r = clamp(r, -1.884467e+19, -5.42101e-20);\n"
	"	return vec4(r);\n"
	"}\n"
	"vec4 nv2a_exp(float x)\n"
	"{\n"
	"	return vec4(exp2(floor(x)), fract(x), exp2(x), 1.0);\n"
	"}\n"
	"vec4 nv2a_log(float x)\n"
	"{\n"
	"	x = abs(x);\n"
	"	if (x == 0.0) return vec4(-1.0e30, 1.0, -1.0e30, 1.0);\n"
	"	float e = floor(log2(x));\n"
	"	return vec4(e, x / exp2(e), log2(x), 1.0);\n"
	"}\n"
	"vec4 nv2a_lit(vec4 s)\n"
	"{\n"
	"	float specular = s.x > 0.0 ? pow(max(s.y, 0.0), clamp(s.w, -127.9961, 127.9961)) : 0.0;\n"
	"	return vec4(1.0, max(s.x, 0.0), specular, 1.0);\n"
	"}\n";

char *nv2a_vertex_shader_to_glsl(const DWORD *instructions, unsigned long instruction_count,
	unsigned long packed_attribute_mask)
{
	struct xgpu_text text = { 0 };
	unsigned long index;

#ifdef HALO_ANDROID
	xgpu_text_append(&text, "#version %s\n", xgpu_capabilities.shading_language);
#endif
	xgpu_text_append(&text, "%s", shader_prologue);
	for (index = 0; index < XGPU_VERTEX_ATTRIBUTE_COUNT; index++)
	{
		if (packed_attribute_mask & (1UL << index))
			xgpu_text_append(&text, "layout(location = %lu) in uint v%lu_packed;\n", index, index);
		else
			xgpu_text_append(&text, "layout(location = %lu) in vec4 v%lu_in;\n", index, index);
	}

	xgpu_text_append(&text, "void main()\n{\n");
	for (index = 0; index < XGPU_VERTEX_ATTRIBUTE_COUNT; index++)
	{
		if (packed_attribute_mask & (1UL << index))
			xgpu_text_append(&text, "\tvec4 v%lu = unpack_normpacked3(v%lu_packed);\n", index, index);
		else
			xgpu_text_append(&text, "\tvec4 v%lu = v%lu_in;\n", index, index);
	}
	xgpu_text_append(&text,
		"\tvec4 r0 = vec4(0.0), r1 = vec4(0.0), r2 = vec4(0.0), r3 = vec4(0.0);\n"
		"\tvec4 r4 = vec4(0.0), r5 = vec4(0.0), r6 = vec4(0.0), r7 = vec4(0.0);\n"
		"\tvec4 r8 = vec4(0.0), r9 = vec4(0.0), r10 = vec4(0.0), r11 = vec4(0.0);\n"
		"\tvec4 oPos = vec4(0.0, 0.0, 0.0, 1.0);\n"
		"\tvec4 oD0 = vec4(0.0, 0.0, 0.0, 1.0), oD1 = vec4(0.0, 0.0, 0.0, 1.0);\n"
		"\tvec4 oB0 = vec4(0.0, 0.0, 0.0, 1.0), oB1 = vec4(0.0, 0.0, 0.0, 1.0);\n"
		"\tvec4 oT0 = vec4(0.0, 0.0, 0.0, 1.0), oT1 = vec4(0.0, 0.0, 0.0, 1.0);\n"
		"\tvec4 oT2 = vec4(0.0, 0.0, 0.0, 1.0), oT3 = vec4(0.0, 0.0, 0.0, 1.0);\n"
		"\tvec4 oFog = vec4(1.0), oPts = vec4(point_size), oUnused = vec4(0.0);\n"
		"\tint a0 = 0;\n"
		"\tvec4 A, B, C, mac, ilu;\n");
	xgpu_text_append(&text, "\tvec4 clip_position = vec4(0.0);\n\tbool clip_captured = false;\n");

	for (index = 0; index < instruction_count; index++)
	{
		const DWORD *instruction = instructions + index * 4;
		unsigned long mac = field(instruction, 1, 21, 4);
		unsigned long ilu = field(instruction, 1, 25, 3);
		unsigned long mac_mask = field(instruction, 3, 24, 4);
		unsigned long temporary = field(instruction, 3, 20, 4);
		unsigned long ilu_mask = field(instruction, 3, 16, 4);
		unsigned long output_mask = field(instruction, 3, 12, 4);
		unsigned long output_is_register = field(instruction, 3, 11, 1);
		unsigned long output_address = field(instruction, 3, 3, 8);
		unsigned long output_from_ilu = field(instruction, 3, 2, 1);
		int relative = (int)field(instruction, 3, 1, 1);
		char mask[5];

		xgpu_text_append(&text, "\t/* %lu */\n", index);
		xgpu_text_append(&text, "\tA = "); operand(&text, instruction, 'A', relative); xgpu_text_append(&text, ";\n");
		xgpu_text_append(&text, "\tB = "); operand(&text, instruction, 'B', relative); xgpu_text_append(&text, ";\n");
		xgpu_text_append(&text, "\tC = "); operand(&text, instruction, 'C', relative); xgpu_text_append(&text, ";\n");

		switch (mac)
		{
		case _mac_nop: break;
		case _mac_mov: xgpu_text_append(&text, "\tmac = A;\n"); break;
		case _mac_mul: xgpu_text_append(&text, "\tmac = A * B;\n"); break;
		case _mac_add: xgpu_text_append(&text, "\tmac = A + C;\n"); break;
		case _mac_mad: xgpu_text_append(&text, "\tmac = A * B + C;\n"); break;
		case _mac_dp3: xgpu_text_append(&text, "\tmac = vec4(dot(A.xyz, B.xyz));\n"); break;
		case _mac_dph: xgpu_text_append(&text, "\tmac = vec4(dot(A.xyz, B.xyz) + B.w);\n"); break;
		case _mac_dp4: xgpu_text_append(&text, "\tmac = vec4(dot(A, B));\n"); break;
		case _mac_dst: xgpu_text_append(&text, "\tmac = vec4(1.0, A.y * B.y, A.z, B.w);\n"); break;
		case _mac_min: xgpu_text_append(&text, "\tmac = min(A, B);\n"); break;
		case _mac_max: xgpu_text_append(&text, "\tmac = max(A, B);\n"); break;
		case _mac_slt: xgpu_text_append(&text, "\tmac = vec4(lessThan(A, B));\n"); break;
		case _mac_sge: xgpu_text_append(&text, "\tmac = vec4(greaterThanEqual(A, B));\n"); break;
		case _mac_arl: xgpu_text_append(&text, "\tmac = A;\n"); break;
		default: xgpu_text_append(&text, "\tmac = vec4(0.0);\n"); break;
		}
		switch (ilu)
		{
		case _ilu_nop: break;
		case _ilu_mov: xgpu_text_append(&text, "\tilu = C;\n"); break;
		case _ilu_rcp: xgpu_text_append(&text, "\tilu = vec4(1.0 / C.x);\n"); break;
		case _ilu_rcc: xgpu_text_append(&text, "\tilu = nv2a_rcc(C.x);\n"); break;
		case _ilu_rsq: xgpu_text_append(&text, "\tilu = vec4(inversesqrt(abs(C.x)));\n"); break;
		case _ilu_exp: xgpu_text_append(&text, "\tilu = nv2a_exp(C.x);\n"); break;
		case _ilu_log: xgpu_text_append(&text, "\tilu = nv2a_log(C.x);\n"); break;
		case _ilu_lit: xgpu_text_append(&text, "\tilu = nv2a_lit(C);\n"); break;
		default: xgpu_text_append(&text, "\tilu = vec4(0.0);\n"); break;
		}
		/* the screen-space conversion takes the reciprocal of the clip-space
		position's w (rcc of r12.w); keep the position it converts */
		if (ilu == _ilu_rcc && field(instruction, 3, 28, 2) == _mux_temporary &&
			((field(instruction, 2, 0, 2) << 2) | field(instruction, 3, 30, 2)) == 12)
		{
			xgpu_text_append(&text, "\tclip_position = oPos;\n\tclip_captured = true;\n");
		}

		/* results are written only after both units have read their inputs */
		if (mac == _mac_arl)
		{
			xgpu_text_append(&text, "\ta0 = int(floor(mac.x + 0.001));\n");
		}
		else if (mac != _mac_nop && mac_mask)
		{
			write_mask(mac_mask, mask);
			if (temporary == 12)
				xgpu_text_append(&text, "\toPos.%s = mac.%s;\n", mask, mask);
			else
				xgpu_text_append(&text, "\tr%lu.%s = mac.%s;\n", temporary, mask, mask);
		}
		if (ilu != _ilu_nop && ilu_mask)
		{
			unsigned long ilu_temporary = mac != _mac_nop ? 1 : temporary;

			write_mask(ilu_mask, mask);
			if (ilu_temporary == 12)
				xgpu_text_append(&text, "\toPos.%s = ilu.%s;\n", mask, mask);
			else
				xgpu_text_append(&text, "\tr%lu.%s = ilu.%s;\n", ilu_temporary, mask, mask);
		}
		if (output_mask && (output_from_ilu ? ilu : mac) != 0)
		{
			const char *source = output_from_ilu ? "ilu" : "mac";

			write_mask(output_mask, mask);
			if (output_is_register)
				xgpu_text_append(&text, "\t%s.%s = %s.%s;\n", output_name(output_address), mask, source, mask);
			/* writes to constant memory are not used by Halo's shaders */
		}
		if (field(instruction, 3, 0, 1))
			break;
	}

	xgpu_text_append(&text,
		"\t/* undo the screen-space conversion done with c[-38] and c[-37] */\n"
		"\tvec3 scale = vec3(viewport_scale.x != 0.0 ? viewport_scale.x : 1.0,\n"
		"\t\tviewport_scale.y != 0.0 ? viewport_scale.y : 1.0,\n"
		"\t\tviewport_scale.z != 0.0 ? viewport_scale.z : 1.0);\n"
		/* Direct3D 8 puts pixel centres on integer screen coordinates (the
		game offsets its screen-space quads by -0.5 to match), OpenGL on
		half-integers */
		/* The conversion is screen = clip * c[-38] * rcc(w) + c[-37]; undoing
		it by multiplying by w again is lossy near the camera plane, where
		rcc clamps and 1/w rounds differently on each GPU (Mali put vertices
		of the first-person weapon at the vanishing point). Where the clip
		position was kept, the same result is computed without dividing. */
		"\tvec4 position;\n"
		"\tif (clip_captured)\n"
		"\t\tposition = vec4((clip_position.xyz * c[%d].xyz + (c[%d].xyz + vec3(0.5 + screen_offset, 0.5, 0.0)\n"
		"\t\t\t- viewport_offset.xyz) * clip_position.w) / scale, clip_position.w);\n"
		"\telse\n"
		"\t{\n"
		"\t\tvec3 ndc = (vec3(oPos.xy + vec2(0.5 + screen_offset, 0.5), oPos.z) - viewport_offset.xyz) / scale;\n"
		"\t\tposition = vec4(ndc * oPos.w, oPos.w);\n"
		"\t}\n"
		/* A position whose w is zero, or is not a number, is the clip-space
		origin: the screen conversion's reciprocal is clamped rather than
		infinite, so a large position times a w of zero is exactly zero, and
		the origin is inside the frustum. Nothing then clips the triangle
		away and OpenGL divides zero by zero there: the vertex lands on the
		middle of the screen and the triangle is drawn out to it from the
		first-person weapon, whose pose follows the camera and so reaches the
		camera plane. The divide on the Xbox sends such a vertex to infinity
		and the clipper takes the triangle; put it behind the camera instead,
		which the clipper also takes. */
		/* Check NaN explicitly: some GLSL compilers optimize the ordered
		comparison in a way that leaves a NaN at the clip-space origin. */
		"\tif (!(abs(position.w) > 0.0) || isnan(position.w))\n"
		"\t\tposition = vec4(0.0, 0.0, 0.0, -1.0);\n"
		"\tgl_Position = position;\n"
#ifdef HALO_ANDROID
		/* what glClipControl(GL_UPPER_LEFT, GL_ZERO_TO_ONE) does on desktop
		GL: rows from the top, depth 0..1 */
		"\tgl_Position.y = -gl_Position.y;\n"
		"\tgl_Position.z = 2.0 * gl_Position.z - gl_Position.w;\n"
#endif
		"\tgl_PointSize = oPts.x;\n"
		"\txD0 = clamp(oD0, 0.0, 1.0);\n"
		"\txD1 = clamp(oD1, 0.0, 1.0);\n"
		"\txB0 = clamp(oB0, 0.0, 1.0);\n"
		"\txB1 = clamp(oB1, 0.0, 1.0);\n"
		"\txT0 = oT0;\n"
		"\txT1 = oT1;\n"
		"\txT2 = oT2;\n"
		"\txT3 = oT3;\n"
		"\txFog = oFog.x;\n"
		"}\n",
		XGPU_VERTEX_CONSTANT_BIAS - 38, XGPU_VERTEX_CONSTANT_BIAS - 37
		);
	return text.buffer;
}

#ifdef HALO_ANDROID
/* This path bypasses the driver's skeletal vertex execution altogether.
Decode once per shader; execute its original parallel MAC/ILU instructions,
not a guessed two-bone formula. In particular, shadow projection, tangent
space, lighting, fog and the viewport conversion retain their original code. */
typedef float cpu_vec4 __attribute__((vector_size(16)));
typedef char cpu_vertex_size_assert[sizeof(struct nv2a_cpu_vertex) == 40 * sizeof(float) ? 1 : -1];
struct cpu_operand
{
	unsigned char mux, index, negate, relative, swizzle[4];
	unsigned char swizzle_kind;
	cpu_vec4 constant;
};
struct cpu_instruction
{
	struct cpu_operand operand[3];
	unsigned char mac, ilu, temporary, mac_mask, ilu_mask;
	unsigned char output_mask, output_address, output_is_register, output_from_ilu;
	unsigned char execution; /* A/B/C reads in bits 0..2, MAC/ILU in 3/4 */
};
typedef BOOL (*cpu_fast_executor)(const float inputs[16][4], const float constants[192][4],
	cpu_vec4 output[14], cpu_vec4 *clip);
static cpu_fast_executor cpu_fast_find(const DWORD *words, unsigned long count);
struct nv2a_cpu_program
{
	unsigned long count;
	BOOL prepared;
	cpu_fast_executor execute;
	/* the input registers any operand reads, and the GPU attributes the
	program writes (nv2a_cpu_program_inputs, nv2a_cpu_program_outputs) */
	unsigned inputs, outputs;
	struct cpu_instruction instruction[];
};

static struct cpu_operand cpu_operand_decode(const DWORD *instruction, unsigned which)
{
	struct cpu_operand result = { 0 };
	unsigned low, word, index;
	if (which == 0)
	{
		word = 1; low = 6;
		result.negate = (unsigned char)field(instruction, 1, 8, 1);
		result.index = (unsigned char)field(instruction, 2, 28, 4);
		result.mux = (unsigned char)field(instruction, 2, 26, 2);
	}
	else if (which == 1)
	{
		word = 2; low = 23;
		result.negate = (unsigned char)field(instruction, 2, 25, 1);
		result.index = (unsigned char)field(instruction, 2, 13, 4);
		result.mux = (unsigned char)field(instruction, 2, 11, 2);
	}
	else
	{
		word = 2; low = 8;
		result.negate = (unsigned char)field(instruction, 2, 10, 1);
		result.index = (unsigned char)((field(instruction, 2, 0, 2) << 2) | field(instruction, 3, 30, 2));
		result.mux = (unsigned char)field(instruction, 3, 28, 2);
	}
	for (index = 0; index < 4; index++)
		result.swizzle[index] = (unsigned char)field(instruction, word, (int)low - (int)index * 2, 2);
	result.swizzle_kind = result.swizzle[0] == result.swizzle[1] && result.swizzle[0] == result.swizzle[2] &&
		result.swizzle[0] == result.swizzle[3] ? result.swizzle[0] :
		result.swizzle[0] == 0 && result.swizzle[1] == 1 && result.swizzle[2] == 2 && result.swizzle[3] == 3 ? 4 : 5;
	if (result.mux == _mux_input)
		result.index = (unsigned char)field(instruction, 1, 9, 4);
	else if (result.mux == _mux_constant)
	{
		result.index = (unsigned char)field(instruction, 1, 13, 8);
		result.relative = (unsigned char)field(instruction, 3, 1, 1);
	}
	return result;
}

struct nv2a_cpu_program *nv2a_cpu_program_create(const DWORD *instructions, unsigned long count)
{
	struct nv2a_cpu_program *program;
	unsigned long index;
	unsigned input_mask = 0, bone_rows = 0, output_mask = 0;
	if (!instructions || !count || count > 256)
		return NULL;
	program = calloc(1, sizeof(*program) + count * sizeof(program->instruction[0]));
	if (!program)
		return NULL;
	for (index = 0; index < count; index++)
	{
		const DWORD *words = instructions + index * 4;
		struct cpu_instruction *instruction = &program->instruction[index];
		unsigned operand_index;
		instruction->mac = (unsigned char)field(words, 1, 21, 4);
		instruction->ilu = (unsigned char)field(words, 1, 25, 3);
		instruction->temporary = (unsigned char)field(words, 3, 20, 4);
		instruction->mac_mask = (unsigned char)field(words, 3, 24, 4);
		instruction->ilu_mask = (unsigned char)field(words, 3, 16, 4);
		instruction->output_mask = (unsigned char)field(words, 3, 12, 4);
		instruction->output_is_register = (unsigned char)field(words, 3, 11, 1);
		instruction->output_address = (unsigned char)field(words, 3, 3, 8);
		instruction->output_from_ilu = (unsigned char)field(words, 3, 2, 1);
		if (instruction->mac > _mac_arl || (instruction->temporary > 12 &&
			((instruction->mac && instruction->mac != _mac_arl && instruction->mac_mask) ||
			 (!instruction->mac && instruction->ilu && instruction->ilu_mask))))
			goto unsupported;
		for (operand_index = 0; operand_index < 3; operand_index++)
		{
			struct cpu_operand *operand = &instruction->operand[operand_index];
			*operand = cpu_operand_decode(words, operand_index);
			if ((operand->mux == _mux_temporary && operand->index > 12) ||
				(operand->mux == _mux_constant && !operand->relative && operand->index >= 192))
				goto unsupported;
			if (operand->mux == _mux_input)
				input_mask |= 1U << operand->index;
			if (operand->mux == _mux_constant && operand->relative && operand->index >= 60 && operand->index <= 62)
				bone_rows |= 1U << (operand->index - 60);
		}
		if (instruction->mac && (instruction->mac_mask || instruction->mac == _mac_arl ||
			(instruction->output_mask && !instruction->output_from_ilu)))
		{
			unsigned opcode = instruction->mac;
			instruction->execution = 8 | (opcode == _mac_mov || opcode == _mac_arl ? 1 :
				opcode == _mac_add ? 5 : opcode == _mac_mad ? 7 : 3);
		}
		if (instruction->output_is_register && instruction->output_mask &&
			(instruction->output_from_ilu ? instruction->ilu : instruction->mac))
		{
			/* as nv2a_cpu_vertex_execute stores them: oD0 oD1 oB0 oB1 oT0..oT3
			are attributes 1..8; oFog, oPts the auxiliary pair */
			switch (instruction->output_address)
			{
			case 3: output_mask |= 1U << 1; break;
			case 4: output_mask |= 1U << 2; break;
			case 5: output_mask |= NV2A_CPU_OUTPUT_FOG; break;
			case 6: output_mask |= NV2A_CPU_OUTPUT_POINT_SIZE; break;
			case 7: case 8: case 9: case 10: case 11: case 12:
				output_mask |= 1U << (instruction->output_address - 4);
				break;
			}
		}
		if (instruction->ilu && (instruction->ilu_mask ||
			(instruction->output_mask && instruction->output_from_ilu) ||
			(instruction->ilu == _ilu_rcc && instruction->operand[2].mux == _mux_temporary && instruction->operand[2].index == 12)))
			instruction->execution |= 16 | 4;
		program->count++;
		if (field(words, 3, 0, 1))
			break;
	}
	/* Only Halo's skeletal programs: position, two node indices, weight,
and all three relative matrix rows. Static meshes/menu shaders stay GPU. */
	if (bone_rows == 7 && (input_mask & 0x61U) == 0x61U)
	{
		program->execute = cpu_fast_find(instructions, program->count);
		program->inputs = input_mask;
		program->outputs = output_mask | 1U; /* the position, always */
		return program;
	}
unsupported:
	free(program);
	return NULL;
}

static cpu_vec4 cpu_operand_read(const struct cpu_operand *operand, const float inputs[16][4],
	const float constants[192][4], const cpu_vec4 temporary[12], cpu_vec4 position, int address, BOOL prepared)
{
	cpu_vec4 source = { 0, 0, 0, 0 }, result;
	unsigned component;
	if (operand->mux == _mux_temporary)
		source = operand->index == 12 ? position : temporary[operand->index];
	else if (operand->mux == _mux_input)
		memcpy(&source, inputs[operand->index], sizeof(source));
	else if (operand->mux == _mux_constant)
	{
		if (prepared && !operand->relative) return operand->constant;
		int index = operand->index + (operand->relative ? address : 0);
		if (index < 0) index = 0;
		if (index > 191) index = 191;
		memcpy(&source, constants[index], sizeof(source));
	}
	if (operand->swizzle_kind == 4) result = source;
	else if (operand->swizzle_kind < 4)
	{
		float value = source[operand->swizzle_kind];
		result = (cpu_vec4){ value, value, value, value };
	}
	else for (component = 0; component < 4; component++) result[component] = source[operand->swizzle[component]];
	return operand->negate ? -result : result;
}

void nv2a_cpu_program_prepare_constants(struct nv2a_cpu_program *program, const float constants[192][4])
{
	unsigned long index;
	/* Fixed executors load constants directly; the compiler removes repeated
operand decoding and swizzles. Unknown programs retain the interpreter. */
	if (program->execute) return;
	for (index = 0; index < program->count; index++)
	{
		unsigned which;
		for (which = 0; which < 3; which++)
		{
			struct cpu_operand *operand = &program->instruction[index].operand[which];
			if (operand->mux == _mux_constant && !operand->relative)
				operand->constant = cpu_operand_read(operand, NULL, constants, NULL, (cpu_vec4){ 0, 0, 0, 0 }, 0, FALSE);
		}
	}
	program->prepared = TRUE;
}

static void cpu_write(cpu_vec4 *destination, cpu_vec4 source, unsigned mask)
{
	unsigned component;
	switch (mask)
	{
	case 0: return;
	case 15: *destination = source; return;
	case 8: (*destination)[0] = source[0]; return;
	case 4: (*destination)[1] = source[1]; return;
	case 2: (*destination)[2] = source[2]; return;
	case 1: (*destination)[3] = source[3]; return;
	}
	for (component = 0; component < 4; component++)
		if (mask & (8U >> component)) (*destination)[component] = source[component];
}

static inline __attribute__((always_inline)) cpu_vec4 cpu_mac(unsigned opcode, cpu_vec4 a, cpu_vec4 b, cpu_vec4 c)
{
	cpu_vec4 result = { 0, 0, 0, 0 };
	unsigned component;
	float dot;
	switch (opcode)
	{
	case _mac_mov: case _mac_arl: return a;
	case _mac_mul: return a * b;
	case _mac_add: return a + c;
	case _mac_mad: return a * b + c;
	case _mac_dp3: case _mac_dph: case _mac_dp4:
		dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
		if (opcode == _mac_dph) dot += b[3];
		if (opcode == _mac_dp4) dot += a[3] * b[3];
		return (cpu_vec4){ dot, dot, dot, dot };
	case _mac_dst: return (cpu_vec4){ 1, a[1] * b[1], a[2], b[3] };
	default:
		for (component = 0; component < 4; component++)
		{
			switch (opcode)
			{
			case _mac_min: result[component] = fminf(a[component], b[component]); break;
			case _mac_max: result[component] = fmaxf(a[component], b[component]); break;
			case _mac_slt: result[component] = a[component] < b[component]; break;
			case _mac_sge: result[component] = a[component] >= b[component]; break;
			}
		}
		return result;
	}
}

static inline __attribute__((always_inline)) cpu_vec4 cpu_ilu(unsigned opcode, cpu_vec4 c)
{
	float x = c[0], value;
	switch (opcode)
	{
	case _ilu_mov: return c;
	case _ilu_rcp: value = 1.0f / x; break;
	case _ilu_rcc:
		value = 1.0f / x;
		value = value > 0.0f ? fminf(fmaxf(value, 5.42101e-20f), 1.884467e19f) :
			fminf(fmaxf(value, -1.884467e19f), -5.42101e-20f);
		break;
	case _ilu_rsq: value = 1.0f / sqrtf(fabsf(x)); break;
	case _ilu_exp: return (cpu_vec4){ exp2f(floorf(x)), x - floorf(x), exp2f(x), 1 };
	case _ilu_log:
		x = fabsf(x);
		if (x == 0.0f) return (cpu_vec4){ -1.0e30f, 1, -1.0e30f, 1 };
		value = floorf(log2f(x));
		return (cpu_vec4){ value, x / exp2f(value), log2f(x), 1 };
	case _ilu_lit:
		value = c[0] > 0.0f ? powf(fmaxf(c[1], 0.0f), fminf(fmaxf(c[3], -127.9961f), 127.9961f)) : 0.0f;
		return (cpu_vec4){ 1, fmaxf(c[0], 0.0f), value, 1 };
	default: value = 0; break;
	}
	return (cpu_vec4){ value, value, value, value };
}

static inline cpu_vec4 cpu_load(const float value[4])
{
	cpu_vec4 result;
	memcpy(&result, value, sizeof(result));
	return result;
}

static inline int cpu_constant_index(int address, unsigned index)
{
	int result = address + (int)index;
	return result < 0 ? 0 : result > 191 ? 191 : result;
}

static inline int cpu_address(float x)
{
	float value = floorf(x + 0.001f);
	return !isfinite(value) ? 0 : value < -256.0f ? -256 : value > 256.0f ? 256 : (int)value;
}

#include "nv2a_cpu_shaders.inc"

BOOL nv2a_cpu_program_is_specialized(const struct nv2a_cpu_program *program)
{
	return program && program->execute != NULL;
}

unsigned nv2a_cpu_program_inputs(const struct nv2a_cpu_program *program)
{
	return program->inputs;
}

unsigned nv2a_cpu_program_outputs(const struct nv2a_cpu_program *program)
{
	return program->outputs;
}

void nv2a_cpu_vertex_execute(const struct nv2a_cpu_program *program, const float inputs[16][4],
	const float constants[192][4], const float viewport_scale[4], const float viewport_offset[4],
	float screen_offset, float point_size, struct nv2a_cpu_vertex *vertex)
{
	cpu_vec4 temporary[12] = { { 0, 0, 0, 0 } };
	cpu_vec4 output[14] = { { 0, 0, 0, 1 } }, clip = { 0, 0, 0, 0 };
	static const unsigned outputs[9] = { 0, 3, 4, 7, 8, 9, 10, 11, 12 };
	BOOL captured = FALSE;
	int address = 0;
	unsigned long index;
	unsigned component;
	for (index = 1; index < 9; index++) output[outputs[index]][3] = 1.0f;
	output[5] = (cpu_vec4){ 1, 1, 1, 1 };
	output[6] = (cpu_vec4){ point_size, point_size, point_size, point_size };
	if (program->execute)
		captured = program->execute(inputs, constants, output, &clip);
	else for (index = 0; index < program->count; index++)
	{
		const struct cpu_instruction *instruction = &program->instruction[index];
		cpu_vec4 a = { 0, 0, 0, 0 }, b = a, c = a, mac = a, ilu = a;
		unsigned execution = instruction->execution;
		if (!execution) continue;
		if (execution & 1) a = cpu_operand_read(&instruction->operand[0], inputs, constants, temporary, output[0], address, program->prepared);
		if (execution & 2) b = cpu_operand_read(&instruction->operand[1], inputs, constants, temporary, output[0], address, program->prepared);
		if (execution & 4) c = cpu_operand_read(&instruction->operand[2], inputs, constants, temporary, output[0], address, program->prepared);
		if (execution & 8) mac = cpu_mac(instruction->mac, a, b, c);
		if (execution & 16) ilu = cpu_ilu(instruction->ilu, c);
		if (instruction->ilu == _ilu_rcc && instruction->operand[2].mux == _mux_temporary &&
			instruction->operand[2].index == 12)
		{
			clip = output[0]; captured = TRUE;
		}
		/* Both units read the old registers; writes follow in the same order
as the GLSL translator, including the parallel ILU destination r1. */
		if (instruction->mac == _mac_arl)
		{
			/* Relative reads clamp to 0..191. Saturating the address avoids
undefined C float-to-int conversion without altering any such read. */
			address = cpu_address(mac[0]);
		}
		else if (instruction->mac && instruction->mac_mask)
			cpu_write(instruction->temporary == 12 ? &output[0] : &temporary[instruction->temporary], mac, instruction->mac_mask);
		if (instruction->ilu && instruction->ilu_mask)
		{
			unsigned reg = instruction->mac ? 1 : instruction->temporary;
			cpu_write(reg == 12 ? &output[0] : &temporary[reg], ilu, instruction->ilu_mask);
		}
		if (instruction->output_is_register && (instruction->output_from_ilu ? instruction->ilu : instruction->mac))
		{
			unsigned reg = instruction->output_address;
			if (!(reg == 0 || reg == 3 || reg == 4 || reg == 5 || reg == 6 || (reg >= 7 && reg <= 12))) reg = 13;
			cpu_write(&output[reg], instruction->output_from_ilu ? ilu : mac, instruction->output_mask);
		}
	}
	for (component = 0; component < 3; component++)
	{
		float scale = viewport_scale[component] != 0.0f ? viewport_scale[component] : 1.0f;
		float half_pixel = component == 0 ? 0.5f + screen_offset : component == 1 ? 0.5f : 0.0f;
		vertex->value[0][component] = captured ?
			(clip[component] * constants[58][component] +
			 (constants[59][component] + half_pixel - viewport_offset[component]) * clip[3]) / scale :
			((output[0][component] + half_pixel - viewport_offset[component]) / scale) * output[0][3];
	}
	vertex->value[0][3] = captured ? clip[3] : output[0][3];
	if (!(fabsf(vertex->value[0][3]) > 0.0f) || isnan(vertex->value[0][3]))
	{
		vertex->value[0][0] = vertex->value[0][1] = vertex->value[0][2] = 0.0f;
		vertex->value[0][3] = -1.0f;
	}
	vertex->value[0][1] = -vertex->value[0][1];
	vertex->value[0][2] = 2.0f * vertex->value[0][2] - vertex->value[0][3];
	for (index = 1; index < 9; index++)
	{
		for (component = 0; component < 4; component++)
		{
			float value = output[outputs[index]][component];
			vertex->value[index][component] = index < 5 ? fminf(fmaxf(value, 0.0f), 1.0f) : value;
		}
	}
	vertex->fog = output[5][0];
	vertex->point_size = output[6][0];
	vertex->padding[0] = vertex->padding[1] = 0.0f;
}

static inline __attribute__((always_inline)) void cpu_attribute_decode(unsigned long type,
	const void *source, float value[4])
{
	unsigned component, count = 0;
	value[0] = value[1] = value[2] = 0.0f; value[3] = 1.0f;
	/* memcpy permits unaligned guest stream elements on every host. */
	switch (type)
	{
	case D3DVSDT_FLOAT1: count = 1; break;
	case D3DVSDT_FLOAT2: count = 2; break;
	case D3DVSDT_FLOAT3: case D3DVSDT_FLOAT2H: count = 3; break;
	case D3DVSDT_FLOAT4: count = 4; break;
	case D3DVSDT_D3DCOLOR:
		value[0] = ((const unsigned char *)source)[2] / 255.0f;
		value[1] = ((const unsigned char *)source)[1] / 255.0f;
		value[2] = ((const unsigned char *)source)[0] / 255.0f;
		value[3] = ((const unsigned char *)source)[3] / 255.0f;
		return;
	case D3DVSDT_NORMPACKED3:
	{
		unsigned int packed;
		int x, y, z;
		memcpy(&packed, source, 4);
		x = (int)(packed & 2047U); if (x & 1024) x -= 2048;
		y = (int)((packed >> 11) & 2047U); if (y & 1024) y -= 2048;
		z = (int)(packed >> 22); if (z & 512) z -= 1024;
		value[0] = x / 1023.0f; value[1] = y / 1023.0f; value[2] = z / 511.0f;
		return;
	}
	default:
		/* XDK types encode the component count in the high nibble; they
are not consecutive enum values. Low nibble: 1 normalized short,
4 normalized byte, 5 short. */
		if ((type & 15) == 1 || (type & 15) == 4 || (type & 15) == 5)
			count = type >> 4;
		if (count > 4) count = 0;
		for (component = 0; component < count; component++)
		{
			if ((type & 15) == 4)
				value[component] = ((const unsigned char *)source)[component] / 255.0f;
			else
			{
				short raw;
				memcpy(&raw, (const unsigned char *)source + component * 2, 2);
				value[component] = (type & 15) == 1 ?
					fmaxf(raw / 32767.0f, -1.0f) : (float)raw;
			}
		}
		return;
	}
	memcpy(value, source, count * sizeof(float));
}

void nv2a_cpu_attribute_decode(unsigned long type, const void *source, float value[4])
{
	cpu_attribute_decode(type, source, value);
}

void nv2a_cpu_attribute_decode_column(unsigned long type, const void *source, unsigned long stride,
	unsigned long count, float (*inputs)[16][4], unsigned reg)
{
	const unsigned char *element = source;
	unsigned long vertex;

	/* one element type for the whole column: the type switch inlines into
	this loop and always takes the same branch */
	for (vertex = 0; vertex < count; vertex++, element += stride)
		cpu_attribute_decode(type, element, inputs[vertex][reg]);
}

char *nv2a_cpu_vertex_glsl(void)
{
	struct xgpu_text text = { 0 };
	xgpu_text_append(&text, "#version %s\n", xgpu_capabilities.shading_language);
	xgpu_text_append(&text, "%s", "precision highp float;\nprecision highp int;\n"
		"/* NVIDIA CPU skeletal vertex path: original c[60] node programs run on the CPU. */\n"
		"layout(location=0) in vec4 p;\n"
		"layout(location=1) in vec4 d0;\nlayout(location=2) in vec4 d1;\n"
		"layout(location=3) in vec4 b0;\nlayout(location=4) in vec4 b1;\n"
		"layout(location=5) in vec4 t0;\nlayout(location=6) in vec4 t1;\n"
		"layout(location=7) in vec4 t2;\nlayout(location=8) in vec4 t3;\n"
		"layout(location=9) in vec2 auxiliary;\n"
		"out vec4 xD0;\nout vec4 xD1;\nout vec4 xB0;\nout vec4 xB1;\n"
		"out vec4 xT0;\nout vec4 xT1;\nout vec4 xT2;\nout vec4 xT3;\nout float xFog;\n"
		"invariant gl_Position;\nvoid main(){\n"
		"gl_Position=p; gl_PointSize=auxiliary.y;\n"
		"xD0=d0; xD1=d1; xB0=b0; xB1=b1;\n"
		"xT0=t0; xT1=t1; xT2=t2; xT3=t3; xFog=auxiliary.x;\n}\n");
	return text.buffer;
}
#endif
