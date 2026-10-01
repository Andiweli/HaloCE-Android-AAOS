package com.halo.decomp;

import android.app.Activity;
import android.graphics.Insets;
import android.os.Build;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowManager;

/** Keep SDL and its touch overlay together inside the OEM-provided safe area. */
final class AutomotiveWindow {
    private AutomotiveWindow() {}

    @SuppressWarnings("deprecation")
    static void apply(Activity activity) {
        Window window = activity.getWindow();
        window.clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN
            | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
            | WindowManager.LayoutParams.FLAG_TRANSLUCENT_STATUS
            | WindowManager.LayoutParams.FLAG_TRANSLUCENT_NAVIGATION);
        WindowManager.LayoutParams attributes = window.getAttributes();
        attributes.layoutInDisplayCutoutMode = Build.VERSION.SDK_INT >= 30
            ? WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
            : WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_NEVER;
        window.setAttributes(attributes);
        View decor = window.getDecorView();
        decor.setSystemUiVisibility(View.SYSTEM_UI_FLAG_VISIBLE);
        if (Build.VERSION.SDK_INT >= 30) {
            // Own insets exactly once, including enforced edge-to-edge on API 35.
            window.setDecorFitsSystemWindows(false);
            if (window.getInsetsController() != null)
                window.getInsetsController().show(WindowInsets.Type.systemBars());
            View content = activity.findViewById(android.R.id.content);
            if (content != null) {
                content.setOnApplyWindowInsetsListener((view, insets) -> {
                    Insets safe = insets.getInsets(WindowInsets.Type.systemBars()
                        | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime());
                    if (view.getPaddingLeft() != safe.left || view.getPaddingTop() != safe.top
                        || view.getPaddingRight() != safe.right || view.getPaddingBottom() != safe.bottom)
                        view.setPadding(safe.left, safe.top, safe.right, safe.bottom);
                    return WindowInsets.CONSUMED;
                });
                content.requestApplyInsets();
            }
        }
        // On API 29, normal non-fullscreen decor fitting handles bars/cutouts.
    }
}
