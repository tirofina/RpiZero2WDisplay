#!/usr/bin/env python3
"""Simple pygame touch/mouse coordinate test."""

from __future__ import annotations

import argparse
import os
import sys
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame


BG = (15, 18, 24)
GRID = (48, 55, 68)
TARGET = (80, 170, 255)
ACTIVE = (255, 64, 120)
TEXT = (235, 238, 245)


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
    return info.current_w or 240, info.current_h or 320


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test touch coordinates.")
    parser.add_argument("--size", type=parse_size, help="Override display size, for example 240x320.")
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds before auto-exit. 0 means wait.")
    parser.add_argument("--windowed", action="store_true", help="Open a window instead of fullscreen.")
    return parser


def draw_cross(surface: pygame.Surface, pos: tuple[int, int], color: tuple[int, int, int]) -> None:
    x, y = pos
    pygame.draw.circle(surface, color, pos, 10, 2)
    pygame.draw.line(surface, color, (x - 18, y), (x + 18, y), 2)
    pygame.draw.line(surface, color, (x, y - 18), (x, y + 18), 2)


def draw(surface: pygame.Surface, font: pygame.font.Font, pos: tuple[int, int] | None, pressed: bool) -> None:
    width, height = surface.get_size()
    surface.fill(BG)

    for x in range(0, width, 40):
        pygame.draw.line(surface, GRID, (x, 0), (x, height), 1)
    for y in range(0, height, 40):
        pygame.draw.line(surface, GRID, (0, y), (width, y), 1)

    margin = 18
    targets = (
        (margin, margin),
        (width - margin, margin),
        (margin, height - margin),
        (width - margin, height - margin),
        (width // 2, height // 2),
    )
    for target in targets:
        draw_cross(surface, target, TARGET)

    if pos:
        draw_cross(surface, pos, ACTIVE if pressed else TEXT)
        coord = f"x={pos[0]} y={pos[1]}"
    else:
        coord = "touch or click"

    lines = [
        "Touch test",
        coord,
        "Esc/q exits",
    ]
    y = 8
    for line in lines:
        rendered = font.render(line, True, TEXT)
        surface.blit(rendered, (8, y))
        y += rendered.get_height() + 4


def main() -> int:
    args = build_parser().parse_args()
    pygame.init()

    driver = pygame.display.get_driver()
    detected_size = desktop_size()
    width, height = args.size or detected_size
    flags = 0 if args.windowed or driver == "offscreen" else pygame.FULLSCREEN
    screen = pygame.display.set_mode((width, height), flags)
    pygame.display.set_caption("Touch Test")
    font = pygame.font.Font(None, 22)

    print(f"SDL driver: {driver}")
    print(f"Detected desktop size: {detected_size[0]}x{detected_size[1]}")
    print(f"Rendered size: {width}x{height}")

    pos: tuple[int, int] | None = None
    pressed = False
    start = time.monotonic()
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return 0
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                return 0
            if event.type == pygame.MOUSEBUTTONDOWN:
                pressed = True
                pos = event.pos
                print(f"down x={pos[0]} y={pos[1]}")
            if event.type == pygame.MOUSEBUTTONUP:
                pressed = False
                pos = event.pos
                print(f"up x={pos[0]} y={pos[1]}")
            if event.type == pygame.MOUSEMOTION:
                pos = event.pos
            if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
                pressed = event.type != pygame.FINGERUP
                pos = (round(event.x * width), round(event.y * height))
                print(f"finger x={pos[0]} y={pos[1]}")

        draw(screen, font, pos, pressed)
        pygame.display.flip()

        if args.duration > 0 and time.monotonic() - start >= args.duration:
            return 0

        clock.tick(30)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        pygame.quit()
        raise SystemExit(130)
