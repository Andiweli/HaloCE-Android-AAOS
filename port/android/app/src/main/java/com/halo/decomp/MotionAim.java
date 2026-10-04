package com.halo.decomp;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.widget.Toast;

/** Optional device gyro; active gameplay enables additional camera movement. */
final class MotionAim implements SensorEventListener {
    private static final String TAG="HaloGyro";
    private static native void nativeEnabled(boolean enabled);
    private static native boolean nativeAiming();
    private static native void nativeDelta(float yaw,float pitch);
    private static native long nativeState();

    private final HaloActivity activity;
    private final SensorManager manager;
    private final Sensor calibrated, uncalibrated;
    private Sensor gyro;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final MotionAimMath math=new MotionAimMath();
    private boolean enabled,resumed,focused,overlay,registered,lastAllowed,failed;
    private int sensitivity=100,accuracy=-1,reports;
    private long events,sent,lastStateLog;
    private float peakRate;

    MotionAim(HaloActivity activity) {
        this.activity=activity;
        manager=(SensorManager)activity.getSystemService(Context.SENSOR_SERVICE);
        calibrated=manager==null?null:manager.getDefaultSensor(Sensor.TYPE_GYROSCOPE);
        uncalibrated=manager==null?null:manager.getDefaultSensor(Sensor.TYPE_GYROSCOPE_UNCALIBRATED);
        gyro=calibrated!=null?calibrated:uncalibrated;
        focused=activity.getWindow().getDecorView().hasWindowFocus();
    }
    boolean available(){return gyro!=null;}
    void configure(boolean enabled,int sensitivity) {
        enabled=enabled && available();
        sensitivity=Math.max(25,Math.min(200,sensitivity));
        if(this.enabled==enabled && this.sensitivity==sensitivity)return;
        this.enabled=enabled;this.sensitivity=sensitivity;
        math.reset();refresh();
    }
    void resume(){resumed=true;refresh();}
    void suspend(){resumed=false;refresh();}
    void focus(boolean focused){this.focused=focused;refresh();}
    void overlay(boolean overlay){this.overlay=overlay;refresh();}

    private boolean register(Sensor sensor) {
        if(sensor==null)return false;
        try {
            if(manager.registerListener(this,sensor,10000,0,handler)) {
                gyro=sensor;return true;
            }
        } catch(SecurityException | IllegalArgumentException e) {
            Log.w(TAG,"Sensor registration failed: "+e.getClass().getSimpleName());
        }
        return false;
    }
    private void refresh() {
        boolean wanted=enabled && resumed && focused && !overlay;
        boolean wasRegistered=registered;
        if(wanted && !registered)
            registered=register(calibrated) || register(uncalibrated);
        else if(!wanted && registered) {
            manager.unregisterListener(this);registered=false;
        }
        math.reset();lastAllowed=false;
        nativeEnabled(wanted && registered);
        if(!wanted)failed=false;
        if(wanted && !registered && !failed) {
            failed=true;Log.w(TAG,"No gyro listener could be registered");
            Toast.makeText(activity,failureMessage(),Toast.LENGTH_LONG).show();
        }
        if(registered!=wasRegistered) {
            handler.removeCallbacks(report);
            if(registered) {
                events=sent=0;peakRate=0;accuracy=-1;
                Log.i(TAG,"registered type="+gyro.getType()+" name="+gyro.getName()+
                    " vendor="+gyro.getVendor()+" minDelayUs="+gyro.getMinDelay()+
                    " sensitivity="+sensitivity);
                scheduleReports();
            } else Log.i(TAG,"listener stopped; resumed="+resumed+" focused="+focused+" overlay="+overlay);
        }
    }
    private String failureMessage() {
        String language=activity.getResources().getConfiguration().getLocales().get(0).getLanguage();
        switch(language) {
            case "de":return "Gyroskop konnte nicht aktiviert werden.";
            case "fr":return "Impossible d’activer le gyroscope.";
            case "it":return "Impossibile attivare il giroscopio.";
            default:return "Could not activate the gyroscope.";
        }
    }
    private void scheduleReports() {
        handler.removeCallbacks(report);reports=4;handler.postDelayed(report,5000);
    }
    private final Runnable report=new Runnable() {
        @Override public void run() {
            if(!registered || reports<=0)return;
            logState("sample summary");reports--;
            if(reports>0)handler.postDelayed(this,5000);
        }
    };
    private void logState(String reason) {
        long state=nativeState();
        Log.i(TAG,reason+" events="+events+" sent="+sent+" peakRadS="+peakRate+
            " accuracy="+accuracy+" nativeFlags=0x"+Long.toHexString(state&0xffffffffL)+
            " consumed="+(state>>>32));
    }
    @Override public void onSensorChanged(SensorEvent event) {
        if(!registered || !enabled || !resumed || !focused || overlay)return;
        if(event.sensor==null || event.sensor.getType()!=gyro.getType() || event.values.length<3)return;
        events++;accuracy=event.accuracy;
        float x=event.values[0],y=event.values[1],z=event.values[2];
        if(gyro.getType()==Sensor.TYPE_GYROSCOPE_UNCALIBRATED && event.values.length>=6) {
            x-=event.values[3];y-=event.values[4];z-=event.values[5];
        }
        if(Float.isFinite(x) && Float.isFinite(y) && Float.isFinite(z))
            peakRate=Math.max(peakRate,Math.max(Math.abs(x),Math.max(Math.abs(y),Math.abs(z))));
        boolean allowed=nativeAiming();
        if(allowed!=lastAllowed) {
            math.reset();lastAllowed=allowed;
            long now=SystemClock.uptimeMillis();
            if(now-lastStateLog>=1500) {lastStateLog=now;logState("gameplay="+allowed);}
            if(allowed)scheduleReports();
        }
        if(!allowed){math.reset();return;}
        // Accuracy is calibration metadata. A zero status must not suppress
        // all finite rate samples; math still rejects invalid values/time gaps.
        int rotation=activity.getWindowManager().getDefaultDisplay().getRotation();
        if(math.sample(event.timestamp,rotation,x,y,z,sensitivity/100f)) {
            nativeDelta(math.yaw,math.pitch);sent++;
        }
    }
    @Override public void onAccuracyChanged(Sensor sensor,int accuracy) {
        if(sensor!=null && gyro!=null && sensor.getType()==gyro.getType())this.accuracy=accuracy;
    }
}
