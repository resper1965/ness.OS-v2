#!/usr/bin/env python3
"""Gera os ícones PNG do PWA seguindo o ness. design system, sem dependência externa.

Desenha o "n." geometricamente (fundo chapado, raio 0, ponto sempre em BlueDot),
com supersampling para antialias, e escreve PNG de 8 bits com zlib. Repetível:
rodar de novo produz o mesmo byte.

Uso: python3 app/frontend/scripts/gen-pwa-icons.py
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "public" / "icons"

BG = (0x0B, 0x13, 0x26)    # surface-page (tema escuro)
INK = (0xF1, 0xF5, 0xF9)   # text-primary
DOT = (0x00, 0xAD, 0xE8)   # BlueDot: o ponto da marca é sempre esta cor

SS = 4                     # supersampling: 16 amostras por pixel final
REF_W = 0.895               # largura do desenho de referência (altura = 1)


def shapes(coverage: float):
    """Formas do "n." normalizadas; devolve (lista, escala, origem)."""
    t = 0.150                          # espessura do traço
    ro = 0.300                         # raio externo do ombro do "n"
    cx, cy = 0.300, 0.300              # centro do ombro: topo do arco em y=0
    y_base = 1.000                     # linha de base
    r_dot = 0.120                      # o ponto senta na base, como um ponto final
    x_dot = cx + ro + 0.055 + r_dot

    out = [
        ("rect", (cx - ro, cy, t, y_base - cy), INK),           # haste esquerda
        ("rect", (cx + ro - t, cy, t, y_base - cy), INK),       # haste direita
        ("arc", (cx, cy, ro - t, ro), INK),                     # ombro do "n"
        ("circle", (x_dot, y_base - r_dot, r_dot), DOT),        # ponto da marca
    ]
    sc = coverage / REF_W
    ox = (1 - REF_W * sc) / 2
    oy = (1 - sc) / 2
    return out, sc, ox, oy


def render(size: int, coverage: float) -> bytes:
    shapes_, sc, ox, oy = shapes(coverage)
    n = size * SS
    inv = 1.0 / n
    rows = []

    for py in range(n):
        y = (py + 0.5) * inv
        row = bytearray()
        for px in range(n):
            x = (px + 0.5) * inv
            color = BG
            for kind, p, c in shapes_:
                if kind == "rect":
                    rx, ry, rw, rh = p
                    if (ox + rx * sc) <= x <= (ox + rx * sc) + rw * sc and \
                       (oy + ry * sc) <= y <= (oy + ry * sc) + rh * sc:
                        color = c
                        break
                elif kind == "arc":
                    acx, acy, ri, aro = p
                    gx = (x - (ox + acx * sc)) / sc
                    gy = (y - (oy + acy * sc)) / sc
                    if gy <= 0 and ri <= math.hypot(gx, gy) <= aro:
                        color = c
                        break
                else:  # circle
                    ccx, ccy, cr = p
                    gx = (x - (ox + ccx * sc)) / sc
                    gy = (y - (oy + ccy * sc)) / sc
                    if math.hypot(gx, gy) <= cr:
                        color = c
                        break
            row += bytes(color)
        rows.append(row)

    step = SS
    w = n // step
    body = bytearray()
    for y in range(w):
        body.append(0)  # filtro None
        base = y * step
        for x in range(w):
            r = g = b = 0
            off = x * step * 3
            for dy in range(step):
                src = rows[base + dy]
                for dx in range(step):
                    i = off + dx * 3
                    r += src[i]
                    g += src[i + 1]
                    b += src[i + 2]
            k = step * step
            body += bytes((r // k, g // k, b // k))
    return png(size, body)


def png(size: int, data: bytes) -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(data), 9)) + chunk(b"IEND", b""))


VARIANTS = [
    ("icon-192.png", 192, 0.74),
    ("icon-512.png", 512, 0.74),
    # maskable: recorte do sistema come 20% de cada lado, então o desenho encolhe
    ("icon-maskable-512.png", 512, 0.48),
]

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size, cov in VARIANTS:
        (OUT / name).write_bytes(render(size, cov))
        print("ok", name)
