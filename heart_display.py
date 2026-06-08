#!/usr/bin/env python3
"""Display a centered heart with pygame.

The script uses the current SDL/pygame desktop size. On a real X11/Wayland/KMS
display it opens fullscreen by default. In headless/offscreen sessions it still
renders the same frame and can save it for verification.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def cli_value(name: str) -> str | None:
    prefix = f"{name}="
    for arg in sys.argv[1:]:
        if arg.startswith(prefix):
            return arg[len(prefix) :]
    if name not in sys.argv:
        return None
    index = sys.argv.index(name)
    if index + 1 >= len(sys.argv):
        return None
    return sys.argv[index + 1]


cli_fbdev = cli_value("--fbdev")
cli_sdl_driver = cli_value("--sdl-driver")
if cli_fbdev:
    os.environ.setdefault("SDL_FBDEV", cli_fbdev)
if cli_sdl_driver:
    os.environ.setdefault("SDL_VIDEODRIVER", cli_sdl_driver)

has_framebuffer = any(os.path.exists(path) for path in ("/dev/fb0", "/dev/fb1"))
has_graphics_session = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
if not has_graphics_session and not has_framebuffer and not os.path.exists("/dev/dri"):
    os.environ.setdefault("SDL_VIDEODRIVER", "offscreen")

import pygame


BG_TOP = (18, 20, 27)
BG_BOTTOM = (42, 46, 58)
HEART = (235, 36, 83)
HEART_DARK = (150, 12, 48)
HIGHLIGHT = (255, 128, 160)


def parse_size(value: str) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("size values must be positive")
    return width, height


def desktop_size() -> tuple[int, int]:
    sizes = pygame.display.get_desktop_sizes()
    if sizes:
        return sizes[0]
    info = pygame.display.Info()
    return info.current_w or 1024, info.current_h or 768


def draw_gradient(surface: pygame.Surface) -> None:
    width, height = surface.get_size()
    if height <= 1:
        surface.fill(BG_TOP)
        return

    for y in range(height):
        t = y / (height - 1)
        color = tuple(
            round(BG_TOP[i] * (1.0 - t) + BG_BOTTOM[i] * t) for i in range(3)
        )
        pygame.draw.line(surface, color, (0, y), (width, y))


def heart_points(center: tuple[int, int], scale: float) -> list[tuple[int, int]]:
    cx, cy = center
    points: list[tuple[int, int]] = []

    for step in range(720):
        t = (math.tau * step) / 720
        x = 16 * math.sin(t) ** 3
        y = (
            13 * math.cos(t)
            - 5 * math.cos(2 * t)
            - 2 * math.cos(3 * t)
            - math.cos(4 * t)
        )
        points.append((round(cx + x * scale), round(cy - y * scale)))

    return points


def draw_heart(surface: pygame.Surface) -> None:
    width, height = surface.get_size()
    draw_gradient(surface)

    render_scale = 3
    large = pygame.Surface((width * render_scale, height * render_scale), pygame.SRCALPHA)
    center = (large.get_width() // 2, large.get_height() // 2 + round(height * 0.035))
    scale = min(width, height) * render_scale / 38
    points = heart_points(center, scale)

    shadow_points = [(x + round(scale * 0.9), y + round(scale * 1.0)) for x, y in points]
    pygame.draw.polygon(large, (0, 0, 0, 86), shadow_points)
    pygame.draw.polygon(large, HEART_DARK, points)

    inner = heart_points(center, scale * 0.93)
    pygame.draw.polygon(large, HEART, inner)

    shine_rect = pygame.Rect(0, 0, round(width * 0.23 * render_scale), round(height * 0.14 * render_scale))
    shine_rect.center = (
        center[0] - round(width * 0.11 * render_scale),
        center[1] - round(height * 0.13 * render_scale),
    )
    pygame.draw.ellipse(large, HIGHLIGHT, shine_rect)

    smooth = pygame.transform.smoothscale(large, (width, height))
    surface.blit(smooth, (0, 0))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show a heart on the current display.")
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds before auto-exit. 0 means wait until closed or Esc.")
    parser.add_argument("--save", default="", help="Optional PNG path to save the rendered frame.")
    parser.add_argument("--size", type=parse_size, help="Override detected size, for example 240x320 or 320x240.")
    parser.add_argument("--fbdev", help="Framebuffer device to target, for example /dev/fb1.")
    parser.add_argument("--sdl-driver", help="SDL video driver to request, for example fbcon, kmsdrm, or offscreen.")
    parser.add_argument("--windowed", action="store_true", help="Open a window instead of fullscreen.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    pygame.display.init()
    driver = pygame.display.get_driver()
    detected_size = desktop_size()
    width, height = args.size or detected_size

    flags = 0 if args.windowed or driver == "offscreen" else pygame.FULLSCREEN
    screen = pygame.display.set_mode((width, height), flags)
    pygame.display.set_caption("Heart")

    draw_heart(screen)
    pygame.display.flip()

    if args.save:
        pygame.image.save(screen, args.save)

    print(f"SDL driver: {driver}")
    print(f"Detected desktop size: {detected_size[0]}x{detected_size[1]}")
    print(f"Rendered size: {width}x{height}")
    print(f"Fullscreen: {bool(flags & pygame.FULLSCREEN)}")
    if os.environ.get("SDL_FBDEV"):
        print(f"SDL_FBDEV: {os.environ['SDL_FBDEV']}")
    if args.save:
        print(f"Saved frame: {os.path.abspath(args.save)}")

    start = time.monotonic()
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return 0
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                pygame.quit()
                return 0

        if args.duration > 0 and time.monotonic() - start >= args.duration:
            pygame.quit()
            return 0

        clock.tick(30)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        pygame.quit()
        raise SystemExit(130)
