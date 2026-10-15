"""
Gera ui/app.ico (ícone do .exe) com o mesmo desenho do logotipo da interface (ui/index.html):
quadrado arredondado em degradê azul, pilar poligonal em U, pavimentos e o ponto âmbar.
Python puro (zlib + struct), sem dependências.  Uso:  python tools/make_icon.py
"""
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "ui" / "app.ico"
SIZES = (256, 64, 48, 32, 24, 16)
SS = 4                                            # supersampling por eixo


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


TOP, BOTTOM = hexrgb("#4B8DF8"), hexrgb("#1B3F8F")
AMBER = hexrgb("#F2B84B")


def inside_round_rect(x, y, r=14.0):
    cx = min(max(x, r), 64 - r)
    cy = min(max(y, r), 64 - r)
    return 0 <= x <= 64 and 0 <= y <= 64 and (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def in_rects(x, y, rects):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rects)


H = 3.25                                          # meia espessura do U (stroke 6.5)
U = [(20 - H, 14 - H, 20 + H, 51 + H), (44 - H, 14 - H, 44 + H, 51 + H), (20 - H, 51 - H, 44 + H, 51 + H)]
FLOORS = [(13, y - 1.2, 51, y + 1.2) for y in (23.5, 34.0, 44.5)]


def pixel(x, y):
    """Cor RGBA (floats 0-1) num ponto do desenho de 64x64."""
    if not inside_round_rect(x, y):
        return (0.0, 0.0, 0.0, 0.0)
    t = min(max((x + y) / 128, 0), 1)
    c = [(a + (b - a) * t) / 255 for a, b in zip(TOP, BOTTOM)]
    if in_rects(x, y, FLOORS):
        c = [v * 0.72 + 0.28 for v in c]
    if in_rects(x, y, U):
        c = [1.0, 1.0, 1.0]
    if (x - 44) ** 2 + (y - 14) ** 2 <= 4.2 ** 2:
        c = [v / 255 for v in AMBER]
    return (*c, 1.0)


def render(n):
    rows = []
    k = 64 / n
    for j in range(n):
        row = bytearray([0])                      # filtro PNG "None"
        for i in range(n):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sj in range(SS):
                for si in range(SS):
                    r, g, b, a = pixel((i + (si + 0.5) / SS) * k, (j + (sj + 0.5) / SS) * k)
                    acc[0] += r * a
                    acc[1] += g * a
                    acc[2] += b * a
                    acc[3] += a
            a = acc[3] / (SS * SS)
            if a > 0:
                rgb = [int(round(v / acc[3] * 255)) for v in acc[:3]]
            else:
                rgb = [0, 0, 0]
            row += bytes(rgb + [int(round(a * 255))])
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    images = [render(n) for n in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for n, png in zip(SIZES, images):
        entries += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        blobs += png
    OUT.write_bytes(header + entries + blobs)
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
