#!/usr/bin/env python3
"""Check the in-game menu (SettingsOverlay.java) and its cheats without a device.

1. The menu's texts: English, German, French and Italian have every string,
   with the same format arguments, and every R.string the Java code uses.
2. The production key mapping, slider steps, cheat switches and texture
   filter choices of SettingsOverlay.java (its static methods, compiled
   against a KeyEvent fixture; requires a JDK).
3. The production cheat mailbox of host_touch.c and android_cheats_update
   of cheats.c, compiled together with fixtures for the game: the switches
   set the original cheat globals only when the menu changes them, never
   in another's network game; each button runs once and is answered (done,
   no Warthog in this level, not in a game).
"""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_upstream_optimizations import function  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'port/android/app/src/main/res'
JAVA = ROOT / 'port/android/app/src/main/java/com/halo/decomp'
overlay = (JAVA / 'SettingsOverlay.java').read_text()

# ---------- 1. texts
def strings(folder):
    text = ''.join(p.read_text() for p in sorted((RES / folder).glob('strings*.xml')))
    return dict(re.findall(r'<string name="([a-z_0-9]+)"[^>]*>(.*?)</string>', text, re.S))

base = strings('values')
for language in ('de', 'fr', 'it'):
    other = strings('values-' + language)
    missing = set(base) - set(other) - {'app_name'}
    assert not missing, (language, missing)
    for name, text in other.items():
        assert sorted(re.findall(r'%\d\$[sd]', text)) == sorted(re.findall(r'%\d\$[sd]', base[name])), (language, name)
        assert "'" not in text.replace("\\'", ''), (language, name, 'unescaped apostrophe')
used = set()
for path in JAVA.glob('*.java'):
    used |= set(re.findall(r'R\.string\.([a-z_0-9]+)', path.read_text()))
assert used <= set(base), used - set(base)
assert strings('values-de')['menu_title'] == 'HALO CE Ingame-Menü'
assert strings('values-de')['menu_resume'] == 'Zurück zum Spiel'
assert strings('values-de')['menu_dof'] == 'Tiefenschärfe'
for name in ('menu_display', 'menu_controls', 'menu_audio', 'menu_cheats', 'menu_msaa', 'menu_dof', 'menu_source_line'):
    assert name in used, name

# ---------- 2. the Java side
def method(start):
    at = overlay.index(start)
    depth = 0
    for index in range(overlay.index('{', at), len(overlay)):
        depth += {'{': 1, '}': -1}.get(overlay[index], 0)
        if depth == 0:
            return overlay[at:index + 1]
    raise ValueError(start)

fps_source = (JAVA / 'FpsCounter.java').read_text()


def braced(source, start):
    at = source.index(start)
    depth = 0
    for index in range(source.index('{', at), len(source)):
        depth += {'{': 1, '}': -1}.get(source[index], 0)
        if depth == 0:
            return source[at:index + 1]
    raise ValueError(start)


fps_methods = '\n'.join(braced(fps_source, m) for m in ('static String line(', 'static String hz(', 'static String size('))
constants = '\n'.join(line for line in overlay.splitlines()
                      if re.match(r'\s+static final (int|String)(\[\])? [A-Z_]+[ =,].*;$', line))
java = 'package check;\nimport java.util.Locale;\n' + r'''
class KeyEvent {
    static final int KEYCODE_VOLUME_UP=24,KEYCODE_VOLUME_DOWN=25,KEYCODE_VOLUME_MUTE=164,KEYCODE_DPAD_UP=19,
        KEYCODE_DPAD_DOWN=20,KEYCODE_DPAD_LEFT=21,KEYCODE_DPAD_RIGHT=22,KEYCODE_BUTTON_A=96,KEYCODE_DPAD_CENTER=23,
        KEYCODE_ENTER=66,KEYCODE_NUMPAD_ENTER=160,KEYCODE_SPACE=62,KEYCODE_BUTTON_B=97,KEYCODE_BACK=4,
        KEYCODE_ESCAPE=111,KEYCODE_BUTTON_START=108,KEYCODE_BUTTON_SELECT=109,KEYCODE_MENU=82,KEYCODE_BUTTON_X=99,
        KEYCODE_BUTTON_L1=102,KEYCODE_BUTTON_R1=103,KEYCODE_Q=45,KEYCODE_E=33,KEYCODE_PAGE_UP=92,KEYCODE_PAGE_DOWN=93,
        KEYCODE_BUTTON_Y=100;
}
class ArrowSelector {
''' + braced((JAVA / 'ArrowSelector.java').read_text(), 'static int keys(') + r'''
}
public class MenuCheck {
''' + constants + '\n' + '\n'.join(method(m) for m in (
    'static int action(', 'static int stepped(', 'static int toggled(', 'static int filter(',
    'static int msaa(', 'static boolean msaaOffered(', 'static int dofStrength(',
    'static int mouseSensitivity(', 'static int resolution(', 'static int upscaler(', 'static int pictureLines(',
    'static boolean upscales(')) + '\n' + fps_methods + r'''
    static void check(boolean condition,String what){if(!condition)throw new AssertionError(what);}
    public static void main(String[] args){
        check(action(KeyEvent.KEYCODE_VOLUME_UP)==PASS && action(KeyEvent.KEYCODE_VOLUME_MUTE)==PASS,"volume keys stay Android's");
        check(action(KeyEvent.KEYCODE_DPAD_UP)==UP && action(KeyEvent.KEYCODE_DPAD_DOWN)==DOWN &&
              action(KeyEvent.KEYCODE_DPAD_LEFT)==LEFT && action(KeyEvent.KEYCODE_DPAD_RIGHT)==RIGHT,"D-pad moves");
        check(action(KeyEvent.KEYCODE_BUTTON_A)==PRESS && action(KeyEvent.KEYCODE_ENTER)==PRESS &&
              action(KeyEvent.KEYCODE_DPAD_CENTER)==PRESS,"A presses");
        check(action(KeyEvent.KEYCODE_BUTTON_B)==BACK && action(KeyEvent.KEYCODE_BACK)==BACK &&
              action(KeyEvent.KEYCODE_ESCAPE)==BACK,"B goes back a page");
        check(action(KeyEvent.KEYCODE_BUTTON_START)==CLOSE && action(KeyEvent.KEYCODE_BUTTON_SELECT)==CLOSE,"Start closes");
        check(action(KeyEvent.KEYCODE_BUTTON_X)==NONE && action(KeyEvent.KEYCODE_BUTTON_Y)==NONE,"other buttons do nothing");
        check(action(KeyEvent.KEYCODE_BUTTON_L1)==STEP_BACK && action(KeyEvent.KEYCODE_Q)==STEP_BACK &&
              action(KeyEvent.KEYCODE_PAGE_UP)==STEP_BACK,"L1, Q, Page up step a value back");
        check(action(KeyEvent.KEYCODE_BUTTON_R1)==STEP_ON && action(KeyEvent.KEYCODE_E)==STEP_ON &&
              action(KeyEvent.KEYCODE_PAGE_DOWN)==STEP_ON,"R1, E, Page down step it on");
        check(mouseSensitivity(MOUSE_DEFAULT)==100 && mouseSensitivity(0)==MOUSE_MIN && mouseSensitivity(9999)==MOUSE_MAX
              && mouseSensitivity(102)==100 && (MOUSE_MAX-MOUSE_MIN)%MOUSE_STEP==0,"the mouse's sensitivity: steps in range");
        check(KEYS.length==MIN.length && MIN.length==MAX.length,"one range per slider");
        for(int i=0;i<KEYS.length;i++){
            check(stepped(i,MIN[i],-1)==MIN[i] && stepped(i,MAX[i],1)==MAX[i],"slider "+KEYS[i]+" stays in its range");
            check(stepped(i,100,1)==Math.min(MAX[i],100+STEP),"slider "+KEYS[i]+" steps by "+STEP);
            check(MIN[i]<=100 && MAX[i]>=100,"100 % (the default) within "+KEYS[i]);
        }
        check(KEYS[BRIGHTNESS].equals("brightness") && KEYS[GAMMA].equals("gamma") && KEYS[MASTER].equals("master"),
              "the settings keep their stored names");
        int bits=0;
        bits=toggled(bits,CHEAT_HEALTH,true);bits=toggled(bits,CHEAT_ONE_HIT,true);
        check(bits==(CHEAT_HEALTH|CHEAT_ONE_HIT),"switches add");
        check(toggled(bits,CHEAT_HEALTH,false)==CHEAT_ONE_HIT,"and come off one at a time");
        check(toggled(0xff,CHEAT_AMMO,true)==CHEAT_SWITCHES,"never more than the four");
        check(filter(1)==1 && filter(2)==2 && filter(8)==8 && filter(16)==16 && filter(32)==DEFAULT_FILTER &&
              filter(0)==DEFAULT_FILTER,"texture filtering: off, 2, 4, 8, 16, else the configuration's 4");
        check(FILTERS.length==5 && FILTERS[0]==1 && FILTERS[4]==16,"the choices off, 2x, 4x, 8x, 16x");
        check(msaa(0)==0 && msaa(2)==2 && msaa(4)==4 && msaa(8)==0 && msaa(-1)==0,"MSAA: off, 2x, 4x, else off");
        check(msaaOffered(0,0) && !msaaOffered(2,0) && !msaaOffered(4,0),"no MSAA on the GPU: only off");
        check(msaaOffered(2,2) && !msaaOffered(4,2) && msaaOffered(4,4),"the GPU's most samples and fewer");
        check(msaaOffered(4,-1),"all while the GPU is not yet asked");
        check(SOURCE_URL.equals("https://github.com/Andiweli/HaloCE-Android-AAOS"),"the port's page");
        check(line("%1$d FPS (Spiel)","%1$d FPS (Spiel) · %2$d FPS (Bild)",false,30,30).equals("30 FPS (Spiel)"),"30 FPS");
        check(line("%1$d FPS (Spiel)","%1$d FPS (Spiel) · %2$d FPS (Bild)",true,30,60).equals("30 FPS (Spiel) · 60 FPS (Bild)"),"60 FPS");
        check(hz(59.94f).equals(" · 60 Hz") && hz(0).equals(""),"the screen's rate");
        check(size(2400,1080).equals(" · 2400×1080") && size(0,0).equals(""),"the picture's size");
        check(dofStrength(50)==50 && dofStrength(200)==200 && dofStrength(10)==10,"the depth of field's strengths");
        check(dofStrength(0)==DOF_DEFAULT && dofStrength(210)==DOF_DEFAULT && dofStrength(55)==DOF_DEFAULT && DOF_DEFAULT==50,
              "else the default 50 %");
        check(RESOLUTIONS.length==4 && RESOLUTIONS[0]==480 && RESOLUTIONS[1]==720 && RESOLUTIONS[2]==1080 && RESOLUTIONS[3]==0,
              "the resolutions: original 480p, 720p, 1080p, native");
        check(resolution(480)==480 && resolution(0)==0 && resolution(1080)==1080 && resolution(999)==DEFAULT_RESOLUTION &&
              DEFAULT_RESOLUTION==1080,"a stored resolution, else 1080p");
        check(upscaler(0)==0 && upscaler(1)==1 && upscaler(2)==2 && upscaler(3)==0 && upscaler(-1)==0,"linear, SGSR, FSR, else linear");
        check(pictureLines(1080,720)==720 && pictureLines(0,1440)==1440 && pictureLines(720,1440)==720 && pictureLines(1080,400)==480,
              "never more lines than the screen's, never fewer than 480");
        check(!upscales(0,1080) && !upscales(1080,1080) && !upscales(1080,720) && upscales(720,1080) && upscales(480,1080) &&
              upscales(1080,1440) && !upscales(1080,0),"the upscaler only while the picture is smaller than the screen");
        System.out.println("menu java ok");
    }
}
'''

# ---------- 2b. the CubeEvil4 1.1.0 look and the keyboard & mouse section (source level)
assert overlay.count('selector(') >= 3, 'MSAA, the resolution and the upscaler are arrow cells'
for choice in ('R.string.menu_msaa,',):
    assert 'selector(' + overlay[overlay.index(choice) - 40:overlay.index(choice)].split('selector(')[-1] + choice in overlay, choice
assert 'setAllowed(i,msaaOffered(MSAA[i],limit))' in overlay, "MSAA steps the GPU can't do are passed over"
for page in ('private void display(', 'private void controls(', 'private void audio(', 'private void cheats('):
    assert 'labelled(R.string.menu_side_' in method(page), page + ' has side labels'
for slider in ('BRIGHTNESS', 'GAMMA', 'GYRO', 'LEFT_STICK', 'RIGHT_STICK', 'MASTER', 'EFFECTS', 'MUSIC'):
    assert re.search(r'percentCell\([\w()]+,R\.string\.\w+,%s\)' % slider, overlay), slider + ' is a slider cell'
assert 'setMinHeight(dp(64))' in method('private Button cellAction('), 'cells 64 dp high'
assert 'SeekBar' not in overlay, 'no bare slider rows left'
# across both columns (the project owner, 22.11.2026): the gyro's sensitivity, the master volume, the texture filtering
assert 'percentCell(single(gyroGroup),R.string.menu_gyro_sensitivity,GYRO)' in overlay
assert 'percentCell(single(sound),R.string.menu_master,MASTER)' in overlay
assert 'single(labelled(R.string.menu_side_textures))' in overlay and 'sliderCell(textures,s(R.string.menu_texture_filter)' in overlay
# the touch controls Auto / Force / Suppress first under Controls, kept and handed to HaloPort (23.11.2026)
controls_page = method('private void controls(')
assert controls_page.index('R.string.menu_touch') < controls_page.index('R.string.menu_motion'), 'touch first'
assert 'selector(touch,R.string.menu_touch_controls' in controls_page and 'activity.touchControls(setting)' in controls_page
assert 'prefs.edit().putInt(HaloPort.TOUCH_KEY,setting)' in controls_page
assert strings('values-de')['menu_touch_always'] == 'Erzwingen' and strings('values-de')['menu_touch_never'] == 'Unterdrücken'
# the FPS display: its frame shows and hides it, the line itself never hidden (it never showed so)
fps_source = (ROOT / 'port/android/app/src/main/java/com/halo/decomp/FpsCounter.java').read_text()
assert 'view.setVisibility(' not in fps_source and 'frame.setVisibility(shown ? View.VISIBLE : View.GONE)' in fps_source
# the mouse: no hover look (as CubeEvil4's), a pressed look; its axes never move the focus
assert 'state_hovered' not in overlay and 'state_pressed},shape(PRESSED' in overlay
assert "!e.isFromSource(android.view.InputDevice.SOURCE_JOYSTICK))return;" in method('void motion(')
# the resolution and the upscaler (Display): kept, sent at the start and on each change, the upscaler only offered
# while it has something to do
display_page = method('private void display(')
assert 'R.string.menu_resolution,' in display_page and 'R.string.menu_upscaler,' in display_page
assert 'enableUpscaler(upscaling[0],upscales(lines,screenLines))' in display_page
assert 'enableUpscaler(upscaling[0],upscales(resolutionLines,screenLines))' in display_page
assert 'nativeResolution(resolutionLines);' in overlay and 'nativeUpscaler(upscalerChoice);' in overlay
for key in ('"resolution"', '"upscaler"'):
    assert overlay.count(key) >= 2, key + ' read and kept'
for key in ('"texture_filter"', '"cheats"', '"msaa"', '"depth_of_field"', '"depth_of_field_strength"', '"fxaa"',
            '"fps_display"', '"sixty_fps"', '"gyro_aim"', '"gyro_invert_pitch"', '"mouse_sensitivity"', '"mouse_invert"'):
    assert overlay.count(key) >= 2, key + ' read and kept'
controls_page = method('private void controls(')
assert 'R.string.menu_keyboard_mouse' in controls_page and 'R.string.menu_mouse_sensitivity' in controls_page
assert 'R.string.menu_mouse_invert' in controls_page and 'keyOverview(' in controls_page
assert 'nativeMouseLook(mouseSensitivity,mouseInvert)' in method('private void apply(')
rows = re.findall(r'\{R\.string\.(menu_key_\w+),R\.string\.(menu_keys_\w+)\}', overlay)
assert len(rows) == 16 and all(a[len('menu_key_'):] == b[len('menu_keys_'):] for a, b in rows), rows
# the overview says what keyboard_gamepad does (xinput_sdl.c)
xinput = (ROOT / 'port/linux/src/xinput_sdl.c').read_text()
pad = braced(xinput, 'static void keyboard_gamepad(')
for code, role in (('W', None), ('A', None), ('S', None), ('D', None), ('SPACE', 'A'), ('RETURN', 'A'), ('F', 'B'),
                   ('BACKSPACE', 'B'), ('E', 'X'), ('R', 'X'), ('TAB', 'Y'), ('Q', 'WHITE'), ('X', 'BLACK'),
                   ('G', 'LEFT_TRIGGER'), ('ESCAPE', 'START'), ('F1', 'BACK'), ('LCTRL', 'LEFT_THUMB'), ('C', 'LEFT_THUMB'),
                   ('Z', 'RIGHT_THUMB')):
    statement = next((st for st in pad.split(';') if 'k[SDL_SCANCODE_%s]' % code in st), None)
    assert statement is not None, code
    assert role is None or 'XINPUT_GAMEPAD_' + role in statement, (code, role)
assert 'm[SDL_BUTTON_LEFT]' in pad and 'm[SDL_BUTTON_RIGHT]' in pad and 'm[SDL_BUTTON_MIDDLE]' in pad and 'm[SDL_BUTTON_X1]' in pad
# the menu's mouse look in the game: a host import, under the lock, for the mouse's motion only
imports = (ROOT / 'port/android/host_imports.list').read_text().split()
assert 'host_settings_mouse_look' in imports
look = braced(touch_source := (ROOT / 'port/android/host/host_touch.c').read_text(), 'int host_settings_mouse_look(')
assert 'pthread_mutex_lock(&lock)' in look and 'pthread_mutex_unlock(&lock)' in look
assert 'Java_com_halo_decomp_SettingsOverlay_nativeMouseLook' in touch_source
mouse_look = braced(xinput, 'int halo_linux_mouse_look(')
assert mouse_look.index('host_settings_mouse_look(') < mouse_look.index('host_touch_look('), 'the touch look keeps its speed'

# the host's side: under the lock, a host import for the game, the JNI names the menu calls
touch_text = (ROOT / 'port/android/host/host_touch.c').read_text()
for name in ('host_settings_resolution', 'host_settings_upscaler'):
    body = braced(touch_text, 'int %s(' % name)
    assert 'pthread_mutex_lock(&lock)' in body and 'pthread_mutex_unlock(&lock)' in body, name
for name in ('nativeResolution', 'nativeUpscaler'):
    assert 'Java_com_halo_decomp_SettingsOverlay_' + name in touch_text, name
assert 'host_settings_resolution' in imports, 'the game asks the menu for the resolution'
assert 'static int settings_resolution=1080;' in touch_text, 'the host starts at the menu\'s default'

# the game's scale (d3d8_gl.c screen_lines_scale), compiled: lines / 480, within the screen and 480
gl_source = (ROOT / 'port/linux/src/d3d8_gl.c').read_text()
scale_c = '#include <assert.h>\n#include <stdio.h>\n#define SCREEN_HEIGHT 480\n' + braced(
    gl_source, 'static float screen_lines_scale(') + r'''
int main(void)
{
	assert(screen_lines_scale(1080, 0) == 1.0f);       /* the screen not known yet: the original */
	assert(screen_lines_scale(480, 1080) == 1.0f);     /* original */
	assert(screen_lines_scale(720, 1080) == 1.5f);
	assert(screen_lines_scale(1080, 1080) == 2.25f);
	assert(screen_lines_scale(1080, 720) == 1.5f);     /* never more than the screen */
	assert(screen_lines_scale(0, 1440) == 3.0f);       /* native */
	assert(screen_lines_scale(0, 400) == 1.0f);        /* never fewer than 480 */
	assert(screen_lines_scale(720, 600) == 1.25f);
	puts("resolution scale ok");
	return 0;
}
'''
assert 'host_settings_present(back_buffer->target.texture,(int)back_buffer->target.gl_width,' in gl_source, \
    'the present passes the picture\'s size for the upscaler'

# ---------- 3. the cheats, host and game together
controls = (ROOT / 'port/linux/include/halo_android_controls.h').read_text()
touch = (ROOT / 'port/android/host/host_touch.c').read_text()
cheats = (ROOT / 'source/game/cheats.c').read_text()
mailbox = touch[touch.index('/* the menu\'s cheats: the switches'):]
mailbox = mailbox[:mailbox.index('\n}\n', mailbox.index('void host_settings_cheat_done(')) + 3]
c = r'''
#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
typedef int jint; typedef void JNIEnv; typedef void *jclass;
#define JNIEXPORT
#define JNICALL
typedef int boolean;
#define TRUE 1
#define FALSE 0
#define NONE (-1)
''' + controls[controls.index('#define HALO_ANDROID_CHEAT_HEALTH'):controls.index('unsigned int host_settings_cheats')] + r'''
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
struct { boolean deathless_player, infinite_ammo, omnipotent, bottomless_clip; } cheat;
enum { _error_log };
static void error(int kind, const char *format, ...) { (void)kind; (void)format; }
static boolean distributed, warthog_here;
static long player = 0;
static int weapons, warthogs;
static boolean network_game_distributed_client(void) { return distributed; }
static long cheat_player_index(void) { return player; }
static void cheat_all_weapons(void) { weapons++; }
static boolean android_cheat_spawn_warthog(void) { if (!warthog_here) return FALSE; warthogs++; return TRUE; }
''' + mailbox + function(cheats, 'android_cheats_update') + r'''
#define nativeCheats Java_com_halo_decomp_SettingsOverlay_nativeCheats
#define nativeAction Java_com_halo_decomp_SettingsOverlay_nativeCheatAction
#define nativeResult Java_com_halo_decomp_SettingsOverlay_nativeCheatResult
int main(void)
{
	android_cheats_update(TRUE);  /* the first frame: all four as the menu has them (off) */
	assert(!cheat.deathless_player && !cheat.infinite_ammo && !cheat.bottomless_clip && !cheat.omnipotent);
	nativeCheats(0, 0, HALO_ANDROID_CHEAT_HEALTH | HALO_ANDROID_CHEAT_ONE_HIT_KILL);
	android_cheats_update(TRUE);
	assert(cheat.deathless_player && cheat.omnipotent && !cheat.infinite_ammo && !cheat.bottomless_clip);
	/* the console's (cheat_infinite_ammo) stays while the menu changes nothing */
	cheat.infinite_ammo = TRUE;
	android_cheats_update(TRUE);
	assert(cheat.infinite_ammo && cheat.deathless_player);
	nativeCheats(0, 0, HALO_ANDROID_CHEAT_ONE_HIT_KILL | HALO_ANDROID_CHEAT_NEVER_RELOAD | 0x100);
	android_cheats_update(TRUE);
	assert(!cheat.deathless_player && cheat.omnipotent && cheat.bottomless_clip && cheat.infinite_ammo);
	/* another's network game: the switches left to its host's rules */
	distributed = TRUE;
	memset(&cheat, 0, sizeof(cheat));
	nativeCheats(0, 0, HALO_ANDROID_CHEAT_SWITCHES);
	android_cheats_update(TRUE);
	assert(!cheat.deathless_player && !cheat.infinite_ammo && !cheat.bottomless_clip && !cheat.omnipotent);
	nativeAction(0, 0, HALO_ANDROID_CHEAT_ACTION_WEAPONS);
	assert(nativeResult(0, 0, HALO_ANDROID_CHEAT_ACTION_WEAPONS) == HALO_ANDROID_CHEAT_RESULT_PENDING);
	android_cheats_update(TRUE);
	assert(weapons == 0 && nativeResult(0, 0, HALO_ANDROID_CHEAT_ACTION_WEAPONS) == HALO_ANDROID_CHEAT_RESULT_NO_GAME);
	distributed = FALSE;
	android_cheats_update(TRUE);  /* back in a game of its own: the menu's switches again */
	assert(cheat.deathless_player && cheat.infinite_ammo && cheat.bottomless_clip && cheat.omnipotent);
	/* the buttons: once each, answered */
	nativeAction(0, 0, HALO_ANDROID_CHEAT_ACTION_WEAPONS);
	nativeAction(0, 0, HALO_ANDROID_CHEAT_ACTION_WARTHOG);
	android_cheats_update(TRUE);
	android_cheats_update(TRUE);
	assert(weapons == 1 && warthogs == 0);
	assert(nativeResult(0, 0, HALO_ANDROID_CHEAT_ACTION_WEAPONS) == HALO_ANDROID_CHEAT_RESULT_DONE);
	assert(nativeResult(0, 0, HALO_ANDROID_CHEAT_ACTION_WARTHOG) == HALO_ANDROID_CHEAT_RESULT_MISSING);
	warthog_here = TRUE;
	nativeAction(0, 0, HALO_ANDROID_CHEAT_ACTION_WARTHOG);
	android_cheats_update(TRUE);
	assert(warthogs == 1 && nativeResult(0, 0, HALO_ANDROID_CHEAT_ACTION_WARTHOG) == HALO_ANDROID_CHEAT_RESULT_DONE);
	/* the main menu (no game, no player) */
	nativeAction(0, 0, HALO_ANDROID_CHEAT_ACTION_WARTHOG);
	android_cheats_update(FALSE);
	assert(warthogs == 1 && nativeResult(0, 0, HALO_ANDROID_CHEAT_ACTION_WARTHOG) == HALO_ANDROID_CHEAT_RESULT_NO_GAME);
	player = NONE;
	nativeAction(0, 0, HALO_ANDROID_CHEAT_ACTION_WEAPONS);
	android_cheats_update(TRUE);
	assert(weapons == 1 && nativeResult(0, 0, HALO_ANDROID_CHEAT_ACTION_WEAPONS) == HALO_ANDROID_CHEAT_RESULT_NO_GAME);
	/* out-of-range buttons are ignored */
	nativeAction(0, 0, 7);
	nativeAction(0, 0, -1);
	assert(nativeResult(0, 0, 7) == HALO_ANDROID_CHEAT_RESULT_NO_GAME);
	puts("menu cheats ok");
	return 0;
}
'''

jdk = Path(os.environ['JAVA_HOME']) / 'bin' if os.environ.get('JAVA_HOME') else None
with tempfile.TemporaryDirectory(prefix='halo-menu-') as name:
    folder = Path(name)
    (folder / 'check').mkdir()
    (folder / 'check/MenuCheck.java').write_text(java)
    subprocess.run([str(jdk / 'javac') if jdk else 'javac', '-d', str(folder), str(folder / 'check/MenuCheck.java')], check=True)
    subprocess.run([str(jdk / 'java') if jdk else 'java', '-cp', str(folder), 'check.MenuCheck'], check=True)
    (folder / 'cheats.c').write_text(c)
    subprocess.run(['cc', '-std=gnu11', '-O1', '-Wall', '-Wno-unused-function', '-Wno-unused-parameter',
                    str(folder / 'cheats.c'), '-o', str(folder / 'cheats'), '-lpthread'], check=True)
    subprocess.run([str(folder / 'cheats')], check=True)
    (folder / 'scale.c').write_text(scale_c)
    subprocess.run(['cc', '-std=gnu11', '-O1', '-Wall', str(folder / 'scale.c'), '-o', str(folder / 'scale')], check=True)
    subprocess.run([str(folder / 'scale')], check=True)
print(f'In-game menu: {len(base)} texts in English, German, French and Italian; keys, sliders, switches and '
      'texture filtering, resolution and upscaling; the cheats from the menu to the game and back.')
