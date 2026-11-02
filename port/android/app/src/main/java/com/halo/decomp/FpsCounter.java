package com.halo.decomp;

import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.Display;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;
import java.util.Locale;

/**
 * The in-game menu's FPS display, as CubeEvil4's (wish of the project owner, 02.11.2026): one line at the
 * bottom left, "30 FPS (Game) · 60 Hz · 2400×1080", counted over a second; with "60 FPS (experimental)"
 * also the pictures on the screen, the in-between ones included ("30 FPS (Game) · 60 FPS (Screen)").
 * The game counts (host_touch.c): the frames it advanced in (game_time_update), the pictures shown and
 * the size they are drawn at (Present). Hidden while the menu is open; counted anew afterwards.
 */
final class FpsCounter {
    /** The text for a second: the game's frames and the pictures shown in it. */
    static String line(String plain, String smooth, boolean sixty, long game, long shown) {
        return sixty ? String.format(Locale.ROOT, smooth, game, shown) : String.format(Locale.ROOT, plain, game);
    }
    /** " · 60 Hz", "" unknown. */
    static String hz(float rate) { return rate > 0 ? String.format(Locale.ROOT, " · %d Hz", Math.round(rate)) : ""; }
    /** " · 2400×1080", "" before the first picture. */
    static String size(int width, int height) {
        return width > 0 && height > 0 ? String.format(Locale.ROOT, " · %d×%d", width, height) : "";
    }

    private final HaloActivity activity;
    private final TextView view;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final int[] counters = new int[4];
    private boolean on, paused, sixty;
    private long since = -1, pictures, frames;
    private final Runnable tick = this::update;

    FpsCounter(HaloActivity activity, ViewGroup parent) {
        this.activity = activity;
        view = new TextView(activity);
        view.setTypeface(Typeface.MONOSPACE);
        view.setTextSize(11);
        view.setTextColor(Color.WHITE);
        view.setBackgroundColor(0x60000000);
        view.setPadding(8, 2, 8, 2);
        view.setTextDirection(View.TEXT_DIRECTION_LTR);
        view.setClickable(false);
        view.setFocusable(false);
        view.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        view.setVisibility(View.GONE);
        parent.addView(view, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT,
            FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM | Gravity.LEFT));
    }

    /** The menu's switch and the 60 FPS switch (whose pictures it counts as well). */
    void configure(boolean on, boolean sixty) {
        this.on = on;
        this.sixty = sixty;
        refresh();
    }
    /** The menu over the game: hidden, counted anew afterwards. */
    void pause(boolean paused) {
        this.paused = paused;
        refresh();
    }

    private void refresh() {
        boolean shown = on && !paused;
        main.removeCallbacks(tick);
        since = -1;
        view.setVisibility(shown ? View.VISIBLE : View.GONE);
        if (!shown) return;
        view.setText(activity.getString(R.string.menu_fps_none) + hz(rate()) + size(counters[2], counters[3]));
        view.bringToFront();
        main.post(tick);
    }

    private float rate() {
        Display display = activity.getWindowManager().getDefaultDisplay();
        return display != null ? display.getRefreshRate() : 0;
    }

    private void update() {
        if (!on || paused) return;
        long now = SystemClock.uptimeMillis();
        SettingsOverlay.nativeCounters(counters);
        long shownNow = counters[0] & 0xffffffffL, gameNow = counters[1] & 0xffffffffL;
        if (since < 0) {
            since = now;
            pictures = shownNow;
            frames = gameNow;
        } else if (now - since >= 1000) {
            double seconds = (now - since) / 1000.0;
            long game = Math.round((gameNow - frames) / seconds), shown = Math.round((shownNow - pictures) / seconds);
            view.setText(line(activity.getString(R.string.menu_fps), activity.getString(R.string.menu_fps_smooth), sixty,
                game, shown) + hz(rate()) + size(counters[2], counters[3]));
            since = now;
            pictures = shownNow;
            frames = gameNow;
        }
        main.postDelayed(tick, 250);
    }
}
