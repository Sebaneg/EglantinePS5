#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Applies the patches in tools/eglantine-patches/ to the Eglantine submodule's working tree, which is
# what the build reads. The Zortos core is referenced directly by the submodule;
# this hook supports optional local patches. Safe to run again: applied patches are left alone.
# --revert takes them out (make update does, before it moves the submodule).
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
mode=${1:-apply}
shopt -s nullglob
patches=("$root"/tools/eglantine-patches/*.patch)
((${#patches[@]})) || exit 0
[[ $mode == --revert ]] && mapfile -t patches < <(printf '%s\n' "${patches[@]}" | sort -r)
# A patch that changes lines next to an earlier one's (0010 beside 0006 in vk_texture_cache.cpp)
# leaves that earlier one no longer seen as applied once both are in, and a second run (make deps
# runs this twice) took it for a patch that does not apply. The set applied last is remembered,
# with the Eglantine commit it went on: the same set on the same commit is left alone.
stamp="$(git -C Eglantine rev-parse --absolute-git-dir)/eglantine-patches.applied"
set_id=$( { git -C Eglantine rev-parse HEAD; cat "${patches[@]}"; } | sha256sum | cut -d' ' -f1)
if [[ $mode == --revert ]]; then
    rm -f "$stamp"
elif [[ -f $stamp && $(cat "$stamp") == "$set_id" ]]; then
    exit 0
fi
for patch in "${patches[@]}"; do
    name=$(basename "$patch")
    if git -C Eglantine apply --reverse --check "$patch" >/dev/null 2>&1; then
        if [[ $mode == --revert ]]; then
            git -C Eglantine apply --reverse "$patch"
            echo "Eglantine patch taken out: $name"
        fi
    elif [[ $mode == --revert ]]; then
        echo "Eglantine patch not in: $name"
    elif git -C Eglantine apply --check "$patch" >/dev/null 2>&1; then
        git -C Eglantine apply "$patch"
        echo "Eglantine patch applied: $name"
    else
        echo "Eglantine patch does not apply: $name (Eglantine moved; make the patch again)" >&2
        exit 1
    fi
done
[[ $mode == --revert ]] || echo "$set_id" > "$stamp"
