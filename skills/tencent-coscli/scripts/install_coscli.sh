#!/usr/bin/env bash
set -euo pipefail

DOWNLOAD_BASE="${COSCLI_DOWNLOAD_BASE:-https://cosbrowser.cloud.tencent.com/software/coscli}"
INSTALL_DIR="${COSCLI_INSTALL_DIR:-$HOME/bin}"
CONFIG_PATH="${COSCLI_CONFIG:-$HOME/.cos.yaml}"
LOG_DIR="${COSCLI_LOG_DIR:-$HOME/coscli_output}"
BUCKET="${COSCLI_BUCKET:-phymi-cos-1438869198}"
ENDPOINT="${COSCLI_ENDPOINT:-cos.ap-shanghai.myqcloud.com}"
ALIAS="${COSCLI_ALIAS:-phymi}"
CREDENTIAL_FILE="${COSCLI_CREDENTIAL_FILE:-}"
CONFIGURE=0
VERIFY=0

usage() {
  cat <<'EOF'
Usage:
  install_coscli.sh [--configure] [--verify]

Options:
  --install-dir DIR   Install wrapper and binary here. Default: $HOME/bin
  --config PATH       coscli config path. Default: $HOME/.cos.yaml
  --log-dir DIR       coscli log directory. Default: $HOME/coscli_output
  --bucket NAME       Default bucket. Default: phymi-cos-1438869198
  --endpoint ENDPOINT Default endpoint. Default: cos.ap-shanghai.myqcloud.com
  --alias ALIAS       Bucket alias. Default: phymi
  --configure         Initialize the config file using COSCLI_SECRET_ID/COSCLI_SECRET_KEY.
  --credential-file FILE
                      Source a private env file before configuring. It may define
                      COSCLI_SECRET_ID and COSCLI_SECRET_KEY.
  --verify            Run "coscli ls" after installation. Requires valid config.

Environment:
  COSCLI_DOWNLOAD_BASE, COSCLI_INSTALL_DIR, COSCLI_CONFIG, COSCLI_LOG_DIR,
  COSCLI_BUCKET, COSCLI_ENDPOINT, COSCLI_ALIAS, COSCLI_CREDENTIAL_FILE,
  COSCLI_SECRET_ID, COSCLI_SECRET_KEY.

Secrets are never printed. Prefer environment variables or a chmod 600 private
credential file instead of pasting AK/SK into chat or committing them to files.
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

need_arg() {
  [ "$#" -ge 2 ] || die "$1 requires a value"
}

detect_asset() {
  local os arch
  os="$(uname -s)"
  arch="$(uname -m)"

  case "$os:$arch" in
    Linux:x86_64|Linux:amd64) printf 'coscli-linux-amd64\n' ;;
    Linux:aarch64|Linux:arm64) printf 'coscli-linux-arm64\n' ;;
    Linux:armv7l|Linux:armv6l) printf 'coscli-linux-arm\n' ;;
    Linux:i386|Linux:i686) printf 'coscli-linux-386\n' ;;
    Darwin:x86_64|Darwin:amd64) printf 'coscli-darwin-amd64\n' ;;
    Darwin:aarch64|Darwin:arm64) printf 'coscli-darwin-arm64\n' ;;
    *) die "unsupported platform: $os $arch" ;;
  esac
}

download() {
  local url="$1"
  local dest="$2"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$dest"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$dest" "$url"
  else
    die "curl or wget is required to download coscli"
  fi
}

write_wrapper() {
  local wrapper_path="$1"
  local binary_path="$2"
  local config_path="$3"
  local log_dir="$4"

  cat >"$wrapper_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

config_path="\${COSCLI_CONFIG:-$config_path}"
log_path="\${COSCLI_LOG_DIR:-$log_dir}"

mkdir -p "\$log_path"
exec "$binary_path" -c "\$config_path" --log-path "\$log_path" "\$@"
EOF
  chmod 755 "$wrapper_path"
}

load_credentials() {
  if [ -n "$CREDENTIAL_FILE" ]; then
    [ -f "$CREDENTIAL_FILE" ] || die "credential file not found: $CREDENTIAL_FILE"
    # shellcheck disable=SC1090
    . "$CREDENTIAL_FILE"
  fi

  [ -n "${COSCLI_SECRET_ID:-}" ] || die "COSCLI_SECRET_ID is required for --configure"
  [ -n "${COSCLI_SECRET_KEY:-}" ] || die "COSCLI_SECRET_KEY is required for --configure"
}

configure_coscli() {
  local binary_path="$1"
  local config_path="$2"
  local log_dir="$3"

  load_credentials
  mkdir -p "$(dirname "$config_path")" "$log_dir"
  touch "$config_path"
  chmod 600 "$config_path"

  "$binary_path" -c "$config_path" --log-path "$log_dir" config init <<EOF
$config_path

$COSCLI_SECRET_ID
$COSCLI_SECRET_KEY

false
false
false
$BUCKET
$ENDPOINT
$ALIAS
EOF
  chmod 600 "$config_path"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --install-dir)
      need_arg "$@"
      INSTALL_DIR="$2"
      shift 2
      ;;
    --config)
      need_arg "$@"
      CONFIG_PATH="$2"
      shift 2
      ;;
    --log-dir)
      need_arg "$@"
      LOG_DIR="$2"
      shift 2
      ;;
    --bucket)
      need_arg "$@"
      BUCKET="$2"
      shift 2
      ;;
    --endpoint)
      need_arg "$@"
      ENDPOINT="$2"
      shift 2
      ;;
    --alias)
      need_arg "$@"
      ALIAS="$2"
      shift 2
      ;;
    --credential-file)
      need_arg "$@"
      CREDENTIAL_FILE="$2"
      shift 2
      ;;
    --configure)
      CONFIGURE=1
      shift
      ;;
    --verify)
      VERIFY=1
      shift
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

asset="$(detect_asset)"
binary_path="$INSTALL_DIR/coscli-bin"
wrapper_path="$INSTALL_DIR/coscli"
tmp_path="$(mktemp)"
trap 'rm -f "$tmp_path"' EXIT

mkdir -p "$INSTALL_DIR" "$LOG_DIR"
download "$DOWNLOAD_BASE/$asset" "$tmp_path"
install -m 755 "$tmp_path" "$binary_path"
write_wrapper "$wrapper_path" "$binary_path" "$CONFIG_PATH" "$LOG_DIR"

if [ "$CONFIGURE" -eq 1 ]; then
  configure_coscli "$binary_path" "$CONFIG_PATH" "$LOG_DIR"
fi

if [ "$VERIFY" -eq 1 ]; then
  "$wrapper_path" ls "cos://$BUCKET/" >/dev/null
fi

printf 'Installed coscli wrapper: %s\n' "$wrapper_path"
printf 'Real coscli binary: %s\n' "$binary_path"
printf 'Config path: %s\n' "$CONFIG_PATH"
printf 'Log directory: %s\n' "$LOG_DIR"
