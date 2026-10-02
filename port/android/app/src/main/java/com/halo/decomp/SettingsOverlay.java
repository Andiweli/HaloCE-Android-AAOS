package com.halo.decomp;

import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.*;

/** In-activity overlay: keeps the game surface and immersive window intact. */
final class SettingsOverlay {
    static native void nativeOpen(boolean open);
    static native void nativeDisplay(int brightness, int gamma);
    private static final String[] KEYS={"master","effects","music","brightness","gamma"};
    private static final int[] MIN={0,0,0,50,50}, MAX={100,100,100,150,200};
    private final HaloActivity activity;
    private final ViewGroup parent;
    private final SharedPreferences prefs;
    private final int[] values=new int[5], original=new int[5];
    private final SeekBar[] sliders=new SeekBar[5];
    private final View[] targets=new View[7];
    private FrameLayout root;
    private int selected;
    private long lastMotion;
    private boolean suspended;
    SettingsOverlay(HaloActivity activity,ViewGroup parent) {
        this.activity=activity;this.parent=parent;
        prefs=activity.getSharedPreferences("halo_android_controls",0);
        for(int i=0;i<5;i++)values[i]=Math.max(MIN[i],Math.min(MAX[i],prefs.getInt(KEYS[i],100)));
        apply();
    }
    boolean isOpen(){return root!=null;}
    private int dp(int n){return Math.round(n*activity.getResources().getDisplayMetrics().density);}
    private String[] strings(){
        String language=android.content.res.Resources.getSystem().getConfiguration().getLocales().get(0).getLanguage();
        switch(language){
            case "de":return new String[]{"Einstellungen","Gesamtlautstärke","Soundeffekt-Lautstärke","Musiklautstärke","Helligkeit","Gamma","OK","Abbrechen"};
            case "fr":return new String[]{"Paramètres","Volume général","Volume des effets sonores","Volume de la musique","Luminosité","Gamma","OK","Annuler"};
            case "it":return new String[]{"Impostazioni","Volume generale","Volume degli effetti sonori","Volume della musica","Luminosità","Gamma","OK","Annulla"};
            default:return new String[]{"Settings","Master volume","Sound effects volume","Music volume","Brightness","Gamma","OK","Cancel"};
        }
    }
    void show(){
        if(isOpen() || suspended)return;
        activity.releaseGameKeys();
        System.arraycopy(values,0,original,0,5);nativeOpen(true);activity.settingsVisibility(true);
        String[] labels=strings();
        root=new FrameLayout(activity);root.setBackgroundColor(Color.TRANSPARENT);root.setClickable(true);
        LinearLayout panel=new LinearLayout(activity);panel.setOrientation(LinearLayout.VERTICAL);panel.setPadding(dp(20),dp(12),dp(20),dp(12));
        GradientDrawable background=new GradientDrawable();background.setColor(0xf0182331);background.setCornerRadius(dp(12));background.setStroke(dp(1),0xff639fbd);panel.setBackground(background);
        int width=Math.min(dp(600),Math.max(dp(200),parent.getWidth()-dp(24)));
        int height=Math.max(dp(180),parent.getHeight()-dp(16));
        int rowHeight=Math.max(dp(40),Math.min(dp(48),(height-dp(108))/5));
        FrameLayout.LayoutParams box=new FrameLayout.LayoutParams(width,Math.min(height,dp(108)+5*rowHeight),Gravity.CENTER);
        root.addView(panel,box);
        TextView title=new TextView(activity);title.setText(labels[0]);title.setTextColor(Color.WHITE);title.setTextSize(22);title.setTypeface(null,Typeface.BOLD);panel.addView(title);
        ScrollView scroll=new ScrollView(activity);scroll.setFillViewport(false);
        panel.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout rows=new LinearLayout(activity);rows.setOrientation(LinearLayout.VERTICAL);scroll.addView(rows);
        for(int i=0;i<5;i++){
            final int index=i;
            LinearLayout row=new LinearLayout(activity);row.setGravity(Gravity.CENTER_VERTICAL);
            rows.addView(row,new LinearLayout.LayoutParams(-1,rowHeight));
            TextView label=new TextView(activity);label.setTextColor(Color.WHITE);label.setTextSize(16);
            label.setMaxLines(2);label.setGravity(Gravity.CENTER_VERTICAL);
            label.setAutoSizeTextTypeUniformWithConfiguration(12,16,1,android.util.TypedValue.COMPLEX_UNIT_SP);
            label.setPadding(0,0,dp(8),0);label.setText(labels[i+1]);
            row.addView(label,new LinearLayout.LayoutParams(0,-1,0.42f));
            LinearLayout controls=new LinearLayout(activity);controls.setGravity(Gravity.CENTER_VERTICAL);
            row.addView(controls,new LinearLayout.LayoutParams(0,-1,0.58f));
            TextView value=new TextView(activity);value.setTextColor(Color.WHITE);value.setTextSize(14);
            value.setGravity(Gravity.END|Gravity.CENTER_VERTICAL);value.setText(values[i]+"%");
            SeekBar slider=new SeekBar(activity);sliders[i]=slider;targets[i]=slider;
            slider.setMax(MAX[i]-MIN[i]);slider.setProgress(values[i]-MIN[i]);slider.setKeyProgressIncrement(5);
            slider.setContentDescription(labels[i+1]);slider.setFocusableInTouchMode(true);
            label.setLabelFor(View.generateViewId());slider.setId(label.getLabelFor());
            controls.addView(slider,new LinearLayout.LayoutParams(0,-1,1));
            controls.addView(value,new LinearLayout.LayoutParams(dp(48),-1));
            slider.setOnFocusChangeListener((v,focused)->{if(focused)selected=index;});
            slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
                public void onProgressChanged(SeekBar bar,int progress,boolean fromUser){values[index]=progress+MIN[index];value.setText(values[index]+"%");apply();}
                public void onStartTrackingTouch(SeekBar bar){selected=index;bar.requestFocus();}
                public void onStopTrackingTouch(SeekBar bar){}
            });
        }
        LinearLayout buttons=new LinearLayout(activity);buttons.setGravity(Gravity.END);panel.addView(buttons);
        for(int i=0;i<2;i++){
            final int index=i+5;Button button=new Button(activity);button.setText(labels[i+6]);button.setFocusableInTouchMode(true);targets[index]=button;
            if (Fullscreen.isAutomotive(activity)) {
                // Car themes supply oversized text/padding for these fixed-height buttons.
                // Keep the 48dp touch target, but fit its caption independently of the OEM style.
                button.setAllCaps(false);
                button.setSingleLine(true);
                button.setIncludeFontPadding(false);
                button.setGravity(Gravity.CENTER);
                button.setMinHeight(0);button.setMinimumHeight(0);
                button.setMinWidth(0);button.setMinimumWidth(0);
                button.setPadding(dp(12),0,dp(12),0);
                button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,16);
                button.setAutoSizeTextTypeUniformWithConfiguration(12,16,1,android.util.TypedValue.COMPLEX_UNIT_SP);
            }
            button.setOnFocusChangeListener((v,focused)->{if(focused)selected=index;});
            button.setOnClickListener(v->close(index==5));buttons.addView(button,new LinearLayout.LayoutParams(0,dp(48),1));
        }
        parent.addView(root,new ViewGroup.LayoutParams(-1,-1));selected=0;targets[0].requestFocus();lastMotion=0;
    }
    void close(boolean save){
        if(!isOpen())return;
        if(save){SharedPreferences.Editor e=prefs.edit();for(int i=0;i<5;i++)e.putInt(KEYS[i],values[i]);e.apply();}
        else{System.arraycopy(original,0,values,0,5);apply();}
        parent.removeView(root);root=null;nativeOpen(false);activity.settingsVisibility(false);
    }
    void suspend(){suspended=true;close(false);}
    void resume(){suspended=false;}
    private void apply(){HaloPort.nativeVolumes(values[0],values[1],values[2]);nativeDisplay(values[3],values[4]);}
    private void direction(int key){
        if(key==KeyEvent.KEYCODE_DPAD_UP)selected=Math.max(0,selected-1);
        else if(key==KeyEvent.KEYCODE_DPAD_DOWN)selected=Math.min(6,selected+1);
        else if(selected<5){int delta=key==KeyEvent.KEYCODE_DPAD_LEFT?-5:5;sliders[selected].setProgress(sliders[selected].getProgress()+delta);}
        else selected=key==KeyEvent.KEYCODE_DPAD_LEFT?5:6;
        targets[selected].requestFocus();
    }
    boolean key(KeyEvent event){
        if(!isOpen())return false;
        int key=event.getKeyCode();
        if(key==KeyEvent.KEYCODE_VOLUME_UP || key==KeyEvent.KEYCODE_VOLUME_DOWN || key==KeyEvent.KEYCODE_VOLUME_MUTE)return false;
        if(event.getAction()!=KeyEvent.ACTION_DOWN)return true;
        if(key==KeyEvent.KEYCODE_BUTTON_B || key==KeyEvent.KEYCODE_BACK || key==KeyEvent.KEYCODE_ESCAPE){close(false);return true;}
        if(key>=KeyEvent.KEYCODE_DPAD_UP && key<=KeyEvent.KEYCODE_DPAD_RIGHT)direction(key);
        else if((key==KeyEvent.KEYCODE_BUTTON_A || key==KeyEvent.KEYCODE_DPAD_CENTER || key==KeyEvent.KEYCODE_ENTER) && event.getRepeatCount()==0){
            if(selected>=5)targets[selected].performClick();else{selected=5;targets[selected].requestFocus();}
        }
        return true;
    }
    void motion(MotionEvent e){
        if(!isOpen())return;
        float x=e.getAxisValue(MotionEvent.AXIS_HAT_X),y=e.getAxisValue(MotionEvent.AXIS_HAT_Y);
        if(Math.abs(x)<.5f && Math.abs(y)<.5f){x=e.getAxisValue(MotionEvent.AXIS_X);y=e.getAxisValue(MotionEvent.AXIS_Y);}
        if(Math.abs(x)<.55f && Math.abs(y)<.55f){lastMotion=0;return;}
        long now=android.os.SystemClock.uptimeMillis();if(now-lastMotion<180)return;lastMotion=now;
        direction(Math.abs(y)>Math.abs(x)?(y<0?KeyEvent.KEYCODE_DPAD_UP:KeyEvent.KEYCODE_DPAD_DOWN):(x<0?KeyEvent.KEYCODE_DPAD_LEFT:KeyEvent.KEYCODE_DPAD_RIGHT));
    }
}
