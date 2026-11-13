#!/usr/bin/env python3
"""Convertit une photo en art ASCII pour la carte de profil.

Usage : python3 ascii_art.py photo.jpg [--invert] [--gravity north]
Écrit ascii.txt (COLS x ROWS caractères). Nécessite ImageMagick (`magick`).
Le recadrage respecte la proportion réelle d'une cellule de texte du SVG,
pour que le visage ne soit ni écrasé ni étiré.
"""
import argparse
import subprocess
from pathlib import Path

COLS, ROWS = 51, 34
CELL_W, CELL_H = 6.9, 14.5  # largeur d'un caractère / hauteur de ligne (cf. profile.py)
# Du plus clair au plus dense. Pas de & < > pour garder un SVG lisible.
RAMPS = {
    "fine": " .'`^\",:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW%B@$",
    "classic": " .:-=+*#%@",
    "soft": " .,:;i1tfLCG08@",
}


def read_pgm(data: bytes):
    # En-tête P5 : magic, largeur, hauteur, maxval, puis les octets bruts.
    parts, idx = [], 0
    while len(parts) < 4:
        while data[idx:idx + 1].isspace():
            idx += 1
        start = idx
        while not data[idx:idx + 1].isspace():
            idx += 1
        parts.append(data[start:idx])
    width, height = int(parts[1]), int(parts[2])
    pixels = data[idx + 1: idx + 1 + width * height]
    return width, height, pixels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--out", default=str(Path(__file__).with_name("ascii.txt")))
    ap.add_argument("--invert", action="store_true", help="sujet clair sur fond sombre")
    ap.add_argument("--gravity", default="north", help="ancrage du recadrage (north, center…)")
    ap.add_argument("--white", type=int, default=88, help="%% de gris au-delà duquel le fond devient blanc")
    ap.add_argument("--gamma", type=float, default=1.3, help=">1 éclaircit les tons moyens")
    ap.add_argument("--ramp", choices=RAMPS, default="classic")
    ap.add_argument("--clahe", action=argparse.BooleanOptionalAction, default=True, help="contraste local (fait ressortir les traits)")
    args = ap.parse_args()

    aspect = (COLS * CELL_W) / (ROWS * CELL_H)  # largeur / hauteur de la zone ASCII
    crop = f"{aspect * 1000:.0f}:1000"
    cmd = [
        "magick", args.photo, "-auto-orient", "-colorspace", "Gray",
        "-gravity", args.gravity, "-crop", crop, "+repage",  # recadrage à la bonne proportion
        *(["-clahe", "12x12%+128+2.5"] if args.clahe else []),
        "-resize", f"{COLS}x{ROWS}!", "-level", f"0%,{args.white}%,{args.gamma}",
        "-depth", "8", "pgm:-",
    ]
    width, height, pixels = read_pgm(subprocess.run(cmd, check=True, capture_output=True).stdout)

    ramp = RAMPS[args.ramp]
    lines = []
    for y in range(height):
        row = pixels[y * width:(y + 1) * width]
        chars = []
        for v in row:
            level = v / 255 if args.invert else 1 - v / 255  # sombre = dense sur fond clair
            chars.append(" " if level < 0.04 else ramp[min(int(level * len(ramp)), len(ramp) - 1)])
        lines.append("".join(chars).rstrip())
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{args.out}: {width}x{height}")


if __name__ == "__main__":
    main()
