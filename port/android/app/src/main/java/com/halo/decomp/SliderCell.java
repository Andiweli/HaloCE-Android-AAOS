package com.halo.decomp;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;
import java.util.function.IntConsumer;
import java.util.function.IntFunction;

/**
 * A slider as a cell, as CubeEvil4-Android's 1.1.0 menu has it (wish of the project owner, 22.11.2026): as high and as
 * wide as the other cells of the grid (64 dp), ‹ and › on the sides beyond thin lines (a step each), in the middle the
 * name small on top, the value big, the bar under them (still dragged with a finger). The cell takes the focus as a
 * button (the bar does not); the D-pad moves on between the cells, L1 / R1 (Q / E, Page up / Page down) step
 * (ArrowSelector.keys, SettingsOverlay.key). Off (setEnabled), the arrows grey and the steps stop.
 */
final class SliderCell extends LinearLayout {
    final SeekBar bar;
    final TextView name, value;
    private IntFunction<String> format = String::valueOf;
    private IntConsumer moved;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private boolean arrowDown;

    SliderCell(Context context, String label, Drawable background) {
        super(context);
        setOrientation(VERTICAL);
        setGravity(Gravity.CENTER);
        setWillNotDraw(false);
        setBackground(background);
        setFocusable(true);
        setClickable(true);
        int arrows = arrowWidth();
        // exactly as high as the other cells: the texts without the font's extra padding, the bar 22 dp
        setPadding(arrows, dp(4), arrows, dp(2));
        setMinimumHeight(dp(64));
        name = new TextView(context);
        name.setText(label);
        name.setTextSize(12.5f);
        name.setGravity(Gravity.CENTER);
        name.setTextColor(SettingsOverlay.MUTED);
        name.setMaxLines(1);
        name.setEllipsize(android.text.TextUtils.TruncateAt.END);
        name.setIncludeFontPadding(false);
        value = new TextView(context);
        value.setTextSize(16);
        value.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        value.setTextColor(SettingsOverlay.INK);
        value.setGravity(Gravity.CENTER);
        value.setMaxLines(1);
        value.setIncludeFontPadding(false);
        bar = new SeekBar(context);
        bar.setFocusable(false);
        bar.setContentDescription(label);
        bar.setProgressTintList(ColorStateList.valueOf(SettingsOverlay.ACCENT));
        bar.setThumbTintList(ColorStateList.valueOf(SettingsOverlay.ACCENT));
        bar.setProgressBackgroundTintList(ColorStateList.valueOf(SettingsOverlay.BORDER));
        addView(name, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        addView(value, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        addView(bar, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(22)));
        bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar b, int progress, boolean fromUser) {
                value.setText(format.apply(progress));
                if (fromUser && moved != null) moved.accept(progress);
            }
            @Override public void onStartTrackingTouch(SeekBar b) {}
            @Override public void onStopTrackingTouch(SeekBar b) {}
        });
    }

    /** The steps (0 .. max), the one shown, its text, and what a move by the player does. */
    void setUp(int max, int progress, IntFunction<String> format, IntConsumer moved) {
        this.format = format;
        this.moved = moved;
        bar.setMax(max);
        bar.setProgress(progress);
        value.setText(format.apply(bar.getProgress()));
    }

    /** One step back (-1) or forward (+1); false at the end or while the cell is off. */
    boolean step(int direction) {
        if (!bar.isEnabled()) return false;
        int next = Math.max(0, Math.min(bar.getMax(), bar.getProgress() + direction));
        if (next == bar.getProgress()) return false;
        bar.setProgress(next);
        if (moved != null) moved.accept(next);
        invalidate();
        return true;
    }

    /** The bar's state follows the cell's; off, the cell is half transparent. */
    @Override public void setEnabled(boolean enabled) {
        super.setEnabled(enabled);
        bar.setEnabled(enabled);
        setAlpha(enabled ? 1f : .5f);
        invalidate();
    }

    /** A finger on ‹ or › is the cell's (a step when it lifts), elsewhere the bar's. */
    @Override public boolean onInterceptTouchEvent(MotionEvent e) {
        if (e.getActionMasked() == MotionEvent.ACTION_DOWN) arrowDown = inArrows(e.getX());
        return arrowDown;
    }

    @Override public boolean onTouchEvent(MotionEvent e) {
        if (e.getActionMasked() == MotionEvent.ACTION_DOWN) arrowDown = inArrows(e.getX());
        if (!arrowDown) return super.onTouchEvent(e);
        if (e.getActionMasked() == MotionEvent.ACTION_UP) {
            step(e.getX() < arrowWidth() ? -1 : 1);
            arrowDown = false;
        }
        return true;
    }

    private boolean inArrows(float x) { return x < arrowWidth() || x > getWidth() - arrowWidth(); }

    @Override protected void dispatchDraw(Canvas canvas) {
        super.dispatchDraw(canvas);
        int w = getWidth(), h = getHeight(), a = arrowWidth();
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(SettingsOverlay.BORDER);
        float line = Math.max(1f, dp(1));
        canvas.drawRect(a - line, dp(6), a, h - dp(6), paint);
        canvas.drawRect(w - a, dp(6), w - a + line, h - dp(6), paint);
        paint.setColor(bar.isEnabled() ? SettingsOverlay.INK : SettingsOverlay.DISABLED);
        paint.setTextSize(dp(26));
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTypeface(Typeface.DEFAULT_BOLD);
        Paint.FontMetrics fm = paint.getFontMetrics();
        float base = h / 2f - (fm.ascent + fm.descent) / 2f;
        canvas.drawText("‹", a / 2f, base, paint);
        canvas.drawText("›", w - a / 2f, base, paint);
    }

    private int arrowWidth() { return dp(44); }

    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
}
