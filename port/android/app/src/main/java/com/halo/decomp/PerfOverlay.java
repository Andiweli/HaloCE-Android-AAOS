package com.halo.decomp;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.RelativeLayout;
import android.widget.TextView;

/**
 * Optional frame-time counter of the NVIDIA Shield performance test, shown
 * only in diagnostic builds. The renderer publishes its text about once a
 * second (port/android/host/host_perf.c); the counter never takes focus or
 * touches, so controller and RetroTouch input reach the game unchanged.
 */
final class PerfOverlay {
    private static native String nativeText();

    /** false when libmain.so predates this overlay: the APK's native payload
     *  was not rebuilt with these sources (port/android/README.md) */
    static boolean nativeCurrent() {
        try {
            nativeText();
            return true;
        } catch (UnsatisfiedLinkError e) {
            return false;
        }
    }

    /** the renderer's latest counter text, also for the GFX capture's device.txt */
    static String text() {
        try {
            String text = nativeText();
            return text == null || text.isEmpty() ? "FPS: waiting for the first frames" : text;
        } catch (UnsatisfiedLinkError e) {
            return "FPS: libmain.so predates the frame-time counter";
        }
    }
    /** how a tester reaches the modes (HaloActivity: SELECT, or a gamepad's Back) */
    static final String HINT = "\nHold Back ◁ or SELECT: test settings";
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final TextView view;
    private boolean enabled, closed;
    private final Runnable refresh = new Runnable() {
        public void run() {
            if (!enabled || closed) return;
            view.setText(text() + HINT);
            handler.postDelayed(this, 500);
        }
    };

    PerfOverlay(Activity activity, ViewGroup parent) {
        view = new TextView(activity);
        view.setTextColor(Color.WHITE);
        view.setTextSize(11);
        view.setTypeface(Typeface.MONOSPACE);
        view.setBackgroundColor(0x99000000);
        float dp = activity.getResources().getDisplayMetrics().density;
        view.setPadding(Math.round(6 * dp), Math.round(2 * dp), Math.round(6 * dp), Math.round(2 * dp));
        view.setFocusable(false);
        view.setClickable(false);
        view.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        view.setVisibility(View.GONE);
        RelativeLayout.LayoutParams layout = new RelativeLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        // Bottom centre: free in Halo's HUD (motion tracker left, meters top).
        layout.addRule(RelativeLayout.ALIGN_PARENT_BOTTOM);
        layout.addRule(RelativeLayout.CENTER_HORIZONTAL);
        layout.bottomMargin = Math.round(4 * dp);
        parent.addView(view, layout);
    }

    void enable(boolean on) {
        if (closed || on == enabled) return;
        enabled = on;
        handler.removeCallbacks(refresh);
        view.setVisibility(on ? View.VISIBLE : View.GONE);
        if (on) handler.post(refresh);
    }

    void close() {
        closed = true;
        handler.removeCallbacksAndMessages(null);
    }
}
