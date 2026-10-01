package com.halo.decomp;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;

/** Install optional startup files next to maps, preserving existing user files. */
final class GameDataDefaults {
    interface Source { InputStream open(String name) throws IOException; }

    static synchronized void install(File root, Source source) throws IOException {
        if (root == null || (!root.isDirectory() && !root.mkdirs()))
            throw new IOException("Game data storage is unavailable");
        for (String name : new String[] {"init.txt", "cheats.txt"}) {
            File target = new File(root, name);
            if (target.isFile()) continue;
            if (target.exists()) throw new IOException("Not a file: " + target);
            File temporary = File.createTempFile(name + ".", ".tmp", root);
            try {
                try (InputStream in = source.open("defaults/" + name);
                     FileOutputStream out = new FileOutputStream(temporary)) {
                    byte[] bytes = new byte[4096];
                    int count;
                    while ((count = in.read(bytes)) != -1) out.write(bytes, 0, count);
                    out.getFD().sync();
                }
                // Check again after copying, before publishing the complete file.
                if (target.isFile()) continue;
                if (target.exists() || !temporary.renameTo(target))
                    throw new IOException("Cannot install " + target);
            } finally {
                if (temporary.exists()) temporary.delete();
            }
        }
    }
}
