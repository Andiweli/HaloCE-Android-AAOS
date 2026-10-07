#!/usr/bin/env python3
"""Check production overlay refresh/navigation code without an Android device.

Requires a JDK; JAVA and JAVAC may override the executables.
Run from the project root: python3 tools/test_android_overlay_sticks.py
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

from test_android_gamepad_integration import block

ROOT = Path(__file__).resolve().parents[1]


def main():
    overlay = (ROOT / "port/android/app/src/main/java/com/halo/decomp/SettingsOverlay.java").read_text()
    fixture = "class OverlayStickRefreshCheck {\n"
    fixture += "\n".join(re.findall(r"^    private static final .*;", overlay, re.M))
    fixture += r'''
    static class View {
        static int nextId;int id;boolean enabled=true;float alpha=1.f;
        ViewGroup parent;ViewGroup.LayoutParams layout;FocusListener focus;
        interface FocusListener {void change(View view,boolean focused);}
        interface ClickListener {void click(View view);}
        boolean isVisible(){return parent!=null;}
        boolean isEnabled(){return enabled;}
        void setEnabled(boolean value){enabled=value;}
        void setAlpha(float value){alpha=value;}
        void requestFocus(){if(enabled&&focus!=null)focus.change(this,true);}
        void setOnFocusChangeListener(FocusListener value){focus=value;}
        void setOnClickListener(ClickListener value){}
        void setFocusableInTouchMode(boolean value){}
        void setContentDescription(String value){}
        void setId(int value){id=value;}
        int getId(){return id;}
        static int generateViewId(){return ++nextId;}
        void setPadding(int left,int top,int right,int bottom){}
        void setMinimumHeight(int value){}
        void setBackgroundColor(int value){}
        void setBackground(GradientDrawable value){}
        void setClickable(boolean value){}
        int getWidth(){return 1000;}
        int getHeight(){return 600;}
    }
    static class ViewGroup extends View {
        final java.util.List<View> children=new java.util.ArrayList<>();
        static class LayoutParams {
            int width,height;float weight;
            LayoutParams(int width,int height){this.width=width;this.height=height;}
        }
        void addView(View value,LayoutParams params){children.add(value);value.parent=this;value.layout=params;}
        void addView(View value){addView(value,new LayoutParams(-1,-2));}
        void removeView(View value){children.remove(value);value.parent=null;}
    }
    static class LinearLayout extends ViewGroup {
        static final int VERTICAL=1,HORIZONTAL=0;
        LinearLayout(Activity activity){}
        void setOrientation(int value){}
        void setGravity(int value){}
        void setBaselineAligned(boolean value){}
        static class LayoutParams extends ViewGroup.LayoutParams {
            LayoutParams(int width,int height){super(width,height);}
            LayoutParams(int width,int height,float weight){super(width,height);this.weight=weight;}
        }
    }
    static class ScrollView extends ViewGroup {
        ScrollView(Activity activity){}
        void setFillViewport(boolean value){}
    }
    static class TextView extends View {
        static final int AUTO_SIZE_TEXT_TYPE_NONE=0;
        TextView(Activity activity){}
        void setText(String value){}
        void setTypeface(Object...value){}
        void setGravity(int value){}
        void setSingleLine(boolean value){}
        void setMinWidth(int value){}
        void setLabelFor(int value){}
        void setAutoSizeTextTypeWithDefaults(int value){}
        void setTextSize(int unit,int value){}
        void setMinHeight(int value){}
        void setMinimumWidth(int value){}
    }
    static class Button extends TextView {
        Button(Activity activity){super(activity);}
        void setAllCaps(boolean value){}
        void setIncludeFontPadding(boolean value){}
    }
    static class SeekBar extends View {
        int progress,max=100;OnSeekBarChangeListener listener;
        interface OnSeekBarChangeListener {
            void onProgressChanged(SeekBar bar,int progress,boolean fromUser);
            void onStartTrackingTouch(SeekBar bar);void onStopTrackingTouch(SeekBar bar);
        }
        SeekBar(Activity activity){}
        int getProgress(){return progress;}
        void setProgress(int value){progress=Math.max(0,Math.min(max,value));if(listener!=null)listener.onProgressChanged(this,progress,false);}
        void setMax(int value){max=value;}
        void setKeyProgressIncrement(int value){}
        void setOnSeekBarChangeListener(OnSeekBarChangeListener value){listener=value;}
    }
    static class Switch extends TextView {
        interface CheckedListener {void change(Switch view,boolean checked);}
        Switch(Activity activity){super(activity);}
        void setChecked(boolean value){}
        void setShowText(boolean value){}
        void setOnCheckedChangeListener(CheckedListener value){}
    }
    static class FrameLayout extends ViewGroup {
        FrameLayout(){}FrameLayout(Activity activity){}
        static class LayoutParams extends ViewGroup.LayoutParams {
            LayoutParams(int width,int height,int gravity){super(width,height);}
        }
        Runnable pending;int delay,removed;
        void post(Runnable value){pending=value;delay=0;}
        void postDelayed(Runnable value,int ms){pending=value;delay=ms;}
        void removeCallbacks(Runnable value){if(pending==value)pending=null;removed++;}
    }
    static class GradientDrawable {void setColor(int value){}void setCornerRadius(int value){}void setStroke(int width,int value){}}
    static class Gravity {static final int CENTER_VERTICAL=1,CENTER=2,END=4;}
    static class Color {static final int TRANSPARENT=0;}
    static class Typeface {static final Typeface DEFAULT=new Typeface();static Typeface create(Typeface value,int weight,boolean italic){return DEFAULT;}}
    static class android {static class util {static class TypedValue {static final int COMPLEX_UNIT_SP=2;}}}
    static class BuildConfig {static final String VERSION_NAME="1.0.8";}
    static class SharedPreferences {
        static class Editor {
            Editor putInt(String key,int value){return this;}
            Editor putBoolean(String key,boolean value){return this;}
            void apply(){}
        }
        Editor edit(){return new Editor();}
    }
    static class Activity {
        boolean gyro;
        boolean motionAvailable(){return gyro;}
        void settingsVisibility(boolean value){}
        void releaseGameKeys(){}
    }
    static class KeyEvent {
        static final int KEYCODE_DPAD_UP=19,KEYCODE_DPAD_DOWN=20,
            KEYCODE_DPAD_LEFT=21,KEYCODE_DPAD_RIGHT=22;
    }
    static int nativeMask=RIGHT_LOOK;
    static int nativeLookSticks(){return nativeMask;}
    static void nativeOpen(boolean value){}
    final Activity activity=new Activity();
    final SharedPreferences prefs=new SharedPreferences();
    final FrameLayout parent=new FrameLayout();
    final SeekBar[] sliders=new SeekBar[KEYS.length];
    final View[] targets=new View[CANCEL+1],stickRows=new View[2];
    final int[] values=new int[KEYS.length],original=new int[KEYS.length];
    Switch gyroSwitch,gyroInvertSwitch;
    boolean gyroEnabled,originalGyro,gyroInvertPitch,originalGyroInvert,suspended;
    int selected,stickLookMask,applyCount;
    long lastMotion;
    FrameLayout root;
    boolean isOpen(){return root!=null;}
    void apply(){applyCount++;}
    int dp(int value){return value;}
    String[] strings(){String[] labels=new String[17];java.util.Arrays.fill(labels,"caption");return labels;}
    TextView text(String caption,int size){return new TextView(activity);}
    void heading(LinearLayout rows,String caption){rows.addView(text(caption,14));}
'''
    fixture += block(overlay, "private final Runnable refreshStickRoles=", True)
    for marker in ("private boolean sliderEnabled(", "private void refreshStickSliders(",
                   "private void direction(", "private LinearLayout row(", "private void slider(",
                   "private Switch gyroToggle(", "void show(", "void close(", "void suspend(", "void resume("):
        fixture += block(overlay, marker)
    fixture += r'''
    OverlayStickRefreshCheck(){
        for(int i=0;i<values.length;i++)values[i]=100;
        show();
    }
    static void check(boolean condition){if(!condition)throw new AssertionError();}
    void checkMask(int mask){
        check(stickLookMask==mask);
        ViewGroup panel=(ViewGroup)root.children.get(0);
        check(panel.children.size()==3);
        check(panel.children.get(1) instanceof ScrollView);
        ViewGroup scroll=(ViewGroup)panel.children.get(1);
        check(scroll.layout.height==0&&scroll.layout.weight==1);
        check(scroll.children.size()==1);
        ViewGroup rows=(ViewGroup)scroll.children.get(0);
        check(rows.children.get(rows.children.size()-3)==sliders[5].parent.parent);
        check(rows.children.get(rows.children.size()-2)==stickRows[0]);
        check(rows.children.get(rows.children.size()-1)==stickRows[1]);
        for(int i=0;i<2;i++){
            boolean enabled=(mask&(1<<i))!=0;
            check(sliders[i+6].isEnabled()==enabled);
            check(stickRows[i].alpha==(enabled?1.f:.65f));
            check(stickRows[i].isVisible()&&stickRows[i].parent==rows&&sliders[i+6].isVisible());
            check(sliders[i+6].getProgress()==50&&values[i+6]==100);
        }
        check(applyCount==0);
    }
    public static void main(String[] args){
        OverlayStickRefreshCheck x=new OverlayStickRefreshCheck();x.checkMask(RIGHT_LOOK);
        x.selected=RIGHT_STICK;
        nativeMask=LEFT_LOOK;x.refreshStickRoles.run();x.checkMask(LEFT_LOOK);
        check(x.selected==OK&&x.root.pending==x.refreshStickRoles&&x.root.delay==100);
        x.selected=4;x.direction(KeyEvent.KEYCODE_DPAD_DOWN);check(x.selected==LEFT_STICK);
        nativeMask=RIGHT_LOOK;x.refreshStickRoles.run();x.checkMask(RIGHT_LOOK);
        check(x.selected==RIGHT_STICK);
        nativeMask=LEFT_LOOK|RIGHT_LOOK;x.refreshStickRoles.run();x.checkMask(3);
        nativeMask=0;x.refreshStickRoles.run();x.checkMask(0);check(x.selected==OK);
        x.selected=4;x.direction(KeyEvent.KEYCODE_DPAD_DOWN);check(x.selected==OK);
        x.activity.gyro=true;check(x.sliderEnabled(5));
        FrameLayout oldRoot=x.root;x.close(true);
        check(!x.isOpen()&&oldRoot.pending==null&&oldRoot.removed==1);
        x.refreshStickRoles.run();check(oldRoot.pending==null);
        nativeMask=LEFT_LOOK;
        x=new OverlayStickRefreshCheck();oldRoot=x.root;x.suspend();
        check(x.suspended&&!x.isOpen()&&oldRoot.pending==null&&x.applyCount==1);
        x.refreshStickRoles.run();check(oldRoot.pending==null);
        x.resume();check(!x.suspended);
        for(int mask=0;mask<4;mask++){nativeMask=mask;new OverlayStickRefreshCheck().checkMask(mask);}
        System.out.println("Actual overlay construction: both stick rows remain inside the scroll content after gyro sensitivity for all roles; live enable/disable, focus, values and close/suspend cleanup passed.");
    }
}
'''
    with tempfile.TemporaryDirectory(prefix="halo-overlay-sticks-") as directory:
        source = Path(directory) / "OverlayStickRefreshCheck.java"
        source.write_text(fixture)
        subprocess.run([os.environ.get("JAVAC", "javac"), "-d", directory, str(source)], check=True)
        subprocess.run([os.environ.get("JAVA", "java"), "-cp", directory, source.stem], check=True)


if __name__ == "__main__":
    main()
