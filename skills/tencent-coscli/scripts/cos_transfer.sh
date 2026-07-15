#!/usr/bin/env bash
set -euo pipefail

COSCLI_BIN="${COSCLI_BIN:-/cfs/users/chenyiming/bin/coscli}"
COSCLI_BUCKET="${COSCLI_BUCKET:-phymi-cos-1438869198}"
COSCLI_USER="${COSCLI_USER:-ymc}"

usage() {
  cat <<'EOF'
Usage:
  cos_transfer.sh ls [cos-prefix-or-url]
  cos_transfer.sh du <cos-prefix-or-url>
  cos_transfer.sh download <cos-prefix-or-url> <local-dir> [coscli flags...]
  cos_transfer.sh upload <local-path> <cos-prefix-or-url> [coscli flags...]
  cos_transfer.sh sync <source> <destination> [coscli flags...]
  cos_transfer.sh cp <source> <destination> [coscli flags...]
  cos_transfer.sh ensure-cfs-dir <local-dir>

Examples:
  cos_transfer.sh ls teleoperate_data_humanoid_nero_sharpa/
  cos_transfer.sh download teleoperate_data_humanoid_nero_sharpa/ /cfs/teleoperate_data_humanoid_nero_sharpa/
  cos_transfer.sh upload /cfs/my_data/ users/chenyiming/transfer/my_data/

Set COSCLI_ALLOW_DELETE=1 to pass destructive flags such as --delete, rm, or --move.
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

need_coscli() {
  [ -x "$COSCLI_BIN" ] || die "coscli not executable: $COSCLI_BIN"
}

cos_url() {
  case "$1" in
    cos://*) printf '%s\n' "$1" ;;
    /*) die "local absolute path where COS prefix was expected: $1" ;;
    *) printf 'cos://%s/%s\n' "$COSCLI_BUCKET" "${1#/}" ;;
  esac
}

has_destructive_flag() {
  for arg in "$@"; do
    case "$arg" in
      --delete|--move|rm) return 0 ;;
    esac
  done
  return 1
}

guard_destructive() {
  if has_destructive_flag "$@" && [ "${COSCLI_ALLOW_DELETE:-}" != "1" ]; then
    die "destructive operation requested; set COSCLI_ALLOW_DELETE=1 after explicit confirmation"
  fi
}

ensure_cfs_dir() {
  local dir="$1"
  [ -n "$dir" ] || die "empty directory"

  mkdir -p "$dir" 2>/dev/null || true

  if [ -d "$dir" ] && touch "$dir/.coscli_write_test" 2>/dev/null; then
    rm -f "$dir/.coscli_write_test"
    return 0
  fi

  case "$dir" in
    /cfs/*) ;;
    *) die "cannot write $dir; automatic ACL repair is only allowed under /cfs" ;;
  esac

  if ! sudo -n true 2>/dev/null; then
    cat >&2 <<EOF
Cannot write $dir and passwordless sudo is unavailable.
Run:
  sudo mkdir -p '$dir'
  sudo chown $COSCLI_USER:$COSCLI_USER '$dir'
  sudo setfacl -m u:$COSCLI_USER:rwx,d:u:$COSCLI_USER:rwx '$dir'
EOF
    exit 1
  fi

  sudo mkdir -p "$dir"
  sudo chown "$COSCLI_USER:$COSCLI_USER" "$dir"
  sudo setfacl -m "u:$COSCLI_USER:rwx,d:u:$COSCLI_USER:rwx" "$dir"
  touch "$dir/.coscli_write_test"
  rm -f "$dir/.coscli_write_test"
}

prepare_download_target() {
  local dest="$1"
  case "$dest" in
    */) ensure_cfs_dir "$dest" ;;
    *) ensure_cfs_dir "$(dirname "$dest")" ;;
  esac
}

main() {
  local cmd="${1:-}"
  [ -n "$cmd" ] || { usage; exit 2; }
  shift || true

  need_coscli
  guard_destructive "$cmd" "$@"

  case "$cmd" in
    -h|--help|help)
      usage
      ;;
    ls)
      local target="${1:-}"
      if [ -z "$target" ]; then
        "$COSCLI_BIN" ls "cos://$COSCLI_BUCKET/"
      else
        "$COSCLI_BIN" ls "$(cos_url "$target")"
      fi
      ;;
    du)
      [ "$#" -ge 1 ] || die "du requires a COS prefix or URL"
      "$COSCLI_BIN" du "$(cos_url "$1")"
      ;;
    ensure-cfs-dir)
      [ "$#" -eq 1 ] || die "ensure-cfs-dir requires exactly one local directory"
      ensure_cfs_dir "$1"
      ;;
    download)
      [ "$#" -ge 2 ] || die "download requires <cos-prefix-or-url> <local-dir>"
      local src="$1"
      local dest="$2"
      shift 2
      prepare_download_target "$dest"
      "$COSCLI_BIN" sync "$(cos_url "$src")" "$dest" -r --update "$@"
      ;;
    upload)
      [ "$#" -ge 2 ] || die "upload requires <local-path> <cos-prefix-or-url>"
      local src="$1"
      local dest="$2"
      shift 2
      [ -e "$src" ] || die "local source does not exist: $src"
      "$COSCLI_BIN" sync "$src" "$(cos_url "$dest")" -r --update "$@"
      ;;
    sync)
      [ "$#" -ge 2 ] || die "sync requires <source> <destination>"
      local src="$1"
      local dest="$2"
      shift 2
      case "$src" in cos://*) ;; *) [ -e "$src" ] || die "local source does not exist: $src" ;; esac
      case "$dest" in /cfs/*) prepare_download_target "$dest" ;; esac
      "$COSCLI_BIN" sync "$src" "$dest" "$@"
      ;;
    cp)
      [ "$#" -ge 2 ] || die "cp requires <source> <destination>"
      "$COSCLI_BIN" cp "$@"
      ;;
    *)
      die "unknown command: $cmd"
      ;;
  esac
}

main "$@"
