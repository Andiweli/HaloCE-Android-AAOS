#ifndef HALO_ANDROID_CONTROLS_H
#define HALO_ANDROID_CONTROLS_H
#define HALO_ANDROID_TOUCH_MODE_MASK 3
#define HALO_ANDROID_TOUCH_AIMING 4
#define HALO_ANDROID_LEFT_STICK_LOOK 1u
#define HALO_ANDROID_RIGHT_STICK_LOOK 2u
void host_touch_read(unsigned int *buttons, float *x, float *y);
void host_touch_look(float *x, float *y);
/* Radians, independent of mouse sensitivity; adds to stick/touch look. */
void host_motion_look(float *yaw, float *pitch);
void host_touch_mode(int mode);
int host_settings_active(void);
/* Bit 0: digital L2 held, bit 1: digital R2 held, where SDL maps no trigger to them. */
int host_sdl_gamepad_digital_triggers(unsigned int gamepad);
void host_settings_sticks(float *left, float *right);
void host_settings_stick_look_mask(unsigned int mask);
/* Nonzero: the settings' 60 FPS (interpolation); zero: the original 30. */
int host_settings_sixty_fps(void);
/* The menu's texture filtering: 1 (off), 2, 4 or 8; 0 for the configuration's. */
int host_settings_texture_filter(void);
/* The menu's anti-aliasing: 0 (off), 2 or 4 samples. */
int host_settings_msaa(void);
/* The most samples the GPU renders with (0: no anti-aliasing), said once. */
void host_settings_msaa_limit(int samples);
/* The menu's depth of field: its strength in per cent (10 to 200), 0 while off. */
int host_settings_depth_of_field(void);
/* The menu's FPS display: a picture shown (at the size it was drawn), a frame the game advanced in. */
void host_settings_picture(int width, int height);
void host_settings_game_frame(void);
/* Nonzero: the menu's FXAA. */
int host_settings_fxaa(void);
/* The menu's cheats (SettingsOverlay.java, cheats.c): the switches, kept
while on; the buttons, each done once in the game's next frame. */
#define HALO_ANDROID_CHEAT_HEALTH 1u
#define HALO_ANDROID_CHEAT_AMMO 2u
#define HALO_ANDROID_CHEAT_NEVER_RELOAD 4u
#define HALO_ANDROID_CHEAT_ONE_HIT_KILL 8u
#define HALO_ANDROID_CHEAT_SWITCHES 15u
#define HALO_ANDROID_CHEAT_ACTION_WEAPONS 0
#define HALO_ANDROID_CHEAT_ACTION_WARTHOG 1
#define HALO_ANDROID_CHEAT_ACTIONS 2
#define HALO_ANDROID_CHEAT_RESULT_NONE 0
#define HALO_ANDROID_CHEAT_RESULT_PENDING 1
#define HALO_ANDROID_CHEAT_RESULT_DONE 2
#define HALO_ANDROID_CHEAT_RESULT_MISSING 3
#define HALO_ANDROID_CHEAT_RESULT_NO_GAME 4
/* The switches; *actions gets the buttons pressed since the last call (bit = action). */
unsigned int host_settings_cheats(unsigned int *actions);
void host_settings_cheat_done(int action, int result);
float host_audio_gain(int category);
void host_audio_profile(const char *key);
int host_audio_level(int category);
int host_audio_set_level(int category, int value);

#endif
