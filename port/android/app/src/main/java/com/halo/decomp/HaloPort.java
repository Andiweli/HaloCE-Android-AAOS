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
    static native void nativeVolumes(int master, int effects, int music);
    private final HaloActivity activity;
    private final RetroTouchView touch;
    private final SharedPreferences prefs;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean active, controllerConnected, overlay;
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
                if (!active || overlay || controllerConnected || touch.isEditing()) return;
                if ("select".equals(id)) { activity.touchSelect(true);return; }
                for (int i=0;i<MENU_IDS.length;i++) if(MENU_IDS[i].equals(id)) { id=MENU_ACTIONS[i];break; }
                for (int i=0;i<IDS.length;i++) if(IDS[i].equals(id)) { nativeAction(i,down);return; }
            }
            @Override public void onMove(float x,float y) { if(active && !overlay && !controllerConnected) nativeMove(x,y); }
            @Override public void onLook(float x,float y) { if(active && !overlay && !controllerConnected) nativeLook(x,y); }
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
            int next=(controllerConnected || overlay)?0:nativeMode();
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
        boolean connected = ControllerPresence.isControllerConnected(activity);
        if (connected != controllerConnected) {
            activity.cancelTouchSelect();
            controllerConnected = connected;
            touch.releaseAllInputs();nativeReset();
            if (connected && touch.isEditing()) touch.setEditing(false);
            touch.setMode(RetroTouchMode.OFF);
            mode = -1;
        }
        touch.setVisibility((connected || overlay) ? View.GONE : View.VISIBLE);
    }
    void overlay(boolean visible) { overlay=visible;activity.cancelTouchSelect();touch.releaseAllInputs();nativeReset();mode=-1;updateControllerPresence(); }
    void controllerInput() { updateControllerPresence(); }
    void focusLost() { activity.cancelTouchSelect();touch.releaseAllInputs();nativeReset(); }
    private void applyVolumes() {
        nativeVolumes(prefs.getInt("master",100), prefs.getInt("effects",100), prefs.getInt("music",100));
    }
}
