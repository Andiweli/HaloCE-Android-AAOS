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

/** Temporary Patch18 UI. Captures one frame only when explicitly requested. */
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
        if (busy || closed) return;
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
                out.write("Halo GFX Patch18\nTime: " + new Date()
                    + "\nApp: " + info.versionName + " (" + info.getLongVersionCode() + ")"
                    + "\nFlavor: " + (BuildConfig.IS_AAOS ? "AAOS" : "mobile")
                    + "\nDevice: " + Build.MANUFACTURER + " " + Build.MODEL + " / " + Build.DEVICE
                    + "\nAndroid: " + Build.VERSION.RELEASE + " API " + Build.VERSION.SDK_INT
                    + "\nABIs: " + Arrays.toString(Build.SUPPORTED_ABIS) + "\n");
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
    private static native boolean nativeRequest(String directory);
    private static native int nativeState();
}
