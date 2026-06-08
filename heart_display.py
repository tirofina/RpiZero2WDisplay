#!/usr/bin/env python3
"""Display a centered Matrix-style green heart with pygame.

The script uses the current SDL/pygame desktop size. On a real X11/Wayland/KMS
display it opens fullscreen by default. In headless/offscreen sessions it still
renders the same frame and can save it for verification.
"""

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
    return info.current_w or 1024, info.current_h or 768


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


def draw_glyph_field(
    surface: pygame.Surface,
    font: pygame.font.Font,
    seed: int,
    elapsed: float = 0.0,
    alpha_scale: float = 1.0,
    density: float = 0.36,
) -> None:
    width, height = surface.get_size()
    cell_h = max(10, font.get_height() + 1)
    cell_w = max(8, font.size("W")[0] + 3)
    tick = int(elapsed * 18)

    for row, y in enumerate(range(0, height, cell_h)):
        for col, x in enumerate(range(0, width, cell_w)):
            rng = random.Random(seed + row * 104729 + col * 7919)
            if rng.random() > density:
                continue
            idx = (rng.randint(0, 9999) + tick * (1 + (row + col) % 4)) % len(MATRIX_CHARS)
            char = MATRIX_CHARS[idx]
            strength = rng.uniform(0.18, 0.88)
            color = mix(MATRIX_DIM, MATRIX_GREEN, strength)
            alpha = round(rng.randint(46, 185) * alpha_scale)
            if rng.random() < 0.08:
                color = MATRIX_WHITE
                alpha = round(rng.randint(130, 230) * alpha_scale)
            blit_text(surface, font, char, (x, y), color, alpha)


def draw_glitch_artifacts(surface: pygame.Surface, elapsed: float, seed: int, density: int) -> None:
    width, height = surface.get_size()
    rng = random.Random(seed + int(elapsed * 16))
    layer = pygame.Surface((width, height), pygame.SRCALPHA)

    for _ in range(density):
        y = rng.randrange(height)
        h = rng.randint(1, max(2, height // 48))
        x = rng.randrange(width)
        w = rng.randint(max(8, width // 20), max(9, width // 2))
        color = rng.choice((MATRIX_GREEN, MATRIX_MID, GLITCH_CYAN))
        alpha = rng.randint(18, 58)
        layer.fill((*color, alpha), (x, y, min(w, width - x), h))

    surface.blit(layer, (0, 0))


def apply_glitch(surface: pygame.Surface, elapsed: float, seed: int, intensity: float) -> None:
    width, height = surface.get_size()
    source = surface.copy()
    rng = random.Random(seed + int(elapsed * 18))
    band_count = max(4, round(8 * intensity))
    max_shift = max(2, round(width * 0.034 * intensity))

    for _ in range(band_count):
        band_h = rng.randint(1, max(3, height // 30))
        y = rng.randint(0, max(0, height - band_h))
        shift = rng.choice((-1, 1)) * rng.randint(1, max_shift)
        src = pygame.Rect(0, y, width, band_h)
        surface.blit(source, (shift, y), src)

        tint = pygame.Surface((width, band_h), pygame.SRCALPHA)
        if rng.random() < 0.55:
            tint.fill((*GLITCH_CYAN, rng.randint(18, 42)))
        else:
            tint.fill((*GLITCH_PURPLE, rng.randint(14, 34)))
        surface.blit(tint, (0, y))

        if rng.random() < 0.45:
            line_y = y + rng.randrange(band_h)
            line = pygame.Surface((width, 1), pygame.SRCALPHA)
            line.fill((*MATRIX_WHITE, rng.randint(70, 138)))
            surface.blit(line, (0, line_y))


def draw_matrix_background(surface: pygame.Surface) -> None:
    width, height = surface.get_size()
    surface.fill(BLACK)

    font = matrix_font(max(15, min(width, height) // 11), bold=True)
    draw_glyph_field(surface, font, seed=2027, alpha_scale=0.72, density=0.24)
    draw_glitch_artifacts(surface, elapsed=0.0, seed=3037, density=18)


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
    draw_matrix_background(surface)

    render_scale = 3
    large = pygame.Surface((width * render_scale, height * render_scale), pygame.SRCALPHA)
    center = (large.get_width() // 2, large.get_height() // 2 + round(height * 0.035))
    scale = min(width, height) * render_scale / 38
    points = heart_points(center, scale)
    inner = heart_points(center, scale * 0.93)
    outline_width = max(3, round(scale * 0.36))

    glow_points = heart_points(center, scale * 1.08)
    pygame.draw.polygon(large, (0, 255, 95, 34), glow_points)
    pygame.draw.lines(large, (0, 255, 95, 70), True, glow_points, max(2, outline_width * 2))
    shadow_points = [(x + round(scale * 0.65), y + round(scale * 0.85)) for x, y in points]
    pygame.draw.polygon(large, (0, 0, 0, 130), shadow_points)
    pygame.draw.polygon(large, HEART_DARK, points)
    mask = pygame.Surface(large.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), inner)

    heart_material = pygame.Surface(large.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(heart_material, (0, 18, 8, 235), inner)
    heart_font = matrix_font(max(13, round(scale * 1.15)), bold=True)
    draw_glyph_field(heart_material, heart_font, seed=4049, alpha_scale=1.0, density=0.54)
    heart_material.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    large.blit(heart_material, (0, 0))

    for offset in range(0, outline_width * 3, max(1, outline_width)):
        pygame.draw.lines(large, (0, 255, 95, max(28, 120 - offset * 16)), True, points, outline_width + offset)
    pygame.draw.lines(large, MATRIX_BRIGHT, True, heart_points(center, scale * 0.96), max(2, outline_width // 2))
    pygame.draw.lines(large, MATRIX_MID, True, inner, max(1, outline_width // 3))

    smooth = pygame.transform.smoothscale(large, (width, height))
    surface.blit(smooth, (0, 0))
    apply_glitch(surface, elapsed=0.0, seed=9091, intensity=0.64)


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
    pygame.font.init()
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
