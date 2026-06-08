#!/usr/bin/env bash
set -Eeuo pipefail

FBDEV="${FBDEV:-/dev/fb1}"
CONF="/etc/X11/xorg.conf.d/98-waveshare28a-fbdev.conf"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt update
apt install -y xserver-xorg xinit x11-xserver-utils xserver-xorg-video-fbdev xserver-xorg-input-evdev xinput xinput-calibrator openbox

mkdir -p /etc/X11/xorg.conf.d
if [[ -f "$CONF" ]]; then
  cp -a "$CONF" "${CONF}.bak.$(date +%Y%m%d-%H%M%S)"
fi

cat > "$CONF" <<EOF
Section "Device"
    Identifier "Waveshare28aFB"
    Driver "fbdev"
    Option "fbdev" "${FBDEV}"
EndSection

Section "Monitor"
    Identifier "Waveshare28aMonitor"
EndSection

Section "Screen"
    Identifier "Waveshare28aScreen"
    Device "Waveshare28aFB"
    Monitor "Waveshare28aMonitor"
EndSection
EOF

echo "Installed on-demand X11 framebuffer config: ${CONF}"
echo "Run X11-only apps with: ./lcd-run.sh x COMMAND [ARGS...]"
