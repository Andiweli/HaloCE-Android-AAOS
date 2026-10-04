"""Run the production look merger in isolation, with deterministic input sources."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / "port/linux/src/xinput_sdl.c").read_text()
start = source.index("int halo_linux_mouse_look(")
end = source.index("/* whether the player", start)
function = source[start:end]
setup = r"""
#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdlib.h>
#define TRUE 1
#define FALSE 0
static pthread_mutex_t mouse_lock = PTHREAD_MUTEX_INITIALIZER;
static float mouse_pending_x, mouse_pending_y;
static unsigned long mouse_polls_unconsumed;
static float tx,ty,gy,gp;
static int open_settings,inverted,touch_reads,motion_reads;
int config_boolean(const char *key) {(void)key;return inverted;}
float mouse_sensitivity(void) {return 2;}
int host_settings_active(void) {return open_settings;}
void host_touch_look(float *x,float *y) {*x=tx;*y=ty;tx=ty=0;touch_reads++;}
void host_motion_look(float *yaw,float *pitch) {*yaw=gy;*pitch=gp;gy=gp=0;motion_reads++;}
static void close_to(float actual,float expected) {assert(fabsf(actual-expected)<1e-6f);}
"""
checks = r"""
int main(int argc,char **argv) {
    assert(argc==2);inverted=atoi(argv[1]);float yaw,pitch;
    assert(!halo_linux_mouse_look(0,&yaw,&pitch));assert(!yaw&&!pitch);
    gy=.01f;gp=-.02f;
    assert(!halo_linux_mouse_look(1,&yaw,&pitch));assert(!yaw&&!pitch);
    assert(halo_linux_mouse_look(0,&yaw,&pitch));close_to(yaw,.01f);close_to(pitch,-.02f);
    assert(!halo_linux_mouse_look(0,&yaw,&pitch)); /* Consume only once. */
    mouse_pending_x=3;mouse_pending_y=4;tx=.001f;ty=-.002f;gy=.01f;gp=-.02f;
    assert(halo_linux_mouse_look(0,&yaw,&pitch));
    close_to(yaw,-.00936f);close_to(pitch,(inverted?.00528f:-.00528f)-.02f);
    open_settings=1;gy=.01f;gp=.02f;
    int reads=motion_reads;
    assert(!halo_linux_mouse_look(0,&yaw,&pitch));assert(!yaw&&!pitch && reads==motion_reads);
    return 0;
}
"""
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)
    (path/"test.c").write_text(setup+function+checks)
    subprocess.run(["cc","-DHALO_ANDROID","-std=gnu11","-Wall","-Wextra","-Werror",str(path/"test.c"),"-pthread","-lm","-o",str(path/"test")],check=True)
    for invert in ("0","1"):
        subprocess.run([str(path/"test"),invert],check=True)
print("Production look merger: gyro alone, additive mouse/touch, independent sensitivity/inversion, player selection and overlay blocking passed.")
