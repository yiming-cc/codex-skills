#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$repo_dir/skills"
target_dir="${SKILL_TARGET:-${CODEX_HOME:-$HOME/.codex}/skills}"
timestamp="$(date +%Y%m%d%H%M%S)"

abs_dir() {
  cd "$1" && pwd -P
}

backup_path() {
  local path="$1"
  local candidate="${path}.backup-${timestamp}"
  local i=1

  while [ -e "$candidate" ] || [ -L "$candidate" ]; do
    candidate="${path}.backup-${timestamp}-${i}"
    i=$((i + 1))
  done

  printf '%s\n' "$candidate"
}

if [ ! -d "$source_dir" ]; then
  echo "missing skills directory: $source_dir" >&2
  exit 1
fi

mkdir -p "$target_dir"

installed=0
for skill_dir in "$source_dir"/*; do
  [ -d "$skill_dir" ] || continue

  skill_name="$(basename "$skill_dir")"
  skill_md="$skill_dir/SKILL.md"
  dest="$target_dir/$skill_name"

  if [ ! -f "$skill_md" ]; then
    echo "skip $skill_name: missing SKILL.md" >&2
    continue
  fi

  if [ -L "$dest" ] && [ -d "$dest" ]; then
    if [ "$(abs_dir "$dest")" = "$(abs_dir "$skill_dir")" ]; then
      echo "ok $skill_name -> $skill_dir"
      installed=$((installed + 1))
      continue
    fi
  fi

  if [ -e "$dest" ] || [ -L "$dest" ]; then
    backup="$(backup_path "$dest")"
    mv "$dest" "$backup"
    echo "backup $skill_name -> $backup"
  fi

  ln -s "$skill_dir" "$dest"
  echo "link $skill_name -> $dest"
  installed=$((installed + 1))
done

if [ "$installed" -eq 0 ]; then
  echo "no skills installed from $source_dir" >&2
  exit 1
fi

echo "Installed $installed skill(s) into $target_dir."
echo "Restart Codex, or start a new task, if newly linked skills are not visible yet."

