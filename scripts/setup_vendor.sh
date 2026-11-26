#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="$root/vendor/HarnessFix"
commit=9167a0b9a58748c73b56c3ee04fdc3437ba0c56e
mkdir -p "$root/vendor"
if [[ ! -d "$target/.git" ]]; then
  git clone https://github.com/HarnessFix/HarnessFix.git "$target"
  git -C "$target" checkout --detach "$commit"
fi
if [[ "$(git -C "$target" rev-parse HEAD)" != "$commit" ]]; then
  echo "Existing vendor checkout is not the pinned commit; left unchanged." >&2
  exit 1
fi
patch="$root/patches/harnessfix-dry-run.patch"
if git -C "$target" apply --reverse --check "$patch" 2>/dev/null; then
  echo 'Pinned HarnessFix with dry-run patch is ready.'
else
  git -C "$target" apply --check "$patch"
  git -C "$target" apply "$patch"
fi
