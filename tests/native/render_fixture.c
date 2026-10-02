/* MIT. Draws a synthetic two-color animation; not a WE scene renderer. */
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
typedef struct GLFWwindow GLFWwindow;
extern GLFWwindow *glfwCreateWindow(int,int,const char *,void *,GLFWwindow *);
extern void glfwGetFramebufferSize(GLFWwindow *,int *,int *);
extern void *glfwGetProcAddress(const char *);
extern void glfwShowWindow(GLFWwindow *);
extern int glfwWindowShouldClose(GLFWwindow *);
extern double glfwGetTime(void);
extern void glfwSwapBuffers(GLFWwindow *);
extern int fixture_mapped(void);
int main(void) {
    GLFWwindow *w=glfwCreateWindow(64,64,"WE Export synthetic test",NULL,NULL);
    if(!w){fputs("No GLX context\n",stderr);return 12;}
    glfwShowWindow(w);int width,height;glfwGetFramebufferSize(w,&width,&height);
    void (*viewport)(int,int,int,int)=glfwGetProcAddress("glViewport");
    void (*scissor)(int,int,int,int)=glfwGetProcAddress("glScissor");
    void (*enable)(unsigned int)=glfwGetProcAddress("glEnable");
    void (*color)(float,float,float,float)=glfwGetProcAddress("glClearColor");
    void (*clear)(unsigned int)=glfwGetProcAddress("glClear");
    viewport(0,0,width,height);enable(0x0C11);
    int n=0;double start=glfwGetTime();
    while(!glfwWindowShouldClose(w) && n<20000) {
        float g=(float)glfwGetTime()/10;
        scissor(0,0,width,height/2);color(0,g,1,1);clear(0x4000);
        scissor(0,height/2,width,height-height/2);color(1,g,0,1);clear(0x4000);
        glfwSwapBuffers(w);usleep(1000);n++;
    }
    fprintf(stderr,"fixture: mapped=%d ticks=%d clock-start=%.6f clock-end=%.6f\n",fixture_mapped(),n,start,glfwGetTime());
    return fixture_mapped()==0 && n<20000 ? 0 : 13;
}
