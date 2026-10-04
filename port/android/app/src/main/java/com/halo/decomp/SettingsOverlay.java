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
    private static final int TEXT_SP=16, HEADING_SP=14;
    private static final int GYRO_TOGGLE=5, GYRO_SLIDER=6, OK=7, CANCEL=8;
    private static final String[] KEYS={"master","effects","music","brightness","gamma","gyro_sensitivity"};
    private static final int[] MIN={0,0,0,50,50,25}, MAX={100,100,100,150,200,200};
    private final HaloActivity activity;
    private final ViewGroup parent;
    private final SharedPreferences prefs;
    private final int[] values=new int[6], original=new int[6];
    private final SeekBar[] sliders=new SeekBar[6];
    private final View[] targets=new View[9];
    private boolean gyroEnabled, originalGyro;
    private Switch gyroSwitch;
    private FrameLayout root;
    private int selected;
    private long lastMotion;
    private boolean suspended;

    SettingsOverlay(HaloActivity activity,ViewGroup parent) {
        this.activity=activity;this.parent=parent;
        prefs=activity.getSharedPreferences("halo_android_controls",0);
        for(int i=0;i<values.length;i++)
            values[i]=Math.max(MIN[i],Math.min(MAX[i],prefs.getInt(KEYS[i],100)));
        gyroEnabled=prefs.getBoolean("gyro_aim",false) && activity.motionAvailable();
        apply();
    }
    boolean isOpen(){return root!=null;}
    private int dp(int n){return Math.round(n*activity.getResources().getDisplayMetrics().density);}
    private String[] strings(){
        String language=android.content.res.Resources.getSystem().getConfiguration().getLocales().get(0).getLanguage();
        switch(language){
            case "de":return new String[]{"Einstellungen","Gesamtlautstärke","Soundeffektlautstärke","Musiklautstärke","Helligkeit","Gamma","Gyro-Empfindlichkeit","Gyrsokop Sicht aktivieren","OK","Abbrechen","kein Gyroskop","Lautstärken","Anzeige","Steuerung"};
            case "fr":return new String[]{"Paramètres","Volume général","Volume des effets sonores","Volume de la musique","Luminosité","Gamma","Sensibilité du gyro","Activer la vue gyroscopique","OK","Annuler","gyroscope absent","Volumes","Affichage","Commandes"};
            case "it":return new String[]{"Impostazioni","Volume generale","Volume degli effetti sonori","Volume della musica","Luminosità","Gamma","Sensibilità gyro","Attiva visuale con giroscopio","OK","Annulla","giroscopio assente","Volumi","Schermo","Controlli"};
            default:return new String[]{"Settings","Master volume","Sound effects volume","Music volume","Brightness","Gamma","Gyro sensitivity","Enable gyroscope look","OK","Cancel","no gyroscope","Volumes","Display","Controls"};
        }
    }
    private TextView text(String caption,int size) {
        TextView label=new TextView(activity);
        label.setText(caption);label.setTextColor(Color.WHITE);
        label.setAutoSizeTextTypeWithDefaults(TextView.AUTO_SIZE_TEXT_TYPE_NONE);
        label.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,size);
        label.setGravity(Gravity.CENTER_VERTICAL);
        return label;
    }
    private void heading(LinearLayout rows,String caption) {
        LinearLayout section=new LinearLayout(activity);
        section.setGravity(Gravity.CENTER_VERTICAL);section.setPadding(0,dp(10),0,dp(6));
        View left=new View(activity);left.setBackgroundColor(0xff639fbd);
        left.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        section.addView(left,new LinearLayout.LayoutParams(0,dp(1),1));
        TextView label=text(caption,HEADING_SP);
        label.setGravity(Gravity.CENTER);label.setTypeface(null,Typeface.BOLD);
        label.setPadding(dp(12),0,dp(12),0);
        section.addView(label,new LinearLayout.LayoutParams(-2,-2));
        View right=new View(activity);right.setBackgroundColor(0xff639fbd);
        right.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        section.addView(right,new LinearLayout.LayoutParams(0,dp(1),1));
        rows.addView(section,new LinearLayout.LayoutParams(-1,-2));
    }
    private LinearLayout row(LinearLayout rows) {
        LinearLayout row=new LinearLayout(activity);
        row.setGravity(Gravity.CENTER_VERTICAL);row.setMinimumHeight(dp(48));
        row.setPadding(0,dp(4),0,dp(4));
        rows.addView(row,new LinearLayout.LayoutParams(-1,-2));
        return row;
    }
    private void slider(LinearLayout rows,int index,String caption) {
        final int target=index==5?GYRO_SLIDER:index;
        LinearLayout row=row(rows);
        TextView label=text(caption,TEXT_SP);label.setPadding(0,0,dp(8),0);
        // Fixed text size; a long translation grows the row instead of shrinking.
        row.addView(label,new LinearLayout.LayoutParams(0,-2,0.42f));
        LinearLayout controls=new LinearLayout(activity);controls.setGravity(Gravity.CENTER_VERTICAL);
        row.addView(controls,new LinearLayout.LayoutParams(0,dp(48),0.58f));
        TextView value=text(values[index]+"%",TEXT_SP);
        value.setGravity(Gravity.END|Gravity.CENTER_VERTICAL);value.setMinWidth(dp(56));
        SeekBar slider=new SeekBar(activity);sliders[index]=slider;targets[target]=slider;
        slider.setMax(MAX[index]-MIN[index]);slider.setProgress(values[index]-MIN[index]);
        slider.setKeyProgressIncrement(5);
        if(index==5)slider.setEnabled(activity.motionAvailable());
        slider.setContentDescription(caption);slider.setFocusableInTouchMode(true);
        slider.setId(View.generateViewId());label.setLabelFor(slider.getId());
        controls.addView(slider,new LinearLayout.LayoutParams(0,-1,1));
        controls.addView(value,new LinearLayout.LayoutParams(-2,-1));
        slider.setOnFocusChangeListener((v,focused)->{if(focused)selected=target;});
        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
            public void onProgressChanged(SeekBar bar,int progress,boolean fromUser){
                values[index]=progress+MIN[index];value.setText(values[index]+"%");apply();
            }
            public void onStartTrackingTouch(SeekBar bar){selected=target;bar.requestFocus();}
            public void onStopTrackingTouch(SeekBar bar){}
        });
    }
    private void gyro(LinearLayout rows,String caption,String missing) {
        boolean available=activity.motionAvailable();
        String labelText=caption+(available?"":" ("+missing+")");
        LinearLayout row=row(rows);
        TextView label=text(labelText,TEXT_SP);label.setPadding(0,0,dp(8),0);
        row.addView(label,new LinearLayout.LayoutParams(0,-2,1));
        gyroSwitch=new Switch(activity);targets[GYRO_TOGGLE]=gyroSwitch;
        gyroSwitch.setAutoSizeTextTypeWithDefaults(TextView.AUTO_SIZE_TEXT_TYPE_NONE);
        gyroSwitch.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,TEXT_SP);
        gyroSwitch.setShowText(false);
        gyroSwitch.setPadding(0,0,0,0);gyroSwitch.setMinHeight(0);gyroSwitch.setMinimumHeight(0);
        gyroSwitch.setId(View.generateViewId());label.setLabelFor(gyroSwitch.getId());
        gyroSwitch.setContentDescription(labelText);gyroSwitch.setFocusableInTouchMode(true);
        gyroSwitch.setEnabled(available);gyroSwitch.setChecked(gyroEnabled);
        gyroSwitch.setOnFocusChangeListener((v,focused)->{if(focused)selected=GYRO_TOGGLE;});
        gyroSwitch.setOnCheckedChangeListener((v,checked)->{gyroEnabled=checked && available;apply();});
        row.addView(gyroSwitch,new LinearLayout.LayoutParams(-2,dp(48)));
    }
    void show(){
        if(isOpen() || suspended)return;
        activity.releaseGameKeys();
        System.arraycopy(values,0,original,0,values.length);originalGyro=gyroEnabled;
        nativeOpen(true);activity.settingsVisibility(true);
        String[] labels=strings();
        root=new FrameLayout(activity);root.setBackgroundColor(Color.TRANSPARENT);root.setClickable(true);
        LinearLayout panel=new LinearLayout(activity);panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(20),dp(12),dp(20),dp(12));
        GradientDrawable background=new GradientDrawable();background.setColor(0xf0182331);
        background.setCornerRadius(dp(12));background.setStroke(dp(1),0xff639fbd);panel.setBackground(background);
        int width=Math.min(dp(600),Math.max(dp(200),parent.getWidth()-dp(24)));
        int height=Math.max(dp(180),parent.getHeight()-dp(16));
        FrameLayout.LayoutParams box=new FrameLayout.LayoutParams(width,Math.min(height,dp(540)),Gravity.CENTER);
        root.addView(panel,box);
        LinearLayout header=new LinearLayout(activity);header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);header.setBaselineAligned(false);
        header.setPadding(0,0,0,dp(8));
        TextView title=text(labels[0],22);title.setTypeface(Typeface.create(Typeface.DEFAULT,800,false));
        header.addView(title,new LinearLayout.LayoutParams(0,-2,1));
        TextView version=text("v"+BuildConfig.VERSION_NAME,12);
        version.setGravity(Gravity.END|Gravity.CENTER_VERTICAL);version.setSingleLine(true);
        version.setPadding(dp(12),0,0,0);
        header.addView(version,new LinearLayout.LayoutParams(-2,-2));
        panel.addView(header,new LinearLayout.LayoutParams(-1,-2));
        ScrollView scroll=new ScrollView(activity);scroll.setFillViewport(false);
        panel.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout rows=new LinearLayout(activity);rows.setOrientation(LinearLayout.VERTICAL);scroll.addView(rows);
        heading(rows,labels[11]);
        for(int i=0;i<3;i++)slider(rows,i,labels[i+1]);
        heading(rows,labels[12]);
        for(int i=3;i<5;i++)slider(rows,i,labels[i+1]);
        heading(rows,labels[13]);
        gyro(rows,labels[7],labels[10]);
        slider(rows,5,labels[6]);
        LinearLayout buttons=new LinearLayout(activity);buttons.setGravity(Gravity.END);panel.addView(buttons);
        for(int i=0;i<2;i++){
            final int index=i+OK;Button button=new Button(activity);
            button.setText(labels[i+8]);button.setFocusableInTouchMode(true);targets[index]=button;
            // Use the same caption size on mobile and Automotive; preserve the
            // AAOS padding fix without shrinking long labels independently.
            button.setAllCaps(false);button.setSingleLine(true);button.setIncludeFontPadding(false);
            button.setGravity(Gravity.CENTER);button.setMinHeight(0);button.setMinimumHeight(0);
            button.setMinWidth(0);button.setMinimumWidth(0);button.setPadding(dp(12),0,dp(12),0);
            button.setAutoSizeTextTypeWithDefaults(TextView.AUTO_SIZE_TEXT_TYPE_NONE);
            button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,TEXT_SP);
            button.setOnFocusChangeListener((v,focused)->{if(focused)selected=index;});
            button.setOnClickListener(v->close(index==OK));
            buttons.addView(button,new LinearLayout.LayoutParams(0,dp(48),1));
        }
        parent.addView(root,new ViewGroup.LayoutParams(-1,-1));
        selected=0;targets[0].requestFocus();lastMotion=0;
    }
    void close(boolean save){
        if(!isOpen())return;
        if(save){
            SharedPreferences.Editor e=prefs.edit();
            for(int i=0;i<values.length;i++)e.putInt(KEYS[i],values[i]);
            e.putBoolean("gyro_aim",gyroEnabled);e.apply();
        } else {
            System.arraycopy(original,0,values,0,values.length);gyroEnabled=originalGyro;apply();
        }
        parent.removeView(root);root=null;nativeOpen(false);activity.settingsVisibility(false);
    }
    void suspend(){suspended=true;close(false);}
    void resume(){suspended=false;}
    private void apply(){
        HaloPort.nativeVolumes(values[0],values[1],values[2]);nativeDisplay(values[3],values[4]);
        activity.motionSettings(gyroEnabled,values[5]);
    }
    private void direction(int key){
        if(key==KeyEvent.KEYCODE_DPAD_UP || key==KeyEvent.KEYCODE_DPAD_DOWN){
            int step=key==KeyEvent.KEYCODE_DPAD_UP?-1:1;
            int next=selected+step;
            while(next>=0 && next<targets.length && !targets[next].isEnabled())next+=step;
            if(next>=0 && next<targets.length)selected=next;
        } else if(selected<GYRO_TOGGLE || selected==GYRO_SLIDER){
            int index=selected==GYRO_SLIDER?5:selected;
            int delta=key==KeyEvent.KEYCODE_DPAD_LEFT?-5:5;
            sliders[index].setProgress(sliders[index].getProgress()+delta);
        } else if(selected==GYRO_TOGGLE)gyroSwitch.setChecked(key==KeyEvent.KEYCODE_DPAD_RIGHT);
        else selected=key==KeyEvent.KEYCODE_DPAD_LEFT?OK:CANCEL;
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
            if(selected==GYRO_TOGGLE || selected>=OK)targets[selected].performClick();
            else{selected=OK;targets[selected].requestFocus();}
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
