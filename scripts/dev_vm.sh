#!/bin/bash
# Dev test VM for archinstall.
# Builds a minimal dev ISO on first run (runtime deps pre-installed, 9p shares
# auto-mounted, `archinstall` aliased to `python -m archinstall`), then launches
# QEMU. Source lives on the host, guest mounts it read-only - no rebuild loop.
#
# Host artifacts (created in repo root, all git-ignored):
#   .dev-iso/                generated dev ISO (mkarchiso output)
#   .dev-disk.qcow2          VM disk image (qemu-img)
#   .dev-ovmf-vars.fd        persistent UEFI NVRAM (copied from OVMF_VARS)
#   .dev-configs/            optional, user-created - shared rw to guest as /root/cfg
#
# Inside the guest after boot:
#   /root/archinstall-dev    project source (9p ro, host edits appear live)
#   /root/cfg                .dev-configs share (9p rw, mounted only if folder exists)
#   archinstall              alias for `python -m archinstall`
#
# Run from the project root or from inside scripts/ - both work, the script
# resolves the project root from its own location.
#
# Usage (from project root):
#   ./scripts/dev_vm.sh              - build ISO if missing, fresh disk, boot
#   ./scripts/dev_vm.sh rebuild | r  - force rebuild ISO, fresh disk, boot
#   ./scripts/dev_vm.sh keep    | k  - reuse disk, boot ISO
#   ./scripts/dev_vm.sh boot    | b  - boot from installed disk (no ISO)
#   ./scripts/dev_vm.sh clean   | c  - remove disk, NVRAM, ISO
#   ./scripts/dev_vm.sh -h           - show this help
#
# Env overrides:
#   SCREEN_W, SCREEN_H       - virtio-vga resolution (default 1280x720)
#
# Host FS note: 9p mapped-xattr mode needs xattr support on the filesystem
# holding the repo (ext4/btrfs work out of the box; ZFS requires xattr=sa).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIGS_DIR="$PROJECT_DIR/.dev-configs"
ISO_DIR="$PROJECT_DIR/.dev-iso"
DISK="$PROJECT_DIR/.dev-disk.qcow2"
OVMF_VARS="$PROJECT_DIR/.dev-ovmf-vars.fd"
DISK_SIZE="30G"
RAM="4G"
CPUS="4"
SCREEN_W="${SCREEN_W:-1280}"
SCREEN_H="${SCREEN_H:-720}"
ARG="${1:-default}"

# OVMF firmware - probed at runtime across common distro paths
OVMF_CODE=""
OVMF_VARS_ORIG=""

err() { echo "ERROR: $*" >&2; exit 1; }

probe_ovmf() {
    local pairs=(
        "/usr/share/edk2/x64/OVMF_CODE.4m.fd:/usr/share/edk2/x64/OVMF_VARS.4m.fd"
        "/usr/share/edk2-ovmf/x64/OVMF_CODE.fd:/usr/share/edk2-ovmf/x64/OVMF_VARS.fd"
        "/usr/share/edk2/ovmf/OVMF_CODE.fd:/usr/share/edk2/ovmf/OVMF_VARS.fd"
        "/usr/share/OVMF/OVMF_CODE_4M.fd:/usr/share/OVMF/OVMF_VARS_4M.fd"
        "/usr/share/OVMF/OVMF_CODE.fd:/usr/share/OVMF/OVMF_VARS.fd"
    )
    local pair code vars
    for pair in "${pairs[@]}"; do
        code="${pair%%:*}"
        vars="${pair##*:}"
        if [ -f "$code" ] && [ -f "$vars" ]; then
            OVMF_CODE="$code"
            OVMF_VARS_ORIG="$vars"
            return 0
        fi
    done
    err "OVMF firmware not found. Install 'edk2-ovmf' (Arch), 'ovmf' (Debian/Ubuntu), or 'edk2-ovmf' (Fedora)."
}

check_host_deps() {
    local missing=() cmd
    for cmd in qemu-system-x86_64 qemu-img sudo; do
        command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
    done
    if [ ${#missing[@]} -gt 0 ]; then
        err "missing host commands: ${missing[*]} (install qemu-base and sudo)"
    fi
}

# ISO build needs pacman + mkarchiso, which are Arch-only. Accept Arch and
# Arch-based derivatives (Manjaro, EndeavourOS, ...) via ID / ID_LIKE.
check_arch_host() {
    local id="" id_like=""
    if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        id="${ID:-}"
        id_like="${ID_LIKE:-}"
    fi
    if [ "$id" != "arch" ] && [[ "$id_like" != *arch* ]]; then
        err "ISO build requires an Arch-based host (pacman + mkarchiso). Detected ID='${id:-unknown}', ID_LIKE='${id_like:-unknown}'."
    fi
}

# Parse runtime deps from pyproject.toml and map to Arch package names.
# Delegates to derive_packages.py so the Python logic lives in a real .py file.
derive_packages() {
    command -v python3 >/dev/null 2>&1 || err "python3 not found on host (needed to parse pyproject.toml)"
    local result
    result=$(python3 "$SCRIPT_DIR/derive_packages.py" "$PROJECT_DIR/pyproject.toml") \
        || err "failed to parse $PROJECT_DIR/pyproject.toml"
    [ -n "$result" ] || err "pyproject.toml has no [project.dependencies]"
    printf '%s\n' "$result"
}

find_iso() {
    ls -t "$ISO_DIR"/archlinux-*-x86_64.iso 2>/dev/null | head -n1
}

build_iso() {
    check_arch_host
    if ! command -v mkarchiso >/dev/null 2>&1; then
        echo ">>> mkarchiso not found on host; archiso will be installed via sudo pacman."
    fi
    local runtime_deps
    runtime_deps=$(derive_packages)
    echo ">>> Runtime deps derived from pyproject.toml:"
    echo "$runtime_deps" | sed 's/^/    /'
    echo ">>> Building dev ISO (sudo needed for pacman/mkarchiso)..."
    sudo env OUT_DIR="$ISO_DIR" HOST_USER="$(id -un)" RUNTIME_DEPS="$runtime_deps" bash <<'SUDO_SCRIPT'
set -e
BUILD_DIR=/tmp/archlive-dev

# Runtime deps - python plus the list derived from pyproject.toml on the host.
# Source comes via 9p, no wheel build needed.
packages=(python git)
while IFS= read -r p; do
    [ -n "$p" ] && packages+=("$p")
done <<< "$RUNTIME_DEPS"

rm -rf "$BUILD_DIR"
pacman --noconfirm --needed -S archiso
cp -r /usr/share/archiso/configs/releng "$BUILD_DIR"

# Drop preinstalled archinstall - we run from 9p-mounted source.
# Anchored pattern so related packages (archinstall-*, python-archinstall-*)
# would not be accidentally removed if releng ever grows them.
sed -i '/^archinstall$/d' "$BUILD_DIR/packages.x86_64"
for p in "${packages[@]}"; do
    echo "$p" >> "$BUILD_DIR/packages.x86_64"
done

# Trust the 9p-mounted source for git: host UIDs differ from the guest's,
# which would otherwise trip git's safe.directory dubious-ownership check.
mkdir -p "$BUILD_DIR/airootfs/etc"
cat > "$BUILD_DIR/airootfs/etc/gitconfig" <<'GIT'
[safe]
	directory = /root/archinstall-dev
GIT

# Auto-mount project, alias archinstall, print info on login
mkdir -p "$BUILD_DIR/airootfs/root"
cat > "$BUILD_DIR/airootfs/root/.zprofile" <<'ZP'
mkdir -p /root/archinstall-dev /root/cfg
if ! mount -t 9p -o trans=virtio,ro dev /root/archinstall-dev 2>/dev/null; then
    echo "ERROR: failed to mount 9p 'dev' share. The archinstall alias will not work."
    echo "Check host qemu virtfs support and that the guest kernel has the 9p module."
fi
mount -t 9p -o trans=virtio cfg /root/cfg 2>/dev/null || true
cd /root/archinstall-dev
export PYTHONDONTWRITEBYTECODE=1
alias archinstall='python -m archinstall'
cat <<MSG

=== archinstall dev environment ===
Source:  /root/archinstall-dev   (9p, read-only, live host edits)
Configs: /root/cfg               (9p, optional, if .dev-configs on host)
Run:     archinstall             (alias for 'python -m archinstall')

MSG
ZP

mkdir -p "$OUT_DIR"
cd "$BUILD_DIR"
mkarchiso -v -w work/ -o "$OUT_DIR" ./
chown -R "$HOST_USER:" "$OUT_DIR"
SUDO_SCRIPT
    echo ">>> ISO built."
}

case "$ARG" in
    -h|--help|help)
        sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    clean|c)
        rm -fv "$DISK" "$OVMF_VARS"
        rm -rf "$ISO_DIR"
        exit 0
        ;;
    boot|b)
        check_host_deps
        probe_ovmf
        [ -f "$DISK" ] || err "Disk missing, run without args first"
        BOOT_ORDER="c"
        ATTACH_ISO=false
        ;;
    rebuild|r)
        check_host_deps
        probe_ovmf
        rm -rf "$ISO_DIR"
        build_iso
        rm -f "$DISK"
        qemu-img create -f qcow2 "$DISK" "$DISK_SIZE"
        BOOT_ORDER="d"
        ATTACH_ISO=true
        ;;
    keep|k)
        check_host_deps
        probe_ovmf
        [ -f "$DISK" ] || err "Disk missing, run without args first"
        [ -n "$(find_iso)" ] || build_iso
        BOOT_ORDER="d"
        ATTACH_ISO=true
        ;;
    default)
        check_host_deps
        probe_ovmf
        [ -n "$(find_iso)" ] || build_iso
        rm -f "$DISK"
        qemu-img create -f qcow2 "$DISK" "$DISK_SIZE"
        BOOT_ORDER="d"
        ATTACH_ISO=true
        ;;
    *)
        err "Unknown argument: $ARG (try -h)"
        ;;
esac

[ -f "$OVMF_VARS" ] || cp "$OVMF_VARS_ORIG" "$OVMF_VARS"

QEMU_ARGS=(
    -machine q35
    -cpu host
    -enable-kvm
    -m "$RAM"
    -smp "$CPUS"
    -drive "file=$DISK,format=qcow2,if=virtio"
    -device virtio-net-pci,netdev=net0
    -netdev user,id=net0
    -device "virtio-vga,xres=$SCREEN_W,yres=$SCREEN_H"
    -display gtk,zoom-to-fit=off
    -monitor stdio
    -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE"
    -drive "if=pflash,format=raw,file=$OVMF_VARS"
    -virtfs "local,path=$PROJECT_DIR,mount_tag=dev,security_model=mapped-xattr,readonly=on"
    -boot "order=$BOOT_ORDER"
)

# Optional second 9p share for test configs, only if host folder exists
if [ -d "$CONFIGS_DIR" ]; then
    QEMU_ARGS+=(-virtfs "local,path=$CONFIGS_DIR,mount_tag=cfg,security_model=mapped-xattr")
fi

if [ "$ATTACH_ISO" = "true" ]; then
    ISO="$(find_iso)"
    [ -n "$ISO" ] && [ -f "$ISO" ] || err "No dev ISO after build step"
    QEMU_ARGS+=(-cdrom "$ISO")
fi

exec qemu-system-x86_64 "${QEMU_ARGS[@]}"
