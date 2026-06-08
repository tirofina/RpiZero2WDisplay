#!/usr/bin/env python3
"""Optimized Matrix-glitch animated pygame display demo for the Waveshare LCD."""

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
MATRIX_WHITE = (222, 255, 226)
HEART_DARK = (0, 74, 34)
GLITCH_CYAN = (68, 255, 220)
GLITCH_PURPLE = (98, 18, 92)
WHITE = MATRIX_WHITE
MATRIX_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ#$%&*@+-/"
PRECOMPUTED_FRAMES = 8


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


def heart_points(center: tuple[int, int], scale: float, steps: int = 128) -> list[tuple[int, int]]:
    cx, cy = center
    points: list[tuple[int, int]] = []
    for step in range(steps):
        t = (math.tau * step) / steps
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        points.append((round(cx + x * scale), round(cy - y * scale)))
    return points


def build_glyph_cache(font: pygame.font.Font, alpha_scale: float) -> list[list[pygame.Surface]]:
    palette = (
        (MATRIX_DIM, 78),
        (MATRIX_MID, 112),
        (MATRIX_GREEN, 150),
        (MATRIX_BRIGHT, 190),
        (MATRIX_WHITE, 220),
    )
    cache: list[list[pygame.Surface]] = []
    for color, alpha in palette:
        row: list[pygame.Surface] = []
        for char in MATRIX_CHARS:
            rendered = font.render(char, True, color).convert_alpha()
            rendered.set_alpha(max(0, min(255, round(alpha * alpha_scale))))
            row.append(rendered)
        cache.append(row)
    return cache


class GlyphField:
    def __init__(
        self,
        size: tuple[int, int],
        font: pygame.font.Font,
        seed: int,
        density: float,
        jitter: int = 0,
    ) -> None:
        width, height = size
        cell_h = max(11, font.get_height() + 1)
        cell_w = max(9, font.size("W")[0] + 4)
        rng = random.Random(seed)
        self.cells: list[tuple[int, int, int, int, int]] = []

        for row, y in enumerate(range(0, height, cell_h)):
            for col, x in enumerate(range(0, width, cell_w)):
                if rng.random() > density:
                    continue
                px = x + (rng.randint(-jitter, jitter) if jitter else 0)
                py = y + (rng.randint(-jitter, jitter) if jitter else 0)
                char_index = rng.randrange(len(MATRIX_CHARS))
                step = rng.randint(1, 4)
                palette = rng.choices((0, 1, 2, 3, 4), weights=(5, 6, 6, 2, 1), k=1)[0]
                self.cells.append((px, py, char_index, step, palette))

    def draw(self, surface: pygame.Surface, cache: list[list[pygame.Surface]], tick: int) -> None:
        char_count = len(MATRIX_CHARS)
        for x, y, char_index, step, palette in self.cells:
            surface.blit(cache[palette][(char_index + tick * step) % char_count], (x, y))


class GlitchArtifacts:
    def __init__(self, size: tuple[int, int], seed: int, frame_count: int, density: int) -> None:
        width, height = size
        self.frames: list[list[tuple[tuple[int, int, int, int], tuple[int, int, int, int]]]] = []
        colors = (MATRIX_GREEN, MATRIX_MID, GLITCH_CYAN)
        for frame in range(frame_count):
            rng = random.Random(seed + frame * 101)
            rects = []
            for _ in range(density):
                y = rng.randrange(height)
                h = rng.randint(1, max(2, height // 52))
                x = rng.randrange(width)
                w = rng.randint(max(8, width // 20), max(9, width // 2))
                color = rng.choice(colors)
                alpha = rng.randint(14, 46)
                rects.append(((x, y, min(w, width - x), h), (*color, alpha)))
            self.frames.append(rects)

    def draw(self, surface: pygame.Surface, frame_index: int) -> None:
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for rect, color in self.frames[frame_index % len(self.frames)]:
            layer.fill(color, rect)
        surface.blit(layer, (0, 0))


class GlitchEffect:
    def __init__(self, size: tuple[int, int], seed: int, frame_count: int, intensity: float) -> None:
        width, height = size
        self.frames: list[list[tuple[int, int, int, int]]] = []
        self.overlays: list[pygame.Surface] = []
        band_count = max(4, round(8 * intensity))
        max_shift = max(2, round(width * 0.03 * intensity))

        for frame in range(frame_count):
            rng = random.Random(seed + frame * 127)
            bands: list[tuple[int, int, int, int]] = []
            overlay = pygame.Surface(size, pygame.SRCALPHA)
            for _ in range(band_count):
                band_h = rng.randint(1, max(3, height // 34))
                y = rng.randint(0, max(0, height - band_h))
                shift = rng.choice((-1, 1)) * rng.randint(1, max_shift)
                bands.append((y, band_h, shift, rng.randint(0, 1)))
                color = GLITCH_CYAN if rng.random() < 0.58 else GLITCH_PURPLE
                alpha = rng.randint(14, 34)
                overlay.fill((*color, alpha), (0, y, width, band_h))
            self.frames.append(bands)
            self.overlays.append(overlay)

    def apply(self, surface: pygame.Surface, frame_index: int) -> None:
        frame = frame_index % len(self.frames)
        for y, band_h, shift, _ in self.frames[frame]:
            strip = surface.subsurface((0, y, surface.get_width(), band_h)).copy()
            surface.blit(strip, (shift, y))
        surface.blit(self.overlays[frame], (0, 0))


def build_background_frames(
    size: tuple[int, int],
    field: GlyphField,
    cache: list[list[pygame.Surface]],
    artifacts: GlitchArtifacts,
) -> list[pygame.Surface]:
    frames: list[pygame.Surface] = []
    for tick in range(PRECOMPUTED_FRAMES):
        frame = pygame.Surface(size).convert()
        frame.fill(BLACK)
        field.draw(frame, cache, tick)
        artifacts.draw(frame, tick)
        frames.append(frame)
    return frames


def build_heart_frames(
    size: tuple[int, int],
    field: GlyphField,
    cache: list[list[pygame.Surface]],
) -> list[pygame.Surface]:
    width, height = size
    frames: list[pygame.Surface] = []

    for tick in range(PRECOMPUTED_FRAMES):
        layer = pygame.Surface(size, pygame.SRCALPHA)
        beat = 1.0 + 0.058 * math.sin((tick / PRECOMPUTED_FRAMES) * math.tau)
        lift = round(math.sin((tick / PRECOMPUTED_FRAMES) * math.tau) * height * 0.010)
        center = (width // 2, height // 2 + round(height * 0.035) + lift)
        scale = min(width, height) / 40 * beat
        points = heart_points(center, scale)
        inner = heart_points(center, scale * 0.93)
        outline_width = max(2, round(scale * 0.34))

        shadow = [(x + round(scale * 0.75), y + round(scale * 0.95)) for x, y in points]
        glow = heart_points(center, scale * 1.10)
        pygame.draw.polygon(layer, (0, 255, 95, 42), glow)
        pygame.draw.lines(layer, (0, 255, 95, 72), True, glow, max(2, outline_width * 2))
        pygame.draw.polygon(layer, (0, 0, 0, 130), shadow)
        pygame.draw.polygon(layer, HEART_DARK, points)

        material = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.polygon(material, (0, 18, 8, 235), inner)
        field.draw(material, cache, tick)
        mask = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), inner)
        material.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        layer.blit(material, (0, 0))

        for offset in range(0, outline_width * 3, max(1, outline_width)):
            pygame.draw.lines(layer, (0, 255, 95, max(26, 120 - offset * 16)), True, points, outline_width + offset)
        pygame.draw.lines(layer, MATRIX_BRIGHT, True, heart_points(center, scale * 0.96), max(2, outline_width // 2))
        pygame.draw.lines(layer, MATRIX_MID, True, inner, max(1, outline_width // 3))
        frames.append(layer)

    return frames


def draw_label(surface: pygame.Surface, font: pygame.font.Font, elapsed: float) -> None:
    width, _ = surface.get_size()
    text = f"{elapsed:04.1f}s"
    rendered = font.render(text, True, WHITE)
    pad = 5
    bg = pygame.Rect(width - rendered.get_width() - pad * 2 - 4, 3, rendered.get_width() + pad * 2, rendered.get_height() + pad)
    pygame.draw.rect(surface, (0, 0, 0), bg)
    surface.blit(rendered, (bg.x + pad, bg.y + pad // 2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show an optimized animated heart demo on the current display.")
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds before auto-exit. 0 means wait until closed or Esc.")
    parser.add_argument("--save-frame", default="", help="Optional PNG path to save the final rendered frame.")
    parser.add_argument("--size", type=parse_size, help="Override detected size, for example 320x240.")
    parser.add_argument("--fps", type=int, default=15, help="Target animation frame rate.")
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

    glyph_font = matrix_font(max(14, min(width, height) // 13), bold=True)
    heart_font = matrix_font(max(10, min(width, height) // 22), bold=True)
    label_font = matrix_font(max(15, min(width, height) // 13), bold=True)

    bg_cache = build_glyph_cache(glyph_font, alpha_scale=0.68)
    heart_cache = build_glyph_cache(heart_font, alpha_scale=0.96)
    background_field = GlyphField((width, height), glyph_font, seed=2027, density=0.18, jitter=1)
    heart_field = GlyphField((width, height), heart_font, seed=4049, density=0.48, jitter=0)
    artifacts = GlitchArtifacts((width, height), seed=3037, frame_count=PRECOMPUTED_FRAMES, density=16)
    glitch = GlitchEffect((width, height), seed=9091, frame_count=PRECOMPUTED_FRAMES, intensity=0.54)
    background_frames = build_background_frames((width, height), background_field, bg_cache, artifacts)
    heart_frames = build_heart_frames((width, height), heart_field, heart_cache)

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
        frame_index = int(elapsed * min(target_fps, PRECOMPUTED_FRAMES)) % PRECOMPUTED_FRAMES
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

        screen.blit(background_frames[frame_index], (0, 0))
        screen.blit(heart_frames[frame_index], (0, 0))
        draw_label(screen, label_font, elapsed)
        glitch.apply(screen, frame_index)
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
