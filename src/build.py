#!/usr/bin/env python3
"""
Monta o index.html a partir do template, embutindo as fontes como data URI.

A CSP dos artefatos e a vontade de ter uma página 100% offline impedem carregar
fonte de CDN, então os .woff2 viram base64 dentro do próprio HTML.

Uso:
    python src/build.py
"""

import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.join(HERE, "fonts")
TEMPLATE = os.path.join(HERE, "template.html")
OUT = os.path.join(ROOT, "index.html")

SUBS = {
    "__QUICKSAND__": "quicksand-latin.woff2",
    "__LATO400__": "lato400-latin.woff2",
    "__LATO700__": "lato700-latin.woff2",
}


def main():
    html = open(TEMPLATE, encoding="utf-8").read()
    for placeholder, arquivo in SUBS.items():
        if placeholder not in html:
            raise SystemExit(f"placeholder ausente no template: {placeholder}")
        with open(os.path.join(FONTS, arquivo), "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        html = html.replace(placeholder, b64)
        print(f"  {arquivo:<26} {len(b64):>7,} chars base64")

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"\ngerado: {os.path.relpath(OUT, ROOT)}  ({len(html.encode()) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
