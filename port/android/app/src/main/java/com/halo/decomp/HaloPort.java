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
    private boolean active, controllerConnected;
    private int mode = -1;
    private static final String[] IDS = {"jump", "melee", "use", "weapon", "flashlight", "grenade_type",
        "grenade", "fire", "pause", "back", "crouch", "zoom", "nav_up", "nav_down", "nav_left", "nav_right"};
    private static final String[] LABELS = {"Springen / OK", "Nahkampf / Zurück", "Nachladen / Benutzen", "Waffe wechseln",
        "Taschenlampe", "Granate wechseln", "Granate werfen", "Feuern", "Pause / Start", "Zurück (Back)",
        "Ducken", "Zoom", "Nach oben", "Nach unten", "Nach links", "Nach rechts"};
    HaloPort(HaloActivity activity, ViewGroup parent) {
        this.activity = activity;
        prefs = activity.getSharedPreferences("halo_android_controls", 0);
        applyVolumes();
        touch = new RetroTouchView(activity);
        touch.setOnTouchListener((view,event) -> {
            boolean handled = touch.onTouchEvent(event);
            // Consume blank overlay touches, so SDL cannot turn them into mouse clicks.
            return touch.getMode() != RetroTouchMode.OFF || handled;
        });
        for (int i=0;i<IDS.length;i++) touch.registerAction(IDS[i], LABELS[i]);
        touch.setGameplayLayout(new RetroTouchLayout("halo_ce_gameplay_v1", Arrays.asList(
            RetroTouchControl.lookZone("look", .72f,.50f,.55f,.85f),
            RetroTouchControl.moveStick("move", .17f,.72f,.30f),
            button("fire", "Feuer", .88f,.56f,.16f),
            button("jump", "Sprung", .88f,.80f,.13f),
            button("use", "Laden", .73f,.81f,.12f),
            button("melee", "Nahkampf", .95f,.35f,.10f),
            button("grenade", "Granate", .58f,.81f,.12f),
            button("weapon", "Waffe", .76f,.36f,.10f),
            button("zoom", "Zoom", .62f,.36f,.10f),
            button("crouch", "Ducken", .34f,.82f,.11f),
            button("flashlight", "Licht", .36f,.34f,.09f),
            button("grenade_type", "Typ", .49f,.35f,.09f),
            button("pause", "Pause", .50f,.10f,.09f))));
        touch.setNavigationLayout(new RetroTouchLayout("halo_ce_navigation_v1", Arrays.asList(
            RetroTouchControl.dPad("navigation", .17f,.72f,.30f),
            button("jump", "OK", .89f,.76f,.13f),
            button("melee", "Zurück", .74f,.82f,.12f),
            button("use", "X", .89f,.53f,.10f),
            button("weapon", "Y", .76f,.53f,.10f),
            button("pause", "Start", .50f,.90f,.09f))));
        touch.setLookWhileHoldingAction("fire", true);
        touch.setAutoHideOnController(false);
        touch.setListener(new RetroTouchAdapter() {
            @Override public void onAction(String id, boolean down) {
                if (!active || controllerConnected || touch.isEditing()) return;
                for (int i=0;i<IDS.length;i++) if(IDS[i].equals(id)) { nativeAction(i,down);return; }
            }
            @Override public void onMove(float x,float y) { if(active && !controllerConnected) nativeMove(x,y); }
            @Override public void onLook(float x,float y) { if(active && !controllerConnected) nativeLook(x,y); }
            @Override public void onEditorStateChanged(boolean editing) {
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
        return RetroTouchControl.button(id,id,label,x,y,size);
    }
    private final Runnable poll = new Runnable() {
        @Override public void run() {
            if(!active) return;
            updateControllerPresence();
            int next=controllerConnected?0:nativeMode();
            if(!touch.isEditing() && next!=mode) {
                mode=next;
                touch.setMode(next==2?RetroTouchMode.GAMEPLAY:next==1?RetroTouchMode.NAVIGATION:RetroTouchMode.OFF);
            }
            handler.postDelayed(this,100);
        }
    };
    void resume() { if(active)return; active=true;updateControllerPresence();handler.post(poll); }
    void suspend() { active=false;handler.removeCallbacks(poll);touch.releaseAllInputs();nativeReset(); }
    private void updateControllerPresence() {
        boolean connected = RetroTouchControllers.isControllerConnected();
        if (connected != controllerConnected) {
            controllerConnected = connected;
            touch.releaseAllInputs();nativeReset();
            if (connected && touch.isEditing()) touch.setEditing(false);
            touch.setMode(RetroTouchMode.OFF);
            mode = -1;
        }
        touch.setVisibility(connected ? View.GONE : View.VISIBLE);
    }
    void controllerInput() { updateControllerPresence(); }
    void focusLost() { touch.releaseAllInputs();nativeReset(); }
    private void applyVolumes() {
        nativeVolumes(prefs.getInt("master",100), prefs.getInt("effects",100), prefs.getInt("music",100));
    }
}
