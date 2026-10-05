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

    private static native void nativeMoviePause(boolean paused);
    private static native boolean nativeMovieSkip();
    private boolean movieTouch;
    private int movieKey = -1;
    private HaloPort haloPort;
    private MotionAim motionAim;
    private SettingsOverlay settings;
    private GraphicsDiagnostics graphicsDiagnostics;
    private final android.os.Handler settingsHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    private boolean selectHeld, selectOpened, selectTouch;
    private int selectDevice;
    private final java.util.Map<Integer,android.view.KeyEvent> gameKeys = new java.util.HashMap<>();
    private final java.util.Set<Integer> overlayKeys = new java.util.HashSet<>();
    private final Runnable openSettings = () -> {
        if (selectHeld && settings != null && getWindow().getDecorView().hasWindowFocus()) {
            if (selectTouch || android.view.InputDevice.getDevice(selectDevice) != null) {
                // Showing the overlay releases RetroTouch's pressed buttons.
                selectOpened=true;
                settings.show();
                if (!settings.isOpen()) selectOpened=false;
            }
        }
    };
    void releaseGameKeys() {
        for (android.view.KeyEvent down : gameKeys.values())
            super.dispatchKeyEvent(android.view.KeyEvent.changeAction(down,android.view.KeyEvent.ACTION_UP));
        gameKeys.clear();
    }
    void settingsVisibility(boolean visible) {
        if (haloPort != null) haloPort.overlay(visible);
        if (motionAim != null) motionAim.overlay(visible);
        if (!visible) restoreFullscreen();
    }
    boolean motionAvailable() { return motionAim != null && motionAim.available(); }
    void motionSettings(boolean enabled, int sensitivity, boolean invertPitch) {
        if (motionAim != null) motionAim.configure(enabled, sensitivity, invertPitch);
    }
    private void cancelSelect() {
        settingsHandler.removeCallbacks(openSettings);selectHeld=false;selectOpened=false;selectTouch=false;
    }
    private void beginSelect(boolean touch, int device) {
        if (settings == null || settings.isOpen() || selectHeld ||
                !getWindow().getDecorView().hasWindowFocus()) return;
        selectHeld=true;selectOpened=false;selectTouch=touch;selectDevice=device;
        settingsHandler.postDelayed(openSettings,500);
    }
    private void endSelect(boolean touch, boolean canceled) {
        if (!selectHeld || selectTouch != touch) return;
        boolean shortPress=!selectOpened && !canceled;
        cancelSelect();
        // Physical SELECT retains its short Back action. The touch button is
        // an overlay shortcut; cancel/release events must not navigate the game.
        if (shortPress && !touch && !nativeMovieSkip()) {
            HaloPort.nativeAction(9,true);HaloPort.nativeAction(9,false);
        }
    }
    void touchSelect(boolean down) {
        if (down) beginSelect(true,-1); else endSelect(true,false);
    }
    void cancelTouchSelect() {
        if (selectHeld && selectTouch) cancelSelect();
    }

    @Override
    protected String[] getLibraries() {
        return new String[] { "SDL3", "main" };
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        if (BuildConfig.HALO_DIAGNOSTICS_ENABLED) StartDiagnostics.prepare(this);
        super.onCreate(savedInstanceState);
        if (BuildConfig.HALO_DIAGNOSTICS_ENABLED) StartDiagnostics.connect(this);
        haloPort = new HaloPort(this, mLayout);
        motionAim = new MotionAim(this);
        settings = new SettingsOverlay(this, mLayout);
        if (BuildConfig.HALO_DIAGNOSTICS_ENABLED)
            graphicsDiagnostics = new GraphicsDiagnostics(this, mLayout);
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
        nativeMoviePause(false);
        if (settings != null) settings.resume();
        if (Fullscreen.isAutomotive(this)) resumeNativeThread();
        if (haloPort != null) haloPort.resume();
        if (motionAim != null) motionAim.resume();
        restoreFullscreen();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (motionAim != null) motionAim.focus(hasFocus);
        if (hasFocus) restoreFullscreen();
        else {
            cancelSelect();
            if (settings != null) settings.close(false);
            if (haloPort != null) haloPort.focusLost();
            releaseGameKeys();
        }
    }

    @Override
    protected void onPause() {
        cancelSelect();
        if (motionAim != null) motionAim.suspend();
        if (settings != null) settings.suspend();
        nativeMoviePause(true);
        if (haloPort != null) haloPort.suspend();
        // SDL normally waits for onStop on modern Android. AAOS can obscure
        // a parked game with only onPause, so stop native video/audio now.
        if (Fullscreen.isAutomotive(this)) pauseNativeThread();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        cancelSelect();
        if (motionAim != null) motionAim.suspend();
        if (graphicsDiagnostics != null) graphicsDiagnostics.close();
        if (settings != null) settings.suspend();
        if (multicastLock != null && multicastLock.isHeld()) multicastLock.release();
        multicastLock = null;
        if (haloPort != null) haloPort.suspend();
        super.onDestroy();
    }

    @Override
    protected boolean sendCommand(int command, Object data) {
        if (command == COMMAND_CHANGE_WINDOW_STYLE) {
            // SDL also sends windowed requests while creating its startup window.
            // Keep the app policy for EVERY request, including delayed native ones.
            // Posting after SDL's handler keeps its legacy flags from winning over
            // our cutout and modern system-bar policy.
            if (Fullscreen.isAutomotive(this)) {
                runOnUiThread(() -> Fullscreen.apply(this));
                return true;
            }
            boolean sent = super.sendCommand(command, Integer.valueOf(1));
            getWindow().getDecorView().post(() -> Fullscreen.apply(this));
            return sent;
        }
        return super.sendCommand(command, data);
    }

    @Override
    public void setOrientationBis(int width, int height, boolean resizable, String hint) {
        if (!Fullscreen.isAutomotive(this))
            super.setOrientationBis(width, height, resizable, hint);
    }

    @Override
    public void onBackPressed() {
        if (settings != null && settings.isOpen()) { settings.close(false); return; }
        super.onBackPressed();
    }

    @Override
    public boolean dispatchTouchEvent(android.view.MotionEvent event) {
        if (settings != null && settings.isOpen()) return super.dispatchTouchEvent(event);
        if (event.getActionMasked() == android.view.MotionEvent.ACTION_DOWN)
            movieTouch = nativeMovieSkip();
        if (movieTouch) {
            if (event.getActionMasked() == android.view.MotionEvent.ACTION_UP ||
                event.getActionMasked() == android.view.MotionEvent.ACTION_CANCEL) movieTouch = false;
            return true;
        }
        return super.dispatchTouchEvent(event);
    }

    @Override
    public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        int key = event.getKeyCode();
        boolean down = event.getAction() == android.view.KeyEvent.ACTION_DOWN;
        if (overlayKeys.contains(key)) {
            if (!down) overlayKeys.remove(key);
            if (settings != null && settings.isOpen()) settings.key(event);
            return true;
        }
        if (key == android.view.KeyEvent.KEYCODE_BUTTON_SELECT && settings != null) {
            if (down && event.getRepeatCount() == 0 && !settings.isOpen()) {
                beginSelect(false,event.getDeviceId());
            } else if (!down) {
                endSelect(false,event.isCanceled());
            }
            return true;
        }
        if (settings != null && settings.isOpen()) {
            if (settings.key(event)) { if (down) overlayKeys.add(key); return true; }
        }

        if (key == movieKey) {
            if (event.getAction() == android.view.KeyEvent.ACTION_UP) movieKey = -1;
            return true;
        }
        if (event.getAction() == android.view.KeyEvent.ACTION_DOWN &&
            (key == android.view.KeyEvent.KEYCODE_BACK || key == android.view.KeyEvent.KEYCODE_ESCAPE ||
             key == android.view.KeyEvent.KEYCODE_ENTER || key == android.view.KeyEvent.KEYCODE_SPACE ||
             android.view.KeyEvent.isGamepadButton(key)) && nativeMovieSkip()) {
            movieKey = key; return true;
        }
        if (haloPort != null && event.getAction() == android.view.KeyEvent.ACTION_DOWN &&
                (event.isFromSource(android.view.InputDevice.SOURCE_GAMEPAD) ||
                 event.isFromSource(android.view.InputDevice.SOURCE_JOYSTICK))) {
            haloPort.controllerInput();
        }
        if (down) gameKeys.put(key,new android.view.KeyEvent(event)); else gameKeys.remove(key);
        return super.dispatchKeyEvent(event);
    }

    @Override
    public boolean dispatchGenericMotionEvent(android.view.MotionEvent event) {
        if (settings != null && settings.isOpen()) {
            settings.motion(event);
            // Update SDL's physical axes even while the guest input is blocked.
            super.dispatchGenericMotionEvent(event);
            return true;
        }
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
        cancelSelect();
        if (settings != null) settings.close(false);
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
