package com.halo.decomp;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Collections;

/**
 * Copies the maps folder out of an Xbox disc image (an "xiso", or a whole
 * disc's ".iso"), as the desktop games do (port/linux/src/xiso.c, which this
 * follows).
 *
 * The image's file system is XDVDFS, read as extract-xiso does
 * (https://github.com/XboxDev/extract-xiso, extract-xiso.c, whose format
 * handling this follows; its license is below and in
 * port/third_party/extract-xiso/LICENSE.TXT): 2048-byte sectors; a volume
 * descriptor at 0x10000 that starts and ends with "MICROSOFT*XBOX*MEDIA" and
 * gives the root directory's sector and size; and directories whose entries
 * form a binary tree (each entry: left and right subtree offsets in 4-byte
 * units, the start sector, the size, attributes, the name's length and the
 * name, 4-byte aligned). Images made from a whole disc put the game partition
 * further in, at one of the offsets below.
 *
 * The files are written to maps.partial first and moved into maps once they
 * all are, so an interrupted extraction never leaves maps/ui.map behind.
 *
 * Some parts of this code are copyright in@fishtank.com. This product
 * includes software developed by in &lt;in@fishtank.com&gt;.
 *
 * Copyright (c) 2003 in &lt;in@fishtank.com&gt;
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * 3. All advertising materials mentioning features or use of this software
 *    must display the following acknowledgement:
 *
 *    This product includes software developed by in &lt;in@fishtank.com&gt;.
 *
 * 4. Neither the name of "in" nor the email address "in@fishtank.com"
 *    may be used to endorse or promote products derived from this software
 *    without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED `AS IS' AND ANY EXPRESS OR IMPLIED WARRANTIES
 * INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
 * FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE
 * AUTHOR OR ANY CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
 * ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
final class XisoExtractor {
    private static final int SECTOR_SIZE = 2048;
    private static final long VOLUME_DESCRIPTOR_OFFSET = 0x10000;
    private static final int ENTRY_HEADER_SIZE = 14;
    private static final int ATTRIBUTE_DIRECTORY = 0x10;
    /* directory tables are a few sectors; anything much larger is not one */
    private static final long MAXIMUM_DIRECTORY_SIZE = 4 << 20;
    private static final int MAXIMUM_FILES = 256;
    private static final int COPY_BUFFER_SIZE = 1 << 20;
    private static final byte[] VOLUME_MAGIC = "MICROSOFT*XBOX*MEDIA".getBytes(StandardCharsets.US_ASCII);

    /* where the game partition starts: a plain image, and whole-disc images
    (extract-xiso's GLOBAL, XGD3 and XGD1 offsets) */
    private static final long[] PARTITION_OFFSETS = { 0, 0x0FD90000L, 0x02080000L, 0x18300000L };

    interface Progress {
        void report(String file, long done, long total);
    }

    /** a reason the player can act on */
    static final class ExtractException extends IOException {
        ExtractException(String message) {
            super(message);
        }
    }

    private static final class Entry {
        final String name;
        final long sector;
        final long size;

        Entry(String name, long sector, long size) {
            this.name = name;
            this.sector = sector;
            this.size = size;
        }
    }

    private final FileChannel image;
    private long partition;

    private XisoExtractor(FileChannel image) {
        this.image = image;
    }

    /** copies the image's maps folder to destination/maps */
    static void extractMaps(FileChannel image, File destination, Progress progress) throws IOException {
        new XisoExtractor(image).extract(destination, progress);
    }

    /** Copies only the two supported movies; never changes maps or saves. */
    static int extractMovies(FileChannel image, File destination, Progress progress) throws IOException {
        return new XisoExtractor(image).movies(destination, progress);
    }

    /* Choose one complete language directory; never mix different map sets. */
    private Entry selectMaps(List<Entry> dirs) throws IOException {
        List<Entry> candidates = new ArrayList<>();
        for (Entry entry : dirs)
            if (entry.name.toLowerCase(Locale.ROOT).matches("maps(?:_[a-z]{2})?"))
                candidates.add(entry);
        final String preferred = "maps_" + Locale.getDefault().getLanguage();
        Collections.sort(candidates, (a, b) -> {
            int ar = a.name.equalsIgnoreCase(preferred) ? 0 : a.name.equalsIgnoreCase("maps") ? 1 : 2;
            int br = b.name.equalsIgnoreCase(preferred) ? 0 : b.name.equalsIgnoreCase("maps") ? 1 : 2;
            return ar != br ? Integer.compare(ar, br) : a.name.compareToIgnoreCase(b.name);
        });
        for (Entry candidate : candidates) {
            List<Entry> files = new ArrayList<>();
            walk(readDirectory(candidate.sector, candidate.size, "Invalid maps directory."),
                0, 0, false, files, new int[1]);
            for (Entry file : files) if (file.name.equalsIgnoreCase("ui.map")) return candidate;
        }
        return null;
    }

    private static Entry selectMovie(List<Entry> files, String base, String language) {
        Entry selected = null;
        int best = Integer.MAX_VALUE;
        for (Entry file : files) {
            String name = file.name.toLowerCase(Locale.ROOT);
            if (!name.matches(base + "(?:_[a-z]{2})?\\.bik")) continue;
            int rank = name.equals(base + ".bik") ? 0 :
                name.equals(base + "_" + language + ".bik") ? 1 :
                name.equals(base + "_" + Locale.getDefault().getLanguage() + ".bik") ? 2 : 3;
            if (rank < best || (rank == best && name.compareToIgnoreCase(selected.name) < 0)) {
                selected = file;
                best = rank;
            }
        }
        return selected;
    }

    private int movies(File destination, Progress progress) throws IOException {
        long[] root = findVolume();
        List<Entry> dirs = new ArrayList<>();
        walk(readDirectory(root[0], root[1], "Invalid disc file system."), 0, 0, true, dirs, new int[1]);
        Entry bink = null;
        for (Entry entry : dirs) if (entry.name.equalsIgnoreCase("bink")) bink = entry;
        if (bink == null) return 0;
        List<Entry> all = new ArrayList<>(), movies = new ArrayList<>();
        walk(readDirectory(bink.sector, bink.size, "Invalid bink directory."), 0, 0, false, all, new int[1]);
        Entry maps = selectMaps(dirs);
        String language = maps != null && maps.name.length() == 7
            ? maps.name.substring(5).toLowerCase(Locale.ROOT) : Locale.getDefault().getLanguage();
        long total = 0, done = 0;
        for (String base : new String[] { "intro", "credits" }) {
            Entry entry = selectMovie(all, base, language);
            if (entry == null) continue;
            if (entry.size < 44 || entry.size > 512L * 1024 * 1024)
                throw new ExtractException("Invalid movie size: " + entry.name);
            movies.add(entry); total += entry.size;
        }
        if (movies.isEmpty()) return 0;
        File folder = new File(destination, "bink");
        if (!folder.isDirectory() && !folder.mkdirs()) throw new ExtractException("Cannot create bink folder.");
        ByteBuffer buffer = ByteBuffer.allocateDirect(COPY_BUFFER_SIZE);
        for (Entry entry : movies) {
            String name = entry.name.toLowerCase(Locale.ROOT).startsWith("intro") ? "intro.bik" : "credits.bik";
            File temp = new File(folder, name + ".partial");
            long offset = partition + entry.sector * SECTOR_SIZE, remaining = entry.size;
            ByteBuffer header = ByteBuffer.allocate(44).order(java.nio.ByteOrder.LITTLE_ENDIAN);
            readAt(offset, header);
            if (header.get(0) != 'B' || header.get(1) != 'I' || header.get(2) != 'K' ||
                Integer.toUnsignedLong(header.getInt(4)) + 8 != entry.size)
                throw new ExtractException("Invalid or incomplete Bink movie: " + name);
            try {
                try (FileOutputStream out = new FileOutputStream(temp)) {
                    FileChannel target = out.getChannel();
                    while (remaining > 0) {
                        buffer.clear(); buffer.limit((int)Math.min(remaining, COPY_BUFFER_SIZE));
                        readAt(offset, buffer); int count = buffer.remaining();
                        while (buffer.hasRemaining()) target.write(buffer);
                        offset += count; remaining -= count; done += count;
                        progress.report(bink.name + "/" + entry.name, done, total);
                    }
                    out.getFD().sync();
                }
                if (!temp.renameTo(new File(folder, name))) throw new ExtractException("Cannot install " + name);
            } finally { temp.delete(); }
        }
        return movies.size();
    }

    private void readAt(long offset, ByteBuffer buffer) throws IOException {
        while (buffer.hasRemaining()) {
            int count = image.read(buffer, offset);

            if (count <= 0)
                throw new ExtractException("Could not read the disc image (is it complete?).");
            offset += count;
        }
        buffer.flip();
    }

    private static boolean magicAt(ByteBuffer buffer, int offset) {
        for (int index = 0; index < VOLUME_MAGIC.length; index++) {
            if (buffer.get(offset + index) != VOLUME_MAGIC[index])
                return false;
        }
        return true;
    }

    /** the partition's volume descriptor: the root directory's sector and size */
    private long[] findVolume() throws IOException {
        for (long offset : PARTITION_OFFSETS) {
            ByteBuffer descriptor = ByteBuffer.allocate(SECTOR_SIZE).order(ByteOrder.LITTLE_ENDIAN);

            try {
                readAt(offset + VOLUME_DESCRIPTOR_OFFSET, descriptor);
            } catch (IOException e) {
                continue;
            }
            if (!magicAt(descriptor, 0) || !magicAt(descriptor, 0x7EC))
                continue;
            partition = offset;
            return new long[] {
                descriptor.getInt(20) & 0xFFFFFFFFL, descriptor.getInt(24) & 0xFFFFFFFFL,
            };
        }
        throw new ExtractException("This is not an Xbox disc image.");
    }

    /** a directory's table, read whole */
    private ByteBuffer readDirectory(long sector, long size, String what) throws IOException {
        if (size <= 0 || size > MAXIMUM_DIRECTORY_SIZE)
            throw new ExtractException(what);
        ByteBuffer table = ByteBuffer.allocate((int) size).order(ByteOrder.LITTLE_ENDIAN);
        readAt(partition + sector * SECTOR_SIZE, table);
        return table;
    }

    /**
     * collects the entries of the subtree at offset (4-byte units), files or
     * directories as asked
     */
    private static void walk(ByteBuffer table, long offset, int depth, boolean directories, List<Entry> out,
        int[] visited) {
        offset *= 4;
        /* a malformed table must not loop or run off its end */
        if (depth > 64 || ++visited[0] > 4096 || offset + ENTRY_HEADER_SIZE > table.limit())
            return;
        int at = (int) offset;
        int left = table.getShort(at) & 0xFFFF;
        int right = table.getShort(at + 2) & 0xFFFF;
        /* 0xFFFF: padding, an empty directory */
        if (left == 0xFFFF)
            return;
        int nameLength = table.get(at + 13) & 0xFF;
        if (left != 0)
            walk(table, left, depth + 1, directories, out, visited);
        boolean isDirectory = (table.get(at + 12) & ATTRIBUTE_DIRECTORY) != 0;
        if (at + ENTRY_HEADER_SIZE + nameLength <= table.limit() && nameLength > 0 && isDirectory == directories
            && out.size() < MAXIMUM_FILES) {
            byte[] bytes = new byte[nameLength];
            for (int index = 0; index < nameLength; index++)
                bytes[index] = table.get(at + ENTRY_HEADER_SIZE + index);
            String name = new String(bytes, StandardCharsets.ISO_8859_1);
            /* (as extract-xiso refuses them: no name may leave the folder) */
            if (!name.equals(".") && !name.equals("..") && name.indexOf('/') < 0 && name.indexOf('\\') < 0)
                out.add(new Entry(name, table.getInt(at + 4) & 0xFFFFFFFFL, table.getInt(at + 8) & 0xFFFFFFFFL));
        }
        if (right != 0)
            walk(table, right, depth + 1, directories, out, visited);
    }

    private void extract(File destination, Progress progress) throws IOException {
        long[] root = findVolume();

        /* the root's maps folder */
        ByteBuffer table = readDirectory(root[0], root[1], "The disc image's file system is damaged.");
        List<Entry> directories = new ArrayList<>();
        walk(table, 0, 0, true, directories, new int[1]);
        Entry maps = selectMaps(directories);
        if (maps == null)
            throw new ExtractException("No maps or maps_xx folder containing ui.map was found.");

        /* its files */
        table = readDirectory(maps.sector, maps.size, "The disc image's maps folder is damaged.");
        List<Entry> files = new ArrayList<>();
        walk(table, 0, 0, false, files, new int[1]);
        long total = 0;
        boolean hasUi = false;
        for (Entry file : files) {
            total += file.size;
            hasUi |= file.name.equalsIgnoreCase("ui.map");
        }
        if (!hasUi)
            throw new ExtractException("The disc image's maps folder has no ui.map: it is not a Halo disc.");

        File partial = new File(destination, "maps.partial");
        File finished = new File(destination, "maps");
        if (!partial.isDirectory() && !partial.mkdirs())
            throw new ExtractException("Could not create " + partial + ".");
        ByteBuffer buffer = ByteBuffer.allocateDirect(COPY_BUFFER_SIZE);
        long done = 0;
        for (Entry file : files) {
            File path = new File(partial, file.name.toLowerCase(Locale.ROOT));
            long offset = partition + file.sector * SECTOR_SIZE;
            long remaining = file.size;

            try (FileOutputStream out = new FileOutputStream(path)) {
                FileChannel output = out.getChannel();

                while (remaining > 0) {
                    buffer.clear();
                    buffer.limit((int) Math.min(remaining, COPY_BUFFER_SIZE));
                    readAt(offset, buffer);
                    int count = buffer.remaining();
                    while (buffer.hasRemaining())
                        output.write(buffer);
                    offset += count;
                    remaining -= count;
                    done += count;
                    progress.report(maps.name + "/" + file.name, done, total);
                }
            } catch (ExtractException e) {
                throw new ExtractException("Could not read " + file.name + " from the disc image (is it complete?).");
            } catch (IOException e) {
                throw new ExtractException("Could not write " + path + " (is the storage full?).");
            }
        }

        /* (the maps folder may be there, empty: the app makes it for adb) */
        if (!finished.isDirectory() && !finished.mkdirs())
            throw new ExtractException("Could not create " + finished + ".");
        for (Entry file : files) {
            File from = new File(partial, file.name.toLowerCase(Locale.ROOT));
            File to = new File(finished, file.name.toLowerCase(Locale.ROOT));

            to.delete();
            if (!from.renameTo(to))
                throw new ExtractException("Could not move " + file.name + " into " + finished + ".");
        }
        partial.delete();
    }
}
