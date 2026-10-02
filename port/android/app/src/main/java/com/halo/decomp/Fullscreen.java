package com.halo.decomp;

import android.app.Activity;
import android.graphics.Color;
import android.os.Build;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;

/** Shared immersive window policy for the importer and SDL game. */
final class Fullscreen {
    private Fullscreen() {}
    private static java.lang.ref.WeakReference<Activity> loggedActivity =
        new java.lang.ref.WeakReference<>(null);

    static boolean isAutomotive(Activity activity) {
        // Window policy follows the running device, not the APK flavor.
        // An AAOS test APK on a handheld must still hide Android system bars.
        return activity.getPackageManager().hasSystemFeature(
            android.content.pm.PackageManager.FEATURE_AUTOMOTIVE);
    }

    @SuppressWarnings("deprecation")
    static void apply(Activity activity) {
        boolean automotive = isAutomotive(activity);
        if (loggedActivity.get() != activity) {
            loggedActivity = new java.lang.ref.WeakReference<>(activity);
            android.util.Log.i("HaloWindow", "flavor=" + (BuildConfig.IS_AAOS ? "aaos" : "mobile")
                + " automotiveDevice=" + automotive
                + " policy=" + (automotive ? "car-safe-area" : "immersive-fullscreen"));
        }
        if (automotive) {
            AutomotiveWindow.apply(activity);
            return;
        }
        apply(activity.getWindow());
    }

    @SuppressWarnings("deprecation")
    static void apply(Window window) {
        window.clearFlags(WindowManager.LayoutParams.FLAG_FORCE_NOT_FULLSCREEN);
        window.addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        window.setStatusBarColor(Color.TRANSPARENT);
        window.setNavigationBarColor(Color.TRANSPARENT);
        window.setNavigationBarDividerColor(Color.TRANSPARENT);
        if (Build.VERSION.SDK_INT >= 29) {
            window.setStatusBarContrastEnforced(false);
            window.setNavigationBarContrastEnforced(false);
        }
        WindowManager.LayoutParams attributes = window.getAttributes();
        attributes.layoutInDisplayCutoutMode = Build.VERSION.SDK_INT >= 30
            ? WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
            : WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        window.setAttributes(attributes);

        View decor = window.getDecorView();
        decor.setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        if (Build.VERSION.SDK_INT >= 30) {
            window.setDecorFitsSystemWindows(false);
            WindowInsetsController controller = window.getInsetsController();
            if (controller != null) {
                controller.setSystemBarsBehavior(
                    WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
                controller.hide(WindowInsets.Type.systemBars());
            }
        }
    }
}
