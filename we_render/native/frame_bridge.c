/* MIT — WE Render contributors.
 * Experimental, per-process GLFW readback bridge. No desktop capture APIs.
 * Loaded ONLY into a user-selected native renderer via LD_PRELOAD.
 * Raw RGB frames are written to an inherited anonymous pipe, not to disk.
 * Does not inject into an already-running process or modify its files.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <limits.h>
#include <fcntl.h>
#include <stdatomic.h>
#include <time.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef struct GLFWwindow GLFWwindow;
typedef struct GLFWmonitor GLFWmonitor;
typedef unsigned int GLenum;
typedef unsigned int GLuint;
typedef int GLint;
typedef void (*GLFWglproc)(void);

static int enabled, data_fd = -1, wanted_w, wanted_h, fps, warmup, frames;
static pid_t owner;
static pthread_t render_thread;
static GLFWwindow *target;
static _Atomic uint64_t tick, emitted;
static unsigned char *pixels;
static int header_sent, prior_warning;

static void fail(const char *text) {
    dprintf(STDERR_FILENO, "[we-render bridge] %s\n", text);
    _exit(71);
}
static void *sym(const char *name) {
    void *p = dlsym(RTLD_NEXT, name);
    if (!p) fail(name);
    return p;
}
static int active(void) { return enabled && getpid() == owner; }
static long number(const char *key, long lo, long hi) {
    const char *value = getenv(key);
    char *end = NULL;
    if (!value || !*value) fail("Missing bridge configuration");
    errno = 0;
    long n = strtol(value, &end, 10);
    if (errno || *end || n < lo || n > hi) fail("Invalid bridge configuration");
    return n;
}
static int inherited_output_fd(void) {
    /*
     * LD_PRELOAD is inherited by CEF/helper exec children, while the frame pipe
     * is intentionally FD_CLOEXEC. Treat a missing/closed pipe as proof that
     * this process is a helper and leave the bridge completely passive.
     */
    const char *value = getenv("WE_RENDER_FD");
    char *end = NULL;
    if (!value || !*value) return -1;
    errno = 0;
    long n = strtol(value, &end, 10);
    if (errno || *end || n < 3 || n > INT_MAX) return -1;
    if (fcntl((int)n, F_GETFD) < 0) return -1;
    return (int)n;
}
__attribute__((constructor)) static void init(void) {
    const char *flag = getenv("WE_RENDER_ACTIVE");
    if (!flag || strcmp(flag, "1")) return;

    /* A CEF/other exec helper keeps the environment but not the CLOEXEC pipe. */
    int candidate_fd = inherited_output_fd();
    if (candidate_fd < 0) return;

    const char *previous = getenv("WE_RENDER_OWNER");
    if (previous && *previous) {
        char *end = NULL;
        errno = 0;
        long previous_pid = strtol(previous, &end, 10);
        if (!errno && end && !*end && previous_pid != (long)getpid()) return;
    }

    owner = getpid();
    char own[32]; snprintf(own, sizeof own, "%ld", (long)owner);
    setenv("WE_RENDER_OWNER", own, 1);
    data_fd = candidate_fd;

    /* From here on this is the intended renderer process: bad config is fatal. */
    wanted_w = (int)number("WE_RENDER_WIDTH", 2, 16384);
    wanted_h = (int)number("WE_RENDER_HEIGHT", 2, 16384);
    if ((uint64_t)wanted_w * wanted_h > 67108864) fail("Frame exceeds safety limit");
    fps = (int)number("WE_RENDER_FPS", 1, 240);
    warmup = (int)number("WE_RENDER_WARMUP", 0, 14400);
    frames = (int)number("WE_RENDER_FRAMES", 1, 864000);

    if (fcntl(data_fd, F_SETFD, FD_CLOEXEC) < 0) fail("Cannot protect output descriptor");
    signal(SIGPIPE, SIG_IGN);
    enabled = 1;
}
static void write_all(const void *ptr, size_t n) {
    const unsigned char *p = ptr;
    while (n) {
        ssize_t written = write(data_fd, p, n);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) fail("Frame pipe closed or could not be written");
        p += written; n -= (size_t)written;
    }
}
GLFWwindow *glfwCreateWindow(int w, int h, const char *title, GLFWmonitor *monitor, GLFWwindow *share) {
    GLFWwindow *(*real_create)(int,int,const char *,GLFWmonitor *,GLFWwindow *) = sym("glfwCreateWindow");
    if (active() && !target) {
        void (*hint)(int,int) = sym("glfwWindowHint");
        hint(0x00020004, 0); /* GLFW_VISIBLE = false */
        hint(0x0002000C, 0); /* GLFW_FOCUS_ON_SHOW = false */
        w = wanted_w; h = wanted_h;
        render_thread = pthread_self();
        target = real_create(w, h, title, NULL, share);
        if (!target) fail("Renderer could not create its hidden OpenGL window");
        return target;
    }
    return real_create(w,h,title,monitor,share);
}
void glfwShowWindow(GLFWwindow *window) {
    if (active() && window == target) return;
    void (*real_show)(GLFWwindow *) = sym("glfwShowWindow"); real_show(window);
}
void glfwFocusWindow(GLFWwindow *window) {
    if (active() && window == target) return;
    void (*real_focus)(GLFWwindow *) = sym("glfwFocusWindow"); real_focus(window);
}
double glfwGetTime(void) {
    if (active() && (!target || pthread_equal(pthread_self(), render_thread))) return (double)tick / fps;
    double (*real_time)(void) = sym("glfwGetTime"); return real_time();
}
void glfwSwapInterval(int interval) {
    void (*real_interval)(int) = sym("glfwSwapInterval");
    real_interval(active() ? 0 : interval);
}
int glfwWindowShouldClose(GLFWwindow *window) {
    if (active() && window == target && emitted >= (uint64_t)frames) return 1;
    int (*real_close)(GLFWwindow *) = sym("glfwWindowShouldClose"); return real_close(window);
}
int usleep(useconds_t microseconds) {
    /* Only the owned render thread's short frame limiter, not audio threads. */
    if (active() && target && pthread_equal(pthread_self(), render_thread) && microseconds <= 1000000) return 0;
    int (*real_sleep)(useconds_t) = sym("usleep"); return real_sleep(microseconds);
}
static void capture(GLFWwindow *window) {
    int w = 0, h = 0;
    void (*get_size)(GLFWwindow *, int *, int *) = sym("glfwGetFramebufferSize");
    GLFWglproc (*get_proc)(const char *) = sym("glfwGetProcAddress");
    get_size(window, &w, &h);
    if (w != wanted_w || h != wanted_h) fail("Hidden framebuffer size differs from requested size; refusing a scaled/cropped export");
    void (*get)(GLenum,GLint *) = (void *)get_proc("glGetIntegerv");
    void (*bind_fb)(GLenum,GLuint) = (void *)get_proc("glBindFramebuffer");
    void (*bind_buf)(GLenum,GLuint) = (void *)get_proc("glBindBuffer");
    void (*store)(GLenum,GLint) = (void *)get_proc("glPixelStorei");
    void (*read_buf)(GLenum) = (void *)get_proc("glReadBuffer");
    void (*read_pixels)(GLint,GLint,GLint,GLint,GLenum,GLenum,void *) = (void *)get_proc("glReadPixels");
    GLenum (*error)(void) = (void *)get_proc("glGetError");
    if (!get || !bind_fb || !bind_buf || !store || !read_buf || !read_pixels || !error) fail("Required OpenGL functions are missing");
    if (!pixels) {
        pixels = malloc((size_t)w * h * 3);
        if (!pixels) fail("Cannot allocate a single RGB frame");
    }
    /* GLEW/legacy engine startup may leave an unrelated GL error. Report it,
       then distinguish a real error produced by OUR readback below. */
    for (int i=0;i<16;i++) {
        GLenum prior=error(); if(!prior) break;
        if(!prior_warning++) dprintf(STDERR_FILENO,"[we-render bridge] Warning: engine left GL error 0x%x before readback; inspect scene fidelity\n",prior);
    }
    GLint fb, pbo, old_buffer;
    const GLenum keys[] = {0x0D05,0x0D02,0x0D03,0x0D04}; /* alignment,row length,skip rows,skip pixels */
    GLint old_pack[4];
    get(0x8CAA, &fb); /* READ_FRAMEBUFFER_BINDING */
    get(0x88ED, &pbo); /* PIXEL_PACK_BUFFER_BINDING */
    for (int i=0;i<4;i++) get(keys[i], &old_pack[i]);
    bind_fb(0x8CA8,0); /* READ_FRAMEBUFFER: this renderer's own back buffer */
    get(0x0C02, &old_buffer);
    bind_buf(0x88EB,0); /* PIXEL_PACK_BUFFER */
    store(keys[0],1); for (int i=1;i<4;i++) store(keys[i],0);
    read_buf(0x0405); /* GL_BACK */
    read_pixels(0,0,w,h,0x1907,0x1401,pixels); /* RGB, UNSIGNED_BYTE */
    GLenum e = error();
    read_buf((GLenum)old_buffer); bind_fb(0x8CA8,(GLuint)fb);
    bind_buf(0x88EB,(GLuint)pbo);
    for (int i=0;i<4;i++) store(keys[i],old_pack[i]);
    if (e) fail("OpenGL readback failed; this renderer/driver configuration is unsupported");
    if (!header_sent) {
        char header[128];
        int n = snprintf(header,sizeof header,"WERRGB1 %d %d %d\n",w,h,fps);
        write_all(header,(size_t)n); header_sent=1;
        dprintf(STDERR_FILENO,"[we-render bridge] Ready: %dx%d @ %d fps; hidden render-buffer readback\n",w,h,fps);
    }
    write_all(pixels,(size_t)w*h*3);
    emitted++;
}
void glfwSwapBuffers(GLFWwindow *window) {
    if (!active() || window != target) {
        void (*real_swap)(GLFWwindow *) = sym("glfwSwapBuffers"); real_swap(window); return;
    }
    /* The owned window remains hidden. Read before swapping; swapping itself
       preserves default-framebuffer semantics. FFmpeg corrects GL row order. */
    if (tick >= (uint64_t)warmup && emitted < (uint64_t)frames) capture(window);
    tick++;
    void (*real_swap)(GLFWwindow *) = sym("glfwSwapBuffers");
    real_swap(window);
}
__attribute__((destructor)) static void done(void) {
    if (active()) {
        dprintf(STDERR_FILENO,"[we-render bridge] Emitted %llu/%d frames\n",(unsigned long long)emitted,frames);
        if (data_fd >= 0) close(data_fd);
        free(pixels);
    }
}
