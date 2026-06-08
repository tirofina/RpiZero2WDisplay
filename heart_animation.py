#!/usr/bin/env python3
"""Matrix-style animated pygame display demo for the Waveshare LCD."""

from __future__ import annotations

import argparse
import math
import os
import random
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
MATRIX_DIM = (0, 42, 18)
MATRIX_MID = (0, 130, 52)
MATRIX_GREEN = (0, 230, 92)
MATRIX_BRIGHT = (190, 255, 210)
HEART_DARK = (0, 74, 34)
MATRIX_WHITE = (222, 255, 226)
WHITE = MATRIX_WHITE
MATRIX_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ#$%&*@+-/"
GLITCH_CYAN = (68, 255, 220)
GLITCH_PURPLE = (98, 18, 92)


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


def matrix_font(size: int, bold: bool = False) -> pygame.font.Font:
    for name in ("dejavusansmono", "liberationmono", "monospace"):
        font = pygame.font.SysFont(name, size, bold=bold)
        if font:
            return font
    return pygame.font.Font(None, size)


def blit_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    pos: tuple[int, int],
    color: tuple[int, int, int],
    alpha: int,
) -> None:
    rendered = font.render(text, True, color)
    rendered.set_alpha(max(0, min(255, alpha)))
    surface.blit(rendered, pos)


def draw_code_rain(
    surface: pygame.Surface,
    font: pygame.font.Font,
    seed: int,
    elapsed: float,
    alpha_scale: float = 1.0,
    speed_boost: float = 1.0,
) -> None:
    width, height = surface.get_size()
    cell_h = max(10, font.get_height())
    cell_w = max(8, font.size("W")[0] + 2)

    for col, x in enumerate(range(0, width, cell_w)):
        rng = random.Random(seed + col * 7919)
        trail = rng.randint(8, 24)
        speed = rng.uniform(20.0, 82.0) * speed_boost
        phase = rng.uniform(0.0, height + trail * cell_h)
        head = int((phase + elapsed * speed) % (height + trail * cell_h)) - trail * cell_h
        mutate_rate = rng.uniform(8.0, 22.0)

        for row in range(trail):
            y = head - row * cell_h
            if y < -cell_h or y >= height:
                continue

            tick = int(elapsed * mutate_rate)
            idx = (rng.randint(0, 9999) + row * 11 + tick * (col % 5 + 1)) % len(MATRIX_CHARS)
            char = MATRIX_CHARS[idx]
            strength = max(0.0, 1.0 - row / max(1, trail - 1))
            color = mix(MATRIX_DIM, MATRIX_GREEN, 0.25 + strength * 0.58)
            alpha = round((42 + strength * 180) * alpha_scale)
            if row == 0:
                color = MATRIX_WHITE
                alpha = round(245 * alpha_scale)
            blit_text(surface, font, char, (x, y), color, alpha)


def apply_glitch(surface: pygame.Surface, elapsed: float, seed: int, intensity: float) -> None:
    width, height = surface.get_size()
    source = surface.copy()
    rng = random.Random(seed + int(elapsed * 18))
    band_count = max(2, round(5 * intensity))
    max_shift = max(1, round(width * 0.018 * intensity))

    for _ in range(band_count):
        band_h = rng.randint(1, max(2, height // 44))
        y = rng.randint(0, max(0, height - band_h))
        shift = rng.choice((-1, 1)) * rng.randint(1, max_shift)
        src = pygame.Rect(0, y, width, band_h)
        surface.blit(source, (shift, y), src)

        tint = pygame.Surface((width, band_h), pygame.SRCALPHA)
        if rng.random() < 0.58:
            tint.fill((*GLITCH_CYAN, rng.randint(8, 20)))
        else:
            tint.fill((*GLITCH_PURPLE, rng.randint(7, 16)))
        surface.blit(tint, (0, y))

        if rng.random() < 0.48:
            line_y = y + rng.randrange(band_h)
            line = pygame.Surface((width, 1), pygame.SRCALPHA)
            line.fill((*MATRIX_WHITE, rng.randint(38, 86)))
            surface.blit(line, (0, line_y))


def draw_monitor_overlay(surface: pygame.Surface, elapsed: float, seed: int) -> None:
    width, height = surface.get_size()
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    flicker = 0.86 + 0.14 * math.sin(elapsed * 37.0)

    for y in range(0, height, 3):
        overlay.fill((0, 0, 0, round(38 * flicker)), (0, y, width, 1))
    for y in range(1, height, 6):
        pygame.draw.line(overlay, (0, 255, 95, 14), (0, y), (width, y), 1)
    for x in range(0, width, 3):
        pygame.draw.line(overlay, (0, 255, 95, 8), (x, 0), (x, height), 1)

    rng = random.Random(seed + int(elapsed * 24))
    specks = max(90, width * height // 820)
    for _ in range(specks):
        x = rng.randrange(width)
        y = rng.randrange(height)
        value = rng.randint(38, 150)
        overlay.set_at((x, y), (0, value, 44, rng.randint(16, 48)))

    edge_steps = max(16, min(width, height) // 8)
    for i in range(edge_steps):
        alpha = round(((edge_steps - i) / edge_steps) ** 2 * 18)
        inner_w = width - i * 2
        inner_h = height - i * 2
        if inner_w <= 0 or inner_h <= 0:
            break
        overlay.fill((0, 0, 0, alpha), (i, i, inner_w, 1))
        overlay.fill((0, 0, 0, alpha), (i, height - i - 1, inner_w, 1))
        overlay.fill((0, 0, 0, alpha), (i, i, 1, inner_h))
        overlay.fill((0, 0, 0, alpha), (width - i - 1, i, 1, inner_h))

    border = pygame.Rect(1, 1, width - 2, height - 2)
    pygame.draw.rect(overlay, (0, 255, 95, 42), border, 1, border_radius=max(8, min(width, height) // 18))
    pygame.draw.rect(overlay, (0, 0, 0, 96), border, 2, border_radius=max(8, min(width, height) // 18))
    surface.blit(overlay, (0, 0))


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
    draw_code_rain(surface, font, seed=2027, elapsed=elapsed, alpha_scale=0.82)

    for row in range(6):
        y = round((row + 0.55) * height / 6)
        jitter = round(math.sin(elapsed * 11.0 + row * 1.7) * 4)
        color = mix((0, 28, 12), (0, 96, 42), row / 5)
        pygame.draw.line(surface, color, (0, y + jitter), (width, y - jitter), 1)


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
    inner = heart_points(center, scale * 0.93)
    outline_width = max(3, round(scale * 0.32))

    shadow = [(x + round(scale * 0.75), y + round(scale * 0.95)) for x, y in points]
    glow = heart_points(center, scale * 1.10)
    pygame.draw.polygon(large, (0, 255, 95, 42), glow)
    pygame.draw.lines(large, (0, 255, 95, 75), True, glow, max(2, outline_width * 2))
    pygame.draw.polygon(large, (0, 0, 0, 130), shadow)
    pygame.draw.polygon(large, HEART_DARK, points)

    mask = pygame.Surface(large.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), inner)
    heart_material = pygame.Surface(large.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(heart_material, (0, 18, 8, 235), inner)
    heart_font = matrix_font(max(13, round(scale * 1.1)), bold=True)
    draw_code_rain(heart_material, heart_font, seed=4049, elapsed=elapsed * 1.35, alpha_scale=1.0, speed_boost=1.25)
    heart_material.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    large.blit(heart_material, (0, 0))

    pulse_radius = round(min(width, height) * render_scale * (0.36 + 0.05 * math.sin(elapsed * math.tau)))
    pygame.draw.circle(large, (0, 255, 95, 55), center, pulse_radius, max(2, render_scale))
    for offset in range(0, outline_width * 3, max(1, outline_width)):
        pygame.draw.lines(large, (0, 255, 95, max(28, 125 - offset * 16)), True, points, outline_width + offset)
    pygame.draw.lines(large, MATRIX_BRIGHT, True, heart_points(center, scale * 0.96), max(2, outline_width // 2))
    pygame.draw.lines(large, MATRIX_MID, True, inner, max(1, outline_width // 3))

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
    font = matrix_font(max(18, min(width, height) // 11), bold=True)

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
        draw_heart(screen, elapsed)
        draw_label(screen, font, elapsed)
        apply_glitch(screen, elapsed, seed=9091, intensity=0.42)
        draw_monitor_overlay(screen, elapsed, seed=5051)
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
