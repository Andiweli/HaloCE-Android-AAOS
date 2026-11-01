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
 */
final class ControllerPresence {
    private static String reported = "";

    private ControllerPresence() {
    }

    static boolean isControllerConnected(Context context) {
        boolean connected = false;
        StringBuilder devices = new StringBuilder();

        for (int id : InputDevice.getDeviceIds()) {
            InputDevice device = InputDevice.getDevice(id);

            if (device == null || !claimsController(device.getSources()))
                continue;
            boolean controller = isController(device);
            connected |= controller;
            devices.append(devices.length() == 0 ? "" : "; ").append(device.getName())
                .append(controller ? " (controller)" : device.isVirtual() ? " (virtual, ignored)" :
                    " (no stick or D-pad axes, ignored)");
        }
        // each change once in Logcat and the diagnostic file
        String report = devices.toString();
        if (!report.equals(reported)) {
            reported = report;
            String line = "touch controls: " + (connected ? "hidden" : "shown") + "; gamepad devices: " +
                (report.isEmpty() ? "none" : report);
            android.util.Log.i("halo", line);
            StartDiagnostics.append(context, line);
        }
        return connected;
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
