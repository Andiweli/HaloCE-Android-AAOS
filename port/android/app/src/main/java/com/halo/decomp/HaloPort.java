package com.halo.decomp;

import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import com.ast.retrotouch.*;
import java.util.Arrays;

/** UI-side adapter; native state crosses the host/guest ABI through fixed-width imports. */
final class HaloPort {
    static native void nativeAction(int action, boolean down);
    static native void nativeMove(float x, float y);
    static native void nativeLook(float x, float y);
    static native void nativeReset();
    static native int nativeMode();
    static native void nativeMouse(boolean present);
    static native void nativeVolumes(int master, int effects, int music);
    private final HaloActivity activity;
    private final RetroTouchView touch;
    private final SharedPreferences prefs;
    private final Handler handler = new Handler(Looper.getMainLooper());
    // touchHidden: the touch controls are hidden by the input devices or by the menu's choice (touchSetting)
    private boolean active, touchHidden, overlay;
    /** The menu's choice for the touch controls (wish of the project owner, 23.11.2026, as CubeEvil4's): Auto follows
     *  the input used last, a finger shows them, a controller's button or stick, a key or the mouse hides them
     *  (one connected hides them too, until a finger); Always shows them whatever is connected, Never hides them
     *  for good (a Chromebook's own keyboard and touchpad, say). */
    static final int TOUCH_AUTO = 0, TOUCH_ALWAYS = 1, TOUCH_NEVER = 2;
    static final String TOUCH_KEY = "touch_controls";
    private static final String[] TOUCH_NAMES = {"auto", "always", "never"};
    private int touchSetting;
    /** A stored choice that is one of the three, else Auto. */
    static int touchSetting(int stored) { return stored == TOUCH_ALWAYS || stored == TOUCH_NEVER ? stored : TOUCH_AUTO; }
    private int mousePresent = -1;
    // a controller, a keyboard or a mouse in use (desk): set by a connected one and by any one's buttons, stick,
    // keys or pointer, cleared by a finger on the screen, which brings the touch controls back (a Galaxy A36
    // listed a built-in keyboard, 1.1.1: no touch controls; 23.11.2026: a controller's too); deskPresent: a
    // connected one is there, mouseSeen: a mouse is there or was used since (the game captures it only then)
    private boolean desk, deskPresent, mouseSeen;
    private int mode = -1;
    private static final String[] IDS = {"jump", "melee", "use", "weapon", "flashlight", "grenade_type",
        "grenade", "fire", "pause", "back", "crouch", "zoom", "nav_up", "nav_down", "nav_left", "nav_right", "select"};
    private static final String[] LABELS = {"Jump / OK", "Melee / Back", "Reload / Use", "Switch weapon",
        "Flashlight", "Switch grenade", "Throw grenade", "Fire", "Pause / Start", "Back",
        "Crouch", "Zoom", "Up", "Down", "Left", "Right", "SELECT"};
    // the menus' face buttons: the actions above, but with their words, not the game's symbols
    private static final String[] MENU_IDS = {"menu_ok", "menu_back", "menu_x", "menu_y"};
    private static final String[] MENU_LABELS = {"OK", "Back", "X", "Y"};
    private static final String[] MENU_ACTIONS = {"jump", "melee", "use", "weapon"};
    HaloPort(HaloActivity activity, ViewGroup parent) {
        this.activity = activity;
        prefs = activity.getSharedPreferences("halo_android_controls", 0);
        touchSetting = touchSetting(prefs.getInt(TOUCH_KEY, TOUCH_AUTO));
        android.util.Log.i("halo", "touch controls: setting " + TOUCH_NAMES[touchSetting]);
        applyVolumes();
        touch = new RetroTouchView(activity);
        touch.setOnTouchListener((view,event) -> {
            if (event.getActionMasked()==android.view.MotionEvent.ACTION_CANCEL) activity.cancelTouchSelect();
            boolean handled = touch.onTouchEvent(event);
            // Consume blank overlay touches, so SDL cannot turn them into mouse clicks.
            return touch.getMode() != RetroTouchMode.OFF || handled;
        });
        // symbols for what the buttons do, as CubeEvil4's RE skin, in one skin only (HaloTouchStyle):
        // RetroTouch 1.0.0-beta.13's ICONS style, no style or skin to switch to
        touch.setAvailableButtonStyles(RetroTouchButtonStyle.ICONS);
        touch.setDefaultButtonStyle(RetroTouchButtonStyle.ICONS);
        for (int i=0;i<IDS.length;i++) touch.registerAction(IDS[i], LABELS[i], null, HaloTouchStyle.icon(IDS[i]));
        for (int i=0;i<MENU_IDS.length;i++) touch.registerAction(MENU_IDS[i], MENU_LABELS[i]);
        touch.setDefaultColors(HaloTouchStyle.COLOURS);
        touch.registerSkin(HaloTouchStyle.skin());
        touch.setDefaultSkin(HaloTouchStyle.SKIN);
        touch.setSkin(HaloTouchStyle.SKIN);
        touch.setGameplayLayout(new RetroTouchLayout("halo_ce_gameplay_v1", Arrays.asList(
            RetroTouchControl.lookZone("look", .72f,.50f,.55f,.85f),
            RetroTouchControl.moveStick("move", .17f,.72f,.30f),
            button("fire", "Fire", .88f,.56f,.16f),
            button("jump", "Jump", .88f,.80f,.13f),
            button("use", "Reload", .73f,.81f,.12f),
            button("melee", "Melee", .95f,.35f,.10f),
            button("grenade", "Grenade", .58f,.81f,.12f),
            button("weapon", "Weapon", .76f,.36f,.10f),
            button("zoom", "Zoom", .62f,.36f,.10f),
            button("crouch", "Crouch", .34f,.82f,.11f),
            button("flashlight", "Light", .36f,.34f,.09f),
            button("grenade_type", "Type", .49f,.35f,.09f),
            button("pause", "Pause", .50f,.10f,.09f),
            button("select", "SELECT", .37f,.10f,.10f))));
        // (v2: the face buttons as the menus' own actions, with their words)
        touch.setNavigationLayout(new RetroTouchLayout("halo_ce_navigation_v2", Arrays.asList(
            RetroTouchControl.dPad("navigation", .17f,.72f,.30f),
            button("menu_ok", "OK", .89f,.76f,.13f),
            button("menu_back", "Back", .74f,.82f,.12f),
            button("menu_x", "X", .89f,.53f,.10f),
            button("menu_y", "Y", .76f,.53f,.10f),
            button("pause", "Start", .50f,.90f,.09f),
            button("select", "SELECT", .37f,.90f,.10f))));
        touch.setLookWhileHoldingAction("fire", true);
        touch.setAutoHideOnController(false);
        touch.setListener(new RetroTouchAdapter() {
            @Override public void onAction(String id, boolean down) {
                if ("select".equals(id) && !down) { activity.touchSelect(false);return; }
                if (!active || overlay || touchHidden || touch.isEditing()) return;
                if ("select".equals(id)) { activity.touchSelect(true);return; }
                for (int i=0;i<MENU_IDS.length;i++) if(MENU_IDS[i].equals(id)) { id=MENU_ACTIONS[i];break; }
                for (int i=0;i<IDS.length;i++) if(IDS[i].equals(id)) { nativeAction(i,down);return; }
            }
            @Override public void onMove(float x,float y) { if(active && !overlay && !touchHidden) nativeMove(x,y); }
            @Override public void onLook(float x,float y) { if(active && !overlay && !touchHidden) nativeLook(x,y); }
            @Override public void onEditorStateChanged(boolean editing) {
                activity.cancelTouchSelect();
                nativeReset();
                // Keep the gameplay layout editable while the engine is in its pause menu.
                if(editing && nativeMode()==2) {nativeAction(8,true);nativeAction(8,false);}
            }
        });
        parent.addView(touch, new ViewGroup.LayoutParams(-1,-1));
        touch.setMode(RetroTouchMode.OFF);
        touch.setVisibility(View.GONE);
        updateControllerPresence();
    }
    private static RetroTouchControl button(String id,String label,float x,float y,float size) {
        return RetroTouchControl.button(id,id,label,x,y,size,null,RetroTouchButtonShape.AUTO,HaloTouchStyle.aspect(id));
    }
    private final Runnable poll = new Runnable() {
        @Override public void run() {
            if(!active) return;
            updateControllerPresence();
            int next=(touchHidden || overlay)?0:nativeMode();
            if(!touch.isEditing() && next!=mode) {
                activity.cancelTouchSelect();
                mode=next;
                touch.setMode(next==2?RetroTouchMode.GAMEPLAY:next==1?RetroTouchMode.NAVIGATION:RetroTouchMode.OFF);
            }
            handler.postDelayed(this,100);
        }
    };
    void resume() { if(active)return; active=true;updateControllerPresence();handler.post(poll); }
    void suspend() { active=false;handler.removeCallbacks(poll);activity.cancelTouchSelect();touch.releaseAllInputs();nativeReset(); }
    private void updateControllerPresence() {
        // a controller, a keyboard or a mouse connected hides the touch controls (ControllerPresence.inputs),
        // a finger brings them back, using one of them hides them again (desk)
        int inputs = ControllerPresence.inputs(activity);
        boolean present = inputs != 0;
        if (present != deskPresent) { deskPresent = present; desk = present; mouseSeen = false; }
        if ((inputs & ControllerPresence.MOUSE) != 0) mouseSeen = true;
        int mouse = desk && mouseSeen ? 1 : 0;
        if (mouse != mousePresent) { mousePresent = mouse; nativeMouse(mouse != 0); }
        boolean hidden = touchSetting == TOUCH_NEVER || (touchSetting == TOUCH_AUTO && desk);
        if (hidden != touchHidden) {
            activity.cancelTouchSelect();
            touchHidden = hidden;
            touch.releaseAllInputs();nativeReset();
            if (hidden && touch.isEditing()) touch.setEditing(false);
            touch.setMode(RetroTouchMode.OFF);
            mode = -1;
        }
        touch.setVisibility((hidden || overlay) ? View.GONE : View.VISIBLE);
    }
    /** The menu's choice (SettingsOverlay): Auto, Always or Never; it applies at once and is kept. */
    void touchControls(int setting) {
        setting = touchSetting(setting);
        if (setting == touchSetting) return;
        touchSetting = setting;
        android.util.Log.i("halo", "touch controls: setting " + TOUCH_NAMES[setting]);
        updateControllerPresence();
    }
    void overlay(boolean visible) { overlay=visible;activity.cancelTouchSelect();touch.releaseAllInputs();nativeReset();mode=-1;updateControllerPresence(); }
    /** A controller's button or stick (HaloActivity, a controller as ControllerPresence.isController says, not a
     *  fingerprint sensor): the touch controls hide. */
    void controllerInput() {
        if (!desk && touchSetting == TOUCH_AUTO)
            android.util.Log.i("halo", "touch controls: hidden (a controller in use)");
        desk = true;
        updateControllerPresence();
    }
    /** A keyboard's key or a mouse's pointer (HaloActivity): the touch controls hide. */
    void deskUsed(boolean mouse) {
        if (mouse) mouseSeen = true;
        if (desk && (!mouse || mousePresent == 1)) return;
        if (touchSetting == TOUCH_AUTO)
            android.util.Log.i("halo", "touch controls: hidden (" + (mouse ? "a mouse" : "a keyboard") + " in use)");
        desk = true;
        updateControllerPresence();
    }
    /** A finger on the screen (HaloActivity): the touch controls come back, if a controller, a keyboard or a
     *  mouse hid them. */
    void fingerUsed() {
        if (!desk) return;
        if (touchSetting == TOUCH_AUTO) android.util.Log.i("halo", "touch controls: shown (the screen touched)");
        desk = false;
        mouseSeen = false;
        updateControllerPresence();
    }
    void focusLost() { activity.cancelTouchSelect();touch.releaseAllInputs();nativeReset(); }
    private void applyVolumes() {
        nativeVolumes(prefs.getInt("master",100), prefs.getInt("effects",100), prefs.getInt("music",100));
    }
}
