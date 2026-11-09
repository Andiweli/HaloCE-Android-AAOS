package com.halo.decomp;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * The in-game menu's update button: of the releases on GitHub (github.com/Andiweli/HaloCE-Android-AAOS/releases),
 * the one with the highest version (its tag the version, "1.0.15", with a phone .apk, "HaloCE.1.0.15.apk")
 * against the installed version. The same: "Up to date", green and off; the installed one older: "Update",
 * red, which opens the releases page (wish of the project owner, 09.11.2026: the game no longer downloads
 * or installs a new version itself). Asked once per run, in the background; without the internet, and in
 * the AAOS build (installed by its store), the button stays hidden.
 */
final class AppUpdate {
  static final String TAG = "halo";
  static final String RELEASES = "https://api.github.com/repos/Andiweli/HaloCE-Android-AAOS/releases?per_page=30";
  static final String RELEASES_PAGE = "https://github.com/Andiweli/HaloCE-Android-AAOS/releases";
  /** The check's answer: not known (yet, or no internet), the same version (or newer), an older one. */
  static final int UNKNOWN = 0, CURRENT = 1, OLDER = 2;

  interface Listener {
    /** The check answered (main thread). */
    void checked(int state);
  }

  private static int state = UNKNOWN;
  private static boolean asked;
  private static final Handler MAIN = new Handler(Looper.getMainLooper());

  static int state() { return state; }

  /** The installed version as the releases name it ("1.0.15"). */
  static String installed(Context c) {
    try {
      return c.getPackageManager().getPackageInfo(c.getPackageName(), 0).versionName;
    } catch (android.content.pm.PackageManager.NameNotFoundException e) { return null; }
  }

  /** A release named by its version ("1.0.16", "v1.0.16"), not the CI's "build-37". */
  static boolean versionTag(String tag) {
    String v = tag == null ? "" : tag.trim();
    if (v.startsWith("v") || v.startsWith("V")) v = v.substring(1);
    return v.matches("\\d+(\\.\\d+)*(-.*)?");
  }

  /** The phone app among a release's files: an .apk, not the AAOS one. */
  static boolean phoneApk(String name) {
    String lower = name.toLowerCase(java.util.Locale.ROOT);
    return lower.endsWith(".apk") && !lower.contains("aaos");
  }

  /**
   * "0.95.2-beta" against "0.96.0-beta": the numbers part by part, then a version without a suffix
   * ahead of one with it ("1.0" after "1.0-beta"), then the suffixes; a leading "v" does not count.
   */
  static int compare(String a, String b) {
    String[] x = split(a), y = split(b);
    String[] p = x[0].split("\\."), q = y[0].split("\\.");
    for (int i = 0; i < Math.max(p.length, q.length); i++) {
      int m = i < p.length ? number(p[i]) : 0, n = i < q.length ? number(q[i]) : 0;
      if (m != n) return m < n ? -1 : 1;
    }
    if (x[1].isEmpty() != y[1].isEmpty()) return x[1].isEmpty() ? 1 : -1;
    return Integer.signum(x[1].compareTo(y[1]));
  }

  private static String[] split(String v) {
    v = v == null ? "" : v.trim();
    if (v.startsWith("v") || v.startsWith("V")) v = v.substring(1);
    int dash = v.indexOf('-');
    return dash < 0 ? new String[] {v, ""} : new String[] {v.substring(0, dash), v.substring(dash + 1)};
  }

  private static int number(String s) {
    try { return Integer.parseInt(s.trim()); } catch (NumberFormatException e) { return 0; }
  }

  /** Asks GitHub once per run (a thread of its own); `listener` hears the answer. */
  static void check(Context context, Listener listener) {
    if (BuildConfig.IS_AAOS) return;
    if (asked) {
      if (state != UNKNOWN) listener.checked(state);
      return;
    }
    asked = true;
    final String mine = installed(context);
    new Thread(() -> {
      int answer = UNKNOWN;
      try {
        // the releases page, newest first: the highest version among the published releases with a phone APK
        // ("1.0.16"; the CI's automatic "build-N" releases and drafts or pre-releases do not count)
        JSONArray releases = new JSONArray(get(RELEASES));
        String tag = null;
        for (int r = 0; r < releases.length(); r++) {
          JSONObject release = releases.getJSONObject(r);
          String name = release.optString("tag_name", "");
          if (release.optBoolean("draft") || release.optBoolean("prerelease") || !versionTag(name)) continue;
          if (tag != null && compare(name, tag) <= 0) continue;
          JSONArray assets = release.getJSONArray("assets");
          for (int i = 0; i < assets.length(); i++) {
            JSONObject a = assets.getJSONObject(i);
            if (phoneApk(a.getString("name"))) { tag = name; break; }
          }
        }
        if (tag == null) throw new java.io.IOException("no release with an APK");
        if (mine != null) answer = compare(mine, tag) < 0 ? OLDER : CURRENT;
        Log.i(TAG, "GitHub's latest release " + tag + ", installed " + mine
            + (answer == OLDER ? ": an update" : ": up to date"));
      } catch (Exception e) {
        asked = false;  // the next menu asks again
        Log.i(TAG, "no answer from GitHub: " + e);
      }
      final int result = answer;
      MAIN.post(() -> { state = result; if (result != UNKNOWN) listener.checked(result); });
    }, "update-check").start();
  }

  private static String get(String address) throws Exception {
    HttpURLConnection c = (HttpURLConnection) new URL(address).openConnection();
    c.setConnectTimeout(8000); c.setReadTimeout(8000);
    c.setRequestProperty("Accept", "application/vnd.github+json");
    try (InputStream in = c.getInputStream()) {
      ByteArrayOutputStream out = new ByteArrayOutputStream();
      byte[] buffer = new byte[8192];
      for (int n; (n = in.read(buffer)) > 0; ) out.write(buffer, 0, n);
      return out.toString("UTF-8");
    } finally { c.disconnect(); }
  }
}
