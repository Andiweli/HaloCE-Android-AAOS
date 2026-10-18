/* The test runner inserts the production writer and public I/O functions. */
#include <assert.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef unsigned char boolean, byte;
typedef unsigned long DWORD;
typedef void *LPVOID;
typedef struct handle *HANDLE;
#define WINAPI
#define TRUE 1
#define FALSE 0
#define CPU_PAGE_SIZE 4096
#define GAME_STATE_FILE_SIZE 16384
#define GENERIC_READ 1
#define GENERIC_WRITE 2
#define OPEN_ALWAYS 1
#define FILE_FLAG_NO_BUFFERING 1
#define FILE_FLAG_SEQUENTIAL_SCAN 2
#define FILE_BEGIN 0
#define INFINITE (~0UL)
#define INVALID_SET_FILE_POINTER (~0UL)
#define INVALID_HANDLE_VALUE ((HANDLE)(intptr_t)-1)
#define _error_log 0
#define match_assert(file, line, condition) assert(condition)
#define match_vassert(file, line, condition, ...) ((void)(condition))

struct handle
{
    int kind, manual, signaled;
    pthread_mutex_t lock;
    pthread_cond_t condition;
    pthread_t thread;
    DWORD (*start)(LPVOID);
    LPVOID argument;
};
static int handles, allocations, fail_allocation, fail_event, fail_thread, logged_errors;
static int paused, writing, write_mode, waiters, last_write_failed;
static unsigned char file_bytes[GAME_STATE_FILE_SIZE];
static unsigned long file_offset;
static pthread_mutex_t io_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t io_condition = PTHREAD_COND_INITIALIZER;
static boolean recover_saved_games_hack;

static void wait_until(int *value)
{
    struct timespec deadline;
    clock_gettime(CLOCK_REALTIME, &deadline);
    deadline.tv_sec += 3;
    pthread_mutex_lock(&io_lock);
    while (!*value)
        assert(pthread_cond_timedwait(&io_condition, &io_lock, &deadline) == 0);
    pthread_mutex_unlock(&io_lock);
}
static HANDLE handle_new(int kind)
{
    HANDLE result = calloc(1, sizeof(*result));
    assert(result);
    result->kind = kind;
    pthread_mutex_init(&result->lock, NULL);
    pthread_cond_init(&result->condition, NULL);
    handles++;
    return result;
}
static HANDLE CreateFileA(const char *name, int access, int sharing, void *security,
                          int creation, int flags, HANDLE template)
{
    (void)name; (void)access; (void)sharing; (void)security;
    (void)creation; (void)flags; (void)template;
    file_offset = 0;
    return handle_new(1);
}
static unsigned long SetFilePointer(HANDLE file, unsigned long offset, void *high, int origin)
{
    (void)high; (void)origin;
    assert(file && file->kind == 1 && offset <= GAME_STATE_FILE_SIZE);
    file_offset = offset;
    return offset;
}
static int SetEndOfFile(HANDLE file) { assert(file->kind == 1); return TRUE; }
static DWORD GetLastError(void) { return last_write_failed ? 123 : 0; }
static int WriteFile(HANDLE file, const void *buffer, unsigned long size,
                     unsigned long *written, void *overlapped)
{
    (void)overlapped;
    assert(file && file->kind == 1);
    assert(file_offset + size <= sizeof(file_bytes));
    pthread_mutex_lock(&io_lock);
    writing = 1;
    pthread_cond_broadcast(&io_condition);
    while (paused)
        pthread_cond_wait(&io_condition, &io_lock);
    *written = write_mode == 2 ? size / 2 : write_mode == 1 ? 0 : size;
    if (*written)
        memcpy(file_bytes + file_offset, buffer, *written);
    last_write_failed = write_mode != 0;
    writing = 0;
    pthread_mutex_unlock(&io_lock);
    return write_mode != 1;
}
static int ReadFile(HANDLE file, void *buffer, unsigned long size,
                    unsigned long *read_count, void *overlapped)
{
    (void)overlapped;
    assert(file && file->kind == 1 && !writing);
    assert(file_offset + size <= sizeof(file_bytes));
    memcpy(buffer, file_bytes + file_offset, size);
    *read_count = size;
    return TRUE;
}
static HANDLE CreateEventA(void *security, int manual, int initial, const char *name)
{
    (void)security; (void)name;
    if (fail_event && --fail_event == 0)
        return NULL;
    HANDLE result = handle_new(2);
    result->manual = manual;
    result->signaled = initial;
    return result;
}
static int SetEvent(HANDLE event)
{
    assert(event && event->kind == 2);
    pthread_mutex_lock(&event->lock);
    event->signaled = 1;
    pthread_cond_broadcast(&event->condition);
    pthread_mutex_unlock(&event->lock);
    return TRUE;
}
static int ResetEvent(HANDLE event)
{
    assert(event && event->kind == 2);
    pthread_mutex_lock(&event->lock);
    event->signaled = 0;
    pthread_mutex_unlock(&event->lock);
    return TRUE;
}
static void *thread_start(void *argument)
{
    HANDLE thread = argument;
    thread->start(thread->argument);
    return NULL;
}
static HANDLE CreateThread(void *security, DWORD stack, DWORD (*start)(LPVOID),
                           LPVOID argument, DWORD flags, void *thread_id)
{
    (void)security; (void)stack; (void)flags; (void)thread_id;
    if (fail_thread)
        return NULL;
    HANDLE result = handle_new(3);
    result->start = start;
    result->argument = argument;
    assert(pthread_create(&result->thread, NULL, thread_start, result) == 0);
    return result;
}
static DWORD WaitForSingleObject(HANDLE object, DWORD timeout)
{
    assert(object);
    if (object->kind == 3)
    {
        assert(pthread_join(object->thread, NULL) == 0);
        return 0;
    }
    assert(object->kind == 2 && timeout == INFINITE);
    pthread_mutex_lock(&object->lock);
    while (!object->signaled)
    {
        /* Expose an actual blocked second save/close to the fixture. */
        if (object->manual)
        {
            pthread_mutex_lock(&io_lock);
            waiters = 1;
            pthread_cond_broadcast(&io_condition);
            pthread_mutex_unlock(&io_lock);
        }
        pthread_cond_wait(&object->condition, &object->lock);
    }
    if (!object->manual)
        object->signaled = 0;
    pthread_mutex_unlock(&object->lock);
    return 0;
}
static int CloseHandle(HANDLE object)
{
    assert(object);
    assert(object->kind != 1 || !writing);
    pthread_cond_destroy(&object->condition);
    pthread_mutex_destroy(&object->lock);
    free(object);
    handles--;
    return TRUE;
}
static void error(int priority, const char *format, ...)
{
    (void)priority; (void)format;
    logged_errors++;
}
static void XPhysicalFree(void *buffer) { assert(!writing); (void)buffer; }
static void *snapshot_malloc(size_t size)
{
    if (fail_allocation)
        return NULL;
    void *result = malloc(size);
    if (result) allocations++;
    return result;
}
static void snapshot_free(void *pointer)
{
    if (pointer) allocations--;
    free(pointer);
}

/* PRODUCTION_GLOBALS */
static boolean game_state_writer_ready(void);
static void game_state_writer_wait(void);
static void game_state_writer_dispose(void);
#define malloc snapshot_malloc
#define free snapshot_free
/* PRODUCTION_FUNCTIONS */
#undef malloc
#undef free

static unsigned char game_buffer[GAME_STATE_FILE_SIZE];
static void open_file(unsigned char value)
{
    memset(game_buffer, value, sizeof(game_buffer));
    xbox_game_state_globals.buffer_allocated = TRUE;
    xbox_game_state_globals.buffer = game_buffer;
    xbox_game_state_globals.buffer_size = sizeof(game_buffer);
    game_state_create_or_open_file();
}
static void expect_bytes(const void *buffer, unsigned char value)
{
    const unsigned char *bytes = buffer;
    for (unsigned i = 0; i < sizeof(game_buffer); i++) assert(bytes[i] == value);
}
static void unpause(void)
{
    pthread_mutex_lock(&io_lock);
    paused = 0;
    pthread_cond_broadcast(&io_condition);
    pthread_mutex_unlock(&io_lock);
}
static void *save_again(void *unused)
{
    (void)unused;
    assert(game_state_write_to_file());
    return NULL;
}
static void *close_file(void *unused)
{
    (void)unused;
    game_state_close_file();
    return NULL;
}
int main(void)
{
    pthread_t caller;
    open_file(0x11);
    assert(game_state_writer.thread && allocations == 1);
    assert((uintptr_t)game_state_writer.snapshot % CPU_PAGE_SIZE == 0);
    paused = 1;
    assert(game_state_write_to_file());
    wait_until(&writing);
    memset(game_buffer, 0x99, sizeof(game_buffer));
    assert(game_state_read_from_file());
    expect_bytes(game_buffer, 0x11);
    memset(game_buffer, 0x22, sizeof(game_buffer));
    waiters = 0;
    assert(pthread_create(&caller, NULL, save_again, NULL) == 0);
    wait_until(&waiters);
    expect_bytes(game_state_writer.snapshot, 0x11);
    unpause();
    assert(pthread_join(caller, NULL) == 0);
    game_state_writer_wait();
    expect_bytes(file_bytes, 0x22);
    memset(game_buffer, 0, sizeof(game_buffer));
    assert(game_state_read_from_file());
    expect_bytes(game_buffer, 0x22);

    for (write_mode = 1; write_mode <= 2; write_mode++)
    {
        memset(game_buffer, 0x30 + write_mode, sizeof(game_buffer));
        assert(game_state_write_to_file());
        game_state_writer_wait();
        memset(game_buffer, 0, sizeof(game_buffer));
        assert(game_state_read_from_file());
        expect_bytes(game_buffer, 0x30 + write_mode);
    }
    assert(logged_errors == 2);
    write_mode = 0;
    paused = 1;
    waiters = 0;
    assert(game_state_write_to_file());
    wait_until(&writing);
    assert(pthread_create(&caller, NULL, close_file, NULL) == 0);
    wait_until(&waiters);
    assert(xbox_game_state_globals.file_open);
    unpause();
    assert(pthread_join(caller, NULL) == 0);
    assert(!game_state_writer.snapshot_valid && !game_state_writer.thread);
    assert(handles == 0 && allocations == 0);

    open_file(0x44);
    assert(!game_state_writer.snapshot_valid);
    recover_saved_games_hack = TRUE;
    assert(game_state_read_from_file());
    expect_bytes(game_buffer, 0x32);
    recover_saved_games_hack = FALSE;
    game_state_dispose();
    assert(!xbox_game_state_globals.buffer_allocated && handles == 0 && allocations == 0);

    for (int failure = 0; failure < 4; failure++)
    {
        fail_allocation = failure == 0;
        fail_event = failure == 1 ? 1 : failure == 2 ? 2 : 0;
        fail_thread = failure == 3;
        open_file(0x55);
        assert(!game_state_writer.thread && allocations == 0 && handles == 1);
        assert(game_state_write_to_file());
        expect_bytes(file_bytes, 0x55);
        memset(game_buffer, 0, sizeof(game_buffer));
        assert(game_state_read_from_file());
        expect_bytes(game_buffer, 0x55);
        game_state_dispose();
        assert(handles == 0 && allocations == 0);
    }
    puts("Checkpoints: pending reverts, serialized saves, short/failed writes, close/reopen, shutdown and setup fallbacks passed.");
    return 0;
}
