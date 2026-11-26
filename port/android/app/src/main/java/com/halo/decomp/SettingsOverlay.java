package com.halo.decomp;

import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.RelativeSizeSpan;
import android.text.style.StyleSpan;
import android.view.FocusFinder;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.util.Locale;

/**
 * The in-game menu (SELECT held, or the touch controls' menu button), laid out as CubeEvil4's in Halo's
 * colours (wish of the project owner, 02.11.2026): "HALO CE In-Game Menu" with the version (vX), the update button and
 * "Back to the game", the pages Display, Controls, Volume and Cheats. Every change applies and is kept at
 * once. An overlay in the activity, not a dialog: the game's surface and immersive window stay as they are.
 * The controller is driven here (key, motion), the touch screen by Android.
 */
final class SettingsOverlay {
    static native void nativeOpen(boolean open);
    static native void nativeDisplay(int brightness, int gamma);
    static native void nativeSticks(int left, int right);
    static native int nativeLookSticks();
    static native void nativeFrameRate(boolean sixty);
    static native void nativeTextureFilter(int level);
    static native void nativeCheats(int bits);
    static native void nativeCampaignUnlocked(boolean on);
    static native void nativeCheatAction(int action);
    static native int nativeCheatResult(int action);
    static native void nativeMsaa(int samples);
    static native void nativeDepthOfField(boolean on);
    static native void nativeDepthOfFieldStrength(int percent);
    static native int nativeMsaaLimit();
    static native void nativeFxaa(boolean on);
    static native void nativeCounters(int[] out);
    /** The mouse's look (host_settings_mouse_look): per cent of the configuration's speed, Y upside down. */
    static native void nativeMouseLook(int percent, boolean invert);
    static native void nativeResolution(int lines);
    static native void nativeUpscaler(int upscaler);

    static final int HOME=0, DISPLAY=1, CONTROLS=2, AUDIO=3, CHEATS=4;
    // Halo's blues instead of CubeEvil4's greens and gold; the update button keeps green and red
    static final int PANEL=0xff0e1a24, SURFACE=0xff16273a, BORDER=0xff2f4a63, INK=0xffe6f0f5,
        MUTED=0xff8fa9bd, ACCENT=0xff6ec6ff, ACTIVE=0xff1f3d57, DISABLED=0xff5a6b7a, DIM=0xb8000000;
    // a cell pressed (with the mouse too); no hover look, as CubeEvil4's (the project owner, 22.11.2026)
    static final int PRESSED=0xff2b587c;
    static final int UPDATE_GREEN=0xff2d5233, UPDATE_GREEN_EDGE=0xff4f8a57,
        UPDATE_RED=0xff7a2a26, UPDATE_RED_EDGE=0xffb2463f;
    private static final int LEFT_LOOK=1, RIGHT_LOOK=2;
    // the sliders: their keys in "halo_android_controls", their ranges in per cent
    static final int MASTER=0, EFFECTS=1, MUSIC=2, BRIGHTNESS=3, GAMMA=4, GYRO=5, LEFT_STICK=6, RIGHT_STICK=7;
    static final String[] KEYS={"master","effects","music","brightness","gamma","gyro_sensitivity","left_stick_sensitivity","right_stick_sensitivity"};
    static final int[] MIN={0,0,0,50,50,25,50,50}, MAX={100,100,100,150,200,200,150,150};
    static final int STEP=5;
    /** The mouse's sensitivity in per cent (prefs "mouse_sensitivity"), its Y axis upside down ("mouse_invert"). */
    static final int MOUSE_MIN=25, MOUSE_MAX=300, MOUSE_STEP=5, MOUSE_DEFAULT=100;
    static int mouseSensitivity(int stored) {
        int v=Math.max(MOUSE_MIN,Math.min(MOUSE_MAX,stored));
        return MOUSE_MIN+(v-MOUSE_MIN)/MOUSE_STEP*MOUSE_STEP;
    }
    /** The key overview (Controls, Keyboard & mouse): what the game does, which keys do it (xinput_sdl.c
     *  keyboard_gamepad, the Xbox buttons' roles of input_abstraction.c). Read-only, no remapping yet. */
    static final int[][] KEY_ROWS={
        {R.string.menu_key_move,R.string.menu_keys_move},{R.string.menu_key_aim,R.string.menu_keys_aim},
        {R.string.menu_key_fire,R.string.menu_keys_fire},{R.string.menu_key_grenade,R.string.menu_keys_grenade},
        {R.string.menu_key_jump,R.string.menu_keys_jump},{R.string.menu_key_use,R.string.menu_keys_use},
        {R.string.menu_key_weapon,R.string.menu_keys_weapon},{R.string.menu_key_grenade_type,R.string.menu_keys_grenade_type},
        {R.string.menu_key_melee,R.string.menu_keys_melee},{R.string.menu_key_crouch,R.string.menu_keys_crouch},
        {R.string.menu_key_zoom,R.string.menu_keys_zoom},{R.string.menu_key_flashlight,R.string.menu_keys_flashlight},
        {R.string.menu_key_pause,R.string.menu_keys_pause},{R.string.menu_key_menu,R.string.menu_keys_menu},
        {R.string.menu_key_pointer,R.string.menu_keys_pointer},{R.string.menu_key_dpad,R.string.menu_keys_dpad},
    };
    // the texture filtering's choices (texels along a pixel's footprint; 1 off); 4 as the configuration's;
    // 16× too (wish of the project owner, 22.11.2026; d3d8_gl.c keeps it within the GPU's most)
    static final int[] FILTERS={1,2,4,8,16};
    static final int DEFAULT_FILTER=4;
    // MSAA's choices (samples; 0 off), off by default
    static final int[] MSAA={0,2,4};
    // the depth of field's strength in per cent, in steps of 10 (wish of the project owner, 02.11.2026: the
    // first build blurred too much; 100 % is that one, 50 % the default)
    static final int DOF_MIN=10, DOF_MAX=200, DOF_STEP=10, DOF_DEFAULT=50;
    /** A stored strength within the range and on a step, else the default. */
    static int dofStrength(int stored) {
        if(stored<DOF_MIN || stored>DOF_MAX || stored%DOF_STEP!=0) return DOF_DEFAULT;
        return stored;
    }
    static final String SOURCE_URL="https://github.com/Andiweli/HaloCE-Android-AAOS";
    // the cheats: the switches' bits and the buttons as halo_android_controls.h numbers them
    static final int CHEAT_HEALTH=1, CHEAT_AMMO=2, CHEAT_RELOAD=4, CHEAT_ONE_HIT=8, CHEAT_SWITCHES=15;
    static final int ACTION_WEAPONS=0, ACTION_WARTHOG=1, ACTION_SCORPION=2, ACTION_GHOST=3, ACTION_BANSHEE=4;
    // each button's label, its answer when done and when the level has none of it (the weapons: always there)
    private static final int[] ACTION_LABELS={R.string.menu_cheat_weapons,R.string.menu_cheat_warthog,
        R.string.menu_cheat_scorpion,R.string.menu_cheat_ghost,R.string.menu_cheat_banshee};
    private static final int[] ACTION_DONE={R.string.menu_cheat_weapons_done,R.string.menu_cheat_warthog_done,
        R.string.menu_cheat_scorpion_done,R.string.menu_cheat_ghost_done,R.string.menu_cheat_banshee_done};
    private static final int[] ACTION_MISSING={R.string.menu_cheat_none,R.string.menu_cheat_none,
        R.string.menu_cheat_no_scorpion,R.string.menu_cheat_no_ghost,R.string.menu_cheat_no_banshee};
    /** The answer the menu shows for a button's result. */
    static int cheatAnswer(int what,int result) {
        return result==RESULT_DONE?ACTION_DONE[what]:result==RESULT_MISSING?ACTION_MISSING[what]:R.string.menu_cheat_no_game;
    }
    static final int RESULT_NONE=0, RESULT_PENDING=1, RESULT_DONE=2, RESULT_MISSING=3, RESULT_NO_GAME=4;
    private static final long CHEAT_FLASH_MS=1500, CHEAT_WAIT_MS=3000;

    /** What a key does in the menu; NONE: the game never sees it, PASS: Android's (the volume keys). */
    /** STEP_BACK / STEP_ON: L1 / R1 (Q / E, Page up / Page down) step the focused arrow or slider cell. */
    static final int NONE=0, PASS=1, UP=2, DOWN=3, LEFT=4, RIGHT=5, PRESS=6, BACK=7, CLOSE=8, STEP_BACK=9, STEP_ON=10;
    static int action(int key) {
        switch(key){
            case KeyEvent.KEYCODE_VOLUME_UP: case KeyEvent.KEYCODE_VOLUME_DOWN: case KeyEvent.KEYCODE_VOLUME_MUTE: return PASS;
            case KeyEvent.KEYCODE_DPAD_UP: return UP;
            case KeyEvent.KEYCODE_DPAD_DOWN: return DOWN;
            case KeyEvent.KEYCODE_DPAD_LEFT: return LEFT;
            case KeyEvent.KEYCODE_DPAD_RIGHT: return RIGHT;
            case KeyEvent.KEYCODE_BUTTON_A: case KeyEvent.KEYCODE_DPAD_CENTER: case KeyEvent.KEYCODE_ENTER:
            case KeyEvent.KEYCODE_NUMPAD_ENTER: case KeyEvent.KEYCODE_SPACE: return PRESS;
            case KeyEvent.KEYCODE_BUTTON_B: case KeyEvent.KEYCODE_BACK: case KeyEvent.KEYCODE_ESCAPE: return BACK;
            case KeyEvent.KEYCODE_BUTTON_START: case KeyEvent.KEYCODE_BUTTON_SELECT: case KeyEvent.KEYCODE_MENU: return CLOSE;
            default: {
                int step=ArrowSelector.keys(key);
                return step<0?STEP_BACK:step>0?STEP_ON:NONE;
            }
        }
    }
    /** The value a slider's key step leads to: STEP per cent, within the slider's range. */
    static int stepped(int index,int value,int direction) {
        return Math.max(MIN[index],Math.min(MAX[index],value+direction*STEP));
    }
    /** The switches after one of them was pressed. */
    static int toggled(int bits,int bit,boolean on) { return (on?bits|bit:bits&~bit)&CHEAT_SWITCHES; }
    /** A stored texture filtering that is one of the choices, else the configuration's. */
    static int filter(int stored) {
        for(int choice:FILTERS) if(choice==stored) return stored;
        return DEFAULT_FILTER;
    }
    /** A stored MSAA that is one of the choices, else off. */
    static int msaa(int stored) {
        for(int choice:MSAA) if(choice==stored) return stored;
        return 0;
    }
    /** The resolution's choices (Display): the picture's lines, 0 the screen's own (d3d8_gl.c screen_mode_choose). */
    static final int[] RESOLUTIONS={480,720,1080,0};
    static final int DEFAULT_RESOLUTION=1080;
    /** The upscaler's choices (host_upscale.c): 0 the plain linear stretch, 1 SGSR, 2 FSR. */
    static final int[] UPSCALERS={0,1,2};
    /** A stored resolution that is one of the choices, else the default (1080p). */
    static int resolution(int stored) {
        for(int choice:RESOLUTIONS) if(choice==stored) return stored;
        return DEFAULT_RESOLUTION;
    }
    /** A stored upscaler that is one of the choices, else the plain stretch. */
    static int upscaler(int stored) {
        for(int choice:UPSCALERS) if(choice==stored) return stored;
        return 0;
    }
    /** The picture's lines at a resolution on a screen of `screenLines` (as screen_mode_choose: never more than the
     *  screen, never fewer than 480; native the screen's own). */
    static int pictureLines(int resolution,int screenLines) {
        int lines=resolution<=0||resolution>screenLines?screenLines:resolution;
        return Math.max(480,lines);
    }
    /** Whether the upscaler has anything to do: the picture smaller than the screen (as host_upscale.c, 2 % room). */
    static boolean upscales(int resolution,int screenLines) {
        return screenLines>0 && pictureLines(resolution,screenLines)*1.02f<screenLines;
    }
    /** Whether a choice of samples is offered: off always; more while the GPU's limit is unknown (-1) or allows it. */
    static boolean msaaOffered(int samples,int limit) { return samples==0 || limit<0 || samples<=limit; }

    private interface Changed<T> { void accept(T value); }
    private final HaloActivity activity;
    private final ViewGroup parent;
    private final SharedPreferences prefs;
    private final int[] values=new int[KEYS.length];
    private boolean gyroEnabled, gyroInvertPitch;
    // 60 FPS with interpolation; off, the original 30 (sdl_platform.c)
    private boolean sixtyFps;
    private int textureFilter, cheatBits, msaaSamples, resolutionLines, upscalerChoice;
    private boolean depthOfField, fxaa, fpsDisplay, mouseInvert, campaignUnlocked;
    private int dofStrength, mouseSensitivity, touchSetting;
    private final FpsCounter fps;
    private FrameLayout root;
    private LinearLayout body;
    private ScrollView scroll;
    private TextView title, cheatStatus;
    private Button back, resume, update;
    private final Button[] navigation=new Button[CHEATS+1];
    private final int[] scrollY=new int[CHEATS+1];
    private final SliderCell[] sliders=new SliderCell[KEYS.length];
    private int page, stickLookMask, serial;
    private long lastMotion;
    private int lastDirection;
    private boolean suspended;
    private final Runnable refreshStickRoles=new Runnable(){
        public void run(){
            if(!isOpen())return;
            refreshStickSliders();
            root.postDelayed(this,100);
        }
    };

    SettingsOverlay(HaloActivity activity,ViewGroup parent) {
        this.activity=activity;this.parent=parent;
        prefs=activity.getSharedPreferences("halo_android_controls",0);
        for(int i=0;i<values.length;i++)
            values[i]=Math.max(MIN[i],Math.min(MAX[i],prefs.getInt(KEYS[i],100)));
        gyroEnabled=prefs.getBoolean("gyro_aim",false) && activity.motionAvailable();
        gyroInvertPitch=prefs.getBoolean("gyro_invert_pitch",false);
        sixtyFps=prefs.getBoolean("sixty_fps",false);
        textureFilter=filter(prefs.getInt("texture_filter",DEFAULT_FILTER));
        cheatBits=prefs.getInt("cheats",0)&CHEAT_SWITCHES;
        campaignUnlocked=prefs.getBoolean("campaign_unlocked",false);
        msaaSamples=msaa(prefs.getInt("msaa",0));
        depthOfField=prefs.getBoolean("depth_of_field",false);
        dofStrength=dofStrength(prefs.getInt("depth_of_field_strength",DOF_DEFAULT));
        fxaa=prefs.getBoolean("fxaa",false);
        fpsDisplay=prefs.getBoolean("fps_display",false);
        mouseSensitivity=mouseSensitivity(prefs.getInt("mouse_sensitivity",MOUSE_DEFAULT));
        mouseInvert=prefs.getBoolean("mouse_invert",false);
        resolutionLines=resolution(prefs.getInt("resolution",DEFAULT_RESOLUTION));
        upscalerChoice=upscaler(prefs.getInt("upscaler",0));
        touchSetting=HaloPort.touchSetting(prefs.getInt(HaloPort.TOUCH_KEY,HaloPort.TOUCH_AUTO));
        fps=new FpsCounter(activity,parent);
        fps.configure(fpsDisplay,sixtyFps);
        apply();
        nativeTextureFilter(textureFilter);
        nativeCheats(cheatBits);
        nativeCampaignUnlocked(campaignUnlocked);
        nativeMsaa(msaaSamples);
        nativeDepthOfField(depthOfField);
        nativeDepthOfFieldStrength(dofStrength);
        nativeFxaa(fxaa);
        nativeResolution(resolutionLines);
        nativeUpscaler(upscalerChoice);
    }
    boolean isOpen(){return root!=null;}
    int page(){return page;}

    // ---------- looks (CubeEvil4's CoreMenu)
    private String s(int id){return activity.getString(id);}
    private int dp(int n){return Math.round(n*activity.getResources().getDisplayMetrics().density);}
    private LinearLayout column(){LinearLayout v=new LinearLayout(activity);v.setOrientation(LinearLayout.VERTICAL);return v;}
    private LinearLayout row(){LinearLayout v=new LinearLayout(activity);v.setBaselineAligned(false);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
    private TextView text(String label,int size,boolean bold){
        TextView v=new TextView(activity);
        v.setText(label);v.setTextSize(size);v.setTextColor(bold?INK:MUTED);
        if(bold)v.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        return v;
    }
    private GradientDrawable shape(int fill,int stroke,int radius){
        GradientDrawable d=new GradientDrawable();d.setColor(fill);d.setCornerRadius(dp(radius));
        d.setStroke(dp(1),stroke);return d;
    }
    private GradientDrawable focused(int fill){
        GradientDrawable d=shape(fill,INK,6);d.setStroke(dp(2),INK);return d;
    }
    private void style(Button b){
        StateListDrawable state=new StateListDrawable();
        // pressed first: a click lights the cell whatever else it is
        state.addState(new int[]{android.R.attr.state_pressed},shape(PRESSED,INK,6));
        state.addState(new int[]{android.R.attr.state_focused,android.R.attr.state_selected},focused(ACTIVE));
        state.addState(new int[]{android.R.attr.state_focused},focused(SURFACE));
        state.addState(new int[]{android.R.attr.state_selected},shape(ACTIVE,ACCENT,6));
        state.addState(new int[0],shape(SURFACE,BORDER,6));
        b.setBackground(state);b.setAllCaps(false);b.setTextSize(16);b.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        b.setTextColor(new ColorStateList(new int[][]{new int[]{-android.R.attr.state_enabled},
            new int[]{android.R.attr.state_selected},new int[0]},new int[]{DISABLED,ACCENT,INK}));
        b.setPadding(dp(12),dp(8),dp(12),dp(8));b.setMinHeight(dp(48));b.setMinimumHeight(dp(48));
        b.setMinWidth(0);b.setMinimumWidth(0);b.setId(View.generateViewId());
        b.setStateListAnimator(null);b.setElevation(0);
    }
    private Button button(String label,View.OnClickListener click){
        Button b=new Button(activity);style(b);b.setText(label);b.setOnClickListener(click);
        return b;
    }
    private void separator(LinearLayout parent){
        View v=new View(activity);v.setBackgroundColor(BORDER);
        v.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(1));
        lp.setMargins(0,dp(10),0,dp(8));parent.addView(v,lp);
    }
    /** A section's heading with a faint line to its right up to the end of the row, as CubeEvil4's. */
    private void heading(int id){
        LinearLayout line=row();
        line.setPaddingRelative(dp(MenuLayout.GAP),dp(16),dp(MenuLayout.GAP),dp(8));
        TextView v=text(s(id).toUpperCase(Locale.getDefault()),14,true);v.setTextColor(MUTED);v.setLetterSpacing(.08f);
        v.setPaddingRelative(0,0,dp(3),0);
        line.addView(v,new LinearLayout.LayoutParams(-2,-2));
        View rule=new View(activity);rule.setBackgroundColor(BORDER);
        rule.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(1),1);
        lp.setMarginStart(dp(12));lp.gravity=Gravity.CENTER_VERTICAL;
        line.addView(rule,lp);
        body.addView(line);
    }
    /** An explanation in the option column (beside the side labels), across the width where they stack. */
    private void help(int id){
        MenuLayout.Columns outer=new MenuLayout.Columns(activity,170,640,true);
        outer.addView(new View(activity));
        TextView t=text(s(id),15,false);t.setPadding(dp(MenuLayout.GAP),dp(4),dp(MenuLayout.GAP),dp(8));
        outer.addView(t);
        body.addView(outer);
    }
    /** A side label as tall as one row of cells, centred on the first. */
    private TextView rowLabel(String label){
        TextView caption=text(label,16,true);
        caption.setPaddingRelative(dp(MenuLayout.GAP),0,dp(8),0);
        caption.setMinHeight(dp(64+2*MenuLayout.GAP));caption.setMinimumHeight(dp(64+2*MenuLayout.GAP));
        caption.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
        return caption;
    }
    /** The side label on the left, the option column (rows of cells) on the right; stacked on narrow windows
     *  (CubeEvil4's labelledOptions, its fourth menu round: every sub-page laid out so). */
    private LinearLayout labelled(int label){
        return labelled(rowLabel(s(label)));
    }
    private LinearLayout labelled(TextView caption){
        MenuLayout.Columns outer=new MenuLayout.Columns(activity,170,640,false);
        outer.setGravity(Gravity.TOP);
        outer.addView(caption);
        LinearLayout options=column();
        outer.addView(options);
        body.addView(outer);
        return options;
    }
    /** A row of two cells (a pair of settings) in an option column. */
    private MenuLayout.Buttons pair(LinearLayout group){
        MenuLayout.Buttons buttons=new MenuLayout.Buttons(activity,2);
        group.addView(buttons,new LinearLayout.LayoutParams(-1,-2));return buttons;
    }
    /** A row of one cell across the option column (a slider over both columns). */
    private MenuLayout.Buttons single(LinearLayout group){
        MenuLayout.Buttons buttons=new MenuLayout.Buttons(activity,1);
        group.addView(buttons,new LinearLayout.LayoutParams(-1,-2));return buttons;
    }
    private MenuLayout.Buttons buttonsRow(int columns){
        MenuLayout.Buttons buttons=new MenuLayout.Buttons(activity,columns);
        body.addView(buttons,new LinearLayout.LayoutParams(-1,-2));return buttons;
    }
    /** A cell of a grid, 64 dp high as every cell (CubeEvil4's third menu round). */
    private Button cellAction(MenuLayout.Buttons parent,String label,View.OnClickListener click){
        Button b=button(label,click);b.setMinHeight(dp(64));b.setMinimumHeight(dp(64));
        parent.addButton(b);return b;
    }
    private Button toggle(MenuLayout.Buttons parent,String label,boolean on,Changed<Boolean> changed){
        Button b=cellAction(parent,"",v->{
            Button pressed=(Button)v;boolean next=!pressed.isSelected();
            toggleLabel(pressed,label,next);changed.accept(next);
        });
        toggleLabel(b,label,on);
        b.setAccessibilityDelegate(new View.AccessibilityDelegate(){
            @Override public void onInitializeAccessibilityNodeInfo(View view,AccessibilityNodeInfo info){
                super.onInitializeAccessibilityNodeInfo(view,info);info.setCheckable(true);info.setChecked(view.isSelected());
            }
        });
        return b;
    }
    private void toggleLabel(Button b,String label,boolean on){
        b.setSelected(on);
        b.setText(activity.getString(R.string.menu_toggle_value,label,s(on?R.string.menu_on:R.string.menu_off)));
    }
    /** A choice of more than two values as an arrow cell (ArrowSelector), lit while it is not off (step 0). */
    private ArrowSelector selector(MenuLayout.Buttons parent,int name,String[] labels,int[] choices,int selected,
                                   Changed<Integer> changed){
        int index=0;
        for(int i=0;i<choices.length;i++)if(choices[i]==selected)index=i;
        ArrowSelector a=new ArrowSelector(activity,s(name),labels,index);
        style(a);a.finishLook();a.setOffIndex(0);
        a.setListener(step->changed.accept(choices[step]));
        parent.addButton(a);
        return a;
    }
    /** The cells' look: the buttons' surface, the focus a light frame. */
    private StateListDrawable cellLook(){
        StateListDrawable state=new StateListDrawable();
        state.addState(new int[]{android.R.attr.state_focused},focused(SURFACE));
        state.addState(new int[0],shape(SURFACE,BORDER,6));
        return state;
    }
    /** A slider as a cell (SliderCell): steps 0 .. max, the value as `format` says, kept as the caller keeps it. */
    private SliderCell sliderCell(MenuLayout.Buttons parent,String label,int max,int progress,
                                  java.util.function.IntFunction<String> format,java.util.function.IntConsumer moved){
        SliderCell cell=new SliderCell(activity,label,cellLook());
        cell.setId(View.generateViewId());
        cell.setUp(max,progress,format,moved);
        parent.addButton(cell);
        return cell;
    }
    /** One of the per-cent sliders (KEYS): MIN .. MAX in steps of STEP, kept at once. */
    private SliderCell percentCell(MenuLayout.Buttons parent,int label,int index){
        SliderCell cell=sliderCell(parent,s(label),(MAX[index]-MIN[index])/STEP,(values[index]-MIN[index])/STEP,
            p->(MIN[index]+p*STEP)+" %",p->{
                values[index]=MIN[index]+p*STEP;
                apply();prefs.edit().putInt(KEYS[index],values[index]).apply();
            });
        sliders[index]=cell;
        enableSlider(index,sliderEnabled(index));
        return cell;
    }
    private void enableSlider(int index,boolean enabled){
        if(sliders[index]==null)return;
        sliders[index].setEnabled(enabled);sliders[index].setFocusable(enabled);
    }
    private boolean sliderEnabled(int index){
        if(index==GYRO)return gyroEnabled;
        if(index==LEFT_STICK)return (stickLookMask&LEFT_LOOK)!=0;
        if(index==RIGHT_STICK)return (stickLookMask&RIGHT_LOOK)!=0;
        return true;
    }
    private void refreshStickSliders(){
        int mask=nativeLookSticks();
        if(mask==stickLookMask)return;
        stickLookMask=mask;
        enableSlider(LEFT_STICK,sliderEnabled(LEFT_STICK));enableSlider(RIGHT_STICK,sliderEnabled(RIGHT_STICK));
        View focus=root.findFocus();
        if(focus!=null && !focus.isEnabled())move(View.FOCUS_DOWN);
    }

    // ---------- the menu
    void show(boolean controller){
        if(isOpen() || suspended)return;
        activity.releaseGameKeys();
        stickLookMask=nativeLookSticks();
        nativeOpen(true);activity.settingsVisibility(true);fps.pause(true);
        final LinearLayout panel=column();
        panel.setPadding(dp(20),dp(16),dp(20),dp(12));
        panel.setBackground(shape(PANEL,BORDER,10));
        panel.setAlpha(.94f);
        panel.setClickable(true);
        // as large as CubeEvil4's window: at most 1000 × 650 dp, 96 % × 94 % of the screen
        root=new FrameLayout(activity){
            @Override protected void onMeasure(int widthSpec,int heightSpec){
                int width=MeasureSpec.getSize(widthSpec),height=MeasureSpec.getSize(heightSpec);
                FrameLayout.LayoutParams box=(FrameLayout.LayoutParams)panel.getLayoutParams();
                box.width=Math.min(dp(1000),Math.round(width*.96f));
                box.height=Math.min(dp(650),Math.round(height*.94f));
                super.onMeasure(widthSpec,heightSpec);
            }
        };
        root.setBackgroundColor(DIM);root.setClickable(true);
        root.addView(panel,new FrameLayout.LayoutParams(dp(600),dp(400),Gravity.CENTER));
        back=button(s(R.string.menu_back),v->goBack());
        title=text("",22,true);
        resume=button(s(R.string.menu_resume),v->close());
        // the update button left of "Back to the game", hidden until GitHub answered (AppUpdate)
        update=button(s(R.string.menu_update),v->openPage(AppUpdate.RELEASES_PAGE));
        update.setVisibility(View.GONE);
        LinearLayout actions=row();
        LinearLayout.LayoutParams gap=new LinearLayout.LayoutParams(-2,-2);
        gap.setMarginEnd(dp(8));
        actions.addView(update,gap);actions.addView(resume);
        // the installed version left of the buttons, small, as CubeEvil4's (wish of the project owner,
        // 19.11.2026; until 1.1.0 in brackets after the start page's title): under the buttons where a
        // narrow window leaves no room beside them (MenuLayout.Header)
        TextView version=text("v"+BuildConfig.VERSION_NAME,14,false);
        panel.addView(new MenuLayout.Header(activity,back,title,version,actions),new LinearLayout.LayoutParams(-1,-2));
        separator(panel);
        scroll=new ScrollView(activity);scroll.setFillViewport(false);
        body=column();body.setPadding(0,dp(4),0,dp(8));
        scroll.addView(body);
        panel.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        parent.addView(root,new ViewGroup.LayoutParams(-1,-1));
        java.util.Arrays.fill(scrollY,0);page=HOME;lastMotion=0;lastDirection=0;
        showPage(HOME,controller);
        AppUpdate.check(activity,updates);
        root.post(refreshStickRoles);
    }
    void close(){
        if(!isOpen())return;
        root.removeCallbacks(refreshStickRoles);
        parent.removeView(root);root=null;body=null;scroll=null;title=null;cheatStatus=null;
        back=resume=update=null;java.util.Arrays.fill(navigation,null);
        java.util.Arrays.fill(sliders,null);
        ++serial;
        nativeOpen(false);activity.settingsVisibility(false);fps.pause(false);
    }
    void suspend(){suspended=true;close();}
    void resume(){suspended=false;}
    /** Back (B, the system's): a page back to the start, from the start into the game. */
    void goBack(){
        if(!isOpen())return;
        if(page==HOME){close();return;}
        int from=page;
        showPage(HOME,false);
        if(navigation[from]!=null && !root.isInTouchMode())navigation[from].requestFocus();
    }
    private final AppUpdate.Listener updates=this::showUpdate;
    private void showUpdate(int state){
        if(update==null)return;
        if(state==AppUpdate.UNKNOWN){update.setVisibility(View.GONE);return;}
        boolean older=state==AppUpdate.OLDER;
        int fill=older?UPDATE_RED:UPDATE_GREEN,stroke=older?UPDATE_RED_EDGE:UPDATE_GREEN_EDGE;
        StateListDrawable look=new StateListDrawable();
        look.addState(new int[]{android.R.attr.state_pressed},shape(stroke,INK,6));
        look.addState(new int[]{android.R.attr.state_focused},focused(fill));
        look.addState(new int[0],shape(fill,stroke,6));
        update.setBackground(look);
        update.setTextColor(INK);
        update.setText(s(older?R.string.menu_update:R.string.menu_up_to_date));
        update.setEnabled(older);update.setFocusable(older);
        update.setVisibility(View.VISIBLE);
    }
    private void showPage(int next,boolean focus){
        scrollY[page]=scroll.getScrollY();page=next;++serial;
        body.removeAllViews();cheatStatus=null;
        java.util.Arrays.fill(sliders,null);
        back.setVisibility(page==HOME?View.GONE:View.VISIBLE);
        int[] titles={R.string.menu_title,R.string.menu_display,R.string.menu_controls,R.string.menu_audio,R.string.menu_cheats};
        title.setText(s(titles[page]));
        if(page==HOME)home();else if(page==DISPLAY)display();else if(page==CONTROLS)controls();
        else if(page==AUDIO)audio();else cheats();
        separator(body);
        TextView footer=text(s(R.string.menu_navigation),14,false);
        footer.setPadding(0,dp(8),0,0);body.addView(footer);
        final int shown=page;
        scroll.post(()->{if(isOpen() && page==shown)scroll.scrollTo(0,scrollY[shown]);});
        if(focus)(page==HOME?resume:back).requestFocusFromTouch();
    }
    private Button nav(MenuLayout.Buttons parent,int title,int summary,int target){
        SpannableStringBuilder label=new SpannableStringBuilder(s(title)+"   ›\n");
        int from=label.length();label.append(s(summary));
        label.setSpan(new StyleSpan(Typeface.BOLD),0,from,Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        label.setSpan(new RelativeSizeSpan(15f/19f),from,label.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        label.setSpan(new StyleSpan(Typeface.NORMAL),from,label.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        Button b=cellAction(parent,label.toString(),v->showPage(target,!root.isInTouchMode()));
        b.setTypeface(Typeface.DEFAULT,Typeface.NORMAL);b.setTextSize(19);
        b.setText(label);b.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
        b.setMinHeight(dp(66));b.setMinimumHeight(dp(66));return b;
    }
    private void home(){
        heading(R.string.menu_settings);
        MenuLayout.Buttons first=buttonsRow(2),second=buttonsRow(2);
        navigation[DISPLAY]=nav(first,R.string.menu_display,R.string.menu_display_summary,DISPLAY);
        navigation[CONTROLS]=nav(first,R.string.menu_controls,R.string.menu_controls_summary,CONTROLS);
        navigation[AUDIO]=nav(second,R.string.menu_audio,R.string.menu_audio_summary,AUDIO);
        navigation[CHEATS]=nav(second,R.string.menu_cheats,R.string.menu_cheats_summary,CHEATS);
        // where the port is (as CubeEvil4's menu says it; wish of the project owner, 02.11.2026)
        heading(R.string.menu_source);
        cellAction(buttonsRow(1),activity.getString(R.string.menu_source_line,SOURCE_URL),v->openPage(SOURCE_URL));
    }
    /** A page in the browser: the source, the releases (the update button). */
    private void openPage(String url){
        try{
            activity.startActivity(new android.content.Intent(android.content.Intent.ACTION_VIEW,android.net.Uri.parse(url)));
        }catch(android.content.ActivityNotFoundException e){
            Toast.makeText(activity,s(R.string.menu_no_browser),Toast.LENGTH_SHORT).show();
        }
    }
    private void display(){
        heading(R.string.menu_picture);
        MenuLayout.Buttons image=pair(labelled(R.string.menu_side_image));
        percentCell(image,R.string.menu_brightness,BRIGHTNESS);
        percentCell(image,R.string.menu_gamma,GAMMA);
        MenuLayout.Buttons rate=pair(labelled(R.string.menu_side_frame_rate));
        toggle(rate,s(R.string.menu_sixty_fps),sixtyFps,on->{
            sixtyFps=on;apply();prefs.edit().putBoolean("sixty_fps",on).apply();fps.configure(fpsDisplay,sixtyFps);
        });
        // the FPS display as CubeEvil4's (wish of the project owner, 02.11.2026)
        toggle(rate,s(R.string.menu_fps_display),fpsDisplay,on->{
            fpsDisplay=on;prefs.edit().putBoolean("fps_display",on).apply();fps.configure(fpsDisplay,sixtyFps);
        });
        help(R.string.menu_sixty_fps_help);
        // the resolution and the upscaler as CubeEvil4's (1.1.0; wish of the project owner, 22.11.2026)
        MenuLayout.Buttons size=pair(labelled(R.string.menu_side_resolution));
        final int screenLines=screenLines();
        ArrowSelector[] upscaling=new ArrowSelector[1];
        selector(size,R.string.menu_resolution,new String[]{s(R.string.menu_resolution_original),"720p","1080p",
            s(R.string.menu_resolution_native)},RESOLUTIONS,resolutionLines,lines->{
            resolutionLines=lines;nativeResolution(lines);prefs.edit().putInt("resolution",lines).apply();
            enableUpscaler(upscaling[0],upscales(lines,screenLines));
        });
        upscaling[0]=selector(size,R.string.menu_upscaler,new String[]{s(R.string.menu_upscaler_linear),
            s(R.string.menu_upscaler_sgsr),s(R.string.menu_upscaler_fsr)},UPSCALERS,upscalerChoice,choice->{
            upscalerChoice=choice;nativeUpscaler(choice);prefs.edit().putInt("upscaler",choice).apply();
        });
        enableUpscaler(upscaling[0],upscales(resolutionLines,screenLines));
        help(R.string.menu_resolution_help);
        help(R.string.menu_upscaler_help);
        heading(R.string.menu_graphics);
        final int limit=nativeMsaaLimit();
        MenuLayout.Buttons edges=pair(labelled(R.string.menu_side_edges));
        ArrowSelector msaa=selector(edges,R.string.menu_msaa,new String[]{s(R.string.menu_off),"2×","4×"},MSAA,msaaSamples,samples->{
            msaaSamples=samples;nativeMsaa(samples);prefs.edit().putInt("msaa",samples).apply();
        });
        for(int i=0;i<MSAA.length;i++)msaa.setAllowed(i,msaaOffered(MSAA[i],limit));
        // FXAA as CubeEvil4's (wish of the project owner, 02.11.2026): beside MSAA, on its own or with it
        toggle(edges,s(R.string.menu_fxaa),fxaa,on->{
            fxaa=on;nativeFxaa(on);prefs.edit().putBoolean("fxaa",on).apply();
        });
        help(limit==0?R.string.menu_msaa_none:R.string.menu_msaa_help);
        help(R.string.menu_fxaa_help);
        // a slider across both columns, off to 16× (wish of the project owner, 22.11.2026)
        MenuLayout.Buttons textures=single(labelled(R.string.menu_side_textures));
        int filterStep=0;
        for(int i=0;i<FILTERS.length;i++)if(FILTERS[i]==textureFilter)filterStep=i;
        sliderCell(textures,s(R.string.menu_texture_filter),FILTERS.length-1,filterStep,
            p->p==0?s(R.string.menu_off):FILTERS[p]+"×",p->{
                textureFilter=FILTERS[p];nativeTextureFilter(textureFilter);
                prefs.edit().putInt("texture_filter",textureFilter).apply();
            });
        help(R.string.menu_texture_filter_help);
        // the switch and its strength side by side (wish of the project owner, 02.11.2026)
        MenuLayout.Buttons focus=pair(labelled(R.string.menu_side_focus));
        SliderCell[] strength=new SliderCell[1];
        toggle(focus,s(R.string.menu_dof),depthOfField,on->{
            depthOfField=on;nativeDepthOfField(on);prefs.edit().putBoolean("depth_of_field",on).apply();
            strength[0].setEnabled(on);strength[0].setFocusable(on);
        });
        strength[0]=sliderCell(focus,s(R.string.menu_dof_strength),(DOF_MAX-DOF_MIN)/DOF_STEP,(dofStrength-DOF_MIN)/DOF_STEP,
            p->(DOF_MIN+p*DOF_STEP)+" %",p->{
                dofStrength=DOF_MIN+p*DOF_STEP;nativeDepthOfFieldStrength(dofStrength);
                prefs.edit().putInt("depth_of_field_strength",dofStrength).apply();
            });
        strength[0].setEnabled(depthOfField);strength[0].setFocusable(depthOfField);
        help(R.string.menu_dof_help);
    }
    /** The game's screen's lines: the surface the menu lies over (the display's while it is not laid out yet). */
    private int screenLines(){
        int h=parent.getHeight();
        if(h<=0){
            android.util.DisplayMetrics m=activity.getResources().getDisplayMetrics();
            h=Math.min(m.heightPixels,m.widthPixels);
        }
        return h;
    }
    private static void enableUpscaler(ArrowSelector upscaler,boolean enabled){
        upscaler.setEnabled(enabled);upscaler.setFocusable(enabled);
    }
    private void controls(){
        // the touch controls Auto, Always or Never, as CubeEvil4's (wish of the project owner, 23.11.2026)
        heading(R.string.menu_touch);
        MenuLayout.Buttons touch=single(labelled(R.string.menu_side_touch));
        selector(touch,R.string.menu_touch_controls,new String[]{s(R.string.menu_touch_auto),s(R.string.menu_touch_always),
            s(R.string.menu_touch_never)},new int[]{HaloPort.TOUCH_AUTO,HaloPort.TOUCH_ALWAYS,HaloPort.TOUCH_NEVER},touchSetting,setting->{
            touchSetting=setting;activity.touchControls(setting);prefs.edit().putInt(HaloPort.TOUCH_KEY,setting).apply();
        });
        help(R.string.menu_touch_help);
        heading(R.string.menu_motion);
        boolean available=activity.motionAvailable();
        LinearLayout gyroGroup=labelled(R.string.menu_side_gyro);
        MenuLayout.Buttons gyro=pair(gyroGroup);
        Button[] invert=new Button[1];
        Button enable=toggle(gyro,s(R.string.menu_gyro)+(available?"":" ("+s(R.string.menu_gyro_none)+")"),gyroEnabled,on->{
            gyroEnabled=on && activity.motionAvailable();apply();prefs.edit().putBoolean("gyro_aim",gyroEnabled).apply();
            invert[0].setEnabled(gyroEnabled);enableSlider(GYRO,gyroEnabled);
        });
        enable.setEnabled(available);
        invert[0]=toggle(gyro,s(R.string.menu_gyro_invert),gyroInvertPitch,on->{
            gyroInvertPitch=on;apply();prefs.edit().putBoolean("gyro_invert_pitch",on).apply();
        });
        invert[0].setEnabled(gyroEnabled);
        // the sensitivity across both columns (wish of the project owner, 22.11.2026)
        percentCell(single(gyroGroup),R.string.menu_gyro_sensitivity,GYRO);
        heading(R.string.menu_sticks);
        MenuLayout.Buttons look=pair(labelled(R.string.menu_side_look));
        percentCell(look,R.string.menu_left_stick,LEFT_STICK);
        percentCell(look,R.string.menu_right_stick,RIGHT_STICK);
        help(R.string.menu_sticks_help);
        // keyboard and mouse (wish of the project owner, 22.11.2026): the mouse's speed and Y axis, the keys
        heading(R.string.menu_keyboard_mouse);
        MenuLayout.Buttons mouse=pair(labelled(R.string.menu_side_mouse));
        sliderCell(mouse,s(R.string.menu_mouse_sensitivity),(MOUSE_MAX-MOUSE_MIN)/MOUSE_STEP,(mouseSensitivity-MOUSE_MIN)/MOUSE_STEP,
            p->(MOUSE_MIN+p*MOUSE_STEP)+" %",p->{
                mouseSensitivity=MOUSE_MIN+p*MOUSE_STEP;apply();prefs.edit().putInt("mouse_sensitivity",mouseSensitivity).apply();
            });
        toggle(mouse,s(R.string.menu_mouse_invert),mouseInvert,on->{
            mouseInvert=on;apply();prefs.edit().putBoolean("mouse_invert",on).apply();
        });
        help(R.string.menu_mouse_help);
        // the side label beside the first key line, not centred on a 64 dp cell (wish of the project owner, 23.11.2026)
        TextView keysLabel=rowLabel(s(R.string.menu_side_keys));
        keysLabel.setMinHeight(0);keysLabel.setMinimumHeight(0);
        keysLabel.setGravity(Gravity.START|Gravity.TOP);
        keysLabel.setPaddingRelative(dp(MenuLayout.GAP),dp(MenuLayout.GAP+6),dp(8),0);
        keyOverview(labelled(keysLabel));
        help(R.string.menu_keys_help);
    }
    /** The keys as a table in two columns where there is room: what it does (small) and the keys (bold);
     *  text only, the focus passes it by. */
    private void keyOverview(LinearLayout group){
        MenuLayout.Buttons table=new MenuLayout.Buttons(activity,2);
        for(int[] key:KEY_ROWS){
            LinearLayout line=row();
            line.setPadding(dp(10),dp(6),dp(10),dp(6));
            line.setBackground(shape(PANEL,BORDER,6));
            line.setFocusable(false);
            TextView what=text(s(key[0]),14,false);
            TextView keys=text(s(key[1]),15,true);keys.setGravity(Gravity.END);
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,-2,1);lp.setMarginEnd(dp(10));
            line.addView(what,lp);
            line.addView(keys,new LinearLayout.LayoutParams(-2,-2));
            line.setContentDescription(s(key[0])+": "+s(key[1]));
            table.addButton(line);
        }
        group.addView(table,new LinearLayout.LayoutParams(-1,-2));
    }
    private void audio(){
        heading(R.string.menu_volumes);
        LinearLayout sound=labelled(R.string.menu_side_sound);
        // the master volume across both columns, effects and music under it (wish of the project owner, 22.11.2026)
        percentCell(single(sound),R.string.menu_master,MASTER);
        MenuLayout.Buttons parts=pair(sound);
        percentCell(parts,R.string.menu_effects,EFFECTS);
        percentCell(parts,R.string.menu_music,MUSIC);
    }
    private void cheats(){
        heading(R.string.menu_cheat_switches);
        int[] labels={R.string.menu_cheat_health,R.string.menu_cheat_ammo,R.string.menu_cheat_reload,R.string.menu_cheat_onehit};
        int[] bits={CHEAT_HEALTH,CHEAT_AMMO,CHEAT_RELOAD,CHEAT_ONE_HIT};
        LinearLayout player=labelled(R.string.menu_side_switches);
        MenuLayout.Buttons first=pair(player),second=pair(player);
        for(int i=0;i<labels.length;i++){
            final int bit=bits[i];
            toggle(i<2?first:second,s(labels[i]),(cheatBits&bit)!=0,on->{
                cheatBits=toggled(cheatBits,bit,on);nativeCheats(cheatBits);prefs.edit().putInt("cheats",cheatBits).apply();
            });
        }
        heading(R.string.menu_cheat_actions);
        LinearLayout objects=labelled(R.string.menu_side_objects);
        // all weapons across both columns, the vehicles two by two under it (wish of the project owner, 26.11.2026)
        cellAction(single(objects),s(ACTION_LABELS[ACTION_WEAPONS]),v->cheatAction(v,ACTION_WEAPONS));
        MenuLayout.Buttons vehicles=null;
        for(int what=ACTION_WARTHOG;what<=ACTION_BANSHEE;what++){
            if((what-ACTION_WARTHOG)%2==0)vehicles=pair(objects);
            final int action=what;
            cellAction(vehicles,s(ACTION_LABELS[what]),v->cheatAction(v,action));
        }
        cheatStatus=text("",15,false);cheatStatus.setPadding(dp(MenuLayout.GAP),dp(6),dp(MenuLayout.GAP),dp(2));
        cheatStatus.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);cheatStatus.setVisibility(View.GONE);
        objects.addView(cheatStatus);
        help(R.string.menu_cheats_help);
        // the campaign's ten levels, the profile's progress kept (ui_widget_event_handler_functions.c, player_profile.c)
        heading(R.string.menu_general);
        toggle(single(labelled(R.string.menu_side_campaign)),s(R.string.menu_campaign_unlock),campaignUnlocked,on->{
            campaignUnlocked=on;nativeCampaignUnlocked(on);prefs.edit().putBoolean("campaign_unlocked",on).apply();
        });
        help(R.string.menu_campaign_help);
    }
    /** A button lit for a moment; the game does it in its next frame (cheats.c) and answers. */
    private void cheatAction(View pressed,int what){
        pressed.setSelected(true);
        final int mine=serial;
        root.postDelayed(()->pressed.setSelected(false),CHEAT_FLASH_MS);
        nativeCheatAction(what);
        final long until=android.os.SystemClock.uptimeMillis()+CHEAT_WAIT_MS;
        root.post(new Runnable(){
            public void run(){
                if(!isOpen() || serial!=mine || cheatStatus==null)return;
                int result=nativeCheatResult(what);
                if(result==RESULT_PENDING && android.os.SystemClock.uptimeMillis()<until){root.postDelayed(this,50);return;}
                cheatStatus.setText(cheatAnswer(what,result));cheatStatus.setVisibility(View.VISIBLE);
            }
        });
    }
    private void apply(){
        HaloPort.nativeVolumes(values[MASTER],values[EFFECTS],values[MUSIC]);nativeDisplay(values[BRIGHTNESS],values[GAMMA]);
        activity.motionSettings(gyroEnabled,values[GYRO],gyroInvertPitch);
        nativeSticks(values[LEFT_STICK],values[RIGHT_STICK]);
        nativeFrameRate(sixtyFps);
        nativeMouseLook(mouseSensitivity,mouseInvert);
    }

    // ---------- the controller
    /** Focus to the next view that way; the first press after touching shows where the focus is. */
    private void move(int direction){
        View focused=root.findFocus();
        if(focused==null || root.isInTouchMode()){
            View start=focused!=null?focused:page==HOME?resume:back;
            start.requestFocusFromTouch();
            return;
        }
        View next=FocusFinder.getInstance().findNextFocus(root,focused,direction);
        if(next!=null)next.requestFocus(direction);
        // past the last cell (or above the first) the text there scrolls into sight: the key overview, the help
        else if(direction==View.FOCUS_DOWN)scroll.smoothScrollTo(0,body.getHeight());
        else if(direction==View.FOCUS_UP)scroll.smoothScrollTo(0,0);
    }
    /** L1 / R1 on an arrow or slider cell: a step back or on. */
    private void step(int direction){
        View focused=root.findFocus();
        if(focused==null || root.isInTouchMode())return;
        if(focused instanceof ArrowSelector)((ArrowSelector)focused).step(direction);
        else if(focused instanceof SliderCell)((SliderCell)focused).step(direction);
    }
    boolean key(KeyEvent event){
        if(!isOpen())return false;
        int what=action(event.getKeyCode());
        if(what==PASS)return false;
        if(event.getAction()!=KeyEvent.ACTION_DOWN)return true;
        boolean first=event.getRepeatCount()==0;
        switch(what){
            case UP: move(View.FOCUS_UP);break;
            case DOWN: move(View.FOCUS_DOWN);break;
            case LEFT: move(View.FOCUS_LEFT);break;
            case RIGHT: move(View.FOCUS_RIGHT);break;
            case PRESS:
                if(!first)break;
                View focused=root.findFocus();
                if(focused==null || root.isInTouchMode())move(View.FOCUS_DOWN);
                else if(!(focused instanceof SliderCell))focused.performClick();
                break;
            case STEP_BACK: step(-1);break;
            case STEP_ON: step(1);break;
            case BACK: if(first)goBack();break;
            case CLOSE: if(first)close();break;
            default: break;
        }
        return true;
    }
    /** A controller's stick or D-pad moves the focus; the mouse does not (its axes are the pointer's place on
     *  the screen: they moved the focus away from the pointer, 22.11.2026), Android hovers and clicks with it. */
    void motion(MotionEvent e){
        if(!isOpen() || !e.isFromSource(android.view.InputDevice.SOURCE_JOYSTICK))return;
        float x=e.getAxisValue(MotionEvent.AXIS_HAT_X),y=e.getAxisValue(MotionEvent.AXIS_HAT_Y);
        if(Math.abs(x)<.5f && Math.abs(y)<.5f){x=e.getAxisValue(MotionEvent.AXIS_X);y=e.getAxisValue(MotionEvent.AXIS_Y);}
        if(Math.abs(x)<.55f && Math.abs(y)<.55f){lastMotion=0;lastDirection=0;return;}
        int direction=Math.abs(y)>Math.abs(x)?(y<0?View.FOCUS_UP:View.FOCUS_DOWN):(x<0?View.FOCUS_LEFT:View.FOCUS_RIGHT);
        long now=android.os.SystemClock.uptimeMillis();
        // a held direction repeats after a pause, as a held key does
        if(direction==lastDirection && now-lastMotion<(lastMotion==0?0:220))return;
        lastMotion=now;lastDirection=direction;
        move(direction);
    }
}
