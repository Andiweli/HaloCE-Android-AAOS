package com.halo.decomp;

import android.app.Activity;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.RelativeLayout;
import android.widget.Toast;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Date;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** On-demand Shield matrix capture, visible only in diagnostic builds. */
final class GraphicsDiagnostics {
    private final Activity activity;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Button button;
    private boolean busy, closed;
    private File capture;

    GraphicsDiagnostics(Activity activity, ViewGroup parent) {
        this.activity = activity;
        button = new Button(activity);
        button.setText("GFX");
        button.setTextSize(12);
        button.setAlpha(0.7f);
        button.setContentDescription("Capture graphics diagnostic");
        button.setFocusable(false); // Preserve controller navigation in the game.
        float dp = activity.getResources().getDisplayMetrics().density;
        RelativeLayout.LayoutParams layout = new RelativeLayout.LayoutParams(Math.round(72 * dp),Math.round(48 * dp));
        layout.addRule(RelativeLayout.ALIGN_PARENT_TOP);
        layout.addRule(RelativeLayout.CENTER_HORIZONTAL);
        button.setOnClickListener(view -> capture());
        parent.addView(button,layout);
    }

    void capture() {
        if (!BuildConfig.HALO_DIAGNOSTICS_ENABLED || busy || closed) return;
        try {
            File media = null;
            for (File folder : activity.getExternalMediaDirs()) {
                if (folder != null && (folder.isDirectory() || folder.mkdirs()) && folder.canWrite()) {
                    media = folder; break;
                }
            }
            if (media == null) throw new IOException("Android/media is not writable");
            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss-SSS",Locale.ROOT).format(new Date());
            capture = new File(media,"halo-gfx-" + stamp);
            if (!capture.mkdir()) throw new IOException("Cannot create " + capture);
            try (Writer out = new OutputStreamWriter(new FileOutputStream(new File(capture,"device.txt")),StandardCharsets.UTF_8)) {
                android.content.pm.PackageInfo info = activity.getPackageManager().getPackageInfo(activity.getPackageName(),0);
                out.write("Halo GFX Shield CPU skeletal compatibility\nTime: " + new Date()
                    + "\nApp: " + info.versionName + " (" + info.getLongVersionCode() + ")"
                    + "\nFlavor: " + (BuildConfig.IS_AAOS ? "AAOS" : "mobile")
                    + "\nDevice: " + Build.MANUFACTURER + " " + Build.MODEL + " / " + Build.DEVICE
                    + "\nAndroid: " + Build.VERSION.RELEASE + " API " + Build.VERSION.SDK_INT
                    + "\nABIs: " + Arrays.toString(Build.SUPPORTED_ABIS)
                    + "\nGuest renderer: persistent geometry mirror bypassed; fresh vertex/index streaming."
                    + "\nNVIDIA skeletal programs execute on CPU; other devices/meshes retain their GPU vertex path."
                    + "\nCPU optimization v1: exact-match fixed executors for original skeletal microcode, interpreter fallback for other programs."
                    + "\nCPU skeletal GPU attributes: 0=clip position, 1..4=colours, 5..8=texcoords, 9=fog/point size."
                    + "\nCapture: GPU attributes/indices and shader sources; GPU c[0..191]/CPU Uniform4fv only for ordinary GPU programs."
                    + "\nNative log reports bounded NVIDIA CPU skeletal timing every 300 frames."
                    + "\nNative breakdown v1: input/setup, execute, pack and upload/bind in ms per active frame; fixed/total vertex counts."
                    + "\nCPU timing export: guest-log bridge v1; timing samples are included in halo-diagnostic.txt."
                    + "\nModel selection is a shader heuristic; capture bounds and skipped data are listed in report.txt."
                    + "\nShield performance test v1: overlay settings " + perfSettings()
                    + " (skinning mode 0 CPU threads, 1 CPU one core, 2 GPU uniform block, 3 GPU full constants, 4 GPU original;"
                    + " 0x100 visibility waits; 0x200 counter; 0x400 no object shadows). halo-perf v2 and halo-profile v1 lines"
                    + " every 300 frames in halo-diagnostic.txt."
                    + "\nCounter now:\n" + PerfOverlay.text()
                    + "\nNative MIRROR_UPLOAD_POLICY describes an unused mirror helper."
                    + "\nNative report labels Patch18/Patch23 are legacy labels, not APK revision identifiers.\n");
            }
            if (!nativeRequest(capture.getAbsolutePath())) throw new IOException("Capture already active");
            busy = true;
            button.setVisibility(View.INVISIBLE);
            handler.postDelayed(poll,250);
        } catch (Exception | UnsatisfiedLinkError e) {
            message("GFX: " + e.getMessage());
        }
    }

    private final Runnable poll = new Runnable() {
        @Override public void run() {
            if (closed) return;
            int state = nativeState();
            if (state == 1 || state == 2) { handler.postDelayed(this,250); return; }
            final File folder = capture;
            final boolean complete = state == 3;
            new Thread(() -> {
                String result;
                try {
                    File log = StartDiagnostics.log(activity);
                    if (log.isFile()) copy(log,new File(folder,"halo-diagnostic.txt"));
                    File zip = new File(folder.getParentFile(),folder.getName() + ".zip");
                    File part = new File(folder.getParentFile(),folder.getName() + ".zip.part");
                    File[] files = folder.listFiles();
                    if (files == null) throw new IOException("Capture directory cannot be read");
                    Arrays.sort(files);
                    try (ZipOutputStream out = new ZipOutputStream(new BufferedOutputStream(new FileOutputStream(part)))) {
                        byte[] bytes = new byte[32768];
                        for (File file : files) {
                            if (!file.isFile()) continue;
                            out.putNextEntry(new ZipEntry(file.getName()));
                            try (InputStream in = new FileInputStream(file)) {
                                int n; while ((n=in.read(bytes))!=-1) out.write(bytes,0,n);
                            }
                            out.closeEntry();
                        }
                    }
                    if (!part.renameTo(zip)) throw new IOException("Cannot finalize ZIP; files remain in " + folder);
                    // Preserve raw files too, so a partial ZIP never loses evidence.
                    result = (complete ? "GFX saved: " : "GFX incomplete; report saved: ") + zip.getAbsolutePath();
                } catch (IOException e) { result = "GFX export failed: " + e.getMessage() + "\nFiles: " + folder; }
                String finalResult = result;
                handler.post(() -> {
                    if (closed) return;
                    busy = false; button.setVisibility(View.VISIBLE);message(finalResult);
                });
            },"Halo-GFX-export").start();
        }
    };
    private static void copy(File source,File target) throws IOException {
        try (InputStream in = new FileInputStream(source); OutputStream out = new FileOutputStream(target)) {
            byte[] bytes = new byte[8192];int n;while((n=in.read(bytes))!=-1)out.write(bytes,0,n);
        }
    }
    private void message(String text) { Toast.makeText(activity,text,Toast.LENGTH_LONG).show(); }
    void close() { closed = true; handler.removeCallbacksAndMessages(null); }
    /** the NVIDIA Shield test settings as saved by the settings overlay */
    private String perfSettings() {
        android.content.SharedPreferences prefs = activity.getSharedPreferences("halo_android_controls", 0);
        return "mode=" + prefs.getInt("nvidia_skinning_mode", 0)
            + " visibility_async=" + prefs.getBoolean("nvidia_visibility_async", true)
            + " counter=" + prefs.getBoolean("perf_overlay", true)
            + " object_shadows=" + prefs.getBoolean("nvidia_object_shadows", true);
    }
    private static native boolean nativeRequest(String directory);
    private static native int nativeState();
}
