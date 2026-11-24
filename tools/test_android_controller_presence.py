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
    "android/os/Build": '''public class Build {
        public static class VERSION { public static int SDK_INT=35; }
    }''',
    "android/view/MotionEvent": '''public class MotionEvent {
        public static final int AXIS_X=0,AXIS_Y=1,AXIS_HAT_X=15,AXIS_HAT_Y=16;
    }''',
    "android/view/InputDevice": '''public class InputDevice {
        public static final int SOURCE_KEYBOARD=0x101,SOURCE_DPAD=0x201,SOURCE_GAMEPAD=0x401,
            SOURCE_TOUCHSCREEN=0x1002,SOURCE_MOUSE=0x2002,SOURCE_JOYSTICK=0x1000010;
        public static final int KEYBOARD_TYPE_NONE=0,KEYBOARD_TYPE_NON_ALPHABETIC=1,KEYBOARD_TYPE_ALPHABETIC=2;
        public int keyboardType=KEYBOARD_TYPE_NON_ALPHABETIC;
        public InputDevice typed(int type){keyboardType=type;return this;}
        public boolean external;
        public InputDevice plugged(){external=true;return this;}
        public boolean isExternal(){return external;}
        public int getKeyboardType(){return keyboardType;}
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
        check(line.startsWith("input devices: leave the touch controls") && line.contains("uinput-fpc (no stick or D-pad axes, ignored)")
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
        check(line.startsWith("input devices: hide the touch controls") && line.contains("Xbox Wireless Controller (controller)"),line);
        InputDevice.devices.remove(InputDevice.devices.size()-1);
        check(ControllerPresence.inputs(c)==0,"the controller gone: nothing hides touch");
        /* the screen's virtual keyboard and a handheld's built-in buttons (keys, no letters) are no keyboards */
        InputDevice.devices.add(new InputDevice("Virtual QWERTY",InputDevice.SOURCE_KEYBOARD,true).typed(InputDevice.KEYBOARD_TYPE_ALPHABETIC));
        InputDevice.devices.add(new InputDevice("gpio-keys",InputDevice.SOURCE_KEYBOARD,false));
        check(ControllerPresence.inputs(c)==0,"virtual and letterless keyboards keep touch");
        /* a Bluetooth keyboard with letters (and a few gamepad buttons in its HID description) */
        /* a built-in device that says keyboard with letters (a Galaxy A36, 1.1.1) or a Chromebook's own keyboard:
           listed, but it hides the touch controls only when used (HaloPort.deskUsed) */
        InputDevice.devices.add(new InputDevice("sec_builtin",InputDevice.SOURCE_KEYBOARD,false).typed(InputDevice.KEYBOARD_TYPE_ALPHABETIC));
        InputDevice.devices.add(new InputDevice("builtin-touchpad",InputDevice.SOURCE_MOUSE,false));
        check(ControllerPresence.inputs(c)==ControllerPresence.POINTER,"built-in keyboards and touchpads keep touch until used, the game has the touchpad");
        check(StartDiagnostics.lines.get(StartDiagnostics.lines.size()-1).startsWith("input devices: leave the touch controls"),"a touchpad alone leaves them");
        line=StartDiagnostics.lines.get(StartDiagnostics.lines.size()-1);
        check(line.contains("sec_builtin (built in: when used)") && line.contains("builtin-touchpad (built in: when used)"),line);
        InputDevice.devices.remove(InputDevice.devices.size()-1);
        InputDevice.devices.remove(InputDevice.devices.size()-1);
        /* before Android 10 nothing tells a connected device from a built-in one: when used */
        android.os.Build.VERSION.SDK_INT=28;
        InputDevice.devices.add(new InputDevice("BT Keyboard",InputDevice.SOURCE_KEYBOARD|InputDevice.SOURCE_GAMEPAD,false)
            .typed(InputDevice.KEYBOARD_TYPE_ALPHABETIC).plugged());
        check(ControllerPresence.inputs(c)==0,"Android 9: a keyboard hides touch only when used");
        android.os.Build.VERSION.SDK_INT=35;
        check(ControllerPresence.inputs(c)==ControllerPresence.KEYBOARD && !ControllerPresence.isControllerConnected(c),
            "a keyboard hides touch, and is no controller");
        line=StartDiagnostics.lines.get(StartDiagnostics.lines.size()-1);
        check(line.startsWith("input devices: hide the touch controls") && line.contains("keyboards: BT Keyboard") && line.contains("mice: none"),line);
        /* a mouse; a touch screen is none */
        InputDevice.devices.add(new InputDevice("Logitech Mouse",InputDevice.SOURCE_MOUSE,false).plugged());
        check(ControllerPresence.inputs(c)==(ControllerPresence.KEYBOARD|ControllerPresence.MOUSE|ControllerPresence.POINTER),"a mouse too");
        InputDevice.devices.remove(InputDevice.devices.size()-2);
        check(ControllerPresence.inputs(c)==(ControllerPresence.MOUSE|ControllerPresence.POINTER),"the mouse alone hides touch");
        line=StartDiagnostics.lines.get(StartDiagnostics.lines.size()-1);
        check(line.contains("keyboards: none") && line.contains("mice: Logitech Mouse"),line);
        /* a controller whose device also says keyboard with letters is still a controller (it has a stick) */
        InputDevice.devices.add(new InputDevice("Retroid Pocket Controller",InputDevice.SOURCE_KEYBOARD|InputDevice.SOURCE_GAMEPAD|
            InputDevice.SOURCE_JOYSTICK,false,MotionEvent.AXIS_X,MotionEvent.AXIS_Y).typed(InputDevice.KEYBOARD_TYPE_ALPHABETIC));
        check(ControllerPresence.inputs(c)==(ControllerPresence.CONTROLLER|ControllerPresence.MOUSE|ControllerPresence.POINTER),"a stick pad stays a controller");
        check(android.util.Log.lines.equals(StartDiagnostics.lines),"Logcat gets the same lines");
        System.out.println("Controller presence: fingerprint sensors, button-only, one-axis and virtual gamepad devices keep the touch controls; stick and hat D-pad controllers, connected keyboards with letters and mice hide them, built-in ones only when used; each change logged once.");
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
