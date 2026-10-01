package com.halo.decomp;

import android.content.Context;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.content.res.Configuration;
import android.view.Display;
import android.view.WindowManager;

import org.libsdl.app.SDLActivity;

/**
 * The game: SDL3's activity, running libmain.so (port/android/host), which
 * loads the game image from the APK's assets.
 */
public class HaloActivity extends SDLActivity {
    /** lets system link's broadcasts in over Wi-Fi while the game runs */
    private WifiManager.MulticastLock multicastLock;

    private HaloPort haloPort;
    @Override
    protected String[] getLibraries() {
        return new String[] { "SDL3", "main" };
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        StartDiagnostics.prepare(this);
        super.onCreate(savedInstanceState);
        StartDiagnostics.connect(this);
        haloPort = new HaloPort(this, mLayout);
        restoreFullscreen();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (!Fullscreen.isAutomotive(this)) preferHighestRefreshRate();
        acquireMulticastLock();
        // a new version looked for while the game starts
        if (!Fullscreen.isAutomotive(this)) Updater.start(this);
    }

    private void restoreFullscreen() {
        // SDL queues a windowed-style command during onCreate. Queue our
        // fullscreen command after it, then apply the modern insets policy.
        setWindowStyle(!Fullscreen.isAutomotive(this));
        getWindow().getDecorView().post(() -> Fullscreen.apply(this));
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (Fullscreen.isAutomotive(this)) resumeNativeThread();
        if (haloPort != null) haloPort.resume();
        restoreFullscreen();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) restoreFullscreen();
        else if (haloPort != null) haloPort.focusLost();
    }

    @Override
    protected void onPause() {
        if (haloPort != null) haloPort.suspend();
        // SDL normally waits for onStop on modern Android. AAOS can obscure
        // a parked game with only onPause, so stop native video/audio now.
        if (Fullscreen.isAutomotive(this)) pauseNativeThread();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (multicastLock != null && multicastLock.isHeld()) multicastLock.release();
        multicastLock = null;
        if (haloPort != null) haloPort.suspend();
        super.onDestroy();
    }

    @Override
    protected boolean sendCommand(int command, Object data) {
        if (command == COMMAND_CHANGE_WINDOW_STYLE && Fullscreen.isAutomotive(this)) {
            // Native SDL fullscreen requests must not undo the automotive policy.
            runOnUiThread(() -> Fullscreen.apply(this));
            return true;
        }
        return super.sendCommand(command, data);
    }

    @Override
    public void setOrientationBis(int width, int height, boolean resizable, String hint) {
        if (!Fullscreen.isAutomotive(this))
            super.setOrientationBis(width, height, resizable, hint);
    }

    @Override
    public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        if (haloPort != null && event.getAction() == android.view.KeyEvent.ACTION_DOWN &&
                (event.isFromSource(android.view.InputDevice.SOURCE_GAMEPAD) ||
                 event.isFromSource(android.view.InputDevice.SOURCE_JOYSTICK))) {
            haloPort.controllerInput();
        }
        return super.dispatchKeyEvent(event);
    }

    @Override
    public boolean dispatchGenericMotionEvent(android.view.MotionEvent event) {
        if (haloPort != null && event.isFromSource(android.view.InputDevice.SOURCE_JOYSTICK)) {
            int[] axes = {android.view.MotionEvent.AXIS_X, android.view.MotionEvent.AXIS_Y,
                android.view.MotionEvent.AXIS_Z, android.view.MotionEvent.AXIS_RZ,
                android.view.MotionEvent.AXIS_HAT_X, android.view.MotionEvent.AXIS_HAT_Y,
                android.view.MotionEvent.AXIS_LTRIGGER, android.view.MotionEvent.AXIS_RTRIGGER};
            for (int axis : axes) {
                if (Math.abs(event.getAxisValue(axis)) > 0.2f) { haloPort.controllerInput(); break; }
            }
        }
        return super.dispatchGenericMotionEvent(event);
    }

    @Override
    public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
        restoreFullscreen();
    }

    /**
     * Many phones drop the Wi-Fi's broadcast and multicast datagrams to
     * save power unless an app holds this: without it they would not see
     * system link games on the local network, nor be seen hosting one.
     */
    private void acquireMulticastLock() {
        try {
            WifiManager wifi = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wifi == null)
                return;
            multicastLock = wifi.createMulticastLock("halo-system-link");
            multicastLock.setReferenceCounted(false);
            multicastLock.acquire();
        } catch (RuntimeException e) {
            // (no Wi-Fi, or not allowed: the local network may miss games)
            multicastLock = null;
        }
    }

    /**
     * The game draws a frame at every display refresh, between its 30 Hz
     * ticks (port/linux/game/render_interpolation.c); Android otherwise
     * often keeps an app at 60 Hz on a faster display.
     */
    private void preferHighestRefreshRate() {
        Display display = getWindowManager().getDefaultDisplay();
        Display.Mode current = display.getMode();
        Display.Mode best = current;

        for (Display.Mode mode : display.getSupportedModes()) {
            if (mode.getPhysicalWidth() == current.getPhysicalWidth() &&
                mode.getPhysicalHeight() == current.getPhysicalHeight() &&
                mode.getRefreshRate() > best.getRefreshRate()) {
                best = mode;
            }
        }
        WindowManager.LayoutParams attributes = getWindow().getAttributes();
        attributes.preferredDisplayModeId = best.getModeId();
        getWindow().setAttributes(attributes);
    }
}
