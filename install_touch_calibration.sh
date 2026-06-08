#!/usr/bin/env bash
set -Eeuo pipefail

CONF="/etc/X11/xorg.conf.d/99-calibration.conf"
MATCH_PRODUCT="${MATCH_PRODUCT:-ADS7846 Touchscreen}"
CALIBRATION="${CALIBRATION:-3821 182 300 3786}"
SWAP_AXES="${SWAP_AXES:-0}"
TOUCH_DRIVER="${TOUCH_DRIVER:-evdev}"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt update
apt install -y xinput xinput-calibrator xserver-xorg-input-evdev

mkdir -p /etc/X11/xorg.conf.d
if [[ -f "$CONF" ]]; then
  cp -a "$CONF" "${CONF}.bak.$(date +%Y%m%d-%H%M%S)"
fi

cat > "$CONF" <<EOF
Section "InputClass"
    Identifier "Waveshare28aTouchCalibration"
    MatchProduct "${MATCH_PRODUCT}"
    Driver "${TOUCH_DRIVER}"
    Option "Calibration" "${CALIBRATION}"
    Option "SwapAxes" "${SWAP_AXES}"
EndSection
EOF

echo "Installed touch calibration config: ${CONF}"
echo "MatchProduct: ${MATCH_PRODUCT}"
echo "Calibration: ${CALIBRATION}"
echo "SwapAxes: ${SWAP_AXES}"
echo "Driver: ${TOUCH_DRIVER}"
echo
echo "List X input devices with:"
echo "  ./lcd-run.sh x xinput list"
echo
echo "Test touch coordinates with:"
echo "  ./lcd-run.sh x python3 touch_test.py"
echo "or, for the current Waveshare framebuffer:"
echo "  ./lcd-run.sh x python3 touch_test.py --size 320x240"
