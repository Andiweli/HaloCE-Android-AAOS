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
    static native void nativeSticks(int left, int right);
    static native int nativeLookSticks();
    private static final int TEXT_SP=16, HEADING_SP=14;
    private static final int LEFT_LOOK=1, RIGHT_LOOK=2;
    private static final int GYRO_TOGGLE=5, GYRO_INVERT=6, GYRO_SLIDER=7, LEFT_STICK=8, RIGHT_STICK=9, OK=10, CANCEL=11;
    private static final String[] KEYS={"master","effects","music","brightness","gamma","gyro_sensitivity","left_stick_sensitivity","right_stick_sensitivity"};
    private static final int[] MIN={0,0,0,50,50,25,50,50}, MAX={100,100,100,150,200,200,150,150};
    private static final int[] SLIDER_TARGETS={0,1,2,3,4,GYRO_SLIDER,LEFT_STICK,RIGHT_STICK};
    private final HaloActivity activity;
    private final ViewGroup parent;
    private final SharedPreferences prefs;
    private final int[] values=new int[KEYS.length], original=new int[KEYS.length];
    private final SeekBar[] sliders=new SeekBar[KEYS.length];
    private final View[] targets=new View[CANCEL+1];
    private final View[] stickRows=new View[2];
    private boolean gyroEnabled, originalGyro, gyroInvertPitch, originalGyroInvert;
    private Switch gyroSwitch, gyroInvertSwitch;
    private FrameLayout root;
    private int selected;
    private int stickLookMask;
    private long lastMotion;
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
        apply();
    }
    boolean isOpen(){return root!=null;}
    private int dp(int n){return Math.round(n*activity.getResources().getDisplayMetrics().density);}
    private String[] strings(){
        String language=android.content.res.Resources.getSystem().getConfiguration().getLocales().get(0).getLanguage();
        switch(language){
            case "de":return new String[]{"Einstellungen","Gesamtlautstärke","Soundeffektlautstärke","Musiklautstärke","Helligkeit","Gamma","Gyro-Empfindlichkeit","Gyroskop Sicht aktivieren","OK","Abbrechen","kein Gyroskop","Lautstärken","Anzeige","Steuerung","Gyro Rauf/Runter invertieren","Linker Stick Empfindlichkeit","Rechter Stick Empfindlichkeit"};
            case "fr":return new String[]{"Paramètres","Volume général","Volume des effets sonores","Volume de la musique","Luminosité","Gamma","Sensibilité du gyro","Activer la vue gyroscopique","OK","Annuler","gyroscope absent","Volumes","Affichage","Commandes","Inverser haut/bas du gyroscope","Sensibilité du stick gauche","Sensibilité du stick droit"};
            case "it":return new String[]{"Impostazioni","Volume generale","Volume degli effetti sonori","Volume della musica","Luminosità","Gamma","Sensibilità gyro","Attiva visuale con giroscopio","OK","Annulla","giroscopio assente","Volumi","Schermo","Controlli","Inverti su/giù del giroscopio","Sensibilità stick sinistro","Sensibilità stick destro"};
            default:return new String[]{"Settings","Master volume","Sound effects volume","Music volume","Brightness","Gamma","Gyro sensitivity","Enable gyroscope look","OK","Cancel","no gyroscope","Volumes","Display","Controls","Invert gyro up/down","Left stick sensitivity","Right stick sensitivity"};
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
    private boolean sliderEnabled(int index) {
        if(index==5)return activity.motionAvailable();
        if(index==6)return (stickLookMask&LEFT_LOOK)!=0;
        if(index==7)return (stickLookMask&RIGHT_LOOK)!=0;
        return true;
    }
    private void refreshStickSliders(){
        int mask=nativeLookSticks();
        if(mask==stickLookMask)return;
        stickLookMask=mask;
        for(int i=6;i<8;i++){
            boolean enabled=sliderEnabled(i);
            sliders[i].setEnabled(enabled);
            stickRows[i-6].setAlpha(enabled?1.f:.65f);
        }
        if(!targets[selected].isEnabled())direction(KeyEvent.KEYCODE_DPAD_DOWN);
    }
    private void slider(LinearLayout rows,int index,String caption) {
        final int target=SLIDER_TARGETS[index];
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
        boolean enabled=sliderEnabled(index);
        slider.setEnabled(enabled);
        if(index>=6){stickRows[index-6]=row;row.setAlpha(enabled?1.f:.65f);}
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
    private Switch gyroToggle(LinearLayout rows,int target,String caption,boolean checked) {
        LinearLayout row=row(rows);
        TextView label=text(caption,TEXT_SP);label.setPadding(0,0,dp(8),0);
        row.addView(label,new LinearLayout.LayoutParams(0,-2,1));
        Switch toggle=new Switch(activity);targets[target]=toggle;
        toggle.setAutoSizeTextTypeWithDefaults(TextView.AUTO_SIZE_TEXT_TYPE_NONE);
        toggle.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP,TEXT_SP);
        toggle.setShowText(false);
        toggle.setPadding(0,0,0,0);toggle.setMinHeight(0);toggle.setMinimumHeight(0);
        toggle.setId(View.generateViewId());label.setLabelFor(toggle.getId());
        toggle.setContentDescription(caption);toggle.setFocusableInTouchMode(true);
        toggle.setEnabled(activity.motionAvailable());toggle.setChecked(checked);
        toggle.setOnFocusChangeListener((v,focused)->{if(focused)selected=target;});
        row.addView(toggle,new LinearLayout.LayoutParams(-2,dp(48)));
        return toggle;
    }
    void show(){
        if(isOpen() || suspended)return;
        activity.releaseGameKeys();
        stickLookMask=nativeLookSticks();
        System.arraycopy(values,0,original,0,values.length);originalGyro=gyroEnabled;
        originalGyroInvert=gyroInvertPitch;
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
        boolean available=activity.motionAvailable();
        gyroSwitch=gyroToggle(rows,GYRO_TOGGLE,labels[7]+(available?"":" ("+labels[10]+")"),gyroEnabled);
        gyroSwitch.setOnCheckedChangeListener((v,checked)->{gyroEnabled=checked && available;apply();});
        gyroInvertSwitch=gyroToggle(rows,GYRO_INVERT,labels[14],gyroInvertPitch);
        gyroInvertSwitch.setOnCheckedChangeListener((v,checked)->{gyroInvertPitch=checked;apply();});
        slider(rows,5,labels[6]);
        slider(rows,6,labels[15]);
        slider(rows,7,labels[16]);
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
        root.post(refreshStickRoles);
    }
    void close(boolean save){
        if(!isOpen())return;
        root.removeCallbacks(refreshStickRoles);
        if(save){
            SharedPreferences.Editor e=prefs.edit();
            for(int i=0;i<values.length;i++)e.putInt(KEYS[i],values[i]);
            e.putBoolean("gyro_aim",gyroEnabled);
            e.putBoolean("gyro_invert_pitch",gyroInvertPitch);e.apply();
        } else {
            System.arraycopy(original,0,values,0,values.length);gyroEnabled=originalGyro;
            gyroInvertPitch=originalGyroInvert;apply();
        }
        parent.removeView(root);root=null;nativeOpen(false);activity.settingsVisibility(false);
    }
    void suspend(){suspended=true;close(false);}
    void resume(){suspended=false;}
    private void apply(){
        HaloPort.nativeVolumes(values[0],values[1],values[2]);nativeDisplay(values[3],values[4]);
        activity.motionSettings(gyroEnabled,values[5],gyroInvertPitch);
        nativeSticks(values[6],values[7]);
    }
    private void direction(int key){
        if(key==KeyEvent.KEYCODE_DPAD_UP || key==KeyEvent.KEYCODE_DPAD_DOWN){
            int step=key==KeyEvent.KEYCODE_DPAD_UP?-1:1;
            int next=selected+step;
            while(next>=0 && next<targets.length && !targets[next].isEnabled())next+=step;
            if(next>=0 && next<targets.length)selected=next;
        } else if(selected<GYRO_TOGGLE || (selected>=GYRO_SLIDER && selected<=RIGHT_STICK)){
            int index=selected>=GYRO_SLIDER?selected-GYRO_SLIDER+5:selected;
            int delta=key==KeyEvent.KEYCODE_DPAD_LEFT?-5:5;
            sliders[index].setProgress(sliders[index].getProgress()+delta);
        } else if(selected==GYRO_TOGGLE)gyroSwitch.setChecked(key==KeyEvent.KEYCODE_DPAD_RIGHT);
        else if(selected==GYRO_INVERT)gyroInvertSwitch.setChecked(key==KeyEvent.KEYCODE_DPAD_RIGHT);
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
            if(selected==GYRO_TOGGLE || selected==GYRO_INVERT || selected>=OK)targets[selected].performClick();
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
