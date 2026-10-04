"""Exercise production Java -> JNI -> host buffer -> production look merger.

Android API stubs only supply lifecycle and sensor events. Camera math, Java
listener, native bridge and look merger are compiled from the project sources.
Requires a Linux C compiler, SDL3 headers and a JDK (JAVA_HOME).
"""
from pathlib import Path
import argparse
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--java-source", type=Path, default=root / "port/android/app/src/main/java")
parser.add_argument("--sdl-include", type=Path, default=root / "build/android/third_party/SDL3/include")
args = parser.parse_args()
jdk = Path(os.environ["JAVA_HOME"])
stubs = {
    "android/content/Context": '''public class Context {
        public static final String SENSOR_SERVICE="sensor";
    }''',
    "android/hardware/Sensor": '''public class Sensor {
        public static final int TYPE_GYROSCOPE=4,TYPE_GYROSCOPE_UNCALIBRATED=16;
        private final int type;
        public Sensor(int type){this.type=type;}
        public int getType(){return type;}
        public String getName(){return "fixture";}
        public String getVendor(){return "fixture";}
        public int getMinDelay(){return 10000;}
    }''',
    "android/hardware/SensorEvent": '''public class SensorEvent {
        public Sensor sensor;public float[] values;public long timestamp;public int accuracy;
        public SensorEvent(Sensor sensor,long timestamp,int accuracy,float[] values){
            this.sensor=sensor;this.timestamp=timestamp;this.accuracy=accuracy;this.values=values;
        }
    }''',
    "android/hardware/SensorEventListener": '''public interface SensorEventListener {
        void onSensorChanged(SensorEvent event);
        void onAccuracyChanged(Sensor sensor,int accuracy);
    }''',
    "android/hardware/SensorManager": '''public class SensorManager {
        public static final int SENSOR_STATUS_UNRELIABLE=0;
        public Sensor calibrated=new Sensor(4),uncalibrated=new Sensor(16),active;
        public boolean calibratedAccepted=true,uncalibratedAccepted=true;
        public Sensor getDefaultSensor(int type){return type==4?calibrated:uncalibrated;}
        public boolean registerListener(SensorEventListener listener,Sensor sensor,int rate,
                int latency,android.os.Handler handler){
            boolean ok=sensor.getType()==4?calibratedAccepted:uncalibratedAccepted;
            if(ok)active=sensor;return ok;
        }
        public void unregisterListener(SensorEventListener listener){active=null;}
    }''',
    "android/os/Looper": '''public class Looper {
        public static Looper getMainLooper(){return new Looper();}
    }''',
    "android/os/Handler": '''public class Handler {
        public Handler(Looper looper){}
        public void removeCallbacks(Runnable callback){}
        public boolean postDelayed(Runnable callback,long delay){return true;}
    }''',
    "android/os/SystemClock": '''public class SystemClock {
        public static long uptimeMillis(){return 10000;}
    }''',
    "android/os/LocaleList": '''public class LocaleList {
        public java.util.Locale get(int index){return java.util.Locale.GERMAN;}
    }''',
    "android/content/res/Configuration": '''public class Configuration {
        public android.os.LocaleList getLocales(){return new android.os.LocaleList();}
    }''',
    "android/content/res/Resources": '''public class Resources {
        public Configuration getConfiguration(){return new Configuration();}
    }''',
    "android/util/Log": '''public class Log {
        public static int i(String tag,String message){return 0;}
        public static int w(String tag,String message){return 0;}
    }''',
    "android/widget/Toast": '''public class Toast {
        public static final int LENGTH_LONG=1;public static int shown;
        public static Toast makeText(android.content.Context context,String text,int length){return new Toast();}
        public void show(){shown++;}
    }''',
    "android/view/View": '''public class View {
        public boolean hasWindowFocus(){return true;}
    }''',
    "android/view/Window": '''public class Window {
        public View getDecorView(){return new View();}
    }''',
    "android/view/Display": '''public class Display {
        public int getRotation(){return 0;}
    }''',
    "android/view/WindowManager": '''public class WindowManager {
        public Display getDefaultDisplay(){return new Display();}
    }''',
    "com/halo/decomp/HaloActivity": '''public class HaloActivity extends android.content.Context {
        public final android.hardware.SensorManager manager=new android.hardware.SensorManager();
        public Object getSystemService(String service){return manager;}
        public android.view.Window getWindow(){return new android.view.Window();}
        public android.view.WindowManager getWindowManager(){return new android.view.WindowManager();}
        public android.content.res.Resources getResources(){return new android.content.res.Resources();}
    }''',
}
fixture = r'''
package com.halo.decomp;
import android.hardware.*;
class MotionAimPipelineTest {
    private static native void mode(int mode);
    private static native float[] look();
    private static native long state();
    private static long time=1_000_000_000L;
    private static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    private static float magnitude(float[] look){return Math.abs(look[0])+Math.abs(look[1]);}
    private static MotionAim start(HaloActivity activity){
        MotionAim motion=new MotionAim(activity);motion.configure(true,100);motion.resume();mode(2);
        return motion;
    }
    private static void sample(MotionAim motion,Sensor sensor,int accuracy,long step,float... values){
        time+=step;motion.onAccuracyChanged(sensor,accuracy);
        motion.onSensorChanged(new SensorEvent(sensor,time,accuracy,values));
    }
    private static float run(MotionAim motion,Sensor sensor,int accuracy,long step,float... values){
        float total=0;
        for(int i=0;i<30;i++){sample(motion,sensor,accuracy,step,values);total+=magnitude(look());}
        return total;
    }
    public static void main(String[] args){
        System.load(args[0]);
        HaloActivity activity=new HaloActivity();MotionAim motion=start(activity);
        Sensor sensor=activity.manager.active;
        check(sensor!=null,"registered gyro");
        check(run(motion,sensor,0,10_000_000L,.4f,.6f,0)> .15f,
            "accuracy zero must still produce camera movement through JNI");
        check((state()&0xffffffffL)==0x27L && (state()>>>32)>0,"native flags and consumed counter");
        motion.overlay(true);check(activity.manager.active==null,"overlay unregisters sensor");
        check(run(motion,sensor,3,10_000_000L,.4f,.6f,0)==0,"overlay blocks queued samples");
        motion.overlay(false);sensor=activity.manager.active;
        check(run(motion,sensor,3,100_000_000L,.4f,.6f,0)>1,"10 Hz sensor moves camera");
        mode(1);check(run(motion,sensor,3,10_000_000L,.4f,.6f,0)==0,"menu blocks camera");
        mode(2);check(run(motion,sensor,3,10_000_000L,.4f,.6f,0)>.15f,"gameplay resumes without zoom");
        sample(motion,sensor,3,10_000_000L,.4f,.6f,0);
        motion.focus(false);check(magnitude(look())==0,"focus loss clears pending delta");
        check(activity.manager.active==null,"focus loss unregisters sensor");
        motion.focus(true);sensor=activity.manager.active;
        check(run(motion,sensor,3,10_000_000L,Float.NaN,.6f,0)==0,"invalid samples blocked");
        motion.suspend();check(activity.manager.active==null,"background unregisters sensor");
        motion.resume();sensor=activity.manager.active;
        check(run(motion,sensor,0,10_000_000L,.4f,.6f,0)>.15f,"resume accepts accuracy zero");
        motion.configure(false,100);
        check(run(motion,sensor,3,10_000_000L,.4f,.6f,0)==0,"disabled toggle blocks samples");

        HaloActivity fallback=new HaloActivity();fallback.manager.calibratedAccepted=false;
        MotionAim uncal=start(fallback);sensor=fallback.manager.active;
        check(sensor!=null && sensor.getType()==16,"uncalibrated registration fallback");
        check(run(uncal,sensor,0,10_000_000L,.1f,.2f,.3f,.1f,.2f,.3f)==0,"reported bias subtracted");
        check(run(uncal,sensor,0,10_000_000L,.5f,.8f,.3f,.1f,.2f,.3f)>.15f,"fallback camera movement");
        uncal.suspend();
        HaloActivity absent=new HaloActivity();absent.manager.calibrated=null;
        absent.manager.uncalibrated=null;MotionAim noSensor=start(absent);
        check(!noSensor.available() && magnitude(look())==0,"no sensor remains safe");
        HaloActivity failure=new HaloActivity();failure.manager.calibratedAccepted=false;
        failure.manager.uncalibratedAccepted=false;start(failure);
        check(android.widget.Toast.shown==1 && (state()&1)==0,"registration failure reported, native gyro disabled");
        System.out.println("Production gyro pipeline: accuracy zero, 10 Hz, JNI consumption, lifecycle, gameplay, invalid data, bias and fallback passed.");
    }
}
'''
merger = (root / "port/linux/src/xinput_sdl.c").read_text()
merger = merger[merger.index("int halo_linux_mouse_look("):]
merger = merger[:merger.index("/* whether the player")]
native = r'''
#include "HOST_TOUCH"
static Uint64 clock_ms=1000;
Uint64 SDL_GetTicks(void){return clock_ms;}
int host_bink_active(void){return 0;}
void host_android_path(int which,char *buffer,unsigned int size){
    (void)which;snprintf(buffer,size,"/tmp");
}
#define TRUE 1
#define FALSE 0
static pthread_mutex_t mouse_lock=PTHREAD_MUTEX_INITIALIZER;
static float mouse_pending_x,mouse_pending_y;
static unsigned long mouse_polls_unconsumed;
int config_boolean(const char *key){(void)key;return 0;}
float mouse_sensitivity(void){return 1;}
'''.replace("HOST_TOUCH", str(root / "port/android/host/host_touch.c"))
native += merger + r'''
JNIEXPORT void JNICALL Java_com_halo_decomp_MotionAimPipelineTest_mode(JNIEnv *env,jclass cls,jint mode){
    (void)env;(void)cls;host_touch_mode(mode==2?2|HALO_ANDROID_TOUCH_AIMING:mode);
}
JNIEXPORT jfloatArray JNICALL Java_com_halo_decomp_MotionAimPipelineTest_look(JNIEnv *env,jclass cls){
    (void)cls;float result[2];halo_linux_mouse_look(0,&result[0],&result[1]);
    jfloatArray array=(*env)->NewFloatArray(env,2);
    (*env)->SetFloatArrayRegion(env,array,0,2,result);return array;
}
JNIEXPORT jlong JNICALL Java_com_halo_decomp_MotionAimPipelineTest_state(JNIEnv *env,jclass cls){
    return Java_com_halo_decomp_MotionAim_nativeState(env,cls);
}
'''
with tempfile.TemporaryDirectory(prefix="halo-gyro-") as directory:
    work = Path(directory)
    sources = []
    for name, body in stubs.items():
        path = work / (name + ".java")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("package " + name.rsplit("/", 1)[0].replace("/", ".") + ";\n" + body)
        sources.append(str(path))
    test = work / "com/halo/decomp/MotionAimPipelineTest.java"
    test.write_text(fixture)
    sources += [str(test), str(args.java_source / "com/halo/decomp/MotionAim.java"),
                str(args.java_source / "com/halo/decomp/MotionAimMath.java")]
    subprocess.run([str(jdk / "bin/javac"), "-d", str(work), *sources], check=True)
    c = work / "pipeline.c"
    c.write_text(native)
    library = work / "libpipeline.so"
    subprocess.run(["cc", "-shared", "-fPIC", "-DHALO_ANDROID", "-std=gnu11",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                    "-I" + str(args.sdl_include), "-I" + str(jdk / "include"),
                    "-I" + str(jdk / "include/linux"), str(c), "-pthread", "-lm",
                    "-o", str(library)], check=True)
    subprocess.run([str(jdk / "bin/java"), "-ea", "-cp", str(work),
                    "com.halo.decomp.MotionAimPipelineTest", str(library)], check=True)
