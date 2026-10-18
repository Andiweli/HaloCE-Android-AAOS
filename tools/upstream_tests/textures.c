#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t DWORD, D3DCOLOR, GLuint, GLenum;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define D3DFORMAT_FORMAT_MASK 255
#define D3DFORMAT_FORMAT_SHIFT 0
#define GL_TEXTURE_2D 1
#define GL_TEXTURE_3D 2
#define GL_TEXTURE_CUBE_MAP 3
/* PRODUCTION_DESCRIPTION */
static unsigned char pixels[16384];
#define PLATFORM_PHYSICAL_TO_VIRTUAL(data) (pixels + (data))
static unsigned long page_generation[sizeof(pixels) / 128], watch_serial = 1;
static int generation_reads, uploads, deleted;
static GLuint texture_id;
static void glGenTextures(int count, GLuint *texture) { assert(count == 1); *texture = ++texture_id; }
static void glDeleteTextures(int count, const GLuint *texture) { assert(count == 1 && *texture); deleted++; }
static void xgpu_gl_state_invalidate(void) {}
static BOOL platform_is_contiguous(void *pointer) { return (unsigned char *)pointer >= pixels && (unsigned char *)pointer < pixels + sizeof(pixels); }
static void platform_log(const char *format, ...) { (void)format; }
static int config_boolean(const char *name) { (void)name; return 0; }
static unsigned long memory_watch_serial(void) { return watch_serial; }
static unsigned long memory_watch_generation(unsigned long address, unsigned long size)
{
    (void)size;
    assert(platform_is_contiguous((void *)address));
    generation_reads++;
    return page_generation[((unsigned char *)address - pixels) / 128];
}
static void memory_watch_protect(unsigned long address, unsigned long size) { (void)address; (void)size; }
static void xgpu_texture_describe(DWORD format, DWORD size, struct xgpu_texture_description *description)
{
    memset(description, 0, sizeof(*description));
    description->format = format & 255;
    description->width = 4 + size % 2;
    description->height = 4;
    description->depth = 1;
    description->levels = 1;
}
static unsigned long xgpu_texture_face_size(const struct xgpu_texture_description *description)
{
    return description->width * description->height * 4;
}
static unsigned long xgpu_texture_level_offset(const struct xgpu_texture_description *description, unsigned long level)
{
    (void)level;
    return xgpu_texture_face_size(description);
}
static long hud_hires_override_find(unsigned long address, unsigned long width, unsigned long height, unsigned long size)
{
    (void)address; (void)width; (void)height; (void)size;
    return -1;
}
static GLuint hud_hires_override_texture(long index, unsigned long *levels) { (void)index; (void)levels; return 0; }
static BOOL hud_hires_override_coverage(long index) { (void)index; return FALSE; }
static void upload(GLuint texture, GLenum target, const struct xgpu_texture_description *description,
                   const unsigned char *source, const D3DCOLOR *palette)
{
    (void)target; (void)description; (void)source; (void)palette;
    assert(texture);
    uploads++;
}
/* PRODUCTION_CACHE */

static GLuint get_texture(DWORD *resource, const D3DCOLOR *palette)
{
    GLenum target;
    struct xgpu_texture_description description;
    GLuint result = xgpu_texture_get(resource, palette, &target, &description);
    assert(result && target == GL_TEXTURE_2D && description.height == 4);
    return result;
}
int main(void)
{
    DWORD resource[5] = {0, 128, 0, 6, 0};
    GLuint original = get_texture(resource, NULL);
    assert(uploads == 1);
    int scans = generation_reads;
    for (int i = 0; i < 100; i++) assert(get_texture(resource, NULL) == original);
    assert(generation_reads == scans && uploads == 1);
    /* A write to a different texture invalidates the serial, not this data. */
    page_generation[2] = ++watch_serial;
    assert(get_texture(resource, NULL) == original);
    assert(generation_reads == scans + 1 && uploads == 1);
    scans = generation_reads;
    page_generation[1] = ++watch_serial;
    assert(get_texture(resource, NULL) == original);
    assert(uploads == 2 && generation_reads == scans + 2);

    /* Evict a recent-slot lookup without deleting its texture entry. */
    DWORD collision[5] = {0, 0, 0, 6, 0};
    for (unsigned long data = 256; data < sizeof(pixels) - 128; data += 128)
        if (bucket_index(data, 6, 0) % RECENT_TEXTURE_COUNT == bucket_index(resource[1], 6, 0) % RECENT_TEXTURE_COUNT)
        { collision[1] = data; break; }
    /* With no collision among these aligned values, directly replace the
    optional lookup slot; the bucket path is still the production code. */
    if (collision[1]) get_texture(collision, NULL);
    else memset(&recent_textures[bucket_index(resource[1], 6, 0) % RECENT_TEXTURE_COUNT], 0, sizeof(recent_textures[0]));
    scans = generation_reads;
    assert(get_texture(resource, NULL) == original && generation_reads == scans);
    resource[4] = 1;
    assert(get_texture(resource, NULL) != original);

    D3DCOLOR palette[256] = {0};
    DWORD palettized[5] = {0, 512, 0, 0x0b, 0};
    GLuint variants[8];
    for (int i = 0; i < 8; i++)
    {
        palette[0] = i;
        variants[i] = get_texture(palettized, palette);
        texture_frame++;
    }
    unsigned long bucket = bucket_index(512, 0x0b, 0);
    int entries = 0;
    for (struct texture_entry *entry = texture_buckets[bucket]; entry; entry = entry->next) entries++;
    assert(entries == 8);
    int before_upload = uploads;
    palette[0] = 0;
    assert(get_texture(palettized, palette) == variants[0] && uploads == before_upload);
    palette[0] = 99;
    assert(get_texture(palettized, palette) == variants[1] && uploads == before_upload + 1);
    entries = 0;
    for (struct texture_entry *entry = texture_buckets[bucket]; entry; entry = entry->next) entries++;
    assert(entries == 8);

    texture_frame = TEXTURE_IDLE_FRAMES + 599;
    xgpu_texture_cache_begin_frame();
    assert(deleted == (int)texture_id);
    assert(get_texture(resource, NULL) > original);
    /* Drop the last entry too; no stale cached pointer is dereferenced. */
    texture_frame += TEXTURE_IDLE_FRAMES + 599;
    xgpu_texture_cache_begin_frame();
    assert(deleted == (int)texture_id);
    puts("Texture cache: watched/unrelated writes, cached generation reuse, format changes, palette cycling and eviction passed.");
    return 0;
}
