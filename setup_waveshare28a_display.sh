#!/usr/bin/env bash
set -Eeuo pipefail

LOG_DIR="/var/log/waveshare28a-setup"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/setup-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

BOOT_CONFIG=""
CMDLINE_TXT=""
OVERLAY_DST_DIR=""
for p in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$p" ]] && BOOT_CONFIG="$p" && break
done
for p in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
  [[ -f "$p" ]] && CMDLINE_TXT="$p" && break
done
for p in /boot/firmware/overlays /boot/overlays; do
  [[ -d "$p" ]] && OVERLAY_DST_DIR="$p" && break
done
[[ -n "$BOOT_CONFIG" ]] || { echo "Missing config.txt"; exit 1; }
[[ -n "$OVERLAY_DST_DIR" ]] || { echo "Missing overlays directory"; exit 1; }

FBCP_SERVICE="/etc/systemd/system/fbcp.service"
CAL_CONF="/etc/X11/xorg.conf.d/99-calibration.conf"
RC_LOCAL="/etc/rc.local"
GETTY_DIR="/etc/systemd/system/getty@tty1.service.d"
GETTY_OVERRIDE="${GETTY_DIR}/autologin.conf"
WORKDIR="/usr/local/src/waveshare28a-setup"
OVERLAY_ZIP_URL="https://files.waveshare.com/upload/3/3f/Waveshare28a-v2.zip"
OVERLAY_NAME_IN_ZIP="waveshare28a-v2.dtbo"
OVERLAY_TARGET_NAME="waveshare28a-v2.dtbo"
USER_NAME="dietpi"
ROTATE="90"
ENABLE_AUTOLOGIN=1
ENABLE_CON2FBMAP=1
REBOOT_NOW=1
REBOOT_DELAY=10
NO_ROLLBACK=0

CAL_MATCH_PRODUCT="ADS7846 Touchscreen"
CAL_VALUES="3821 182 300 3786"
CAL_SWAPAXES="0"

BACKUP_DIR="/var/backups/waveshare28a-setup/$(date +%Y%m%d-%H%M%S)"
RESTORE_BOOT=0
RESTORE_CMDLINE=0
RESTORE_FBCP=0
RESTORE_CAL=0
RESTORE_RCLOCAL=0
RESTORE_GETTY=0
RESTORE_OVERLAY=0

usage() {
  cat <<USAGE
Usage:
  sudo bash $0 [--user USERNAME] [--rotate 0|90|180|270] [--no-autologin] [--no-con2fbmap] [--no-reboot] [--reboot-delay 10] [--no-rollback]

DietPi + Raspberry Pi Zero 2 W setup for Waveshare 2.8inch RPi LCD (A):
  - Keeps CUI console boot, no LightDM/Desktop.
  - Installs/updates waveshare28a-v2 overlay.
  - Sets screen rotation (default: 90).
  - Maps tty1 to fb1 automatically at boot with con2fbmap.
  - Enables tty1 autologin for the selected user (default: dietpi).
  - Leaves Python GUI optional; launch manually only when needed.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      USER_NAME="$2"
      shift 2
      ;;
    --rotate)
      ROTATE="$2"
      shift 2
      ;;
    --no-autologin)
      ENABLE_AUTOLOGIN=0
      shift
      ;;
    --no-con2fbmap)
      ENABLE_CON2FBMAP=0
      shift
      ;;
    --no-reboot)
      REBOOT_NOW=0
      shift
      ;;
    --reboot-delay)
      REBOOT_DELAY="$2"
      shift 2
      ;;
    --no-rollback)
      NO_ROLLBACK=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

case "$ROTATE" in
  0|90|180|270) ;;
  *) echo "rotate must be one of: 0, 90, 180, 270"; exit 1 ;;
esac

backup_file_if_exists() {
  local src="$1"
  local dst_name="$2"
  mkdir -p "$BACKUP_DIR"
  if [[ -f "$src" ]]; then
    cp -a "$src" "$BACKUP_DIR/$dst_name"
  fi
  return 0
}

append_once() {
  local line="$1"
  local file="$2"
  grep -Fqx "$line" "$file" 2>/dev/null || echo "$line" >> "$file"
}

rollback() {
  [[ "$NO_ROLLBACK" -eq 1 ]] && return 0
  echo "[ROLLBACK] Restoring previous state..."
  [[ "$RESTORE_BOOT" -eq 1 && -f "$BACKUP_DIR/config.txt.bak" ]] && cp -f "$BACKUP_DIR/config.txt.bak" "$BOOT_CONFIG" || true
  [[ "$RESTORE_CMDLINE" -eq 1 && -n "$CMDLINE_TXT" && -f "$BACKUP_DIR/cmdline.txt.bak" ]] && cp -f "$BACKUP_DIR/cmdline.txt.bak" "$CMDLINE_TXT" || true
  if [[ "$RESTORE_FBCP" -eq 1 ]]; then
    [[ -f "$BACKUP_DIR/fbcp.service.bak" ]] && cp -f "$BACKUP_DIR/fbcp.service.bak" "$FBCP_SERVICE" || rm -f "$FBCP_SERVICE" || true
  fi
  if [[ "$RESTORE_CAL" -eq 1 ]]; then
    [[ -f "$BACKUP_DIR/99-calibration.conf.bak" ]] && cp -f "$BACKUP_DIR/99-calibration.conf.bak" "$CAL_CONF" || rm -f "$CAL_CONF" || true
  fi
  if [[ "$RESTORE_RCLOCAL" -eq 1 ]]; then
    [[ -f "$BACKUP_DIR/rc.local.bak" ]] && cp -f "$BACKUP_DIR/rc.local.bak" "$RC_LOCAL" || rm -f "$RC_LOCAL" || true
    chmod +x "$RC_LOCAL" 2>/dev/null || true
  fi
  if [[ "$RESTORE_GETTY" -eq 1 ]]; then
    [[ -f "$BACKUP_DIR/getty-autologin.conf.bak" ]] && cp -f "$BACKUP_DIR/getty-autologin.conf.bak" "$GETTY_OVERRIDE" || rm -f "$GETTY_OVERRIDE" || true
  fi
  [[ "$RESTORE_OVERLAY" -eq 1 ]] && rm -f "${OVERLAY_DST_DIR}/${OVERLAY_TARGET_NAME}" || true
  systemctl daemon-reload || true
}

on_error() {
  local exit_code=$?
  local line_no=${1:-unknown}
  echo "[ERROR] Script failed at line ${line_no} with exit code ${exit_code}."
  rollback
  echo "[ERROR] See log: ${LOG_FILE}"
  exit "$exit_code"
}
trap 'on_error ${LINENO}' ERR

echo "[INFO] Log file: ${LOG_FILE}"
echo "[INFO] BOOT_CONFIG=${BOOT_CONFIG}"
[[ -n "$CMDLINE_TXT" ]] && echo "[INFO] CMDLINE_TXT=${CMDLINE_TXT}"
echo "[INFO] OVERLAY_DST_DIR=${OVERLAY_DST_DIR}"
echo "[INFO] USER_NAME=${USER_NAME}"
echo "[INFO] ROTATE=${ROTATE}"

echo "[1/8] Installing DietPi/Trixie-compatible packages..."
apt update
apt install -y fbset xserver-xorg xinit x11-xserver-utils xserver-xorg-video-fbdev xserver-xorg-input-evdev xinput xinput-calibrator unzip wget curl openbox

echo "[2/8] Preparing work directory..."
mkdir -p "$WORKDIR"
cd "$WORKDIR"

echo "[3/8] Backing up current files..."
backup_file_if_exists "$BOOT_CONFIG" config.txt.bak
RESTORE_BOOT=1
if [[ -n "$CMDLINE_TXT" ]]; then
  backup_file_if_exists "$CMDLINE_TXT" cmdline.txt.bak
  RESTORE_CMDLINE=1
fi
backup_file_if_exists "$FBCP_SERVICE" fbcp.service.bak
RESTORE_FBCP=1
backup_file_if_exists "$CAL_CONF" 99-calibration.conf.bak
RESTORE_CAL=1
backup_file_if_exists "$RC_LOCAL" rc.local.bak
RESTORE_RCLOCAL=1
backup_file_if_exists "$GETTY_OVERRIDE" getty-autologin.conf.bak
RESTORE_GETTY=1

echo "[4/8] Downloading and installing Waveshare overlay..."
rm -f Waveshare28a-v2.zip
wget -O Waveshare28a-v2.zip "$OVERLAY_ZIP_URL"
rm -rf overlay_zip
mkdir -p overlay_zip
unzip -o Waveshare28a-v2.zip -d overlay_zip >/dev/null
[[ -f "overlay_zip/${OVERLAY_NAME_IN_ZIP}" ]] || { echo "Overlay file ${OVERLAY_NAME_IN_ZIP} not found in zip"; exit 1; }
install -Dm644 "overlay_zip/${OVERLAY_NAME_IN_ZIP}" "${OVERLAY_DST_DIR}/${OVERLAY_TARGET_NAME}"
RESTORE_OVERLAY=1

echo "[5/8] Updating boot config for Zero 2 W + Waveshare 2.8A..."
sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/' "$BOOT_CONFIG" || true
sed -i 's/^dtoverlay=vc4-fkms-v3d/#dtoverlay=vc4-fkms-v3d/' "$BOOT_CONFIG" || true
append_once 'dtparam=spi=on' "$BOOT_CONFIG"
if grep -q '^dtoverlay=waveshare28a-v2' "$BOOT_CONFIG"; then
  sed -i "s/^dtoverlay=waveshare28a-v2.*/dtoverlay=waveshare28a-v2,rotate=${ROTATE}/" "$BOOT_CONFIG"
else
  echo "dtoverlay=waveshare28a-v2,rotate=${ROTATE}" >> "$BOOT_CONFIG"
fi
if grep -q '^dtoverlay=ads7846' "$BOOT_CONFIG"; then
  sed -i 's/^dtoverlay=ads7846.*/dtoverlay=ads7846,cs=1,penirq=17,penirq_pull=2,speed=50000,keep_vref_on=1,pmax=255,xohms=60/' "$BOOT_CONFIG"
else
  echo 'dtoverlay=ads7846,cs=1,penirq=17,penirq_pull=2,speed=50000,keep_vref_on=1,pmax=255,xohms=60' >> "$BOOT_CONFIG"
fi
append_once 'hdmi_force_hotplug=1' "$BOOT_CONFIG"
append_once 'display_rotate=0' "$BOOT_CONFIG"

if [[ -n "$CMDLINE_TXT" ]]; then
  if grep -q 'consoleblank=' "$CMDLINE_TXT" 2>/dev/null; then
    sed -i 's/\bconsoleblank=[^ ]*\b/consoleblank=0/' "$CMDLINE_TXT" || true
  else
    sed -i '1 s|$| consoleblank=0|' "$CMDLINE_TXT" || true
  fi
fi

echo "[6/8] Writing calibration file..."
mkdir -p /etc/X11/xorg.conf.d
cat > "$CAL_CONF" <<EOF2
Section "InputClass"
    Identifier "ADS7846 Calibration"
    MatchProduct "${CAL_MATCH_PRODUCT}"
    Driver "evdev"
    Option "Calibration" "${CAL_VALUES}"
    Option "SwapAxes" "${CAL_SWAPAXES}"
EndSection
EOF2

echo "[7/8] Configuring tty1 on fb1 and autologin..."
if [[ "$ENABLE_CON2FBMAP" -eq 1 ]]; then
  if [[ ! -f "$RC_LOCAL" ]]; then
    cat > "$RC_LOCAL" <<'RCLOCAL'
#!/bin/sh -e
con2fbmap 1 1 || true
exit 0
RCLOCAL
  else
    grep -q 'con2fbmap 1 1' "$RC_LOCAL" || sed -i '/^exit 0/i con2fbmap 1 1 || true' "$RC_LOCAL"
    grep -q '^#!/bin/sh -e' "$RC_LOCAL" || sed -i '1i #!/bin/sh -e' "$RC_LOCAL"
    grep -q '^exit 0$' "$RC_LOCAL" || echo 'exit 0' >> "$RC_LOCAL"
  fi
  chmod +x "$RC_LOCAL"
fi

if [[ "$ENABLE_AUTOLOGIN" -eq 1 ]]; then
  mkdir -p "$GETTY_DIR"
  cat > "$GETTY_OVERRIDE" <<EOF3
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${USER_NAME} --noclear %I \$TERM
EOF3
fi

echo "[8/8] Finalizing..."
rm -f "$FBCP_SERVICE" || true
systemctl daemon-reload || true

echo
echo "[SUCCESS] Setup completed for Raspberry Pi Zero 2 W + Waveshare 2.8inch RPi LCD (A)."
echo "[SUCCESS] Rotation set to ${ROTATE} degrees."
echo "[SUCCESS] tty1 -> fb1 mapping enabled: ${ENABLE_CON2FBMAP}."
echo "[SUCCESS] tty1 autologin enabled for user: ${USER_NAME} (enabled=${ENABLE_AUTOLOGIN})."
echo "[SUCCESS] GUI is NOT enabled by default; CUI remains the primary interface."
echo "[SUCCESS] Log saved to: ${LOG_FILE}"
echo "[INFO] Test on-demand X11 output with:"
echo "       cd /home/dietpi/RpiZero2WDisplay && ./run_heart_waveshare28a.sh"

if [[ "$REBOOT_NOW" -eq 1 ]]; then
  echo "[INFO] Rebooting in ${REBOOT_DELAY} seconds..."
  sleep "$REBOOT_DELAY"
  reboot || true
  systemctl reboot || true
  echo "[WARN] Automatic reboot failed. Power-cycle the device manually."
else
  echo "[INFO] Auto reboot disabled. Reboot or power-cycle manually to apply rotation at boot."
fi
