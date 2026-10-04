package com.halo.decomp;

/** Gyro rates in the display's axes, integrated to radians per sample. */
final class MotionAimMath {
    private static final float QUIET_RATE = 0.006f;
    private long previous;
    private int rotation = -1;
    private float filteredYaw, filteredPitch;
    float yaw, pitch;

    void reset() {
        previous = 0;
        rotation = -1;
        filteredYaw = filteredPitch = yaw = pitch = 0;
    }

    boolean sample(long timestamp, int displayRotation, float x, float y, float z, float gain) {
        yaw = pitch = 0;
        if (!Float.isFinite(x) || !Float.isFinite(y) || !Float.isFinite(z) ||
                !Float.isFinite(gain) || gain <= 0 || Math.abs(x) > 25 ||
                Math.abs(y) > 25 || Math.abs(z) > 25 || timestamp <= 0) {
            reset();
            return false;
        }
        float dt = (timestamp - previous) * 1e-9f;
        if (previous == 0 || displayRotation != rotation || dt <= 0 || dt > 0.250f) {
            reset();
            previous = timestamp;
            rotation = displayRotation;
            return false;
        }
        previous = timestamp;
        float screenX, screenY;
        switch (displayRotation) {
            case 1: screenX = -y; screenY = x; break;   // Surface.ROTATION_90
            case 2: screenX = -x; screenY = -y; break;
            case 3: screenX = y; screenY = -x; break;
            default: screenX = x; screenY = y; break;
        }
        float alpha = (float)(1.0 - Math.exp(-dt / 0.020));
        filteredYaw += alpha * (quiet(screenY) - filteredYaw);
        filteredPitch += alpha * (quiet(screenX) - filteredPitch);
        yaw = clamp(filteredYaw * dt * gain);
        pitch = clamp(filteredPitch * dt * gain);
        return yaw != 0 || pitch != 0;
    }

    private static float quiet(float rate) {
        return Math.copySign(Math.max(0, Math.abs(rate) - QUIET_RATE), rate);
    }

    private static float clamp(float angle) {
        return Math.max(-0.12f, Math.min(0.12f, angle));
    }
}
