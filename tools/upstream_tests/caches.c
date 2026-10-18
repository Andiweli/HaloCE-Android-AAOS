#include <assert.h>
#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef unsigned char boolean, byte;
typedef unsigned short word;
typedef float real;
typedef struct { real x, y, z; } real_point3d;
#define TRUE 1
#define FALSE 0
#define NONE (-1L)
#define TAG_STRING_LENGTH 31
#define MAXIMUM_CLUSTERS_PER_STRUCTURE 8
#define HALO_PORT_MAXIMUM_CLUSTER_REFERENCES 64
#define DATUM_INDEX_TO_ABSOLUTE_INDEX(index) ((index) & 65535)
#define NUMBEROF(array) (sizeof(array) / sizeof((array)[0]))
#define REAL_MAX FLT_MAX
#define TICKS_PER_SECOND 30
#define GARBAGE_ACTIVE_RETRY_TICKS TICKS_PER_SECOND
#define _game_connection_network_client 1
#define _game_connection_network_server 2
#define _error_immediate 0
#define _error_silent 1
#define _light_definition_dont_light_own_object_bit 0
#define TEST_FLAG(value, bit) (((value) & (1u << (bit))) != 0)
#define csmemset memset
#define csmemcpy memcpy
#define match_assert(file, line, condition) assert(condition)
#define match_vassert(file, line, condition, ...) assert(condition)

/* PRODUCTION_STRUCTURES */
_Static_assert(sizeof(struct cluster_partition) == 3 * sizeof(void *), "unchanged checkpoint partition layout");
struct location { short cluster_index; };
static struct { struct { short count; } clusters; } bsp = {{MAXIMUM_CLUSTERS_PER_STRUCTURE}};
#define global_structure_bsp_get() (&bsp)
static short sphere_clusters[MAXIMUM_CLUSTERS_PER_STRUCTURE], sphere_count;
static int debug_allocations, fail_debug, game_allocations;
static void *game_heap[64];
static void error(int kind, const char *format, ...) { (void)kind; (void)format; assert(0); }
static void data_verify(struct data_array *data) { assert(data && data->data && data->maximum_count > 0); }
/* PRODUCTION_DATA */
static void *game_state_malloc(const char *name, const char *type, size_t size)
{
    (void)name; (void)type;
    assert(game_allocations < (int)NUMBEROF(game_heap));
    void *result = calloc(1, size);
    assert(result);
    game_heap[game_allocations++] = result;
    return result;
}
static struct data_array *game_state_data_new(const char *name, short maximum, short size)
{
    struct data_array *array = game_state_malloc(name, NULL, sizeof(*array) + maximum * size);
    snprintf(array->name, sizeof(array->name), "%s", name);
    array->maximum_count = maximum;
    array->size = size;
    array->data = array + 1;
    return array;
}
static void data_make_valid(struct data_array *array)
{
    memset(array->data, 0, array->maximum_count * array->size);
    array->valid = TRUE;
    array->first_free_absolute_index = array->count = array->actual_count = 0;
    array->next_identifier = 1;
}
static void data_make_invalid(struct data_array *array) { array->valid = FALSE; }
static void *debug_malloc(size_t size, boolean clear, const char *file, long line)
{
    (void)file; (void)line;
    if (fail_debug) return NULL;
    void *result = clear ? calloc(1, size) : malloc(size);
    if (result) debug_allocations++;
    return result;
}
static void debug_free(void *pointer, const char *file, long line)
{
    (void)file; (void)line;
    if (pointer) debug_allocations--;
    free(pointer);
}
static short structure_clusters_in_sphere(short first, const real_point3d *position, real radius,
                                         short maximum, short *clusters)
{
    (void)first; (void)position; (void)radius;
    assert(sphere_count <= maximum);
    memcpy(clusters, sphere_clusters, sphere_count * sizeof(short));
    return sphere_count;
}
/* PRODUCTION_REFERENCES */
/* PRODUCTION_PARTITIONS */

static struct cluster_partition light_cluster_partition;
struct light_datum
{
    long object_index, definition_index;
    short rasterizer_light_index;
    real_point3d position;
    real radius;
    struct { real brightness; } color;
};
struct light_definition { unsigned flags; };
static struct light_datum fixture_lights[16];
static struct light_definition fixture_definitions[16];
static struct { boolean marker_initialized; } lights_globals = {TRUE};
static unsigned marked;
static struct light_datum *light_get(long index) { assert(index >= 0 && index < 16); return &fixture_lights[index]; }
static struct light_definition *light_definition_get(long index) { assert(index >= 0 && index < 16); return &fixture_definitions[index]; }
static boolean light_unmarked(long index) { return !(marked & (1u << index)); }
static void light_mark(long index) { marked |= 1u << index; }
static real distance3d(const real_point3d *a, const real_point3d *b)
{
    real x = a->x - b->x, y = a->y - b->y, z = a->z - b->z;
    return sqrtf(x * x + y * y + z * z);
}
static real light_attenuation(real radius, real distance) { return 1.0f / (1.0f + distance / (1 + radius)); }
#define real_rgb_color_brightness(color) ((color)->brightness)
/* PRODUCTION_LIGHT_CACHE */
/* PRODUCTION_LIGHT_FUNCTIONS */

static boolean cooperative, playing = TRUE, engine;
static short connection;
static long clock_tick, garbage_active_retry_time = NONE;
static short game_connection(void) { return connection; }
static boolean game_is_cooperative(void) { return cooperative; }
static boolean game_in_progress(void) { return playing; }
static boolean game_engine_running(void) { return engine; }
static long game_time_get(void) { return clock_tick; }
/* PRODUCTION_GARBAGE */

static boolean profile_global_enable, profile_graph, profile_dump_frames, profile_dump_lost_frames;
static struct { struct { int texture; } current_frame; } profile_globals;
static int profile_calls;
static void profile_timesection_begin_now(int *timer) { (void)timer; profile_calls++; }
static void profile_timesection_end_now(int *timer) { (void)timer; profile_calls++; }
/* PRODUCTION_PROFILE */

static void connect_to(struct cluster_partition *partition, long datum, long *reference, short first, short count)
{
    real_point3d position = {0};
    struct location location = {first};
    sphere_count = count;
    for (short i = 0; i < count; i++) sphere_clusters[i] = (first + i) % MAXIMUM_CLUSTERS_PER_STRUCTURE;
    cluster_partition_reconnect(partition, datum, reference, &position, 1, &location);
}
static boolean cluster_has(struct cluster_partition *partition, short cluster, long datum)
{
    long reference;
    for (long index = cluster_partition_get_first_datum(partition, &reference, cluster); index != NONE;
         index = cluster_partition_get_next_datum(partition, &reference))
        if (index == datum) return TRUE;
    return FALSE;
}
static void test_partitions(void)
{
    struct cluster_partition partition = {0}, copy = {0};
    long references[16];
    short first[16], count[16];
    boolean attached[16] = {0};
    cluster_partition_new(&partition, "fixture");
    cluster_partition_new(&copy, "copy");
    assert(game_allocations == 6 && debug_allocations == 4);
    cluster_partition_make_valid(&partition);
    cluster_partition_make_valid(&copy);
    for (int i = 0; i < 16; i++) references[i] = NONE;
    uint32_t random = 123;
    for (int step = 0; step < 1200; step++)
    {
        random = random * 1664525u + 1013904223u;
        int datum = (random >> 16) % 16;
        if (attached[datum])
        {
            cluster_partition_disconnect(&partition, datum, &references[datum]);
            attached[datum] = FALSE;
        }
        else
        {
            first[datum] = random % MAXIMUM_CLUSTERS_PER_STRUCTURE;
            count[datum] = 1 + (random >> 24) % 3;
            connect_to(&partition, datum, &references[datum], first[datum], count[datum]);
            attached[datum] = TRUE;
        }
        if (step % 19 == 0) cluster_partitions_port_forget();
        int expected_count = 0;
        for (int item = 0; item < 16; item++)
        {
            if (attached[item]) expected_count += count[item];
            for (short cluster = 0; cluster < MAXIMUM_CLUSTERS_PER_STRUCTURE; cluster++)
            {
                boolean expected = attached[item] &&
                    (cluster + MAXIMUM_CLUSTERS_PER_STRUCTURE - first[item]) % MAXIMUM_CLUSTERS_PER_STRUCTURE < count[item];
                assert(cluster_has(&partition, cluster, item) == expected);
            }
        }
        assert(partition.data_reference_data->actual_count == expected_count);
        assert(partition.cluster_reference_data->actual_count == expected_count);
    }
    unsigned long long generation = cluster_partition_port_modification_count(&copy);
    /* The original copy API copies list entries; array metadata is supplied
    by its caller. Keep that pre-existing contract in this fixture. */
    copy.data_reference_data->count = partition.data_reference_data->count;
    copy.cluster_reference_data->count = partition.cluster_reference_data->count;
    cluster_partition_copy(&copy, &partition);
    assert(cluster_partition_port_modification_count(&copy) != generation);
    for (short cluster = 0; cluster < MAXIMUM_CLUSTERS_PER_STRUCTURE; cluster++)
    {
        long a, b, ar, br;
        for (a = cluster_partition_get_first_datum(&partition, &ar, cluster),
             b = cluster_partition_get_first_datum(&copy, &br, cluster); a != NONE || b != NONE;
             a = cluster_partition_get_next_datum(&partition, &ar), b = cluster_partition_get_next_datum(&copy, &br))
            assert(a == b);
    }
    cluster_partition_make_invalid(&partition);
    cluster_partition_make_valid(&partition);
    long saved_ref = NONE, other_ref = NONE;
    connect_to(&partition, 42, &saved_ref, 0, 2);
    size_t array_size = HALO_PORT_MAXIMUM_CLUSTER_REFERENCES * sizeof(struct data_reference);
    void *saved_data = malloc(array_size), *saved_clusters = malloc(array_size);
    memcpy(saved_data, partition.data_reference_data->data, array_size);
    memcpy(saved_clusters, partition.cluster_reference_data->data, array_size);
    struct data_array saved_data_array = *partition.data_reference_data;
    struct data_array saved_cluster_array = *partition.cluster_reference_data;
    long saved_heads[MAXIMUM_CLUSTERS_PER_STRUCTURE];
    memcpy(saved_heads, partition.cluster_first_data_references, sizeof(saved_heads));
    long original_ref = saved_ref;
    cluster_partition_disconnect(&partition, 42, &saved_ref);
    connect_to(&partition, 99, &other_ref, 0, 2);
    /* Restore a checkpoint without restoring any runtime cache. */
    memcpy(partition.data_reference_data->data, saved_data, array_size);
    memcpy(partition.cluster_reference_data->data, saved_clusters, array_size);
    *partition.data_reference_data = saved_data_array;
    *partition.cluster_reference_data = saved_cluster_array;
    memcpy(partition.cluster_first_data_references, saved_heads, sizeof(saved_heads));
    cluster_partitions_port_forget();
    cluster_partition_disconnect(&partition, 42, &original_ref);
    assert(partition.data_reference_data->actual_count == 0 && partition.cluster_reference_data->actual_count == 0);
    free(saved_data); free(saved_clusters);
    cluster_partition_delete(&partition);
    cluster_partition_delete(&copy);
    assert(debug_allocations == 0);

    /* Optional cache allocation fails: the original list walk still works. */
    fail_debug = TRUE;
    cluster_partition_new(&partition, "no cache");
    cluster_partition_make_valid(&partition);
    saved_ref = NONE;
    connect_to(&partition, 55, &saved_ref, 0, 2);
    cluster_partition_disconnect(&partition, 55, &saved_ref);
    assert(partition.data_reference_data->actual_count == 0);
    cluster_partition_delete(&partition);
    fail_debug = FALSE;
}
struct light_result { long indices[4]; real intensities[4], attenuations[4]; short count; };
static struct light_result light_result_for(boolean cached, real_point3d center, real radius, long object)
{
    struct light_result result = {{0}, {0}, {0}, 0};
    marked = 0;
    for (short cluster = 0; cluster < 3; cluster++)
    {
        if (cached)
            find_point_lights_for_object_in_cluster(object, cluster, &center, radius, result.indices,
                result.intensities, result.attenuations, &result.count, 4);
        else
        {
            long reference;
            for (long index = cluster_partition_get_first_datum(&light_cluster_partition, &reference, cluster); index != NONE;
                 index = cluster_partition_get_next_datum(&light_cluster_partition, &reference))
                find_point_light_for_object(object, index, &center, radius, result.indices,
                    result.intensities, result.attenuations, &result.count, 4);
        }
    }
    return result;
}
static void test_lights(void)
{
    long references[16];
    cluster_partition_new(&light_cluster_partition, "light");
    cluster_partition_make_valid(&light_cluster_partition);
    for (int i = 0; i < 16; i++)
    {
        references[i] = NONE;
        fixture_lights[i].position = (real_point3d){i - 6, i % 3, i % 2};
        fixture_lights[i].radius = 1 + i % 4;
        fixture_lights[i].color.brightness = 1 + i % 5;
        fixture_lights[i].rasterizer_light_index = i % 7 == 0 ? NONE : i;
        fixture_lights[i].object_index = i % 2;
        fixture_lights[i].definition_index = i;
        fixture_definitions[i].flags = i % 3 == 0;
        connect_to(&light_cluster_partition, i, &references[i], i % 3, 2);
    }
    for (int scene = 0; scene < 90; scene++)
    {
        int light = scene % 16;
        fixture_lights[light].radius = 1 + scene % 6;
        fixture_lights[light].rasterizer_light_index = scene % 2 ? NONE : light;
        lights_port.radius_writes++;
        if (scene % 7 == 0) cluster_partitions_port_forget();
        for (int object = 0; object < 12; object++)
        {
            real_point3d center = {object - 7, object % 3, 0};
            struct light_result cached = light_result_for(TRUE, center, 0.5f, object % 2);
            struct light_result original = light_result_for(FALSE, center, 0.5f, object % 2);
            assert(cached.count == original.count);
            assert(!memcmp(cached.indices, original.indices, sizeof(cached.indices)));
            assert(!memcmp(cached.intensities, original.intensities, sizeof(cached.intensities)));
            assert(!memcmp(cached.attenuations, original.attenuations, sizeof(cached.attenuations)));
        }
    }
    /* Explicitly exhaust the optional cache: identical list-walk results. */
    lights_port.entry_count = LIGHTS_PORT_MAXIMUM_ENTRIES - 1;
    memset(lights_port.cluster_generations, 0, sizeof(lights_port.cluster_generations));
    real_point3d center = {0};
    struct light_result cached = light_result_for(TRUE, center, 1, 0);
    struct light_result original = light_result_for(FALSE, center, 1, 0);
    assert(cached.count == original.count && !memcmp(cached.indices, original.indices, sizeof(cached.indices)));
    assert(lights_port.cluster_first_entries[0] == NONE);
    cluster_partition_delete(&light_cluster_partition);
    assert(debug_allocations == 0);
}
int main(void)
{
    struct data_array *array = game_state_data_new("full", 16, sizeof(struct datum_header));
    data_make_valid(array);
    long indices[16];
    for (int i = 0; i < 16; i++) indices[i] = datum_new(array);
    array->first_free_absolute_index = 0;
    assert(datum_new(array) == NONE && array->first_free_absolute_index == array->maximum_count);
    assert(datum_new(array) == NONE);
    datum_delete(array, indices[7]);
    assert(array->first_free_absolute_index == 7 && DATUM_INDEX_TO_ABSOLUTE_INDEX(datum_new(array)) == 7);
    int initial_allocations = game_allocations;
    game_allocations = 0;
    void *data_allocation = game_heap[0];
    test_partitions();
    test_lights();
    for (int i = 0; i < game_allocations; i++) free(game_heap[i]);
    free(data_allocation);
    assert(initial_allocations == 1);

    garbage_active_retry_time = 100;
    clock_tick = 50;
    assert(objects_garbage_active_due());
    cooperative = TRUE;
    connection = _game_connection_network_server;
    clock_tick = 80;
    assert(!objects_garbage_active_due());
    clock_tick = 100;
    assert(objects_garbage_active_due());
    clock_tick = 20;
    assert(objects_garbage_active_due() && garbage_active_retry_time == NONE);
    garbage_active_retry_time = 40;
    engine = TRUE;
    assert(objects_garbage_active_due());

    profile_texture_start(); profile_texture_end();
    assert(profile_calls == 0);
    boolean *flags[] = {&profile_global_enable, &profile_graph, &profile_dump_frames, &profile_dump_lost_frames};
    for (int i = 0; i < 4; i++)
    {
        *flags[i] = TRUE;
        profile_texture_start(); profile_texture_end();
        assert(profile_calls == 2 * (i + 1));
        *flags[i] = FALSE;
    }
    puts("Caches: full-array reuse, 1,200 partition updates, copied/restored checkpoints, allocation fallback, equivalent lighting, GC timing and texture profiling passed.");
    return 0;
}
