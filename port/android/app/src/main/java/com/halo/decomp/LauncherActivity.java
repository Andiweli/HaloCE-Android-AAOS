package com.halo.decomp;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelFileDescriptor;
import android.provider.Settings;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.nio.channels.FileChannel;

/**
 * Starts the game once its data is in place.
 *
 * The game reads the Xbox game data (the folder holding maps/) from the
 * app's external files directory, /sdcard/Android/data/com.halo.decomp/files.
 * If it is missing, this screen lets the player pick an Xbox disc image of
 * the game (.xiso or .iso, any version) with the system file picker, and
 * copies its maps folder there (XisoExtractor), as the desktop games do; or
 * they can push the maps folder with adb.
 */
public class LauncherActivity extends Activity {
    private static final int PICK_IMAGE = 1;
    private static final int EXPORT_DIAGNOSTIC = 2;

    private File dataRoot;
    private TextView status;
    private ProgressBar progress;
    private Button pick;
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Fullscreen.apply(this);
        dataRoot = getExternalFilesDir(null);
        // created by the app, so that files pushed into it with adb stay
        // readable (a directory adb creates there belongs to the shell user)
        if (dataRoot != null)
            new File(dataRoot, "maps").mkdirs();
        passOnHardwareId();
        passOnInvite(getIntent());
        if (haveData()) {
            if (StartDiagnostics.interrupted(this)) { showDiagnostics(); return; }
            startGame();
            return;
        }
        buildInterface();
    }

    /**
     * An internet play invite link the app was opened with: the game
     * (port/linux/src/p2p.c) picks it up from join_link.txt, whether it is
     * starting now or already running.
     */
    private void passOnInvite(Intent intent) {
        if (intent == null || !Intent.ACTION_VIEW.equals(intent.getAction()) || intent.getData() == null
            || dataRoot == null)
            return;
        // written whole under another name, then renamed: the game never
        // reads it half written
        File partial = new File(dataRoot, "join_link.txt.tmp");
        try (OutputStream out = new FileOutputStream(partial)) {
            out.write(intent.getData().toString().getBytes("UTF-8"));
        } catch (java.io.IOException e) {
            // the link is lost; the player can copy it instead
            partial.delete();
            return;
        }
        if (!partial.renameTo(new File(dataRoot, "join_link.txt")))
            partial.delete();
    }

    /**
     * This device's ANDROID_ID (the app's own: one per app signing key and
     * user, until a factory reset), which native code cannot read: the game
     * (port/linux/src/p2p.c) hashes it from hardware_id.txt into the
     * hardware id a host it joins is told.
     */
    private void passOnHardwareId() {
        String id;

        if (dataRoot == null)
            return;
        try {
            id = Settings.Secure.getString(getContentResolver(), Settings.Secure.ANDROID_ID);
        } catch (RuntimeException e) {
            return;
        }
        if (id == null || id.isEmpty())
            return;
        File partial = new File(dataRoot, "hardware_id.txt.tmp");
        try (OutputStream out = new FileOutputStream(partial)) {
            out.write(id.getBytes("UTF-8"));
        } catch (java.io.IOException e) {
            partial.delete();
            return;
        }
        if (!partial.renameTo(new File(dataRoot, "hardware_id.txt")))
            partial.delete();
    }

    private boolean haveData() {
        return dataRoot != null && new File(dataRoot, "maps/ui.map").isFile();
    }

    private void startGame() {
        try {
            GameDataDefaults.install(dataRoot, name -> getAssets().open(name));
        } catch (java.io.IOException e) {
            new android.app.AlertDialog.Builder(this)
                .setTitle("Game data setup")
                .setMessage("Cannot install startup files: " + e.getMessage())
                .setPositiveButton("Retry", (dialog, which) -> startGame())
                .setNegativeButton("Close", (dialog, which) -> finish())
                .show();
            return;
        }
        startActivity(new Intent(this, HaloActivity.class));
        finish();
    }

    private void showDiagnostics() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(16),dp(12),dp(16),dp(12));
        TextView title = new TextView(this);
        title.setText("Halo – Diagnose / Diagnostics");
        title.setTextSize(22);layout.addView(title);
        TextView text = new TextView(this);
        text.setText(StartDiagnostics.read(this));text.setTextSize(14);text.setTextIsSelectable(true);
        android.widget.ScrollView scroll = new android.widget.ScrollView(this);
        scroll.addView(text);layout.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        Button export = new Button(this);export.setText("Diagnose exportieren / Export diagnostic");
        export.setOnClickListener(v -> {
            Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("text/plain");
            intent.putExtra(Intent.EXTRA_TITLE,"halo-diagnostic.txt");
            try { startActivityForResult(intent,EXPORT_DIAGNOSTIC); }
            catch (android.content.ActivityNotFoundException e) {
                android.widget.Toast.makeText(this,"No file picker. Diagnostic remains in Android/media/com.halo.decomp/",android.widget.Toast.LENGTH_LONG).show();
            }
        });layout.addView(export);
        Button retry = new Button(this);retry.setText("Spiel erneut starten / Retry game");
        retry.setOnClickListener(v -> startGame());layout.addView(retry);
        setContentView(layout);Fullscreen.apply(this);
    }

    private int dp(float value) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value,
            getResources().getDisplayMetrics());
    }

    private void buildInterface() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        layout.setPadding(dp(48), dp(24), dp(48), dp(24));
        layout.setBackgroundColor(Color.rgb(12, 16, 20));

        TextView title = new TextView(this);
        title.setText("Halo needs its game data");
        title.setTextColor(Color.WHITE);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 24);
        title.setGravity(Gravity.CENTER);
        layout.addView(title);

        TextView message = new TextView(this);
        message.setText("Choose an Xbox disc image of Halo: Combat Evolved (an .iso or .xiso file, any "
            + "version) on this device. Its maps folder is copied into the app's storage (about 1.8 GB), "
            + "and you can delete the image afterwards.\n\n"
            + "You can also copy a maps folder from a computer:\n"
            + "adb push <folder with maps>/. " + (dataRoot != null ? dataRoot.getAbsolutePath() : "") + "/");
        message.setTextColor(Color.rgb(200, 205, 210));
        message.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        message.setGravity(Gravity.CENTER);
        message.setPadding(0, dp(16), 0, dp(16));
        layout.addView(message);

        pick = new Button(this);
        pick.setText("Choose disc image");
        pick.setOnClickListener(v -> {
            // (disc images have no MIME type of their own: any file, checked
            // when it is read)
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("*/*");
            startActivityForResult(intent, PICK_IMAGE);
        });
        layout.addView(pick, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT));

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(1000);
        progress.setVisibility(View.GONE);
        LinearLayout.LayoutParams progressLayout = new LinearLayout.LayoutParams(dp(480),
            LinearLayout.LayoutParams.WRAP_CONTENT);
        progressLayout.topMargin = dp(16);
        layout.addView(progress, progressLayout);

        status = new TextView(this);
        status.setTextColor(Color.rgb(160, 200, 160));
        status.setGravity(Gravity.CENTER);
        status.setPadding(0, dp(8), 0, 0);
        layout.addView(status);

        setContentView(layout);
        pick.requestFocus();
    }

    @Override
    protected void onResume() {
        super.onResume();
        Fullscreen.apply(this);
        // data pushed with adb while this screen was open
        if (pick != null && pick.isEnabled() && haveData())
            startGame();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) Fullscreen.apply(this);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == EXPORT_DIAGNOSTIC) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null) {
                try (FileInputStream in = new FileInputStream(StartDiagnostics.log(this));
                     OutputStream out = getContentResolver().openOutputStream(data.getData())) {
                    if (out == null) throw new java.io.IOException("Cannot open destination");
                    byte[] buffer = new byte[8192];int count;
                    while ((count=in.read(buffer))!=-1) out.write(buffer,0,count);
                    android.widget.Toast.makeText(this,"Diagnostic exported",android.widget.Toast.LENGTH_SHORT).show();
                } catch (Exception e) {
                    android.widget.Toast.makeText(this,"Export failed: "+e.getMessage(),android.widget.Toast.LENGTH_LONG).show();
                }
            }
            return;
        }
        if (requestCode != PICK_IMAGE || resultCode != RESULT_OK || data == null || data.getData() == null)
            return;
        Uri image = data.getData();
        pick.setEnabled(false);
        progress.setVisibility(View.VISIBLE);
        status.setText("Reading the disc image...");
        new Thread(() -> importImage(image)).start();
    }

    private void report(String text, int permille) {
        handler.post(() -> {
            status.setText(text);
            if (permille >= 0)
                progress.setProgress(permille);
        });
    }

    private void fail(String text) {
        handler.post(() -> {
            status.setText(text);
            progress.setVisibility(View.GONE);
            pick.setEnabled(true);
            pick.requestFocus();
        });
    }

    private void importImage(Uri image) {
        try (ParcelFileDescriptor descriptor = getContentResolver().openFileDescriptor(image, "r")) {
            if (descriptor == null)
                throw new java.io.IOException("the file could not be opened");
            try (FileInputStream in = new FileInputStream(descriptor.getFileDescriptor())) {
                FileChannel channel = in.getChannel();

                XisoExtractor.extractMaps(channel, dataRoot, (file, done, total) ->
                    report("Extracting maps/" + file + " (" + (done >> 20) + " of " + (total >> 20) + " MB)",
                        total > 0 ? (int) (done * 1000 / total) : 0));
            }
            handler.post(() -> {
                if (haveData()) {
                    startGame();
                } else {
                    fail("The extraction finished but maps/ui.map is missing.");
                }
            });
        } catch (XisoExtractor.ExtractException exception) {
            fail(exception.getMessage());
        } catch (Exception exception) {
            fail("Extracting failed: " + exception.getMessage());
        }
    }
}
