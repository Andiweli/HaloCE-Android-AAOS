package com.halo.decomp;

import com.ast.retrotouch.RetroTouchButtonShape;
import com.ast.retrotouch.RetroTouchButtonStyle;
import com.ast.retrotouch.RetroTouchColors;
import com.ast.retrotouch.RetroTouchIcon;
import com.ast.retrotouch.RetroTouchLook;
import com.ast.retrotouch.RetroTouchSkin;

/**
 * The touch controls' look (RetroTouch 1.0.0-beta.13; wish of the project owner, 19.11.2026): as the "RE"
 * skin of CubeEvil4-Android, symbols for what each button does instead of words (the symbol alone, centred on
 * its ink: RetroTouch draws no label with an icon), one colour set for every button, the shoulder buttons
 * (L1/L2, R1/R2) and Pause and SELECT as rectangles, not round (the project owner, 19.11.2026); in the in-game
 * menu's Halo blues. One skin only: no style or skin to switch between.
 *
 * The symbols are RetroTouch's own where one fits (the crosshair, the cartridge, pause, the menu, the
 * arrows) and simple line drawings of the port's own for the rest (24 x 24, drawn as RetroTouch draws its
 * icons: strokes, rounded ends). The menus' buttons (OK, Back, X, Y) keep their words.
 */
final class HaloTouchStyle {
    private HaloTouchStyle() {}

    static final String SKIN = "halo";

    // ---------------------------------------------------------------- the colours (the in-game menu's blues)
    // RetroTouch takes the transparency from each control's opacity (the editor's ALPHA), not from these
    static final int FILL = 0xFF1B2733, BORDER = 0xFF6EA8C8, ICON = 0xFFE6F0F5;
    static final int PRESSED_FILL = 0xFF2A3E52, PRESSED_BORDER = 0xFF9FD4F0, PRESSED_ICON = 0xFFFFFFFF;
    // a latched button: RetroTouch adds the outer ring in the border's colour
    static final int LATCHED_FILL = 0xFF22354A, LATCHED_BORDER = 0xFF6EC6FF, LATCHED_ICON = 0xFFFFFFFF;

    static final RetroTouchColors COLOURS = new RetroTouchColors(FILL, PRESSED_FILL, BORDER, ICON)
        .withPressedColors(PRESSED_FILL, PRESSED_BORDER, PRESSED_ICON)
        .withLatchedColors(LATCHED_FILL, LATCHED_BORDER, LATCHED_ICON);

    // ---------------------------------------------------------------- the port's own symbols
    /** an arrow up from the ground */
    static final RetroTouchIcon JUMP = RetroTouchIcon.fromPaths(24f, "M12 15V4", "m7 9 5-5 5 5", "M5 20h14");
    /** an arrow down to the ground */
    static final RetroTouchIcon CROUCH = RetroTouchIcon.fromPaths(24f, "M12 4v11", "m7 10 5 5 5-5", "M5 20h14");
    /** two arrows the other way round each */
    static final RetroTouchIcon SWAP = RetroTouchIcon.fromPaths(24f, "M4 8h15", "m15 4 4 4-4 4", "M20 16H5",
        "m9 12-4 4 4 4");
    /** a grenade: the body with its ridges, the fuze, the lever and the ring */
    static final RetroTouchIcon GRENADE = RetroTouchIcon.fromPaths(24f,
        "M6.5 15.5a5.5 5.5 0 1 0 11 0a5.5 5.5 0 1 0-11 0Z", "M7 14h10", "M12 10v11", "M10 10V7.5h4V10",
        "M14 8h2a3 3 0 0 1 3 3v2.5", "M6 5.5a2 2 0 1 0 4 0a2 2 0 1 0-4 0Z");
    /** a small grenade and the two arrows of a change */
    static final RetroTouchIcon GRENADE_SWAP = RetroTouchIcon.fromPaths(24f,
        "M2.5 16a4.5 4.5 0 1 0 9 0a4.5 4.5 0 1 0-9 0Z", "M3 15h8", "M7 11.5v9", "M5.5 11.5V9.5h3v2",
        "M15 5h6", "m19 3 2 2-2 2", "M21 12h-6", "m17 10-2 2 2 2");
    /** a torch and its beam */
    static final RetroTouchIcon FLASHLIGHT = RetroTouchIcon.fromPaths(24f,
        "M3 10h7v4H3a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Z", "M10 9.5l4-2.5v10l-4-2.5Z", "m17 8.5 3.5-2",
        "M17.5 12H22", "m17 15.5 3.5 2");
    /** a magnifier with a plus */
    static final RetroTouchIcon ZOOM = RetroTouchIcon.fromPaths(24f, "M3 10a7 7 0 1 0 14 0a7 7 0 1 0-14 0Z",
        "m21 21-5.5-5.5", "M10 7v6", "M7 10h6");
    /** a blow: lines out from where it hits */
    static final RetroTouchIcon MELEE = RetroTouchIcon.fromPaths(24f, "M12 2v5", "M12 17v5", "M2 12h5", "M17 12h5",
        "m4.9 4.9 3.5 3.5", "m15.6 15.6 3.5 3.5", "m4.9 19.1 3.5-3.5", "m15.6 8.4 3.5-3.5");

    /** Width over height of the shoulder buttons and of Pause and SELECT (all rectangles). */
    static final float SHOULDER_ASPECT = 1.6f, START_ASPECT = 1.8f;

    /** An action's symbol (HaloPort.IDS), null for none: the button shows its label. */
    static RetroTouchIcon icon(String action) {
        switch (action) {
            case "fire": return RetroTouchIcon.CROSSHAIR;
            case "jump": return JUMP;
            case "crouch": return CROUCH;
            case "use": return RetroTouchIcon.CARTRIDGE_HORIZONTAL;
            case "melee": return MELEE;
            case "weapon": return SWAP;
            case "grenade": return GRENADE;
            case "grenade_type": return GRENADE_SWAP;
            case "flashlight": return FLASHLIGHT;
            case "zoom": return ZOOM;
            case "pause": return RetroTouchIcon.CIRCLE_PAUSE;
            case "select": return RetroTouchIcon.MENU;
            case "back": return RetroTouchIcon.CHEVRON_LEFT;
            case "nav_up": return RetroTouchIcon.ARROW_UP;
            case "nav_down": return RetroTouchIcon.ARROW_DOWN;
            case "nav_left": return RetroTouchIcon.ARROW_LEFT;
            case "nav_right": return RetroTouchIcon.ARROW_RIGHT;
            default: return null;
        }
    }

    /** Width over height of an action's button (1: round). */
    static float aspect(String action) {
        switch (action) {
            case "fire": case "grenade": case "flashlight": case "grenade_type": return SHOULDER_ASPECT;
            case "pause": case "select": return START_ASPECT;
            default: return 1f;
        }
    }

    /** The one skin: the colours, the rectangles of the shoulder buttons and of Pause and SELECT. */
    static RetroTouchSkin skin() {
        RetroTouchLook shoulder = new RetroTouchLook().withShape(RetroTouchButtonShape.ROUNDED_RECT)
            .withAspect(SHOULDER_ASPECT);
        RetroTouchLook start = new RetroTouchLook().withShape(RetroTouchButtonShape.ROUNDED_RECT)
            .withAspect(START_ASPECT);
        return new RetroTouchSkin(SKIN, "Halo", RetroTouchButtonStyle.ICONS)
            .setDefaultColors(COLOURS)
            .setLook("fire", shoulder)
            .setLook("grenade", shoulder)
            .setLook("flashlight", shoulder)
            .setLook("grenade_type", shoulder)
            .setLook("pause", start)
            .setLook("select", start);
    }
}
