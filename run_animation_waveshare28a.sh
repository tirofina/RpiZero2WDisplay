#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FBDEV="${FBDEV:-/dev/fb1}"
RUN_MODE="${RUN_MODE:-x}"
SDL_DRIVER="${SDL_DRIVER:-auto}"
DURATION="${DURATION:-0}"
SIZE="${SIZE:-}"
FPS="${FPS:-30}"

if [[ ! -e "$FBDEV" ]]; then
  echo "Missing framebuffer device: ${FBDEV}"
  echo "Reboot after the Waveshare overlay setup, then check: ls /dev/fb*"
  exit 1
fi

if [[ "$RUN_MODE" == "fb" && ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run framebuffer mode as root so SDL can open ${FBDEV}: sudo RUN_MODE=fb $0"
  exit 1
fi

args=(
  "${SCRIPT_DIR}/heart_animation.py"
  --fbdev "$FBDEV"
  --duration "$DURATION"
  --fps "$FPS"
)

if [[ "$SDL_DRIVER" != "auto" && -n "$SDL_DRIVER" ]]; then
  args+=(--sdl-driver "$SDL_DRIVER")
fi

if [[ -n "$SIZE" ]]; then
  args+=(--size "$SIZE")
fi

exec "${SCRIPT_DIR}/lcd-run.sh" "$RUN_MODE" "$PYTHON_BIN" "${args[@]}"
