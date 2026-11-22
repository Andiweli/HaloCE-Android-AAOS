package org.libsdl.app;

/**
 * The game's pointer capture around the in-game menu (com.halo.decomp.HaloActivity): SDL captures the
 * mouse while the game plays (sdl_platform.c, SDL's relative mouse mode), but the game's thread may
 * not run while the menu is open, so the menu lets it go here at once and takes it back when it closes,
 * if SDL still wants it. In SDL's package for its motion listener (package-private).
 */
public final class HaloPointer {
    private HaloPointer() {}

    /** Lets the mouse go (the menu takes its clicks, its pointer shows); SDL's own state stays. */
    public static void release() {
        if (android.os.Build.VERSION.SDK_INT < 26) return;
        android.view.View view = SDLActivity.getContentView();
        if (view != null && view.hasPointerCapture()) view.releasePointerCapture();
    }

    /** Takes the mouse again where SDL's relative mode still wants it. */
    public static void reclaim() {
        if (android.os.Build.VERSION.SDK_INT < 26) return;
        SDLGenericMotionListener_API14 listener = SDLActivity.getMotionListener();
        android.view.View view = SDLActivity.getContentView();
        if (listener != null && listener.inRelativeMode() && view != null && !view.hasPointerCapture())
            view.requestPointerCapture();
    }
}
