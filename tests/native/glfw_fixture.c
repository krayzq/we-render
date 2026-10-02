/* MIT. Minimal TEST FIXTURE, NOT GLFW or Wallpaper Engine.
 * Supplies a GLFW-shaped ABI over a real hidden X11/GLX OpenGL context so the
 * bridge's actual readback, timing and pipe can be exercised without wallpaper
 * assets. Passing this test does not establish upstream engine compatibility.
 */
#define _GNU_SOURCE
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <GL/glxtokens.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
typedef void *GLXContext;
extern XVisualInfo *glXChooseVisual(Display *, int, int *);
extern GLXContext glXCreateContext(Display *, XVisualInfo *, GLXContext, int);
extern int glXMakeCurrent(Display *, unsigned long, GLXContext);
extern void glXSwapBuffers(Display *, unsigned long);
extern void *glXGetProcAddressARB(const unsigned char *);
typedef struct GLFWwindow { Display *d; Window w; int width,height; } GLFWwindow;
static int mapped;
void glfwWindowHint(int hint,int value) { (void)hint;(void)value; }
GLFWwindow *glfwCreateWindow(int width,int height,const char *title,void *monitor,GLFWwindow *share) {
    (void)title;(void)monitor;(void)share;
    GLFWwindow *win=calloc(1,sizeof *win);win->d=XOpenDisplay(NULL);
    if (!win->d) return NULL;
    int attrs[]={GLX_RGBA,GLX_DOUBLEBUFFER,GLX_RED_SIZE,8,GLX_GREEN_SIZE,8,GLX_BLUE_SIZE,8,None};
    XVisualInfo *vi=glXChooseVisual(win->d,DefaultScreen(win->d),attrs);if(!vi)return NULL;
    XSetWindowAttributes swa={0};swa.colormap=XCreateColormap(win->d,RootWindow(win->d,vi->screen),vi->visual,AllocNone);
    win->w=XCreateWindow(win->d,RootWindow(win->d,vi->screen),0,0,width,height,0,vi->depth,InputOutput,vi->visual,CWColormap,&swa);
    GLXContext context=glXCreateContext(win->d,vi,NULL,True);
    if(!context || !glXMakeCurrent(win->d,win->w,context))return NULL;
    win->width=width;win->height=height;XFree(vi);return win;
}
void glfwShowWindow(GLFWwindow *w) { mapped++;XMapWindow(w->d,w->w); }
void glfwFocusWindow(GLFWwindow *w) { (void)w; }
void glfwSwapInterval(int n) { (void)n; }
double glfwGetTime(void) { struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9; }
int glfwWindowShouldClose(GLFWwindow *w) { (void)w;return 0; }
void glfwSwapBuffers(GLFWwindow *w) {glXSwapBuffers(w->d,w->w);}
void glfwGetFramebufferSize(GLFWwindow *w,int *width,int *height) {
    *width=w->width+(getenv("WE_TEST_MISMATCH")?2:0);*height=w->height;
}
void *glfwGetProcAddress(const char *name) { return glXGetProcAddressARB((const unsigned char *)name); }
int fixture_mapped(void) { return mapped; }
