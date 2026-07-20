#!/usr/bin/env bash
set -Eeuo pipefail

VRDMA_URL="${VRDMA_URL:-https://vrdma-release-1251001002.cos.ap-guangzhou.myqcloud.com/online-release/vrdma_bundle_build_202605261904.tgz}"
VRDMA_SHA256="${VRDMA_SHA256:-c974156d6bf6b288f202570c20d120de6b38f95cf786d8d482324d32d58defbb}"
AWS_OFI_NCCL_REF="${AWS_OFI_NCCL_REF:-v1.7.3-aws}"
WORKDIR="${WORKDIR:-/var/tmp/restore-vrdma}"
BACKUP_DIR="${BACKUP_DIR:-/var/tmp/restore-vrdma-backup-$(date +%Y%m%d-%H%M%S)}"
EXPECTED_RDMA_VERSION="34.0-1-95cc24ad"
CHANGES_STARTED=0
RESTORE_COMPLETED=0
DEB_DIR=""

log() {
    printf '[restore-vrdma] %s\n' "$*"
}

fail() {
    printf '[restore-vrdma] ERROR: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage:
  restore_vrdma.sh                Restore packages and rebuild aws-ofi-nccl (root required)
  restore_vrdma.sh --verify-only  Inspect packages and shared libraries without changing them
  restore_vrdma.sh --help
EOF
}

require_commands() {
    local command_name
    for command_name in "$@"; do
        command -v "$command_name" >/dev/null 2>&1 || fail "missing required command: $command_name"
    done
}

package_status() {
    local package_name
    for package_name in \
        rdma-core ibverbs-providers libibverbs1 librdmacm1 \
        libfabric hccl python3-pyverbs librdmacm1t64 libibnetdisc5t64; do
        dpkg-query -W -f='${Package}\t${Version}\t${db:Status-Status}\n' \
            "$package_name" 2>/dev/null || true
    done
}

check_library() {
    local path="$1"
    [ -e "$path" ] || fail "missing library: $path"
    if ldd "$path" 2>&1 | grep -q 'not found'; then
        ldd "$path" >&2
        fail "unresolved dependency in $path"
    fi
    log "library dependencies resolved: $path"
}

verify_result() {
    local package_name actual_version

    log "installed RDMA package status"
    package_status

    for package_name in rdma-core ibverbs-providers libibverbs1 librdmacm1; do
        actual_version="$(dpkg-query -W -f='${Version}' "$package_name" 2>/dev/null || true)"
        [ "$actual_version" = "$EXPECTED_RDMA_VERSION" ] || \
            fail "$package_name has version ${actual_version:-missing}; expected $EXPECTED_RDMA_VERSION"
    done

    [ ! -e /etc/libibverbs.d/irdma.driver ] || \
        fail "/etc/libibverbs.d/irdma.driver should be removed"
    [ -e /usr/lib/x86_64-linux-gnu/libibverbs/libvrdma-rdmav34.so ] || \
        fail "missing vRDMA ibverbs provider"

    check_library /usr/lib/x86_64-linux-gnu/libvrdma.so.1
    check_library /usr/local/lib/libfabric.so.1
    check_library /usr/lib/x86_64-linux-gnu/libnccl-vrdma.so
    check_library /usr/local/lib/libnccl-net.so

    log "local library verification passed"
    log "a multi-node NCCL smoke test is still required to prove the vRDMA transport"
}

prepare_sources() {
    require_commands wget sha256sum tar git
    rm -rf "$WORKDIR"
    mkdir -p "$WORKDIR"

    log "downloading the pinned Tencent vRDMA bundle"
    wget -q --show-progress -O "$WORKDIR/vrdma_bundle.tgz" "$VRDMA_URL"
    printf '%s  %s\n' "$VRDMA_SHA256" "$WORKDIR/vrdma_bundle.tgz" | sha256sum -c -
    tar -xf "$WORKDIR/vrdma_bundle.tgz" -C "$WORKDIR"
    DEB_DIR="$WORKDIR/vrdma_bundle/deb/amd64/ubuntu-22.04"
    [ -d "$DEB_DIR" ] || fail "bundle does not contain the expected deb directory"
    [ "$(find "$DEB_DIR" -maxdepth 1 -type f -name '*.deb' | wc -l)" -eq 25 ] || \
        fail "bundle does not contain the expected 25 deb packages"
    rm -f "$DEB_DIR"/python3-pyverbs_*.deb
    [ "$(find "$DEB_DIR" -maxdepth 1 -type f -name '*.deb' | wc -l)" -eq 24 ] || \
        fail "failed to exclude the Python 3.10-only python3-pyverbs package"

    log "cloning aws-ofi-nccl $AWS_OFI_NCCL_REF"
    git clone --quiet --depth 1 --branch "$AWS_OFI_NCCL_REF" \
        https://github.com/aws/aws-ofi-nccl.git "$WORKDIR/aws-ofi-nccl"
}

backup_current_state() {
    log "saving the current package manifest and library hashes to $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    dpkg-query -W >"$BACKUP_DIR/dpkg-packages.txt"
    package_status >"$BACKUP_DIR/rdma-packages.txt"
    find /usr/lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu/libibverbs /usr/local/lib \
        -maxdepth 1 \
        \( -name 'libvrdma.so*' -o -name 'libvrdma-rdmav34.so*' -o \
           -name 'libfabric.so*' -o -name 'libnccl-vrdma.so*' -o \
           -name 'libnccl-net.so*' \) \
        -print0 2>/dev/null | sort -z | xargs -0 -r sha256sum \
        >"$BACKUP_DIR/libraries.sha256"
}

install_prerequisites() {
    log "repairing apt state and installing build prerequisites"
    CHANGES_STARTED=1
    if dpkg-query -W python3-pyverbs >/dev/null 2>&1; then
        log "removing python3-pyverbs, which is incompatible with system Python 3.12"
        dpkg --remove --force-depends python3-pyverbs
    fi
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get -y --fix-broken install
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        perl libnl-3-dev libnl-route-3-dev libpci3 udev wget pciutils libhwloc-dev \
        ca-certificates git autoconf automake libtool make gcc g++ pkg-config
}

remove_conflicting_t64_packages() {
    local package_name status
    for package_name in librdmacm1t64 libibnetdisc5t64; do
        status="$(dpkg-query -W -f='${db:Status-Status}' "$package_name" 2>/dev/null || true)"
        if [ "$status" = "installed" ]; then
            log "removing incompatible package $package_name"
            dpkg --remove --force-depends "$package_name"
        fi
    done
}

install_vrdma_bundle() {
    log "restoring the complete pinned Tencent vRDMA package set"
    remove_conflicting_t64_packages
    dpkg -i --force-downgrade "$DEB_DIR"/*.deb || \
        dpkg -i --force-downgrade "$DEB_DIR"/*.deb
    rm -f /etc/libibverbs.d/irdma.driver
    ldconfig
    RESTORE_COMPLETED=1
}

build_aws_ofi_nccl() {
    require_commands autoconf automake libtoolize make gcc g++ pkg-config
    [ -x /usr/local/cuda/bin/nvcc ] || fail "CUDA toolkit not found at /usr/local/cuda"

    log "building aws-ofi-nccl $AWS_OFI_NCCL_REF against /usr/local/cuda"
    cd "$WORKDIR/aws-ofi-nccl"
    ./autogen.sh
    ./configure --with-cuda=/usr/local/cuda
    make -j"$(nproc)"
    make install
    ldconfig
}

recover_on_error() {
    local status=$?
    trap - ERR
    if [ "$CHANGES_STARTED" = "1" ] && [ "$RESTORE_COMPLETED" = "0" ] && [ -n "$DEB_DIR" ]; then
        log "failure occurred after apt changes; attempting to reinstall the pinned bundle"
        remove_conflicting_t64_packages || true
        dpkg -i --force-downgrade "$DEB_DIR"/*.deb || true
        rm -f /etc/libibverbs.d/irdma.driver
        ldconfig || true
    fi
    printf '[restore-vrdma] recovery command failed; inspect %s before further apt operations\n' \
        "$BACKUP_DIR" >&2
    exit "$status"
}

main() {
    case "${1:-}" in
        --verify-only)
            [ "$#" -eq 1 ] || fail "--verify-only takes no additional arguments"
            require_commands dpkg-query ldd
            verify_result
            return
            ;;
        --help|-h)
            usage
            return
            ;;
        '')
            ;;
        *)
            usage >&2
            fail "unknown argument: $1"
            ;;
    esac

    [ "$(id -u)" -eq 0 ] || fail "run recovery as root"
    require_commands apt-get dpkg dpkg-query ldd ldconfig
    trap recover_on_error ERR

    prepare_sources
    backup_current_state
    install_prerequisites
    install_vrdma_bundle
    build_aws_ofi_nccl
    verify_result

    log "vRDMA recovery completed"
    log "backup=$BACKUP_DIR"
    log "make this the final apt/system-library step before saving the image"
}

main "$@"
