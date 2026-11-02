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
        KEYCODE_BUTTON_L1=102;
}
public class MenuCheck {
''' + constants + '\n' + '\n'.join(method(m) for m in (
    'static int action(', 'static int stepped(', 'static int toggled(', 'static int filter(',
    'static int msaa(', 'static boolean msaaOffered(', 'static int dofStrength(')) + '\n' + fps_methods + r'''
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
        check(action(KeyEvent.KEYCODE_BUTTON_X)==NONE && action(KeyEvent.KEYCODE_BUTTON_L1)==NONE,"other buttons do nothing");
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
        check(filter(1)==1 && filter(2)==2 && filter(8)==8 && filter(16)==DEFAULT_FILTER && filter(0)==DEFAULT_FILTER,
              "texture filtering: off, 2, 4, 8, else the configuration's 4");
        check(FILTERS.length==4 && FILTERS[0]==1,"the choices off, 2x, 4x, 8x");
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
        System.out.println("menu java ok");
    }
}
'''

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
print(f'In-game menu: {len(base)} texts in English, German, French and Italian; keys, sliders, switches and '
      'texture filtering; the cheats from the menu to the game and back.')
