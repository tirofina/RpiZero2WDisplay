#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage:
  sudo ./lcd-run.sh fb COMMAND [ARGS...]
  ./lcd-run.sh x COMMAND [ARGS...]

Modes:
  fb  Run a framebuffer/SDL app directly on the Waveshare LCD.
      Good only when the installed SDL build supports a direct console driver.

  x   Start a temporary X11 session, run COMMAND, then return to CLI.
      Good for cv2.imshow, tkinter, Qt, matplotlib, and other X11 apps.

Environment overrides:
  FBDEV=/dev/fb1          Framebuffer device, default /dev/fb1.
  SDL_DRIVER=auto         SDL driver for fb mode. Set fbcon/kmsdrm only if available.
  DISPLAY_NUM=:1          X11 display number for x mode, default :1.

Examples:
  ./lcd-run.sh x python3 heart_display.py --size 240x320 --duration 10
  sudo RUN_MODE=fb SDL_DRIVER=kmsdrm ./run_heart_waveshare28a.sh
  ./lcd-run.sh x python3 camera_gui.py
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

MODE="$1"
shift

FBDEV="${FBDEV:-/dev/fb1}"
SDL_DRIVER="${SDL_DRIVER:-auto}"
DISPLAY_NUM="${DISPLAY_NUM:-:1}"
FB_NUM="1"

if [[ "$FBDEV" =~ ^/dev/fb([0-9]+)$ ]]; then
  FB_NUM="${BASH_REMATCH[1]}"
fi

require_fbdev() {
  if [[ ! -e "$FBDEV" ]]; then
    echo "Missing framebuffer device: ${FBDEV}"
    echo "Reboot after the Waveshare overlay setup, then check: ls /dev/fb*"
    exit 1
  fi
}

map_console_if_possible() {
  if command -v con2fbmap >/dev/null 2>&1 && [[ ${EUID:-$(id -u)} -eq 0 ]]; then
    con2fbmap 1 "$FB_NUM" || true
  fi
}

case "$MODE" in
  fb)
    require_fbdev
    map_console_if_possible
    if [[ "$SDL_DRIVER" == "auto" || -z "$SDL_DRIVER" ]]; then
      exec env SDL_FBDEV="$FBDEV" "$@"
    fi
    exec env SDL_VIDEODRIVER="$SDL_DRIVER" SDL_FBDEV="$FBDEV" "$@"
    ;;

  x)
    require_fbdev
    map_console_if_possible

    if ! command -v startx >/dev/null 2>&1; then
      echo "Missing startx. Install xinit first: sudo apt install xinit"
      exit 1
    fi

    xinitrc="$(mktemp /tmp/lcd-xinitrc.XXXXXX)"
    trap 'rm -f "$xinitrc"' EXIT

    cat > "$xinitrc" <<'XINITRC'
#!/usr/bin/env bash
set -Eeuo pipefail

xset s off -dpms 2>/dev/null || true

WM_PID=""
if command -v openbox >/dev/null 2>&1; then
  openbox >/tmp/lcd-openbox.log 2>&1 &
  WM_PID="$!"
elif command -v matchbox-window-manager >/dev/null 2>&1; then
  matchbox-window-manager -use_titlebar no >/tmp/lcd-matchbox.log 2>&1 &
  WM_PID="$!"
fi

"$@"
status=$?

if [[ -n "$WM_PID" ]]; then
  kill "$WM_PID" 2>/dev/null || true
fi

exit "$status"
XINITRC
    chmod +x "$xinitrc"

    export SDL_FBDEV="$FBDEV"
    export SDL_VIDEODRIVER=x11
    startx "$xinitrc" "$@" -- "$DISPLAY_NUM" -nolisten tcp
    ;;

  *)
    echo "Unknown mode: $MODE"
    usage
    exit 1
    ;;
esac
