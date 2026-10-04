"""Exercise the actual overlay controller methods with deterministic widget inputs.
This checks navigation and key dispatch; it does not emulate Android layout.
Requires a JDK on PATH (or JAVA_HOME).
"""
from pathlib import Path
import os
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
source=(root/'port/android/app/src/main/java/com/halo/decomp/SettingsOverlay.java').read_text()
def method(start,end):
    return source[source.index(start):source.index(end,source.index(start))]
constants=next(line.strip() for line in source.splitlines() if 'int GYRO_TOGGLE=' in line)
direction=method('    private void direction(', '    boolean key(')
keys=method('    boolean key(', '    void motion(')
fixture=r'''
class OverlayNavigationTest {
    static class KeyEvent {
        static final int ACTION_DOWN=0, KEYCODE_DPAD_UP=19, KEYCODE_DPAD_DOWN=20,
          KEYCODE_DPAD_LEFT=21, KEYCODE_DPAD_RIGHT=22, KEYCODE_VOLUME_UP=24,
          KEYCODE_VOLUME_DOWN=25, KEYCODE_VOLUME_MUTE=164, KEYCODE_BUTTON_B=97,
          KEYCODE_BACK=4, KEYCODE_ESCAPE=111, KEYCODE_BUTTON_A=96,
          KEYCODE_DPAD_CENTER=23, KEYCODE_ENTER=66;
        int code;KeyEvent(int code){this.code=code;}
        int getKeyCode(){return code;}int getAction(){return ACTION_DOWN;}int getRepeatCount(){return 0;}
    }
    static class Widget {
        boolean enabled=true;int clicked,focused;
        boolean isEnabled(){return enabled;}
        void requestFocus(){focused++;}void performClick(){clicked++;}
    }
    static class Slider extends Widget {
        int progress=75;
        int getProgress(){return progress;}void setProgress(int value){progress=value;}
    }
    static class Toggle extends Widget {
        boolean checked;
        void setChecked(boolean value){checked=value;}
        @Override void performClick(){super.performClick();checked=!checked;}
    }
    int selected;boolean open=true,save;
    Slider[] sliders=new Slider[6];Widget[] targets=new Widget[9];Toggle gyroSwitch=new Toggle();
    OverlayNavigationTest(boolean gyro){
        for(int i=0;i<6;i++){sliders[i]=new Slider();targets[i==5?6:i]=sliders[i];}
        targets[5]=gyroSwitch;targets[7]=new Widget();targets[8]=new Widget();
        targets[5].enabled=targets[6].enabled=gyro;
    }
    boolean isOpen(){return open;}void close(boolean save){this.save=save;open=false;}
    void press(int code){assert key(new KeyEvent(code));}
'''
checks=r'''
    public static void main(String[] args){
        OverlayNavigationTest t=new OverlayNavigationTest(true);
        for(int i=0;i<5;i++)t.press(KeyEvent.KEYCODE_DPAD_DOWN);
        assert t.selected==5; /* Switch before sensitivity. */
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.gyroSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert !t.gyroSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.gyroSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);assert t.selected==6;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.sliders[5].progress==80;
        assert t.sliders[4].progress==75; /* Gamma is untouched. */
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.selected==7;
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.targets[7].clicked==1;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.selected==8;
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.targets[8].clicked==1;
        t.press(KeyEvent.KEYCODE_BUTTON_B);assert !t.open && !t.save;
        t=new OverlayNavigationTest(false);
        for(int i=0;i<5;i++)t.press(KeyEvent.KEYCODE_DPAD_DOWN);
        assert t.selected==7;
        t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==4;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert t.sliders[4].progress==70;
        assert !t.key(new KeyEvent(KeyEvent.KEYCODE_VOLUME_UP));
        System.out.println("Production overlay keys: toggle/slider order, independent sensitivity, confirm/cancel dispatch, disabled gyro and volume keys passed.");
    }
}
'''
jdk=Path(os.environ['JAVA_HOME'])/'bin' if os.environ.get('JAVA_HOME') else None
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp);(path/'OverlayNavigationTest.java').write_text(fixture+constants+'\n'+direction+keys+checks)
    subprocess.run([str(jdk/'javac') if jdk else 'javac','-d',str(path),str(path/'OverlayNavigationTest.java')],check=True)
    subprocess.run([str(jdk/'java') if jdk else 'java','-ea','-cp',str(path),'OverlayNavigationTest'],check=True)
