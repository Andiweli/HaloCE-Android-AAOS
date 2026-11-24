package com.halo.decomp;

import android.content.Context;
import android.view.InputDevice;

/**
 * Whether a game controller is connected, which hides the touch controls
 * (HaloPort). RetroTouchControllers counts every device with a gamepad or
 * joystick source, but phones list more than controllers that way: the
 * fingerprint sensors of Xiaomi, Redmi and Poco phones (uinput-fpc,
 * uinput-goodix) and some key devices say they are gamepads, and the touch
 * controls never showed. A controller here is a physical device that also
 * has a stick or a D-pad on axes (a hat), which those have not.
 *
 * A keyboard or a mouse hides them as well (wish of the project owner, 22.11.2026): a physical keyboard
 * with letters (KEYBOARD_TYPE_ALPHABETIC) and no stick, not the screen's virtual keyboard nor a
 * handheld's built-in buttons (keys without letters), and a physical mouse (SOURCE_MOUSE), not a
 * touch screen. Both play through SDL as on Linux (port/linux/src/xinput_sdl.c); the mouse is told to
 * the game (nativeMouse), which captures it while it plays (sdl_platform.c).
 */
final class ControllerPresence {
    private static String reported = "";

    private ControllerPresence() {
    }

    /** What inputs() finds: a controller, a keyboard, a mouse connected (these hide the touch controls), and
     *  POINTER: any physical mouse, built in too (a Chromebook's touchpad), which the game takes as in 1.1.1
     *  (HaloPort.nativeMouse); 1.1.2 told the game only of a connected one or one used since the last finger,
     *  and a Chromebook's mouse showed only its pointer, in the menus and in the game (24.11.2026). */
    static final int CONTROLLER = 1, KEYBOARD = 2, MOUSE = 4, POINTER = 8;
    /** The inputs that hide the touch controls (not POINTER). */
    static final int HIDING = CONTROLLER | KEYBOARD | MOUSE;

    /** Whether a controller is connected (inputs). */
    static boolean isControllerConnected(Context context) {
        return (inputs(context) & CONTROLLER) != 0;
    }

    /** The controllers, keyboards and mice connected (CONTROLLER | KEYBOARD | MOUSE); the touch
     *  controls hide with any of them. */
    static int inputs(Context context) {
        int found = 0;
        StringBuilder devices = new StringBuilder(), keyboards = new StringBuilder(), mice = new StringBuilder();

        for (int id : InputDevice.getDeviceIds()) {
            InputDevice device = InputDevice.getDevice(id);

            if (device == null)
                continue;
            boolean connected = connected(device);
            if (isKeyboard(device)) {
                if (connected) found |= KEYBOARD;
                keyboards.append(keyboards.length() == 0 ? "" : "; ").append(device.getName())
                    .append(connected ? "" : " (built in: when used)");
            }
            if (isMouse(device)) {
                found |= POINTER;
                if (connected) found |= MOUSE;
                mice.append(mice.length() == 0 ? "" : "; ").append(device.getName())
                    .append(connected ? "" : " (built in: when used)");
            }
            if (!claimsController(device.getSources()) || isKeyboard(device))
                continue;
            boolean controller = isController(device);
            if (controller)
                found |= CONTROLLER;
            devices.append(devices.length() == 0 ? "" : "; ").append(device.getName())
                .append(controller ? " (controller)" : device.isVirtual() ? " (virtual, ignored)" :
                    " (no stick or D-pad axes, ignored)");
        }
        // each change once in Logcat and the diagnostic file
        String report = devices + "|" + keyboards + "|" + mice;
        if (!report.equals(reported)) {
            reported = report;
            String line = "input devices: " + ((found & HIDING) != 0 ? "hide the touch controls" : "leave the touch controls") + "; gamepad devices: " +
                (devices.length() == 0 ? "none" : devices) + "; keyboards: " +
                (keyboards.length() == 0 ? "none" : keyboards) + "; mice: " + (mice.length() == 0 ? "none" : mice);
            android.util.Log.i("halo", line);
            StartDiagnostics.append(context, line);
        }
        return found;
    }

    /** A keyboard or a mouse that hides the touch controls as soon as it is there: a connected one
     *  (Bluetooth, USB; Android 10 and later). Built-in ones hide them only when used (HaloPort.deskUsed):
     *  some phones list a built-in device as a physical keyboard with letters (a Galaxy A36, 1.1.1: no
     *  touch controls, no keyboard), and a Chromebook's own keyboard and touchpad are built in too. */
    static boolean connected(InputDevice device) {
        return android.os.Build.VERSION.SDK_INT >= 29 && device.isExternal();
    }

    /** A physical keyboard with letters and no stick (CubeEvil4-Android's keyboardDevice): some
     *  Bluetooth keyboards also declare a few gamepad buttons; a handheld's buttons have no letters. */
    static boolean isKeyboard(InputDevice device) {
        if (device.isVirtual())
            return false;
        int sources = device.getSources();
        if ((sources & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK)
            return false;
        return (sources & InputDevice.SOURCE_KEYBOARD) == InputDevice.SOURCE_KEYBOARD &&
            device.getKeyboardType() == InputDevice.KEYBOARD_TYPE_ALPHABETIC;
    }

    /** A physical mouse (or a trackpad that moves a pointer), not a touch screen or a stylus. */
    static boolean isMouse(InputDevice device) {
        return !device.isVirtual() && (device.getSources() & InputDevice.SOURCE_MOUSE) == InputDevice.SOURCE_MOUSE;
    }

    static boolean claimsController(int sources) {
        return (sources & InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD ||
            (sources & InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK;
    }

    static boolean isController(InputDevice device) {
        if (device.isVirtual() || !claimsController(device.getSources()))
            return false;
        return axes(device, android.view.MotionEvent.AXIS_X, android.view.MotionEvent.AXIS_Y) ||
            axes(device, android.view.MotionEvent.AXIS_HAT_X, android.view.MotionEvent.AXIS_HAT_Y);
    }

    private static boolean axes(InputDevice device, int x, int y) {
        return device.getMotionRange(x, InputDevice.SOURCE_JOYSTICK) != null &&
            device.getMotionRange(y, InputDevice.SOURCE_JOYSTICK) != null;
    }
}
