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
        int code,action=ACTION_DOWN,repeat;KeyEvent(int code){this.code=code;}
        int getKeyCode(){return code;}int getAction(){return action;}int getRepeatCount(){return repeat;}
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
    Slider[] sliders=new Slider[6];Widget[] targets=new Widget[10];
    Toggle gyroSwitch=new Toggle(),gyroInvertSwitch=new Toggle();
    OverlayNavigationTest(boolean gyro){
        for(int i=0;i<6;i++){sliders[i]=new Slider();targets[i==5?7:i]=sliders[i];}
        targets[5]=gyroSwitch;targets[6]=gyroInvertSwitch;
        targets[8]=new Widget();targets[9]=new Widget();
        targets[5].enabled=targets[6].enabled=targets[7].enabled=gyro;
    }
    boolean isOpen(){return open;}void close(boolean save){this.save=save;open=false;}
    void press(int code){assert key(new KeyEvent(code));}
'''
checks=r'''
    public static void main(String[] args){
        OverlayNavigationTest t=new OverlayNavigationTest(true);
        for(int i=0;i<5;i++)t.press(KeyEvent.KEYCODE_DPAD_DOWN);
        assert t.selected==5; /* Enable, invert, then sensitivity. */
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.gyroSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert !t.gyroSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.gyroSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);assert t.selected==6;
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.gyroInvertSwitch.checked && t.selected==6;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert !t.gyroInvertSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.gyroInvertSwitch.checked;
        assert t.gyroSwitch.checked; /* Invert never changes gyro enable. */
        t.press(KeyEvent.KEYCODE_ENTER);assert !t.gyroInvertSwitch.checked && t.selected==6;
        t.press(KeyEvent.KEYCODE_DPAD_CENTER);assert t.gyroInvertSwitch.checked && t.selected==6;
        KeyEvent repeated=new KeyEvent(KeyEvent.KEYCODE_BUTTON_A);repeated.repeat=1;
        assert t.key(repeated) && t.gyroInvertSwitch.checked;
        KeyEvent released=new KeyEvent(KeyEvent.KEYCODE_BUTTON_A);released.action=1;
        assert t.key(released) && t.gyroInvertSwitch.checked;
        for(Slider slider:t.sliders)assert slider.progress==75;
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);assert t.selected==7;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.sliders[5].progress==80;
        assert t.sliders[4].progress==75; /* Gamma is untouched. */
        t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==6;
        t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==5;
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);t.press(KeyEvent.KEYCODE_DPAD_DOWN);
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.selected==8;
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.targets[8].clicked==1;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.selected==9;
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.targets[9].clicked==1;
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);assert t.selected==9;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert t.selected==8;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert t.selected==8;
        t.press(KeyEvent.KEYCODE_BUTTON_B);assert !t.open && !t.save;
        assert !t.key(new KeyEvent(KeyEvent.KEYCODE_ENTER));
        t=new OverlayNavigationTest(false);
        for(int i=0;i<5;i++)t.press(KeyEvent.KEYCODE_DPAD_DOWN);
        assert t.selected==8; /* Skip all three unavailable gyro controls. */
        t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==4;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert t.sliders[4].progress==70;
        for(int code:new int[]{KeyEvent.KEYCODE_VOLUME_UP,KeyEvent.KEYCODE_VOLUME_DOWN,KeyEvent.KEYCODE_VOLUME_MUTE})
            assert !t.key(new KeyEvent(code));
        t.selected=0;t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==0;
        for(int code:new int[]{KeyEvent.KEYCODE_BUTTON_B,KeyEvent.KEYCODE_BACK,KeyEvent.KEYCODE_ESCAPE}){
            t=new OverlayNavigationTest(true);t.press(code);assert !t.open && !t.save;
        }
        System.out.println("Production overlay keys: enable/invert/sensitivity order, independent toggles, repeat/release safety, confirm/cancel dispatch, disabled gyro and volume keys passed.");
    }
}
'''
jdk=Path(os.environ['JAVA_HOME'])/'bin' if os.environ.get('JAVA_HOME') else None
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp);(path/'OverlayNavigationTest.java').write_text(fixture+constants+'\n'+direction+keys+checks)
    subprocess.run([str(jdk/'javac') if jdk else 'javac','-d',str(path),str(path/'OverlayNavigationTest.java')],check=True)
    subprocess.run([str(jdk/'java') if jdk else 'java','-ea','-cp',str(path),'OverlayNavigationTest'],check=True)
