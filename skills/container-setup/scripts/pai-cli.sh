#!/usr/bin/env bash
# Install the official Alibaba Cloud PAI CLI into the persistent personal volume.
set -eu
personal=$1
bin_dir="$personal/.local/bin"
target="$bin_dir/pai"
mkdir -p "$bin_dir"
chmod 700 "$bin_dir"
config_dir="$personal/.config/aliyun-pai/cli"
mkdir -p "$config_dir"
chmod 700 "$config_dir"

case "$(uname -m)" in
    x86_64|amd64) artifact=pai-linux-amd64 ;;
    aarch64|arm64) artifact=pai-linux-arm64 ;;
    *) printf 'Unsupported CPU architecture for PAI CLI: %s\n' "$(uname -m)" >&2; exit 1 ;;
esac
url="https://pai-dsw-ai-machine.oss-cn-beijing.aliyuncs.com/cli/$artifact"

if [[ -x "$target" ]] && [[ "$("$target" --version 2>/dev/null || true)" == v1.1.0* ]]; then
    printf '[pai-cli] already installed: %s\n' "$target"
    exit 0
fi

tmp=$(mktemp "$bin_dir/.pai.tmp.XXXXXX")
cleanup() { rm -f "$tmp"; }
trap cleanup EXIT
curl --fail --location --retry 3 --connect-timeout 15 --output "$tmp" "$url"
chmod 700 "$tmp"
version=$("$tmp" --version 2>/dev/null || true)
if [[ "$version" != v1.1.0* ]]; then
    printf 'Downloaded PAI CLI has unexpected version: %s\n' "$version" >&2
    exit 1
fi
mv -f "$tmp" "$target"
chmod 700 "$target"
trap - EXIT
printf '[pai-cli] installed %s (%s)\n' "$target" "$version"
