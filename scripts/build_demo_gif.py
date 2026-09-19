"""Build docs/media/demo-hero.gif from the frames apps/web/e2e/capture-media.mjs recorded.

Usage: python scripts/build_demo_gif.py <capture-dir>   (needs Pillow: pip install pillow)
Each frame is shown for as long as it actually lasted in the recording, capped at 0.9 s, so waiting on
the network isn't sped up or slowed down beyond that cap. The last frame holds for 3 s.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

MEDIA = Path(__file__).resolve().parents[1] / "docs" / "media"


def main(capture: Path) -> None:
    stamps = json.loads((capture / "frames" / "stamps.json").read_text())
    files = sorted((capture / "frames").glob("f*.png"))
    frames, durations = [], []
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGB").resize((960, 600), Image.LANCZOS)
        frames.append(
            im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        )
        gap = stamps[i + 1] - stamps[i] if i + 1 < len(stamps) else 3000
        durations.append(max(80, min(gap, 900)))
    durations[-1] = 3000
    frames[0].save(
        MEDIA / "demo-hero.gif",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )
    print(f"{len(frames)} frames, {sum(durations) / 1000:.1f} s")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
