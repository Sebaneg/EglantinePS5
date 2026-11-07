#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(cat "$root/.local/headless-cache")
[[ "$(cat "$scratch/owner")" == "$root" ]]
export PS5_PAYLOAD_SDK="$scratch/sdk"
source="$scratch/source/.cache/cpm/ffmpeg/c7b5f1537d"
test -f "$source/configure"
install="$scratch/ffmpeg-native/install"
mkdir -p "$scratch/ffmpeg-native" "$install"

# dav1d (tools/deps.json) for FFmpeg's libdav1d: Switch 2 titles' movies are AV1 (Ocarina of
# Time's opening; without it the game waits on a black screen), and FFmpeg's own AV1 decoder only
# works with a hardware decoder. Built static with the same compiler as FFmpeg.
dav1d_source="$root/.deps/dav1d-1.5.1"
test -f "$dav1d_source/meson.build"
dav1d_build="$scratch/ffmpeg-native/dav1d"
rm -rf "$dav1d_build"
mkdir -p "$dav1d_build"
cat > "$dav1d_build/cross.ini" <<EOF
[binaries]
c = ['bash', '$root/tools/ffmpeg-ps5-cc.sh']
ar = 'llvm-ar-18'
strip = 'llvm-strip-18'
nasm = 'nasm'

[properties]
needs_exe_wrapper = true

[host_machine]
system = 'freebsd'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'
EOF
meson setup "$dav1d_build/out" "$dav1d_source" --cross-file "$dav1d_build/cross.ini" \
    --prefix="$install" --libdir=lib --buildtype=release --default-library=static \
    -Denable_tools=false -Denable_tests=false -Denable_examples=false -Denable_docs=false
ninja -C "$dav1d_build/out" install
# Its pkg-config file may ask for system libraries the console's link does not have (-ldl):
# FFmpeg's configure links a probe with them and reports dav1d missing. dav1d alone is enough.
sed -i -e '/^Libs.private:/d' -e '/^Requires.private:/d' "$install/lib/pkgconfig/dav1d.pc"

cd "$scratch/ffmpeg-native"
# Use the same pinned, minimal decoder set as the Linux core, with libdav1d for AV1. Avoid the
# full prebuilt FFmpeg package's unrelated codec and C++ runtime dependencies.
PKG_CONFIG_PATH="$install/lib/pkgconfig" bash "$source/configure" --prefix="$install" \
    --enable-cross-compile --arch=x86_64 --target-os=freebsd \
    --cc="bash $root/tools/ffmpeg-ps5-cc.sh" --ld="bash $root/tools/ffmpeg-ps5-cc.sh" \
    --ar=llvm-ar-18 --ranlib=llvm-ranlib-18 --nm=llvm-nm-18 \
    --pkg-config=pkg-config --pkg-config-flags=--static \
    --disable-autodetect --disable-everything --disable-programs --disable-doc \
    --disable-avdevice --disable-avformat --disable-network --disable-swresample \
    --enable-libdav1d --enable-decoder=h264,vp8,vp9,libdav1d \
    --enable-filter=yadif,scale --enable-pic \
    --enable-pthreads --disable-shared --enable-static ||
    { tail -n 60 ffbuild/config.log; exit 1; }
make -j"${EDEN_BUILD_JOBS:-$(nproc)}"
make install

# The core links libavcodec.a alone: dav1d's objects go into it, so nothing else changes.
mri="$dav1d_build/merge.mri"
printf 'CREATE %s\nADDLIB %s\nADDLIB %s\nSAVE\nEND\n' "$install/lib/libavcodec-merged.a" \
    "$install/lib/libavcodec.a" "$install/lib/libdav1d.a" > "$mri"
llvm-ar-18 -M < "$mri"
mv "$install/lib/libavcodec-merged.a" "$install/lib/libavcodec.a"
llvm-ranlib-18 "$install/lib/libavcodec.a"
