#ifndef HALO_ANDROID_CONTROLS_H
#define HALO_ANDROID_CONTROLS_H
#define HALO_ANDROID_TOUCH_MODE_MASK 3
#define HALO_ANDROID_TOUCH_AIMING 4
void host_touch_read(unsigned int *buttons, float *x, float *y);
void host_touch_look(float *x, float *y);
/* Radians, independent of mouse sensitivity; adds to stick/touch look. */
void host_motion_look(float *yaw, float *pitch);
void host_touch_mode(int mode);
float host_audio_gain(int category);
void host_audio_profile(const char *key);
int host_audio_level(int category);
int host_audio_set_level(int category, int value);

#endif
