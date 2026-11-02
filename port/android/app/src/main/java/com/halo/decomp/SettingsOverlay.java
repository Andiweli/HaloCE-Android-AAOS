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
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;
import java.util.Locale;

/**
 * The in-game menu (SELECT held, or the touch controls' menu button), laid out as CubeEvil4's in Halo's
 * colours (wish of the project owner, 02.11.2026): "HALO CE In-Game Menu (vX)" with the update button and
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
    static native void nativeCheatAction(int action);
    static native int nativeCheatResult(int action);
    static native void nativeMsaa(int samples);
    static native void nativeDepthOfField(boolean on);
    static native int nativeMsaaLimit();
    static native void nativeFxaa(boolean on);

    static final int HOME=0, DISPLAY=1, CONTROLS=2, AUDIO=3, CHEATS=4;
    // Halo's blues instead of CubeEvil4's greens and gold; the update button keeps green and red
    static final int PANEL=0xff0e1a24, SURFACE=0xff16273a, BORDER=0xff2f4a63, INK=0xffe6f0f5,
        MUTED=0xff8fa9bd, ACCENT=0xff6ec6ff, ACTIVE=0xff1f3d57, DISABLED=0xff5a6b7a, DIM=0xb8000000;
    static final int UPDATE_GREEN=0xff2d5233, UPDATE_GREEN_EDGE=0xff4f8a57,
        UPDATE_RED=0xff7a2a26, UPDATE_RED_EDGE=0xffb2463f;
    private static final int LEFT_LOOK=1, RIGHT_LOOK=2;
    // the sliders: their keys in "halo_android_controls", their ranges in per cent
    static final int MASTER=0, EFFECTS=1, MUSIC=2, BRIGHTNESS=3, GAMMA=4, GYRO=5, LEFT_STICK=6, RIGHT_STICK=7;
    static final String[] KEYS={"master","effects","music","brightness","gamma","gyro_sensitivity","left_stick_sensitivity","right_stick_sensitivity"};
    static final int[] MIN={0,0,0,50,50,25,50,50}, MAX={100,100,100,150,200,200,150,150};
    static final int STEP=5;
    // the texture filtering's choices (texels along a pixel's footprint; 1 off); 4 as the configuration's
    static final int[] FILTERS={1,2,4,8};
    static final int DEFAULT_FILTER=4;
    // MSAA's choices (samples; 0 off), off by default
    static final int[] MSAA={0,2,4};
    static final String SOURCE_URL="https://github.com/Andiweli/HaloCE-Android-AAOS";
    // the cheats: the switches' bits and the buttons as halo_android_controls.h numbers them
    static final int CHEAT_HEALTH=1, CHEAT_AMMO=2, CHEAT_RELOAD=4, CHEAT_ONE_HIT=8, CHEAT_SWITCHES=15;
    static final int ACTION_WEAPONS=0, ACTION_WARTHOG=1;
    static final int RESULT_NONE=0, RESULT_PENDING=1, RESULT_DONE=2, RESULT_MISSING=3, RESULT_NO_GAME=4;
    private static final long CHEAT_FLASH_MS=1500, CHEAT_WAIT_MS=3000;

    /** What a key does in the menu; NONE: the game never sees it, PASS: Android's (the volume keys). */
    static final int NONE=0, PASS=1, UP=2, DOWN=3, LEFT=4, RIGHT=5, PRESS=6, BACK=7, CLOSE=8;
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
            default: return NONE;
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
    private int textureFilter, cheatBits, msaaSamples;
    private boolean depthOfField, fxaa;
    private FrameLayout root;
    private LinearLayout body;
    private ScrollView scroll;
    private TextView title, cheatStatus;
    private Button back, resume, update;
    private final Button[] navigation=new Button[CHEATS+1];
    private final int[] scrollY=new int[CHEATS+1];
    private final SeekBar[] sliders=new SeekBar[KEYS.length];
    private final View[] sliderRows=new View[KEYS.length];
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
        msaaSamples=msaa(prefs.getInt("msaa",0));
        depthOfField=prefs.getBoolean("depth_of_field",false);
        fxaa=prefs.getBoolean("fxaa",false);
        apply();
        nativeTextureFilter(textureFilter);
        nativeCheats(cheatBits);
        nativeMsaa(msaaSamples);
        nativeDepthOfField(depthOfField);
        nativeFxaa(fxaa);
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
        state.addState(new int[]{android.R.attr.state_focused,android.R.attr.state_selected},focused(ACTIVE));
        state.addState(new int[]{android.R.attr.state_focused},focused(SURFACE));
        state.addState(new int[]{android.R.attr.state_pressed},shape(ACTIVE,ACCENT,6));
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
    private void heading(int id){
        TextView v=text(s(id).toUpperCase(Locale.getDefault()),14,true);v.setTextColor(MUTED);v.setLetterSpacing(.08f);
        v.setPadding(0,dp(16),0,dp(8));body.addView(v);
    }
    private void help(int id){
        TextView t=text(s(id),15,false);t.setPadding(0,dp(4),0,dp(8));body.addView(t);
    }
    /** Row label as tall as one button row, centred on it. */
    private TextView rowLabel(String label){
        TextView caption=text(label,16,true);
        caption.setPadding(0,0,dp(8),0);caption.setMinHeight(dp(48+2*MenuLayout.GAP));caption.setMinimumHeight(dp(48+2*MenuLayout.GAP));
        caption.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
        return caption;
    }
    private MenuLayout.Buttons buttonsRow(int columns){
        MenuLayout.Buttons buttons=new MenuLayout.Buttons(activity,columns);
        body.addView(buttons,new LinearLayout.LayoutParams(-1,-2));return buttons;
    }
    /** A row of buttons in the choices' column, left-aligned with their buttons (CubeEvil4's labelledOptions(0));
     *  narrow, where the choices stack under their labels, across the whole width. */
    private MenuLayout.Buttons optionsRow(){
        MenuLayout.Columns outer=new MenuLayout.Columns(activity,170,640,true);
        outer.addView(new View(activity));
        MenuLayout.Buttons buttons=new MenuLayout.Buttons(activity,1);
        outer.addView(buttons);
        body.addView(outer);
        return buttons;
    }
    private Button cellAction(MenuLayout.Buttons parent,String label,View.OnClickListener click){
        Button b=button(label,click);parent.addButton(b);return b;
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
    /** One choice of several in a row beside its label, the chosen one lit. */
    private interface Offered { boolean test(int choice); }
    private Button[] choices(int label,String[] labels,int[] choices,int selected,Changed<Integer> changed){
        return choices(label,labels,choices,selected,choice->true,changed);
    }
    private Button[] choices(int label,String[] labels,int[] choices,int selected,Offered offered,Changed<Integer> changed){
        MenuLayout.Columns outer=new MenuLayout.Columns(activity,170,640,false);
        outer.addView(rowLabel(s(label)));
        MenuLayout.Buttons options=new MenuLayout.Buttons(activity,labels.length);
        outer.addView(options);
        Button[] buttons=new Button[labels.length];
        for(int i=0;i<labels.length;i++){
            final int index=i;
            Button b=cellAction(options,labels[i],v->{select(buttons,labels,index);changed.accept(choices[index]);});
            b.setEnabled(offered.test(choices[i]));
            buttons[i]=b;
        }
        for(int i=0;i<labels.length;i++)if(choices[i]==selected)select(buttons,labels,i);
        body.addView(outer);
        return buttons;
    }
    private void select(Button[] buttons,String[] labels,int index){
        for(int k=0;k<buttons.length;k++){
            buttons[k].setSelected(k==index);
            buttons[k].setContentDescription(labels[k]+", "+s(k==index?R.string.menu_on:R.string.menu_off));
        }
    }
    /** A slider as a row: its label, the bar, its value in per cent; kept at once. */
    private void slider(int label,int index){
        MenuLayout.Columns line=new MenuLayout.Columns(activity,170,520,false);
        line.addView(rowLabel(s(label)));
        LinearLayout controls=row();
        SeekBar bar=new SeekBar(activity);
        TextView value=text(values[index]+" %",15,false);
        value.setGravity(Gravity.END|Gravity.CENTER_VERTICAL);value.setMinWidth(dp(56));
        controls.addView(bar,new LinearLayout.LayoutParams(0,dp(48),1));
        controls.addView(value);
        line.addView(controls);
        bar.setMax(MAX[index]-MIN[index]);bar.setProgress(values[index]-MIN[index]);
        bar.setKeyProgressIncrement(STEP);bar.setContentDescription(s(label));
        bar.setProgressTintList(ColorStateList.valueOf(ACCENT));bar.setThumbTintList(ColorStateList.valueOf(ACCENT));
        bar.setProgressBackgroundTintList(ColorStateList.valueOf(BORDER));
        GradientDrawable ring=new GradientDrawable();ring.setColor(0);ring.setCornerRadius(dp(6));ring.setStroke(dp(2),INK);
        StateListDrawable look=new StateListDrawable();
        look.addState(new int[]{android.R.attr.state_focused},ring);
        look.addState(new int[0],new GradientDrawable());
        bar.setBackground(look);
        bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
            public void onProgressChanged(SeekBar b,int progress,boolean fromUser){
                values[index]=progress+MIN[index];value.setText(values[index]+" %");
                apply();prefs.edit().putInt(KEYS[index],values[index]).apply();
            }
            public void onStartTrackingTouch(SeekBar b){}
            public void onStopTrackingTouch(SeekBar b){}
        });
        sliders[index]=bar;sliderRows[index]=line;
        enableSlider(index,sliderEnabled(index));
        body.addView(line);
    }
    private void enableSlider(int index,boolean enabled){
        if(sliders[index]==null)return;
        sliders[index].setEnabled(enabled);sliders[index].setFocusable(enabled);
        sliderRows[index].setAlpha(enabled?1f:.5f);
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
        nativeOpen(true);activity.settingsVisibility(true);
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
        update=button(s(R.string.menu_update),v->AppUpdate.install(activity,updates));
        update.setVisibility(View.GONE);
        LinearLayout actions=row();
        LinearLayout.LayoutParams gap=new LinearLayout.LayoutParams(-2,-2);
        gap.setMarginEnd(dp(8));
        actions.addView(update,gap);actions.addView(resume);
        panel.addView(new MenuLayout.Header(activity,back,title,actions),new LinearLayout.LayoutParams(-1,-2));
        separator(panel);
        scroll=new ScrollView(activity);scroll.setFillViewport(false);
        body=column();body.setPadding(0,dp(4),0,dp(8));
        scroll.addView(body);
        panel.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        parent.addView(root,new ViewGroup.LayoutParams(-1,-1));
        java.util.Arrays.fill(scrollY,0);page=HOME;lastMotion=0;lastDirection=0;
        showPage(HOME,controller);
        if(AppUpdate.loading())updates.progress(0,null);else AppUpdate.check(activity,updates);
        root.post(refreshStickRoles);
    }
    void close(){
        if(!isOpen())return;
        root.removeCallbacks(refreshStickRoles);
        parent.removeView(root);root=null;body=null;scroll=null;title=null;cheatStatus=null;
        back=resume=update=null;java.util.Arrays.fill(navigation,null);
        java.util.Arrays.fill(sliders,null);java.util.Arrays.fill(sliderRows,null);
        ++serial;
        nativeOpen(false);activity.settingsVisibility(false);
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
    private final AppUpdate.Listener updates=new AppUpdate.Listener(){
        @Override public void checked(int state){showUpdate(state);}
        @Override public void progress(int percent,String problem){
            if(percent<0){
                if(problem!=null)Toast.makeText(activity,problem,Toast.LENGTH_LONG).show();
                showUpdate(AppUpdate.OLDER);
                return;
            }
            if(update==null)return;
            showUpdate(AppUpdate.OLDER);
            update.setEnabled(false);
            update.setText(percent>=100?s(R.string.menu_update_install):activity.getString(R.string.menu_update_loading,percent));
        }
    };
    private void showUpdate(int state){
        if(update==null)return;
        if(state==AppUpdate.UNKNOWN){update.setVisibility(View.GONE);return;}
        boolean older=state==AppUpdate.OLDER;
        int fill=older?UPDATE_RED:UPDATE_GREEN,stroke=older?UPDATE_RED_EDGE:UPDATE_GREEN_EDGE;
        StateListDrawable look=new StateListDrawable();
        look.addState(new int[]{android.R.attr.state_focused},focused(fill));
        look.addState(new int[]{android.R.attr.state_pressed},shape(fill,INK,6));
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
        java.util.Arrays.fill(sliders,null);java.util.Arrays.fill(sliderRows,null);
        back.setVisibility(page==HOME?View.GONE:View.VISIBLE);
        int[] titles={R.string.menu_title,R.string.menu_display,R.string.menu_controls,R.string.menu_audio,R.string.menu_cheats};
        if(page==HOME){
            SpannableStringBuilder t=new SpannableStringBuilder(s(titles[page]));
            int start=t.length();t.append(" (v").append(BuildConfig.VERSION_NAME).append(")");
            t.setSpan(new RelativeSizeSpan(.6f),start,t.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            t.setSpan(new StyleSpan(Typeface.NORMAL),start,t.length(),Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            title.setText(t);
        } else title.setText(s(titles[page]));
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
        cellAction(buttonsRow(1),activity.getString(R.string.menu_source_line,SOURCE_URL),v->openSource());
    }
    private void openSource(){
        try{
            activity.startActivity(new android.content.Intent(android.content.Intent.ACTION_VIEW,android.net.Uri.parse(SOURCE_URL)));
        }catch(android.content.ActivityNotFoundException e){
            Toast.makeText(activity,s(R.string.menu_no_browser),Toast.LENGTH_SHORT).show();
        }
    }
    private void display(){
        heading(R.string.menu_picture);
        slider(R.string.menu_brightness,BRIGHTNESS);
        slider(R.string.menu_gamma,GAMMA);
        toggle(optionsRow(),s(R.string.menu_sixty_fps),sixtyFps,on->{
            sixtyFps=on;apply();prefs.edit().putBoolean("sixty_fps",on).apply();
        });
        help(R.string.menu_sixty_fps_help);
        heading(R.string.menu_graphics);
        final int limit=nativeMsaaLimit();
        choices(R.string.menu_msaa,new String[]{s(R.string.menu_off),"2×","4×"},MSAA,msaaSamples,
            choice->msaaOffered(choice,limit),samples->{
            msaaSamples=samples;nativeMsaa(samples);prefs.edit().putInt("msaa",samples).apply();
        });
        help(limit==0?R.string.menu_msaa_none:R.string.menu_msaa_help);
        // FXAA as CubeEvil4's (wish of the project owner, 02.11.2026): under MSAA, on its own or with it
        toggle(optionsRow(),s(R.string.menu_fxaa),fxaa,on->{
            fxaa=on;nativeFxaa(on);prefs.edit().putBoolean("fxaa",on).apply();
        });
        help(R.string.menu_fxaa_help);
        choices(R.string.menu_texture_filter,new String[]{s(R.string.menu_off),"2×","4×","8×"},FILTERS,textureFilter,level->{
            textureFilter=level;nativeTextureFilter(level);prefs.edit().putInt("texture_filter",level).apply();
        });
        help(R.string.menu_texture_filter_help);
        toggle(optionsRow(),s(R.string.menu_dof),depthOfField,on->{
            depthOfField=on;nativeDepthOfField(on);prefs.edit().putBoolean("depth_of_field",on).apply();
        });
        help(R.string.menu_dof_help);
    }
    private void controls(){
        heading(R.string.menu_motion);
        boolean available=activity.motionAvailable();
        MenuLayout.Buttons gyro=buttonsRow(2);
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
        slider(R.string.menu_gyro_sensitivity,GYRO);
        heading(R.string.menu_sticks);
        slider(R.string.menu_left_stick,LEFT_STICK);
        slider(R.string.menu_right_stick,RIGHT_STICK);
        help(R.string.menu_sticks_help);
    }
    private void audio(){
        heading(R.string.menu_volumes);
        slider(R.string.menu_master,MASTER);
        slider(R.string.menu_effects,EFFECTS);
        slider(R.string.menu_music,MUSIC);
    }
    private void cheats(){
        heading(R.string.menu_cheat_switches);
        int[] labels={R.string.menu_cheat_health,R.string.menu_cheat_ammo,R.string.menu_cheat_reload,R.string.menu_cheat_onehit};
        int[] bits={CHEAT_HEALTH,CHEAT_AMMO,CHEAT_RELOAD,CHEAT_ONE_HIT};
        MenuLayout.Buttons first=buttonsRow(2),second=buttonsRow(2);
        for(int i=0;i<labels.length;i++){
            final int bit=bits[i];
            toggle(i<2?first:second,s(labels[i]),(cheatBits&bit)!=0,on->{
                cheatBits=toggled(cheatBits,bit,on);nativeCheats(cheatBits);prefs.edit().putInt("cheats",cheatBits).apply();
            });
        }
        heading(R.string.menu_cheat_actions);
        MenuLayout.Buttons spawn=buttonsRow(2);
        cellAction(spawn,s(R.string.menu_cheat_weapons),v->cheatAction(v,ACTION_WEAPONS));
        cellAction(spawn,s(R.string.menu_cheat_warthog),v->cheatAction(v,ACTION_WARTHOG));
        cheatStatus=text("",15,false);cheatStatus.setPadding(0,dp(6),0,dp(2));
        cheatStatus.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);cheatStatus.setVisibility(View.GONE);
        body.addView(cheatStatus);
        help(R.string.menu_cheats_help);
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
                int text=result==RESULT_DONE?(what==ACTION_WEAPONS?R.string.menu_cheat_weapons_done:R.string.menu_cheat_warthog_done)
                    :result==RESULT_MISSING?R.string.menu_cheat_none:R.string.menu_cheat_no_game;
                cheatStatus.setText(text);cheatStatus.setVisibility(View.VISIBLE);
            }
        });
    }
    private void apply(){
        HaloPort.nativeVolumes(values[MASTER],values[EFFECTS],values[MUSIC]);nativeDisplay(values[BRIGHTNESS],values[GAMMA]);
        activity.motionSettings(gyroEnabled,values[GYRO],gyroInvertPitch);
        nativeSticks(values[LEFT_STICK],values[RIGHT_STICK]);
        nativeFrameRate(sixtyFps);
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
        if(focused instanceof SeekBar && (direction==View.FOCUS_LEFT || direction==View.FOCUS_RIGHT)){
            SeekBar bar=(SeekBar)focused;
            for(int i=0;i<sliders.length;i++)if(sliders[i]==bar){
                bar.setProgress(stepped(i,values[i],direction==View.FOCUS_LEFT?-1:1)-MIN[i]);
                return;
            }
        }
        View next=FocusFinder.getInstance().findNextFocus(root,focused,direction);
        if(next!=null)next.requestFocus(direction);
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
                else if(!(focused instanceof SeekBar))focused.performClick();
                break;
            case BACK: if(first)goBack();break;
            case CLOSE: if(first)close();break;
            default: break;
        }
        return true;
    }
    void motion(MotionEvent e){
        if(!isOpen())return;
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
