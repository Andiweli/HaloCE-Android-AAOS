/*
HALO_ANDROID_PERF.H

The NVIDIA Shield performance test (diagnostic builds): the in-game
settings overlay (SettingsOverlay.java) packs these settings into one word,
the host keeps it (port/android/host/host_perf.c) and the renderer reads it
once a frame (port/linux/src/d3d8_gl.c). The skinning and visibility
settings take effect on NVIDIA GPUs only; every other GPU keeps its path.

Included by the guest, the host and mirrored in SettingsOverlay.java.
*/

#ifndef __HALO_ANDROID_PERF_H
#define __HALO_ANDROID_PERF_H

/* how skeletal (animated) models are transformed on NVIDIA */
#define HALO_PERF_SKINNING_MASK 0x0fu
enum
{
	/* the original NV2A programs on the CPU, split over worker threads */
	HALO_PERF_CPU_THREADS,
	/* the same on the render thread only (the earlier Shield build) */
	HALO_PERF_CPU_SINGLE,
	/* test: the GPU programs read c[] from a uniform buffer per draw */
	HALO_PERF_GPU_UNIFORM_BLOCK,
	/* test: the GPU programs get all of c[] uploaded for every draw */
	HALO_PERF_GPU_FULL_CONSTANTS,
	/* the unchanged GPU path (known artefacts; for frame-rate comparison) */
	HALO_PERF_GPU_ORIGINAL,
	HALO_PERF_SKINNING_COUNT
};
/* wait for lens flare visibility counts as before, instead of reading the
latest finished hardware result */
#define HALO_PERF_VISIBILITY_WAIT 0x100u
/* the on-screen frame-time counter (PerfOverlay.java) */
#define HALO_PERF_OVERLAY 0x200u
/* test 4: the CPU skinning runs one vertex at a time (tests 1 to 3)
instead of four at once, one in each NEON lane (nv2a_cpu_vertex_execute4) */
#define HALO_PERF_ONE_VERTEX 0x400u
/* set once the overlay has passed its saved settings */
#define HALO_PERF_SET 0x80000000u

#endif
