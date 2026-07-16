#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$repo_dir/skills"
target_dir="${SKILL_TARGET:-${CODEX_HOME:-$HOME/.codex}/skills}"
timestamp="$(date +%Y%m%d%H%M%S)"
install_mode="${SKILL_INSTALL_MODE:-keep}"
backup_root="${SKILL_BACKUP_DIR:-}"

usage() {
  cat <<'USAGE'
Usage: bootstrap.sh [--keep-existing|--overwrite] [--target-dir DIR] [--backup-dir DIR]

Options:
  --keep-existing  Keep an existing same-named skill in the target directory.
                   This is the default.
  --overwrite      Replace an existing same-named skill with the repo version.
                   The old skill is moved outside the skills directory first.
  --target-dir DIR Install links into DIR instead of $CODEX_HOME/skills.
  --backup-dir DIR Store overwritten skills in DIR.
  -h, --help       Show this help.

Environment:
  SKILL_INSTALL_MODE=keep|overwrite
  SKILL_TARGET=/path/to/skills
  SKILL_BACKUP_DIR=/path/to/backups
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --keep-existing|--keep)
      install_mode="keep"
      ;;
    --overwrite)
      install_mode="overwrite"
      ;;
    --target-dir)
      shift
      if [ "$#" -eq 0 ]; then
        echo "--target-dir requires a directory" >&2
        exit 1
      fi
      target_dir="$1"
      ;;
    --backup-dir)
      shift
      if [ "$#" -eq 0 ]; then
        echo "--backup-dir requires a directory" >&2
        exit 1
      fi
      backup_root="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac

  shift
done

case "$install_mode" in
  keep|overwrite)
    ;;
  *)
    echo "invalid install mode: $install_mode" >&2
    exit 1
    ;;
esac

if [ -z "$backup_root" ]; then
  backup_root="$(dirname "$target_dir")/skill-backups/bootstrap-$timestamp"
fi

abs_dir() {
  cd "$1" && pwd -P
}

unique_path() {
  local path="$1"
  local candidate="$path"
  local i=1

  while [ -e "$candidate" ] || [ -L "$candidate" ]; do
    candidate="${path}-${i}"
    i=$((i + 1))
  done

  printf '%s\n' "$candidate"
}

if [ ! -d "$source_dir" ]; then
  echo "missing skills directory: $source_dir" >&2
  exit 1
fi

mkdir -p "$target_dir"

handled=0
linked=0
kept=0
unchanged=0
for skill_dir in "$source_dir"/*; do
  [ -d "$skill_dir" ] || continue

  skill_name="$(basename "$skill_dir")"
  skill_md="$skill_dir/SKILL.md"
  dest="$target_dir/$skill_name"

  if [ ! -f "$skill_md" ]; then
    echo "skip $skill_name: missing SKILL.md" >&2
    continue
  fi

  if [ -d "$dest" ]; then
    if [ "$(abs_dir "$dest")" = "$(abs_dir "$skill_dir")" ]; then
      echo "ok $skill_name -> $skill_dir"
      unchanged=$((unchanged + 1))
      handled=$((handled + 1))
      continue
    fi
  fi

  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if [ "$install_mode" = "keep" ]; then
      echo "keep $skill_name at $dest"
      kept=$((kept + 1))
      handled=$((handled + 1))
      continue
    fi

    mkdir -p "$backup_root"
    backup="$(unique_path "$backup_root/$skill_name")"
    mv "$dest" "$backup"
    echo "backup $skill_name -> $backup"
  fi

  ln -s "$skill_dir" "$dest"
  echo "link $skill_name -> $dest"
  linked=$((linked + 1))
  handled=$((handled + 1))
done

if [ "$handled" -eq 0 ]; then
  echo "no skills installed from $source_dir" >&2
  exit 1
fi

echo "Handled $handled skill(s) in $target_dir: linked $linked, kept $kept, unchanged $unchanged."
echo "Restart Codex, or start a new task, if newly linked skills are not visible yet."
