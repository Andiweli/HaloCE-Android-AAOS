"""Run the actual touch adapter and SELECT hold logic with a deterministic clock.

Uses the bundled RetroTouch control/layout classes. Android widgets, controller
presence, sensor-free activity shell and JNI sinks are fixtures. Requires a JDK.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
java_root = root / "port/android/app/src/main/java/com/halo/decomp"
activity = (java_root / "HaloActivity.java").read_text()
port = (java_root / "HaloPort.java").read_text()
jdk = Path(os.environ["JAVA_HOME"])

def block(source, marker):
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        if source[end] == "{": depth += 1
        elif source[end] == "}": depth -= 1
        end += 1
    return source[start:end]

fields = activity[activity.index("    private final android.os.Handler settingsHandler"):
                  activity.index("    void releaseGameKeys()")]
methods = "\n".join(block(activity, marker) for marker in (
    "    private void cancelSelect()", "    private void beginSelect(",
    "    private void endSelect(", "    void touchSelect(", "    void cancelTouchSelect()"))
dispatch = block(activity, "        if (key == android.view.KeyEvent.KEYCODE_BUTTON_SELECT")
shell = '''package com.halo.decomp;
public class HaloActivity extends android.content.Context {
    final android.view.Window window=new android.view.Window();
    final SettingsOverlay settings=new SettingsOverlay(this);
    HaloPort port;boolean movie;
    android.view.Window getWindow(){return window;}
    boolean nativeMovieSkip(){return movie;}
    void cancelAll(){cancelSelect();}
''' + fields + methods + '''
    boolean physical(android.view.KeyEvent event){
        int key=event.getKeyCode();boolean down=event.getAction()==0;
''' + dispatch + '''
        return false;
    }
}
class SettingsOverlay {
    final HaloActivity activity;boolean open;int opens;
    SettingsOverlay(HaloActivity activity){this.activity=activity;}
    boolean isOpen(){return open;}
    void show(){if(open)return;open=true;opens++;activity.port.overlay(true);}
    void close(){open=false;activity.port.overlay(false);}
}
'''
replacements = {
    "static native void nativeAction(int action, boolean down);":
        'static void nativeAction(int action,boolean down){actions.add(action+":"+down);}',
    "static native void nativeMove(float x, float y);": "static void nativeMove(float x,float y){}",
    "static native void nativeLook(float x, float y);": "static void nativeLook(float x,float y){}",
    "static native void nativeReset();": "static void nativeReset(){}",
    "static native int nativeMode();": "static int nativeMode(){return engineMode;}",
    "static native void nativeVolumes(int master, int effects, int music);":
        "static void nativeVolumes(int master,int effects,int music){}",
}
for old, new in replacements.items():
    assert port.count(old) == 1
    port = port.replace(old, new)
port = port.replace("final class HaloPort {", """final class HaloPort {
    static int engineMode=2;
    static final java.util.List<String> actions=new java.util.ArrayList<>();""")

stubs = {
    "org/json/JSONException": '''public class JSONException extends Exception {
        public JSONException(String message){super(message);}
    }''',
    "org/json/JSONObject": '''public class JSONObject {}''',
    "org/json/JSONArray": '''public class JSONArray {}''',
    "android/content/SharedPreferences": '''public interface SharedPreferences {
        int getInt(String key,int fallback);
    }''',
    "android/content/Context": '''public class Context {
        public SharedPreferences getSharedPreferences(String name,int mode){return (key,value)->value;}
    }''',
    "android/os/Looper": '''public class Looper {
        public static Looper getMainLooper(){return new Looper();}
    }''',
    "android/os/Handler": '''public class Handler {
        private static long now;
        private static final java.util.List<Task> tasks=new java.util.ArrayList<>();
        static class Task {Handler handler;Runnable callback;long at;
            Task(Handler h,Runnable r,long at){handler=h;callback=r;this.at=at;}}
        public Handler(Looper looper){}
        public boolean post(Runnable callback){return postDelayed(callback,0);}
        public boolean postDelayed(Runnable callback,long delay){tasks.add(new Task(this,callback,now+delay));return true;}
        public void removeCallbacks(Runnable callback){tasks.removeIf(t->t.handler==this && t.callback==callback);}
        public static void advance(long duration){
            long end=now+duration;
            while(true){
                Task next=null;
                for(Task t:tasks)if(t.at<=end && (next==null || t.at<next.at))next=t;
                if(next==null)break;
                tasks.remove(next);now=next.at;next.callback.run();
            }
            now=end;
        }
    }''',
    "android/view/View": '''public class View {
        public static final int GONE=8,VISIBLE=0;
        public boolean focused=true;public int visibility;
        public interface OnTouchListener {boolean onTouch(View view,MotionEvent event);}
        protected OnTouchListener touchListener;
        public void setOnTouchListener(OnTouchListener listener){touchListener=listener;}
        public void setVisibility(int visibility){this.visibility=visibility;}
        public boolean hasWindowFocus(){return focused;}
        public boolean dispatchTouchEvent(MotionEvent event){return touchListener.onTouch(this,event);}
    }''',
    "android/view/ViewGroup": '''public class ViewGroup extends View {
        public static class LayoutParams {public LayoutParams(int width,int height){}}
        public void addView(View view,LayoutParams params){}
    }''',
    "android/view/Window": '''public class Window {
        public final View decor=new View();public View getDecorView(){return decor;}
    }''',
    "android/view/MotionEvent": '''public class MotionEvent {
        public static final int ACTION_CANCEL=3;
        private final int action;public MotionEvent(int action){this.action=action;}
        public int getActionMasked(){return action;}
    }''',
    "android/view/InputDevice": '''public class InputDevice {
        public static boolean present=true;
        public static InputDevice getDevice(int id){return present && id==1?new InputDevice():null;}
    }''',
    "android/view/KeyEvent": '''public class KeyEvent {
        public static final int ACTION_DOWN=0,KEYCODE_BUTTON_SELECT=109;
        private final int action;private final boolean canceled;private final int repeat;
        public KeyEvent(int action,boolean canceled,int repeat){this.action=action;this.canceled=canceled;this.repeat=repeat;}
        public int getKeyCode(){return KEYCODE_BUTTON_SELECT;}public int getAction(){return action;}
        public int getRepeatCount(){return repeat;}public int getDeviceId(){return 1;}
        public boolean isCanceled(){return canceled;}
    }''',
    "com/ast/retrotouch/RetroTouchControllers": '''public class RetroTouchControllers {
        public static boolean connected;
        public static boolean isControllerConnected(){return connected;}
    }''',
    "com/ast/retrotouch/RetroTouchView": '''public class RetroTouchView extends android.view.View {
        public static RetroTouchView last;
        public final java.util.Map<String,String> actions=new java.util.LinkedHashMap<>();
        public RetroTouchLayout gameplay,navigation;private RetroTouchListener listener;
        private RetroTouchMode mode=RetroTouchMode.OFF;private boolean editing,selectPressed;
        public RetroTouchView(android.content.Context context){last=this;}
        public void registerAction(String id,String label){actions.put(id,label);}
        public void setGameplayLayout(RetroTouchLayout layout){gameplay=layout;}
        public void setNavigationLayout(RetroTouchLayout layout){navigation=layout;}
        public void setLookWhileHoldingAction(String id,boolean enabled){}
        public void setAutoHideOnController(boolean enabled){}
        public void setListener(RetroTouchListener listener){this.listener=listener;}
        public void setMode(RetroTouchMode mode){if(this.mode!=mode)releaseAllInputs();this.mode=mode;}
        public RetroTouchMode getMode(){return mode;}
        public boolean isEditing(){return editing;}
        public void setEditing(boolean editing){
            releaseAllInputs();this.editing=editing;listener.onEditorStateChanged(editing);
        }
        public void press(String id,boolean down){
            if(id.equals("select"))selectPressed=down;listener.onAction(id,down);
        }
        public void releaseAllInputs(){if(selectPressed){selectPressed=false;listener.onAction("select",false);}}
        public boolean onTouchEvent(android.view.MotionEvent event){
            if(event.getActionMasked()==3)releaseAllInputs();return true;
        }
    }''',
}
checks = r'''
package com.halo.decomp;
import android.os.Handler;
import android.view.*;
import com.ast.retrotouch.*;
class TouchSelectTest {
    static void check(boolean ok,String message){if(!ok)throw new AssertionError(message);}
    static void press(RetroTouchView view,boolean down){view.press("select",down);}
    static boolean containsSelect(RetroTouchLayout layout){
        return layout.getControls().stream().anyMatch(c->"select".equals(c.getActionId()));
    }
    static KeyEvent key(boolean down,boolean canceled,int repeat){return new KeyEvent(down?0:1,canceled,repeat);}
    public static void main(String[] args){
        HaloActivity a=new HaloActivity();HaloPort p=new HaloPort(a,new ViewGroup());a.port=p;
        RetroTouchView v=RetroTouchView.last;
        check(v.actions.containsKey("select"),"editor SELECT registration");
        check(containsSelect(v.gameplay) && containsSelect(v.navigation),"both default layouts have SELECT");
        check(v.gameplay.getGameId().equals("halo_ce_gameplay_v1") &&
            v.navigation.getGameId().equals("halo_ce_navigation_v1"),"saved layout identities preserved");
        press(v,true);Handler.advance(600);check(a.settings.opens==0,"inactive adapter blocks SELECT");
        p.resume();Handler.advance(0);HaloPort.actions.clear();
        press(v,true);Handler.advance(499);check(a.settings.opens==0,"499 ms cannot open overlay");
        Handler.advance(1);check(a.settings.opens==1 && a.settings.open,"500 ms opens without controller device");
        check(v.visibility==View.GONE,"overlay hides touch controls");
        check(HaloPort.actions.isEmpty(),"overlay release cannot inject Back or native SELECT bit");
        press(v,false);Handler.advance(600);check(a.settings.opens==1,"long press opens once");
        a.settings.close();Handler.advance(100);

        press(v,true);Handler.advance(100);press(v,false);Handler.advance(600);
        check(a.settings.opens==1 && HaloPort.actions.isEmpty(),"short touch tap neither opens nor navigates");
        press(v,true);Handler.advance(100);v.dispatchTouchEvent(new MotionEvent(MotionEvent.ACTION_CANCEL));
        Handler.advance(600);check(a.settings.opens==1,"canceled touch removes timer");
        press(v,true);p.focusLost();Handler.advance(600);check(a.settings.opens==1,"focus loss removes timer");
        a.window.decor.focused=false;press(v,true);Handler.advance(600);
        check(a.settings.opens==1,"unfocused window cannot start timer");a.window.decor.focused=true;
        press(v,true);p.suspend();Handler.advance(600);check(a.settings.opens==1,"suspend removes timer");
        p.resume();Handler.advance(0);
        press(v,true);v.setEditing(true);Handler.advance(600);check(a.settings.opens==1,"editor release removes timer");
        press(v,true);Handler.advance(600);check(a.settings.opens==1,"editing cannot open settings");
        v.setEditing(false);HaloPort.actions.clear();
        press(v,true);RetroTouchControllers.connected=true;Handler.advance(600);
        check(a.settings.opens==1 && v.visibility==View.GONE,"controller connection cancels touch hold");
        press(v,true);Handler.advance(600);check(a.settings.opens==1,"hidden touch control remains blocked");
        RetroTouchControllers.connected=false;Handler.advance(100);
        press(v,true);HaloPort.engineMode=1;Handler.advance(600);
        check(a.settings.opens==1 && v.getMode()==RetroTouchMode.NAVIGATION,"mode switch cancels pending hold");
        press(v,true);Handler.advance(500);check(a.settings.opens==2,"navigation layout also opens overlay");
        a.settings.close();Handler.advance(100);HaloPort.actions.clear();

        v.press("nav_right",true);v.press("nav_right",false);
        check(HaloPort.actions.equals(java.util.Arrays.asList("15:true","15:false")),"existing native action indices preserved");
        HaloPort.actions.clear();a.physical(key(true,false,0));Handler.advance(100);a.physical(key(false,false,0));
        check(HaloPort.actions.equals(java.util.Arrays.asList("9:true","9:false")),"physical short SELECT retains Back");
        HaloPort.actions.clear();a.physical(key(true,false,0));a.physical(key(true,false,1));
        Handler.advance(500);check(a.settings.opens==3,"physical long SELECT still opens once");
        a.physical(key(false,false,0));check(HaloPort.actions.isEmpty(),"physical long hold does not inject Back");
        a.settings.close();Handler.advance(100);
        a.physical(key(true,false,0));InputDevice.present=false;Handler.advance(500);
        check(a.settings.opens==3,"removed physical device cannot open overlay");a.physical(key(false,true,0));
        InputDevice.present=true;
        a.physical(key(true,false,0));a.cancelAll();Handler.advance(600);
        check(a.settings.opens==3,"activity lifecycle cancellation removes physical timer");
        press(v,true);a.physical(key(false,false,0));Handler.advance(500);
        check(a.settings.opens==4,"other input source cannot release touch hold");
        a.settings.close();Handler.advance(100);
        check(HaloPort.actions.isEmpty(),"no unintended gameplay actions after cancellation");
        p.suspend();
        System.out.println("Production SELECT adapter: both layouts/editor, 500 ms, reentrant release, cancel, focus, lifecycle, editor, controller, mode and physical SELECT passed.");
    }
}
'''
with tempfile.TemporaryDirectory(prefix="halo-select-") as directory:
    work = Path(directory)
    jar = work / "retrotouch.jar"
    with zipfile.ZipFile(root / "port/android/app/libs/retrotouch.aar") as archive:
        jar.write_bytes(archive.read("classes.jar"))
    sources = []
    for name, body in stubs.items():
        file = work / (name + ".java")
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("package " + name.rsplit("/", 1)[0].replace("/", ".") + ";\n" + body)
        sources.append(str(file))
    for name, body in (("HaloActivity", shell), ("HaloPort", port), ("TouchSelectTest", checks)):
        file = work / "com/halo/decomp" / (name + ".java")
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(body)
        sources.append(str(file))
    subprocess.run([str(jdk / "bin/javac"), "-cp", str(jar), "-d", str(work), *sources], check=True)
    subprocess.run([str(jdk / "bin/java"), "-ea", "-cp", str(work) + os.pathsep + str(jar),
                    "com.halo.decomp.TouchSelectTest"], check=True)
