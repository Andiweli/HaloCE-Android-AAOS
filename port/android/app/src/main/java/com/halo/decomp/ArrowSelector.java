package com.halo.decomp;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.RelativeSizeSpan;
import android.text.style.StyleSpan;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.widget.Button;

/**
 * A choice of more than two values in one cell, as CubeEvil4-Android's 1.1.0 menu has it (wish of the project owner,
 * 22.11.2026: its new menu in Halo): ‹ on the left and › on the right, each beyond a thin line, the choice's name small
 * on top, its value big below and a dot for each step under it, the current one light. A tap on ‹ goes back, on › or
 * the middle forward, after the last step back to the first.
 *
 * <p>With a controller or a keyboard: the D-pad moves the focus between the cells as between buttons; A (Enter) steps
 * forward as a tap on the middle; L1 / R1 (Q / E, Page up / Page down) step back and forward (keys(),
 * SettingsOverlay.key). Lit (Halo's blue, as an "On" switch) while its value is not the off one (`offIndex`).
 *
 * <p>Steps that are not allowed (the GPU's limits) are passed over. A Button, so it sits in the menu's grids and takes
 * their look and focus.
 */
final class ArrowSelector extends Button {
    interface Listener { void changed(int index); }

    private static final int DOT = 0xff3d5a73;
    private final String name;
    private final String[] values;
    private final boolean[] allowed;
    private int index, offIndex = -1;
    private Listener listener;
    private float touchX = -1f;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

    /** `name` may be null or empty: then only the value and the dots. */
    ArrowSelector(Context context, String name, String[] values, int index) {
        super(context);
        this.name = name == null ? "" : name;
        this.values = values.clone();
        this.allowed = new boolean[values.length];
        java.util.Arrays.fill(allowed, true);
        this.index = Math.max(0, Math.min(values.length - 1, index));
    }

    /** After the menu's style (its padding and height): the arrows' room on both sides, the text in the middle. */
    void finishLook() {
        int arrows = arrowWidth();
        setPadding(arrows, dp(5), arrows, dp(13));
        setMinHeight(dp(64));
        setMinimumHeight(dp(64));
        setAllCaps(false);
        setOnClickListener(v -> { });  // (the step is performClick's)
        refresh();
    }

    void setListener(Listener listener) { this.listener = listener; }

    /** The value that counts as off (not lit); -1: none. */
    void setOffIndex(int off) {
        offIndex = off;
        refresh();
    }

    int index() { return index; }

    /** Which steps may be chosen; the current one stays as it is. */
    void setAllowed(int step, boolean ok) {
        if (step >= 0 && step < allowed.length) allowed[step] = ok;
        invalidate();
    }

    /** One step back (-1) or forward (+1), over the steps not allowed, round after the last; false when it stays. */
    boolean step(int direction) {
        if (!isEnabled() || values.length < 2) return false;
        int at = index;
        for (int n = 0; n < values.length; n++) {
            at = (at + direction + values.length) % values.length;
            if (allowed[at]) break;
        }
        if (at == index || !allowed[at]) return false;
        index = at;
        refresh();
        if (listener != null) listener.changed(index);
        return true;
    }

    private void refresh() {
        SpannableStringBuilder t = new SpannableStringBuilder();
        if (!name.isEmpty()) {
            t.append(name);
            t.setSpan(new RelativeSizeSpan(.78f), 0, t.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            t.setSpan(new StyleSpan(Typeface.NORMAL), 0, t.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            t.append('\n');
        }
        int from = t.length();
        t.append(values[index]);
        t.setSpan(new StyleSpan(Typeface.BOLD), from, t.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        setText(t);
        setSelected(index != offIndex);
        setContentDescription((name.isEmpty() ? "" : name + ", ") + values[index]);
        invalidate();
    }

    @Override public void setEnabled(boolean enabled) {
        super.setEnabled(enabled);
        if (values != null) refresh();
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        if (event.getActionMasked() == MotionEvent.ACTION_DOWN || event.getActionMasked() == MotionEvent.ACTION_UP) {
            touchX = event.getX();
        }
        return super.onTouchEvent(event);
    }

    /** A tap (or A, Enter): ‹ back, › forward, the middle forward. */
    @Override public boolean performClick() {
        float x = touchX;
        touchX = -1f;
        super.performClick();
        boolean back = x >= 0f && x < arrowWidth();
        step(back ? -1 : 1);
        return true;
    }

    /** L1 / R1 (Q / E, Page up / Page down): -1 back, +1 forward, 0 another key. */
    static int keys(int keyCode) {
        switch (keyCode) {
            case KeyEvent.KEYCODE_BUTTON_L1: case KeyEvent.KEYCODE_Q: case KeyEvent.KEYCODE_PAGE_UP: return -1;
            case KeyEvent.KEYCODE_BUTTON_R1: case KeyEvent.KEYCODE_E: case KeyEvent.KEYCODE_PAGE_DOWN: return 1;
            default: return 0;
        }
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int w = getWidth(), h = getHeight(), a = arrowWidth();
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(SettingsOverlay.BORDER);
        float line = Math.max(1f, dp(1));
        canvas.drawRect(a - line, dp(6), a, h - dp(6), paint);
        canvas.drawRect(w - a, dp(6), w - a + line, h - dp(6), paint);
        boolean can = isEnabled() && canMove();
        paint.setColor(can ? (isSelected() ? SettingsOverlay.ACCENT : SettingsOverlay.INK) : SettingsOverlay.DISABLED);
        paint.setTextSize(dp(26));
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTypeface(Typeface.DEFAULT_BOLD);
        Paint.FontMetrics fm = paint.getFontMetrics();
        float base = h / 2f - (fm.ascent + fm.descent) / 2f;
        canvas.drawText("‹", a / 2f, base, paint);
        canvas.drawText("›", w - a / 2f, base, paint);
        float r = dp(2) + .5f, gap = dp(9);
        float y = h - dp(9);
        float x = w / 2f - (values.length - 1) * gap / 2f;
        for (int i = 0; i < values.length; i++, x += gap) {
            paint.setColor(i == index ? (isEnabled() ? SettingsOverlay.INK : SettingsOverlay.DISABLED) : DOT);
            canvas.drawCircle(x, y, r, paint);
        }
    }

    private boolean canMove() {
        for (int i = 0; i < allowed.length; i++) if (i != index && allowed[i]) return true;
        return false;
    }

    private int arrowWidth() { return dp(44); }

    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }

    // for the tests
    String valueText() { return values[index]; }
}
