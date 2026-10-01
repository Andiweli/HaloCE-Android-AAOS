package com.halo.decomp;

import android.app.Activity;
import android.content.Context;
import android.os.Build;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** Own native startup log; no READ_LOGS permission, ADB or logcat process. */
final class StartDiagnostics {
    private static File folder(Context context) {
        for (File dir : context.getExternalMediaDirs()) {
            if (dir != null && (dir.isDirectory() || dir.mkdirs()) && dir.canWrite()) return dir;
        }
        // Retain a readable in-app diagnostic if removable/shared storage fails.
        return context.getFilesDir();
    }
    static File log(Context context) { return new File(folder(context), "halo-diagnostic.txt"); }
    static File marker(Context context) { return new File(context.getFilesDir(), "halo-start-pending"); }
    static boolean interrupted(Context context) { return marker(context).exists(); }

    static void prepare(Activity activity) {
        try {
            File log = log(activity), previous = new File(log.getParentFile(), "halo-diagnostic-previous.txt");
            if (log.exists()) {
                try (InputStream in = new FileInputStream(log); OutputStream out = new FileOutputStream(previous)) {
                    byte[] b = new byte[8192]; int n; while ((n=in.read(b))!=-1) out.write(b,0,n);
                }
            }
            try (Writer out = new OutputStreamWriter(new FileOutputStream(log), StandardCharsets.UTF_8)) {
                android.content.pm.PackageInfo info = activity.getPackageManager().getPackageInfo(activity.getPackageName(),0);
                out.write("Halo start diagnostic - Patch11\nTime: " + new java.util.Date()
                    + "\nApp: " + info.versionName + " (" + info.getLongVersionCode() + ")"
                    + "\nFlavor: " + (BuildConfig.IS_AAOS ? "AAOS" : "mobile")
                    + "\nDevice: " + Build.MANUFACTURER + " " + Build.MODEL + " / " + Build.DEVICE
                    + "\nAndroid: " + Build.VERSION.RELEASE + " / API " + Build.VERSION.SDK_INT
                    + "\nABIs: " + java.util.Arrays.toString(Build.SUPPORTED_ABIS)
                    + "\nLog: " + log.getAbsolutePath() + "\n");
            }
            try (FileOutputStream out = new FileOutputStream(marker(activity))) { out.write(1); }
        } catch (Exception e) { android.util.Log.e("halo", "Diagnostic preparation failed",e); }
    }
    static void connect(Activity activity) {
        try { nativeOpen(log(activity).getAbsolutePath(), marker(activity).getAbsolutePath()); }
        catch (UnsatisfiedLinkError e) { append(activity,"Native diagnostics missing: old libmain.so: " + e); }
    }
    static void append(Context context, String text) {
        try (Writer out=new OutputStreamWriter(new FileOutputStream(log(context),true),StandardCharsets.UTF_8)) {
            out.write(text+"\n");
        } catch (IOException e) { android.util.Log.e("halo",text,e); }
    }
    static String read(Context context) {
        File file=log(context);
        try (RandomAccessFile in=new RandomAccessFile(file,"r")) {
            long start=Math.max(0,in.length()-48000);in.seek(start);
            byte[] bytes=new byte[(int)(in.length()-start)];in.readFully(bytes);
            return file.getAbsolutePath()+"\n\n"+(start>0?"[Last 48 KB]\n":"")+new String(bytes,StandardCharsets.UTF_8);
        } catch(IOException e) { return file.getAbsolutePath()+"\n"+e; }
    }
    private static native void nativeOpen(String path,String marker);
}
