#ifndef HALO_ANDROID_CONTROLS_H
#define HALO_ANDROID_CONTROLS_H
void host_touch_read(unsigned int *buttons, float *x, float *y);
void host_touch_look(float *x, float *y);
void host_touch_mode(int mode);
float host_audio_gain(int category);
void host_audio_profile(const char *key);
int host_audio_level(int category);
int host_audio_set_level(int category, int value);

#endif
