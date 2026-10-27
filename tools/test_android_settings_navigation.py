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
constants=next(line.strip() for line in source.splitlines() if 'int FRAME_RATE=' in line)
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
    Slider[] sliders=new Slider[8];Widget[] targets=new Widget[CANCEL+1];
    Toggle frameRateSwitch=new Toggle(),gyroSwitch=new Toggle(),gyroInvertSwitch=new Toggle();
    /* the order of SettingsOverlay.show: volumes and display (sliders 0-4),
    60 FPS, gyro enable, invert, sensitivity (slider 5), the sticks (6, 7) */
    OverlayNavigationTest(boolean gyro){
        for(int i=0;i<8;i++){sliders[i]=new Slider();targets[i<5?i:i-5+GYRO_SLIDER]=sliders[i];}
        targets[FRAME_RATE]=frameRateSwitch;targets[GYRO_TOGGLE]=gyroSwitch;targets[GYRO_INVERT]=gyroInvertSwitch;
        targets[OK]=new Widget();targets[CANCEL]=new Widget();
        targets[GYRO_TOGGLE].enabled=targets[GYRO_INVERT].enabled=targets[GYRO_SLIDER].enabled=gyro;
    }
    boolean isOpen(){return open;}void close(boolean save){this.save=save;open=false;}
    void press(int code){assert key(new KeyEvent(code));}
'''
checks=r'''
    public static void main(String[] args){
        OverlayNavigationTest t=new OverlayNavigationTest(true);
        for(int i=0;i<5;i++)t.press(KeyEvent.KEYCODE_DPAD_DOWN);
        assert t.selected==FRAME_RATE; /* the display's 60 FPS switch after gamma */
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.frameRateSwitch.checked && t.selected==FRAME_RATE;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert !t.frameRateSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.frameRateSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert !t.frameRateSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);
        assert t.selected==GYRO_TOGGLE; /* Enable, invert, then sensitivity. */
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.gyroSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert !t.gyroSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.gyroSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);assert t.selected==GYRO_INVERT;
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.gyroInvertSwitch.checked && t.selected==GYRO_INVERT;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert !t.gyroInvertSwitch.checked;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.gyroInvertSwitch.checked;
        /* Invert changes neither gyro enable nor 60 FPS. */
        assert t.gyroSwitch.checked && !t.frameRateSwitch.checked;
        t.press(KeyEvent.KEYCODE_ENTER);assert !t.gyroInvertSwitch.checked && t.selected==GYRO_INVERT;
        t.press(KeyEvent.KEYCODE_DPAD_CENTER);assert t.gyroInvertSwitch.checked && t.selected==GYRO_INVERT;
        KeyEvent repeated=new KeyEvent(KeyEvent.KEYCODE_BUTTON_A);repeated.repeat=1;
        assert t.key(repeated) && t.gyroInvertSwitch.checked;
        KeyEvent released=new KeyEvent(KeyEvent.KEYCODE_BUTTON_A);released.action=1;
        assert t.key(released) && t.gyroInvertSwitch.checked;
        for(Slider slider:t.sliders)assert slider.progress==75;
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);assert t.selected==GYRO_SLIDER;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.sliders[5].progress==80;
        assert t.sliders[4].progress==75; /* Gamma is untouched. */
        t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==GYRO_INVERT;
        t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==GYRO_TOGGLE;
        t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==FRAME_RATE;
        for(int i=0;i<4;i++)t.press(KeyEvent.KEYCODE_DPAD_DOWN);
        assert t.selected==LEFT_STICK;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.sliders[6].progress==80;
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);assert t.selected==RIGHT_STICK;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert t.sliders[7].progress==70;
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.selected==OK;
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.targets[OK].clicked==1;
        t.press(KeyEvent.KEYCODE_DPAD_RIGHT);assert t.selected==CANCEL;
        t.press(KeyEvent.KEYCODE_BUTTON_A);assert t.targets[CANCEL].clicked==1;
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);assert t.selected==CANCEL;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert t.selected==OK;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert t.selected==OK;
        t.press(KeyEvent.KEYCODE_BUTTON_B);assert !t.open && !t.save;
        assert !t.key(new KeyEvent(KeyEvent.KEYCODE_ENTER));
        t=new OverlayNavigationTest(false);
        for(int i=0;i<5;i++)t.press(KeyEvent.KEYCODE_DPAD_DOWN);
        assert t.selected==FRAME_RATE; /* 60 FPS needs no gyroscope */
        t.press(KeyEvent.KEYCODE_DPAD_DOWN);
        assert t.selected==LEFT_STICK; /* Skip all three unavailable gyro controls. */
        t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==FRAME_RATE;
        t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==4;
        t.press(KeyEvent.KEYCODE_DPAD_LEFT);assert t.sliders[4].progress==70;
        for(int code:new int[]{KeyEvent.KEYCODE_VOLUME_UP,KeyEvent.KEYCODE_VOLUME_DOWN,KeyEvent.KEYCODE_VOLUME_MUTE})
            assert !t.key(new KeyEvent(code));
        t.selected=0;t.press(KeyEvent.KEYCODE_DPAD_UP);assert t.selected==0;
        for(int code:new int[]{KeyEvent.KEYCODE_BUTTON_B,KeyEvent.KEYCODE_BACK,KeyEvent.KEYCODE_ESCAPE}){
            t=new OverlayNavigationTest(true);t.press(code);assert !t.open && !t.save;
        }
        System.out.println("Production overlay keys: 60 FPS switch, gyro enable/invert/sensitivity and stick order, independent toggles, repeat/release safety, confirm/cancel dispatch, disabled gyro and volume keys passed.");
    }
}
'''
jdk=Path(os.environ['JAVA_HOME'])/'bin' if os.environ.get('JAVA_HOME') else None
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp);(path/'OverlayNavigationTest.java').write_text(fixture+constants+'\n'+direction+keys+checks)
    subprocess.run([str(jdk/'javac') if jdk else 'javac','-d',str(path),str(path/'OverlayNavigationTest.java')],check=True)
    subprocess.run([str(jdk/'java') if jdk else 'java','-ea','-cp',str(path),'OverlayNavigationTest'],check=True)
