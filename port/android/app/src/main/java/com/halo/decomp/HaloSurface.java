package com.halo.decomp;

import android.content.Context;
import android.view.MotionEvent;
import org.libsdl.app.SDLActivity;
import org.libsdl.app.SDLSurface;

/**
 * SDL's surface with the captured mouse's events passed on whole (Android 8 and later). While the game
 * captures the mouse (sdl_platform.c), Android sends its motion as ACTION_MOVE events of the relative
 * mouse source, and its buttons as button presses; SDL 3.4's surface hands captured events to its
 * generic motion listener, which takes only hover moves and the wheel, so the aim never moved and the
 * buttons never fired (the project owner's device test, 22.11.2026). Here every move goes to SDL as
 * relative motion (with the batched samples Android folds into one event) and every button change as
 * a press or a release. Other captured sources (a touchpad's absolute fingers) stay with SDL.
 */
final class HaloSurface extends SDLSurface {
    // the buttons SDL knows (MotionEvent.BUTTON_PRIMARY .. BUTTON_FORWARD)
    private static final int BUTTONS = MotionEvent.BUTTON_PRIMARY | MotionEvent.BUTTON_SECONDARY |
        MotionEvent.BUTTON_TERTIARY | MotionEvent.BUTTON_BACK | MotionEvent.BUTTON_FORWARD;
    private int buttons;

    HaloSurface(Context context) {
        super(context);
    }

    /** The steps from the buttons `before` to `after`, as pairs of action (down or up) and the state
     *  after it, one button a step: SDL finds the button from what changed since its last call. */
    static int[] changes(int before, int after) {
        int changed = (before ^ after) & BUTTONS, count = Integer.bitCount(changed);
        int[] steps = new int[count * 2];
        int state = before, n = 0;
        for (int bit = 1; bit <= MotionEvent.BUTTON_FORWARD; bit <<= 1) {
            if ((changed & bit) == 0) continue;
            boolean down = (after & bit) != 0;
            state = down ? state | bit : state & ~bit;
            steps[n++] = down ? MotionEvent.ACTION_DOWN : MotionEvent.ACTION_UP;
            steps[n++] = state;
        }
        return steps;
    }

    @Override
    public boolean onCapturedPointerEvent(MotionEvent event) {
        if (event.getSource() != android.view.InputDevice.SOURCE_MOUSE_RELATIVE)
            return super.onCapturedPointerEvent(event);
        int action = event.getActionMasked();
        if (action == MotionEvent.ACTION_SCROLL) {
            SDLActivity.onNativeMouse(0, action, event.getAxisValue(MotionEvent.AXIS_HSCROLL),
                event.getAxisValue(MotionEvent.AXIS_VSCROLL), false);
            return true;
        }
        int[] steps = changes(buttons, event.getButtonState() & BUTTONS);
        for (int i = 0; i < steps.length; i += 2)
            SDLActivity.onNativeMouse(steps[i + 1], steps[i], 0f, 0f, true);
        buttons = event.getButtonState() & BUTTONS;
        // captured: the motion since the last event (the relative source's X and Y)
        float x = event.getX(), y = event.getY();
        for (int h = 0; h < event.getHistorySize(); h++) {
            x += event.getHistoricalX(h);
            y += event.getHistoricalY(h);
        }
        if (x != 0f || y != 0f)
            SDLActivity.onNativeMouse(buttons, MotionEvent.ACTION_MOVE, x, y, true);
        return true;
    }
}
