#!/usr/bin/env python3
"""Run the actual ControllerPresence (HaloPort's touch controls) on made-up devices.

A Xiaomi fingerprint sensor (uinput-fpc: keys and a gamepad source, no
axes) and other button-only or virtual gamepad devices leave the touch
controls shown; a controller with a stick, or with a D-pad on hat axes,
hides them. Each change is logged once. Android classes are fixtures.
Requires a JDK.
"""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
presence = (root / "port/android/app/src/main/java/com/halo/decomp/ControllerPresence.java").read_text()
jdk = Path(os.environ["JAVA_HOME"]) / "bin" if os.environ.get("JAVA_HOME") else None

stubs = {
    "android/content/Context": "public class Context {}",
    "android/util/Log": '''public class Log {
        public static final java.util.List<String> lines=new java.util.ArrayList<>();
        public static int i(String tag,String text){lines.add(text);return 0;}
    }''',
    "android/view/MotionEvent": '''public class MotionEvent {
        public static final int AXIS_X=0,AXIS_Y=1,AXIS_HAT_X=15,AXIS_HAT_Y=16;
    }''',
    "android/view/InputDevice": '''public class InputDevice {
        public static final int SOURCE_KEYBOARD=0x101,SOURCE_DPAD=0x201,SOURCE_GAMEPAD=0x401,
            SOURCE_TOUCHSCREEN=0x1002,SOURCE_JOYSTICK=0x1000010;
        public static final java.util.List<InputDevice> devices=new java.util.ArrayList<>();
        final String name;final int sources;final boolean virtual;final java.util.Set<Integer> axes=new java.util.HashSet<>();
        public InputDevice(String name,int sources,boolean virtual,int... axes){
            this.name=name;this.sources=sources;this.virtual=virtual;for(int a:axes)this.axes.add(a);}
        public static int[] getDeviceIds(){int[] ids=new int[devices.size()];for(int i=0;i<ids.length;i++)ids[i]=i;return ids;}
        public static InputDevice getDevice(int id){return id<devices.size()?devices.get(id):null;}
        public int getSources(){return sources;}
        public boolean isVirtual(){return virtual;}
        public String getName(){return name;}
        public Object getMotionRange(int axis,int source){
            return source==SOURCE_JOYSTICK && (sources&SOURCE_JOYSTICK)==SOURCE_JOYSTICK && axes.contains(axis)?this:null;}
    }''',
    "com/halo/decomp/StartDiagnostics": '''class StartDiagnostics {
        static final java.util.List<String> lines=new java.util.ArrayList<>();
        static void append(android.content.Context context,String text){lines.add(text);}
    }''',
}
checks = r'''package com.halo.decomp;
import android.view.InputDevice;
import android.view.MotionEvent;
public class PresenceTest {
    static void check(boolean condition,String what){if(!condition)throw new AssertionError(what);}
    public static void main(String[] args){
        android.content.Context c=new android.content.Context();
        InputDevice.devices.add(new InputDevice("Virtual",InputDevice.SOURCE_KEYBOARD,true));
        InputDevice.devices.add(new InputDevice("touchpanel",InputDevice.SOURCE_TOUCHSCREEN,false));
        check(!ControllerPresence.isControllerConnected(c),"no gamepad device: touch shown");
        /* the Poco M4 Pro's fingerprint sensor and a phone's key device */
        InputDevice.devices.add(new InputDevice("uinput-fpc",InputDevice.SOURCE_KEYBOARD|InputDevice.SOURCE_GAMEPAD,false));
        InputDevice.devices.add(new InputDevice("uinput-goodix",InputDevice.SOURCE_KEYBOARD|InputDevice.SOURCE_DPAD|InputDevice.SOURCE_GAMEPAD,false));
        InputDevice.devices.add(new InputDevice("virtual-pad",InputDevice.SOURCE_GAMEPAD|InputDevice.SOURCE_JOYSTICK,true,
            MotionEvent.AXIS_X,MotionEvent.AXIS_Y));
        InputDevice.devices.add(new InputDevice("half-stick",InputDevice.SOURCE_JOYSTICK,false,MotionEvent.AXIS_X));
        check(!ControllerPresence.isControllerConnected(c),"fingerprint sensors, a virtual pad and one axis keep touch");
        String line=StartDiagnostics.lines.get(StartDiagnostics.lines.size()-1);
        check(line.startsWith("touch controls: shown") && line.contains("uinput-fpc (no stick or D-pad axes, ignored)")
            && line.contains("virtual-pad (virtual, ignored)"),line);
        int logged=StartDiagnostics.lines.size();
        check(!ControllerPresence.isControllerConnected(c) && StartDiagnostics.lines.size()==logged,"logged once a change");
        /* a D-pad-only pad with its D-pad on hat axes */
        InputDevice.devices.add(new InputDevice("8BitDo Zero 2",InputDevice.SOURCE_GAMEPAD|InputDevice.SOURCE_JOYSTICK,false,
            MotionEvent.AXIS_HAT_X,MotionEvent.AXIS_HAT_Y));
        check(ControllerPresence.isControllerConnected(c),"a hat D-pad pad hides touch");
        InputDevice.devices.remove(InputDevice.devices.size()-1);
        check(!ControllerPresence.isControllerConnected(c),"and touch returns when it leaves");
        /* a controller with sticks */
        InputDevice.devices.add(new InputDevice("Xbox Wireless Controller",InputDevice.SOURCE_GAMEPAD|InputDevice.SOURCE_JOYSTICK,false,
            MotionEvent.AXIS_X,MotionEvent.AXIS_Y,MotionEvent.AXIS_HAT_X,MotionEvent.AXIS_HAT_Y));
        check(ControllerPresence.isControllerConnected(c),"a stick controller hides touch");
        line=StartDiagnostics.lines.get(StartDiagnostics.lines.size()-1);
        check(line.startsWith("touch controls: hidden") && line.contains("Xbox Wireless Controller (controller)"),line);
        check(android.util.Log.lines.equals(StartDiagnostics.lines),"Logcat gets the same lines");
        System.out.println("Controller presence: fingerprint sensors, button-only, one-axis and virtual gamepad devices keep the touch controls; stick and hat D-pad controllers hide them; each change logged once.");
    }
}
'''
with tempfile.TemporaryDirectory(prefix="halo-presence-") as directory:
    work = Path(directory)
    sources = []
    for name, body in list(stubs.items()) + [("com/halo/decomp/ControllerPresence", None),
                                             ("com/halo/decomp/PresenceTest", None)]:
        file = work / (name + ".java")
        file.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith("ControllerPresence"):
            file.write_text(presence)
        elif name.endswith("PresenceTest"):
            file.write_text(checks)
        else:
            file.write_text("package " + name.rsplit("/", 1)[0].replace("/", ".") + ";\n" + body)
        sources.append(str(file))
    subprocess.run([str(jdk / "javac") if jdk else "javac", "-d", str(work), *sources], check=True)
    subprocess.run([str(jdk / "java") if jdk else "java", "-ea", "-cp", str(work), "com.halo.decomp.PresenceTest"],
                   check=True)
