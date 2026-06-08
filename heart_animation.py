#!/usr/bin/env python3
"""Matrix-style animated pygame display demo for the Waveshare LCD."""

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


BLACK = (0, 4, 2)
MATRIX_DIM = (0, 58, 24)
MATRIX_GREEN = (0, 220, 88)
MATRIX_BRIGHT = (190, 255, 210)
HEART = (0, 245, 92)
HEART_DARK = (0, 74, 34)
HEART_LIGHT = (176, 255, 196)
WHITE = MATRIX_BRIGHT
MATRIX_CHARS = "0101011010010110"


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
    return info.current_w or 320, info.current_h or 240


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] * (1.0 - t) + b[i] * t) for i in range(3))


def heart_points(center: tuple[int, int], scale: float) -> list[tuple[int, int]]:
    cx, cy = center
    points: list[tuple[int, int]] = []
    for step in range(240):
        t = (math.tau * step) / 240
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        points.append((round(cx + x * scale), round(cy - y * scale)))
    return points


def draw_background(surface: pygame.Surface, font: pygame.font.Font, elapsed: float) -> None:
    width, height = surface.get_size()
    surface.fill(BLACK)

    cell_h = max(12, font.get_height())
    cell_w = max(9, font.size("0")[0] + 4)

    for col, x in enumerate(range(0, width, cell_w)):
        speed = 24 + (col * 13) % 46
        offset = int(elapsed * speed + col * cell_h * 3) % (height + cell_h * 8)
        for trail in range(12):
            y = offset - trail * cell_h
            if y < -cell_h or y >= height:
                continue
            idx = (col * 17 + trail * 5 + int(elapsed * 9)) % len(MATRIX_CHARS)
            intensity = max(0.0, 1.0 - trail / 12)
            color = mix(MATRIX_DIM, MATRIX_GREEN, 0.25 + intensity * 0.6)
            if trail == 0:
                color = MATRIX_BRIGHT
            rendered = font.render(MATRIX_CHARS[idx], True, color)
            surface.blit(rendered, (x, y))

    for row in range(5):
        y = round((row + 0.8) * height / 5)
        amplitude = max(5, height * 0.035)
        points = []
        for x in range(-8, width + 9, 8):
            wave = math.sin(x * 0.045 + elapsed * (1.5 + row * 0.18) + row)
            points.append((x, round(y + wave * amplitude)))
        color = mix((0, 45, 20), (0, 130, 56), row / 4)
        pygame.draw.lines(surface, color, False, points, 1)


def draw_orbit(surface: pygame.Surface, elapsed: float) -> None:
    width, height = surface.get_size()
    cx, cy = width // 2, height // 2
    radius_x = width * 0.34
    radius_y = height * 0.25

    for i in range(12):
        angle = elapsed * 1.4 + i * math.tau / 12
        depth = math.sin(angle) * 0.5 + 0.5
        x = round(cx + math.cos(angle) * radius_x)
        y = round(cy + math.sin(angle) * radius_y)
        size = round(2 + depth * 4)
        color = mix(MATRIX_GREEN, MATRIX_BRIGHT, depth)
        pygame.draw.circle(surface, color, (x, y), size)


def draw_heart(surface: pygame.Surface, elapsed: float) -> None:
    width, height = surface.get_size()
    render_scale = 3
    large = pygame.Surface((width * render_scale, height * render_scale), pygame.SRCALPHA)
    beat = 1.0 + 0.075 * math.sin(elapsed * math.tau * 1.25)
    lift = round(math.sin(elapsed * 2.1) * height * 0.012)
    center = (
        large.get_width() // 2,
        large.get_height() // 2 + round(height * 0.035 * render_scale) + lift * render_scale,
    )
    scale = min(width, height) * render_scale / 40 * beat
    points = heart_points(center, scale)

    shadow = [(x + round(scale * 0.75), y + round(scale * 0.95)) for x, y in points]
    glow = heart_points(center, scale * 1.10)
    pygame.draw.polygon(large, (0, 255, 95, 42), glow)
    pygame.draw.polygon(large, (0, 0, 0, 130), shadow)
    pygame.draw.polygon(large, HEART_DARK, points)
    pygame.draw.polygon(large, HEART, heart_points(center, scale * 0.92))

    shine = pygame.Rect(0, 0, round(width * 0.20 * render_scale), round(height * 0.13 * render_scale))
    shine.center = (
        center[0] - round(width * 0.10 * render_scale),
        center[1] - round(height * 0.12 * render_scale),
    )
    pygame.draw.ellipse(large, HEART_LIGHT, shine)

    pulse_radius = round(min(width, height) * render_scale * (0.36 + 0.05 * math.sin(elapsed * math.tau)))
    pygame.draw.circle(large, (0, 255, 95, 55), center, pulse_radius, max(2, render_scale))

    smooth = pygame.transform.smoothscale(large, (width, height))
    surface.blit(smooth, (0, 0))


def draw_label(surface: pygame.Surface, font: pygame.font.Font, elapsed: float) -> None:
    width, height = surface.get_size()
    text = f"{elapsed:04.1f}s"
    rendered = font.render(text, True, WHITE)
    pad = 6
    bg = pygame.Rect(width - rendered.get_width() - pad * 2 - 4, 4, rendered.get_width() + pad * 2, rendered.get_height() + pad)
    pygame.draw.rect(surface, (0, 0, 0, 72), bg, border_radius=4)
    surface.blit(rendered, (bg.x + pad, bg.y + pad // 2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show an animated heart demo on the current display.")
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds before auto-exit. 0 means wait until closed or Esc.")
    parser.add_argument("--save-frame", default="", help="Optional PNG path to save the final rendered frame.")
    parser.add_argument("--size", type=parse_size, help="Override detected size, for example 320x240.")
    parser.add_argument("--fps", type=int, default=30, help="Target animation frame rate.")
    parser.add_argument("--fbdev", help="Framebuffer device to target, for example /dev/fb1.")
    parser.add_argument("--sdl-driver", help="SDL video driver to request, for example kmsdrm or offscreen.")
    parser.add_argument("--windowed", action="store_true", help="Open a window instead of fullscreen.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pygame.init()

    driver = pygame.display.get_driver()
    detected_size = desktop_size()
    width, height = args.size or detected_size
    flags = 0 if args.windowed or driver == "offscreen" else pygame.FULLSCREEN
    screen = pygame.display.set_mode((width, height), flags)
    pygame.display.set_caption("Heart Animation")
    font = pygame.font.Font(None, max(18, min(width, height) // 11))

    print(f"SDL driver: {driver}")
    print(f"Detected desktop size: {detected_size[0]}x{detected_size[1]}")
    print(f"Rendered size: {width}x{height}")
    print(f"Fullscreen: {bool(flags & pygame.FULLSCREEN)}")
    if os.environ.get("SDL_FBDEV"):
        print(f"SDL_FBDEV: {os.environ['SDL_FBDEV']}")

    start = time.monotonic()
    clock = pygame.time.Clock()
    target_fps = max(1, args.fps)

    while True:
        elapsed = time.monotonic() - start
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if args.save_frame:
                    pygame.image.save(screen, args.save_frame)
                pygame.quit()
                return 0
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                if args.save_frame:
                    pygame.image.save(screen, args.save_frame)
                pygame.quit()
                return 0

        draw_background(screen, font, elapsed)
        draw_orbit(screen, elapsed)
        draw_heart(screen, elapsed)
        draw_label(screen, font, elapsed)
        pygame.display.flip()

        if args.duration > 0 and elapsed >= args.duration:
            if args.save_frame:
                pygame.image.save(screen, args.save_frame)
                print(f"Saved frame: {os.path.abspath(args.save_frame)}")
            pygame.quit()
            return 0

        clock.tick(target_fps)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        pygame.quit()
        raise SystemExit(130)
