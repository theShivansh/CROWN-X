"""Build demo/documents/workspace-a/project-brief-v1.pdf from demo/sources/project-brief-v1.md.

A text PDF (not an image), so ingestion can extract it page by page. The rupee sign needs a Unicode
TrueType font; pass one with --font if the default isn't on this machine. Run from the repo root:

    cd services/api && uv run python ../../demo/build_pdf.py
"""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "sources" / "project-brief-v1.md"
TARGET = ROOT / "documents" / "workspace-a" / "project-brief-v1.pdf"
DEFAULT_FONTS = [
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]


def build(source: Path, target: Path, font: Path) -> None:
    pdf = FPDF(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.add_font("body", fname=str(font))
    # Fixed metadata so a rebuild from the same source gives the same text content.
    pdf.set_creation_date(datetime(2026, 8, 31, tzinfo=UTC))
    pdf.set_title("FestPass project brief v1")
    pdf.add_page()
    for line in source.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            size = {1: 16, 2: 13, 3: 12}[len(heading.group(1))]
            pdf.set_font("body", size=size)
            pdf.ln(3)
            pdf.multi_cell(0, 8, heading.group(2), new_x="LMARGIN", new_y="NEXT")
            continue
        pdf.set_font("body", size=11)
        if not line.strip():
            pdf.ln(3)
            continue
        text = f"• {line[2:]}" if line.startswith("- ") else line
        pdf.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
    target.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(target))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--font", type=Path, help="a Unicode .ttf with the rupee sign")
    args = parser.parse_args()
    font = args.font or next((f for f in DEFAULT_FONTS if f.exists()), None)
    if font is None:
        raise SystemExit("No Unicode font found; pass --font /path/to/font.ttf")
    build(SOURCE, TARGET, font)
    print(f"wrote {TARGET.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
