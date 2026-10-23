#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint32_t GLuint, GLenum, DWORD, UINT;
typedef uint64_t ULONGLONG;
typedef intptr_t GLintptr;
typedef int BOOL, HRESULT, GLint, GLsizei;
#define WINAPI
#define TRUE 1
#define FALSE 0
#define S_OK 0
#define XGPU_VERTEX_CONSTANT_COUNT 192
#define VISIBILITY_TEST_SLOTS 16
#define VISIBILITY_ALL_SAMPLES 1048576u
#define VISIBILITY_QUERY 1
#define GL_QUERY_RESULT 2
#define GL_QUERY_RESULT_AVAILABLE 3
#define GL_QUERY_BUFFER 4
#define GL_ATOMIC_COUNTER_BUFFER 5

static struct
{
    BOOL gl_ready, visibility_test_active;
    GLuint queries[VISIBILITY_TEST_SLOTS + 1];
    BOOL query_pending[VISIBILITY_TEST_SLOTS], visibility_unread[VISIBILITY_TEST_SLOTS];
    GLuint visibility_known[VISIBILITY_TEST_SLOTS];
    float query_area[VISIBILITY_TEST_SLOTS];
    GLuint visibility_counters, visibility_results_buffer;
    unsigned long counter_next, counter_active, counter_of_slot[VISIBILITY_TEST_SLOTS];
    BOOL counter_test;
    volatile GLuint *visibility_results;
    float constants[XGPU_VERTEX_CONSTANT_COUNT][4];
} device;
static struct { BOOL atomic_counters; } xgpu_capabilities;
/* d3d8_gl.c: other GPUs wait for the counts; NVIDIA reads the latest
finished hardware result */
static BOOL nvidia;
static BOOL android_visibility_wait(void) { return !nvidia; }
static float target_scale[2] = {1, 1};
static GLuint active_query, fake_samples[VISIBILITY_TEST_SLOTS + 2];
static BOOL fake_available[VISIBILITY_TEST_SLOTS + 2];
static GLuint counters[VISIBILITY_TEST_SLOTS];
static int query_reads, availability_reads;

static void glBeginQuery(GLenum type, GLuint query)
{
    assert(type == VISIBILITY_QUERY && !active_query);
    active_query = query;
    fake_available[query] = FALSE;
}
static void glEndQuery(GLenum type) { assert(type == VISIBILITY_QUERY && active_query); active_query = 0; }
static void glGetQueryObjectuiv(GLuint query, GLenum parameter, GLuint *result)
{
    assert(query > 0 && query <= VISIBILITY_TEST_SLOTS + 1);
    if (parameter == GL_QUERY_RESULT_AVAILABLE)
    {
        availability_reads++;
        *result = fake_available[query];
    }
    else
    {
        assert(parameter == GL_QUERY_RESULT);
#ifndef HALO_ANDROID
        assert(fake_available[query]);
#else
        assert(xgpu_capabilities.atomic_counters || fake_available[query]);
#endif
        query_reads++;
        *result = fake_samples[query];
    }
}
static void glBindBuffer(GLenum target, GLuint buffer) { (void)target; (void)buffer; }
static void host_gl_buffer_write(GLenum target, unsigned int offset, unsigned int size, const void *data)
{
    assert(target == GL_ATOMIC_COUNTER_BUFFER && size == sizeof(GLuint));
    memcpy(&counters[offset / sizeof(GLuint)], data, size);
}
static GLuint host_gl_read_buffer_word(GLuint buffer, unsigned int offset)
{
    (void)buffer;
    return counters[offset / sizeof(GLuint)];
}
static void glGetQueryBufferObjectuiv(GLuint query, GLuint buffer, GLenum parameter, GLintptr offset)
{
    (void)query; (void)buffer; (void)offset;
    assert(parameter == GL_QUERY_RESULT);
}

struct program_entry
{
    unsigned long constant_count;
    BOOL constants_consecutive;
    GLint constants;
/* PRODUCTION_SERIAL_FIELD */
};
_Static_assert(sizeof(((struct program_entry *)0)->constants_serial) == 8, "64-bit program serial");
/* PRODUCTION_CONSTANT_GLOBALS */
/* PRODUCTION_CONSTANT_STORE */
static float uploaded[XGPU_VERTEX_CONSTANT_COUNT][4];
static unsigned uploads;
static void glUniform4fv(GLint location, GLsizei count, const float *values)
{
    assert(location >= 0 && location + count <= XGPU_VERTEX_CONSTANT_COUNT);
    memcpy(uploaded[location], values, count * sizeof(uploaded[0]));
    uploads++;
}
static void upload_constants(struct program_entry *entry)
{
/* PRODUCTION_CONSTANT_UPLOAD */
}
/* PRODUCTION_VISIBILITY */

static void begin_test(UINT index, GLuint samples, BOOL available)
{
    D3DDevice_BeginVisibilityTest();
    D3DDevice_EndVisibilityTest(index);
    index %= VISIBILITY_TEST_SLOTS;
    fake_samples[device.queries[index]] = samples;
    fake_available[device.queries[index]] = available;
}
static GLuint result_of(UINT index)
{
    UINT result = 123;
    ULONGLONG timestamp = 99;
    assert(D3DDevice_GetVisibilityTestResult(index, &result, &timestamp) == S_OK);
    assert(timestamp == 0);
    return result;
}
int main(void)
{
    device.gl_ready = TRUE;
    for (UINT i = 0; i <= VISIBILITY_TEST_SLOTS; i++) device.queries[i] = i + 1;
    assert(result_of(0) == 0);
    begin_test(0, 400, FALSE);
    GLuint slot_zero = device.queries[0];
    begin_test(1, 0, FALSE);
    assert(device.queries[0] == slot_zero && device.queries[1] != slot_zero);
    assert(result_of(0) == 0 && result_of(1) == 0 && query_reads == 0);
    fake_available[device.queries[0]] = TRUE;
#ifdef HALO_ANDROID
    assert(result_of(0) == VISIBILITY_ALL_SAMPLES);
#else
    device.query_area[0] = 4;
    assert(result_of(0) == 100);
#endif
    int reads = query_reads, polls = availability_reads;
    assert(result_of(0) != 0 && query_reads == reads && availability_reads == polls);
    begin_test(0, 0, FALSE);
    assert(result_of(VISIBILITY_TEST_SLOTS) != 0 && query_reads == reads);
    fake_available[device.queries[0]] = TRUE;
    assert(result_of(0) == 0 && query_reads == reads + 1);
    assert(D3DDevice_GetVisibilityTestResult(0, NULL, NULL) == S_OK);
    device.gl_ready = FALSE;
    assert(result_of(0) == 0);
    device.gl_ready = TRUE;

#ifdef HALO_ANDROID
    /* The tutorial's hardware fallback remains authoritative on ES 3.1. */
    xgpu_capabilities.atomic_counters = TRUE;
    begin_test(0, 1, TRUE);
    assert(result_of(0) == VISIBILITY_ALL_SAMPLES);
    counters[device.counter_of_slot[0]] = 12;
    assert(result_of(0) == 12);
    fake_samples[device.queries[0]] = 0;
    assert(result_of(0) == 0);
    /* NVIDIA: no counter, no wait; the latest finished hardware result */
    nvidia = TRUE;
    begin_test(2, 1, FALSE);
    assert(!device.counter_test && device.counter_of_slot[2] == VISIBILITY_TEST_SLOTS);
    reads = query_reads;
    assert(result_of(2) == 0 && query_reads == reads);
    fake_available[device.queries[2]] = TRUE;
    assert(result_of(2) == VISIBILITY_ALL_SAMPLES && query_reads == reads + 1);
    /* other GPUs again: counters, and a test begun without one */
    nvidia = FALSE;
    assert(result_of(2) == VISIBILITY_ALL_SAMPLES);
    begin_test(3, 1, TRUE);
    assert(device.counter_test && device.counter_of_slot[3] < VISIBILITY_TEST_SLOTS);
    counters[device.counter_of_slot[3]] = 7;
    assert(result_of(3) == 7);
    xgpu_capabilities.atomic_counters = FALSE;
#else
    GLuint gpu_results[VISIBILITY_TEST_SLOTS] = {400};
    device.visibility_results = gpu_results;
    device.query_area[0] = 4;
    assert(result_of(0) == 100);
    device.visibility_results = NULL;
#endif

    struct program_entry program = {XGPU_VERTEX_CONSTANT_COUNT, TRUE, 0, UINT32_MAX - 4ULL};
    constants_serial = program.constants_serial;
    constants_checkpoint_serial = constants_serial;
    float values[10][4];
    for (int r = 0; r < 10; r++)
        for (int c = 0; c < 4; c++) values[r][c] = r + c + 1;
    constants_store(5, values, 10);
    assert(constants_serial > UINT32_MAX);
    upload_constants(&program);
    assert(uploads == 1 && !memcmp(uploaded, device.constants, sizeof(uploaded)));
    uploads = 0;
    upload_constants(&program);
    assert(uploads == 0);
    struct program_entry stale = {XGPU_VERTEX_CONSTANT_COUNT, FALSE, 0, 1};
    memset(uploaded, 0, sizeof(uploaded));
    upload_constants(&stale);
    assert(uploads == 1 && !memcmp(uploaded, device.constants, sizeof(uploaded)));
    assert(constants_checkpoint_serial == constants_serial);

    program.constant_count = 3;
    constants_store(150, values, 1);
    uploads = 0;
    upload_constants(&program);
    assert(uploads == 0 && program.constants_serial == constants_serial);
    program.constant_count = XGPU_VERTEX_CONSTANT_COUNT;
    program.constants_serial = 1;
    memset(uploaded, 0, sizeof(uploaded));
    upload_constants(&program);
    assert(uploads == 1 && !memcmp(uploaded, device.constants, sizeof(uploaded)));
#ifdef HALO_ANDROID
    puts("Android visibility: independent slots 0/1, delayed/zero results, tutorial hardware fallback, NVIDIA reads without waiting and other GPUs' wait passed; constant serials cross 32 bits correctly.");
#else
    puts("Desktop visibility: delayed queries, pixel scaling and mapped results passed; constant serials cross 32 bits correctly.");
#endif
    return 0;
}
