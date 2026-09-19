"""Draw the README's SVG diagrams and charts into docs/media/.

Every number below is copied from docs/BENCHMARKS.md (the section is named next to it), so a chart
can be checked against its table. Run: python scripts/readme_media.py
Colours are the DESIGN.md tokens. Each SVG draws its own dark card, so it reads the same on GitHub's
light and dark themes.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

MEDIA = Path(__file__).resolve().parents[1] / "docs" / "media"

BG = "#0a0a0b"
SURFACE = "#111113"
SURFACE_2 = "#18181b"
BORDER = "#26262b"
BORDER_STRONG = "#34343a"
TEXT = "#ededef"
MUTED = "#a1a1aa"
SUBTLE = "#8b8b93"
ACCENT = "#6e9bff"
GROUNDED = "#3dd68c"
CONFLICT = "#f5a524"
FONT = "Geist, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Consolas, monospace"


def svg(w: int, h: int, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(title)}">\n<title>{escape(title)}</title>\n'
        "<defs><marker id='arrow' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' "
        f"orient='auto-start-reverse'><path d='M0,0 L10,5 L0,10 z' fill='{SUBTLE}'/></marker>"
        "<marker id='arrowA' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' "
        f"orient='auto-start-reverse'><path d='M0,0 L10,5 L0,10 z' fill='{ACCENT}'/></marker></defs>\n"
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{BG}" stroke="{BORDER}"/>\n'
        f"{body}\n</svg>\n"
    )


def text(x, y, s, size=14, fill=TEXT, weight=400, anchor="start", mono=False, opacity=1.0) -> str:
    fam = MONO if mono else FONT
    return (
        f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" opacity="{opacity}">{escape(str(s))}</text>'
    )


def box(
    x, y, w, h, title, lines=(), stroke=BORDER_STRONG, tag=None, tag_fill=ACCENT, fill=SURFACE
) -> str:
    out = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}"/>'
    ]
    ty = y + 26
    if tag:
        out.append(text(x + 14, ty, tag.upper(), 10, tag_fill, 600, mono=True))
        ty += 20
    out.append(text(x + 14, ty, title, 15, TEXT, 600))
    for i, line in enumerate(lines):
        out.append(text(x + 14, ty + 20 + i * 18, line, 12, MUTED))
    return "\n".join(out)


def line(
    x1, y1, x2, y2, color=SUBTLE, dashed=False, label=None, lx=None, ly=None, marker="arrow"
) -> str:
    dash = ' stroke-dasharray="5 5"' if dashed else ""
    out = (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5"{dash} '
        f'marker-end="url(#{marker})"/>'
    )
    if label:
        out += text(
            lx if lx is not None else (x1 + x2) / 2,
            ly if ly is not None else (y1 + y2) / 2 - 6,
            label,
            11,
            SUBTLE,
            anchor="middle",
            mono=True,
        )
    return out


# ---------------------------------------------------------------- architecture overview
def architecture() -> str:
    b = [
        text(32, 44, "CROWN-X on AWS · ap-south-1 (Mumbai) · as deployed", 20, TEXT, 600),
        text(
            32,
            68,
            "One AWS SAM template. Two Lambdas with one IAM role each. Every query is filtered to its workspace.",
            13,
            MUTED,
        ),
        box(
            32,
            250,
            220,
            118,
            "Browser",
            ["Next.js static export", "served by Amplify Hosting", "redeploys on git push"],
            tag="Amplify",
        ),
        box(
            318,
            150,
            220,
            100,
            "API Gateway (HTTP)",
            ["CORS for the app origin", "per-route throttles"],
            tag="edge",
        ),
        box(
            318,
            400,
            220,
            100,
            "Amazon S3",
            ["raw documents (pre-signed POST)", "pinned ONNX model files"],
            tag="storage",
        ),
        box(
            604,
            130,
            240,
            140,
            "Lambda · API",
            [
                "Python 3.12, arm64",
                "ONNX bge-small inside",
                "quota check before any work",
                "citation validator",
            ],
            tag="compute",
            stroke=ACCENT,
        ),
        box(
            604,
            390,
            240,
            130,
            "Lambda · ingestion",
            [
                "parse MD / TXT / PDF",
                "chunk with offsets, embed (ONNX)",
                "rule-based claim extraction",
            ],
            tag="compute",
            stroke=ACCENT,
        ),
        box(
            910,
            96,
            258,
            88,
            "OpenSearch Service",
            ["BM25 + k-NN (HNSW), one index"],
            tag="retrieval",
        ),
        box(
            910,
            204,
            258,
            88,
            "DynamoDB (on demand)",
            ["docs, claims, audit, events, quotas"],
            tag="metadata",
        ),
        box(
            910,
            312,
            258,
            88,
            "Groq · gpt-oss-120b",
            ["answers; key in SSM Parameter Store"],
            tag="model, outside AWS",
            tag_fill=CONFLICT,
        ),
        box(
            910,
            420,
            258,
            100,
            "CloudWatch Logs",
            ["request_id on every line", "per-stage latency, Logs Insights"],
            tag="observability",
        ),
        line(252, 290, 316, 210, ACCENT, label="HTTPS", lx=268, ly=238, marker="arrowA"),
        line(252, 330, 316, 440, ACCENT, label="upload, ≤5 MB", lx=258, ly=408, marker="arrowA"),
        line(538, 200, 602, 200),
        line(724, 270, 724, 388, label="async invoke", lx=770, ly=334),
        line(538, 450, 602, 450, label="read", lx=570, ly=442),
        line(844, 160, 908, 140),
        line(844, 200, 908, 248),
        line(844, 240, 908, 352, dashed=True),
        line(844, 430, 908, 160),
        line(844, 450, 908, 262),
        line(844, 490, 908, 470, dashed=True),
        text(
            32,
            592,
            "Solid: data path. Dashed: model call and logs. Bedrock sits behind the same provider interface as one config switch (ADR-017).",
            12,
            SUBTLE,
        ),
    ]
    return svg(1200, 620, "\n".join(b), "CROWN-X architecture on AWS")


# ---------------------------------------------------------------- retrieval pipeline
def pipeline() -> str:
    b = [
        text(32, 44, "The evidence pipeline", 20, TEXT, 600),
        text(
            32,
            68,
            "Code decides what counts as evidence and what conflicts. The model only writes sentences over stored passages.",
            13,
            MUTED,
        ),
    ]
    ing = [
        ("Upload", "pre-signed POST"),
        ("Parse", "MD · TXT · PDF"),
        ("Chunk", "char offsets"),
        ("Embed", "ONNX bge-small int8"),
        ("Index", "BM25 + k-NN"),
        ("Claims", "rules, typed, normalized"),
    ]
    b.append(text(32, 112, "INGEST", 11, ACCENT, 600, mono=True))
    x = 32
    for i, (t, s) in enumerate(ing):
        b.append(box(x, 124, 172, 70, t, [s]))
        if i < len(ing) - 1:
            b.append(line(x + 172, 159, x + 190, 159))
        x += 190
    q = [
        ("Quota", "DynamoDB ADD, before work"),
        ("Embed", "question, ONNX"),
        ("BM25 ‖ k-NN", "workspace filter inside"),
        ("RRF fusion", "top 8 stored"),
        ("Conflict compare", "deterministic predicate"),
    ]
    b.append(text(32, 240, "RETRIEVE  ·  POST /query", 11, ACCENT, 600, mono=True))
    x = 32
    for i, (t, s) in enumerate(q):
        b.append(
            box(
                x,
                252,
                206,
                70,
                t,
                [s],
                stroke=CONFLICT if t == "Conflict compare" else BORDER_STRONG,
            )
        )
        if i < len(q) - 1:
            b.append(line(x + 206, 287, x + 226, 287))
        x += 226
    b.append(
        box(
            484,
            334,
            206,
            56,
            "Cross-encoder rerank",
            ["built + measured, off (ADR-017)"],
            fill=SURFACE_2,
        )
    )
    b.append(
        f'<rect x="484" y="334" width="206" height="56" rx="10" fill="none" stroke="{SUBTLE}" stroke-dasharray="4 4"/>'
    )
    a = [
        ("Answer", "gpt-oss-120b over an escaped data block"),
        ("Citation validator", "drops uncited sentences"),
        ("Status by code", "grounded · partial · conflict · insufficient"),
    ]
    b.append(
        text(
            32,
            436,
            "ANSWER  ·  POST /answer  (one model call; none without evidence)",
            11,
            ACCENT,
            600,
            mono=True,
        )
    )
    x = 32
    for i, (t, s) in enumerate(a):
        b.append(box(x, 448, 360, 70, t, [s], stroke=GROUNDED if i == 2 else BORDER_STRONG))
        if i < len(a) - 1:
            b.append(line(x + 360, 483, x + 378, 483))
        x += 378
    b.append(
        text(
            32,
            560,
            "Measured on the deployed stack: query 39 / 65 ms and answer call 731 / 1153 ms (p50 / p95, inside Lambda).",
            12,
            SUBTLE,
        )
    )
    return svg(1180, 584, "\n".join(b), "CROWN-X evidence pipeline")


# ---------------------------------------------------------------- grouped bar chart helper
def bars(title, subtitle, groups, series, colors, vmax, fmt, footnote, w=1100, h=490):
    left, top, right, bottom = 70, 120, 30, 80
    pw, ph = w - left - right, h - top - bottom
    b = [text(32, 44, title, 20, TEXT, 600), text(32, 68, subtitle, 13, MUTED)]
    for k in range(6):
        v = vmax * k / 5
        y = top + ph - ph * k / 5
        b.append(f'<line x1="{left}" y1="{y}" x2="{w - right}" y2="{y}" stroke="{BORDER}"/>')
        b.append(text(left - 10, y + 4, f"{v:.1f}", 11, SUBTLE, anchor="end", mono=True))
    gw = pw / len(groups)
    bw = min(48, (gw - 30) / len(series))
    for gi, (gname, vals) in enumerate(groups):
        gx = left + gi * gw + (gw - bw * len(series)) / 2
        for si, v in enumerate(vals):
            if v is None:
                continue
            bh = ph * v / vmax
            x = gx + si * bw
            b.append(
                f'<rect x="{x + 3}" y="{top + ph - bh}" width="{bw - 6}" height="{bh}" rx="4" fill="{colors[si]}"/>'
            )
            b.append(
                text(x + bw / 2, top + ph - bh - 6, fmt(v), 11, TEXT, 500, "middle", mono=True)
            )
        for li, part in enumerate(gname.split("\n")):
            b.append(
                text(
                    left + gi * gw + gw / 2,
                    top + ph + 22 + li * 16,
                    part,
                    12,
                    MUTED if li else TEXT,
                    500 if not li else 400,
                    "middle",
                )
            )
    lx = w - right
    for si in reversed(range(len(series))):
        lx -= len(series[si]) * 7 + 34
        b.append(f'<rect x="{lx}" y="80" width="12" height="12" rx="3" fill="{colors[si]}"/>')
        b.append(text(lx + 18, 90, series[si], 12, MUTED))
    b.append(text(32, h - 18, footnote, 11, SUBTLE))
    return svg(w, h, "\n".join(b), title)


RETRIEVAL_V2 = [  # BENCHMARKS "Retrieval benchmark v2": offline bge-small rows, and the freeze live run
    ("BM25", "offline", 0.700, 0.783, 0.632),
    ("dense", "bge-small, offline", 0.867, 0.883, 0.839),
    ("hybrid RRF", "production, offline", 0.883, 0.967, 0.694),
    ("hybrid + rerank", "off in prod, offline", 0.950, 0.967, 0.864),
    ("hybrid RRF", "deployed, live", 0.917, 0.950, 0.747),
]


def recall_chart() -> str:
    return bars(
        "Retrieval recall · benchmark v2 (60 passages, 30 queries)",
        "Recall@8 is what limits answers: the model reads all 8 passages. Production hybrid has the best recall@8.",
        [(f"{a}\n{b}", [r5, r8]) for a, b, r5, r8, _ in RETRIEVAL_V2],
        ["Recall@5", "Recall@8"],
        [ACCENT, GROUNDED],
        1.0,
        lambda v: f"{v:.2f}".rstrip("0").rstrip(".") if v in (0, 1) else f"{v:.3f}",
        "Source: docs/BENCHMARKS.md, 'Retrieval benchmark v2' and 'Final evaluation at the freeze'. Our own corpus and labels.",
    )


def mrr_chart() -> str:
    return bars(
        "Ranking quality · MRR on benchmark v2",
        "Equal-weight RRF lowers MRR; the reranker restores it but misses the +150 ms p95 latency gate, so it stays off.",
        [(f"{a}\n{b}", [m]) for a, b, _, _, m in RETRIEVAL_V2],
        ["MRR"],
        [CONFLICT],
        1.0,
        lambda v: f"{v:.3f}" if 0 < v < 1 else f"{v:.1f}",
        "Source: docs/BENCHMARKS.md, 'Retrieval benchmark v2' (offline, bge-small) and the live run at the freeze (tag freeze-1).",
    )


def workflow_chart() -> str:
    return bars(
        "Workflow miner · labelled synthetic traces (20 scenarios)",
        "The first run suggested workflow fragments; the fragment rule (ADR-022) removed every false suggestion.",
        [
            ("Pattern precision", [0.4, 1.0]),
            ("Pattern recall", [1.0, 1.0]),
            ("False-suggestion rate", [0.6, 0.0]),
            ("Support-count accuracy", [1.0, 1.0]),
        ],
        ["First run (ADR-018 rule)", "With the fragment rule (ADR-022)"],
        [SUBTLE, GROUNDED],
        1.0,
        lambda v: f"{v:.1f}",
        "Source: docs/BENCHMARKS.md, 'Workflow Learning Lite, M5'. Deterministic: identical output on repeat runs. Our own synthetic benchmark.",
    )


LATENCY = [  # BENCHMARKS "M4 latency per stage", inside Lambda, CloudWatch Logs Insights
    ("Query, end to end", 68, 39, 65),
    ("  question embedding (ONNX)", 68, 4, 5),
    ("  BM25 + k-NN search", 68, 13, 33),
    ("  conflict compare", 68, 0, 3),
    ("Answer call (Groq, incl. retries)", 6, 731, 1153),
    ("Ingestion, end to end", 10, 927, 1367),
    ("  index write (refresh)", 10, 806, 1246),
    ("Documents list", 98, 7, 10),
]


def latency_chart() -> str:
    w, row, top, left = 1100, 42, 110, 300
    h = top + row * len(LATENCY) + 70
    scale = (w - left - 110) / 1400
    b = [
        text(32, 44, "Latency per stage · deployed stack, inside Lambda", 20, TEXT, 600),
        text(
            32,
            68,
            "p50 (solid) and p95 (outline), from the `request finished` and `ingestion stages` log lines.",
            13,
            MUTED,
        ),
    ]
    for k in range(8):
        x = left + k * 200 * scale
        b.append(
            f'<line x1="{x}" y1="{top - 10}" x2="{x}" y2="{top + row * len(LATENCY)}" stroke="{BORDER}"/>'
        )
        b.append(
            text(
                x,
                top + row * len(LATENCY) + 18,
                f"{k * 200} ms",
                11,
                SUBTLE,
                anchor="middle",
                mono=True,
            )
        )
    for i, (name, n, p50, p95) in enumerate(LATENCY):
        y = top + i * row
        sub = name.startswith("  ")
        b.append(
            text(
                32 + (16 if sub else 0),
                y + 20,
                name.strip(),
                13,
                MUTED if sub else TEXT,
                400 if sub else 500,
            )
        )
        b.append(text(left - 12, y + 20, f"n={n}", 11, SUBTLE, anchor="end", mono=True))
        color = ACCENT if not name.startswith(("Answer", "Ingestion", "  index")) else CONFLICT
        b.append(
            f'<rect x="{left}" y="{y + 6}" width="{max(p95 * scale, 2)}" height="20" rx="4" fill="none" stroke="{color}" opacity="0.7"/>'
        )
        b.append(
            f'<rect x="{left}" y="{y + 6}" width="{max(p50 * scale, 2)}" height="20" rx="4" fill="{color}"/>'
        )
        b.append(
            text(
                left + max(p95 * scale, 2) + 10,
                y + 21,
                f"{p50} / {p95} ms",
                12,
                TEXT,
                500,
                mono=True,
            )
        )
    b.append(
        text(
            32,
            h - 20,
            "Source: docs/BENCHMARKS.md, 'M4 latency per stage'. Small samples, so p95 is close to the max. The browser adds the network round trip.",
            11,
            SUBTLE,
        )
    )
    return svg(w, h, "\n".join(b), "Latency per stage on the deployed stack")


# ---------------------------------------------------------------- AWS poster
def poster() -> str:
    w, h = 1200, 1000
    b = [
        text(40, 58, "CROWN-X · AWS architecture poster", 26, TEXT, 700),
        text(
            40,
            86,
            "AWS First Commit 2026 · Ship It · ap-south-1 · one SAM template · measured, not estimated",
            14,
            MUTED,
        ),
    ]
    services = [
        (
            "Amplify Hosting",
            "Next.js static export, rebuilt on every push",
            "no server to run (ADR-014)",
        ),
        (
            "API Gateway · HTTP API",
            "CORS + throttles: /query 3 rps, /answer 1 rps",
            "a cost control at the edge (ADR-021)",
        ),
        (
            "AWS Lambda × 2",
            "API and ingestion; ONNX embeddings inside",
            "scales to zero; no per-call embedding cost",
        ),
        (
            "Amazon S3",
            "browser uploads via size-limited pre-signed POST",
            "no file bytes pass through Lambda",
        ),
        (
            "OpenSearch Service",
            "BM25 + k-NN in one index, workspace-filtered",
            "hybrid retrieval in one store (ADR-011)",
        ),
        (
            "Amazon DynamoDB",
            "claims, audit, events, templates, hourly quotas (TTL)",
            "keyed by workspace; on demand",
        ),
        (
            "CloudWatch Logs",
            "request_id + per-stage latency on every line",
            "any error on screen found in seconds",
        ),
        (
            "SSM Parameter Store",
            "Groq key as a SecureString, read at cold start",
            "the key never enters repo or logs",
        ),
        (
            "IAM + CloudFormation",
            "one least-privilege role per function",
            "reviewable, repeatable deploys",
        ),
    ]
    for i, (name, job, why) in enumerate(services):
        cx, cy = 40 + (i % 3) * 378, 120 + (i // 3) * 150
        b.append(
            f'<rect x="{cx}" y="{cy}" width="358" height="132" rx="12" fill="{SURFACE}" stroke="{BORDER_STRONG}"/>'
        )
        b.append(f'<rect x="{cx}" y="{cy}" width="4" height="132" rx="2" fill="{ACCENT}"/>')
        b.append(text(cx + 20, cy + 34, name, 17, TEXT, 600))
        b.append(text(cx + 20, cy + 64, job, 12.5, MUTED))
        b.append(text(cx + 20, cy + 104, "why: " + why, 12, SUBTLE, mono=True))
    y = 590
    b.append(text(40, y, "MEASURED ON THE DEPLOYED STACK", 12, ACCENT, 600, mono=True))
    stats = [
        ("1.0 / 1.0", "contradiction precision / recall"),
        ("0.95", "recall@8, retrieval v2 (live)"),
        ("39 ms", "query p50 inside Lambda"),
        ("731 ms", "answer call p50 (Groq)"),
        ("$1.86", "AWS usage, 17-19 Sep"),
    ]
    for i, (v, lbl) in enumerate(stats):
        sx = 40 + i * 226
        b.append(
            f'<rect x="{sx}" y="{y + 16}" width="210" height="100" rx="12" fill="{SURFACE}" stroke="{BORDER}"/>'
        )
        b.append(text(sx + 18, y + 64, v, 28, GROUNDED if i < 2 else TEXT, 700, mono=True))
        b.append(text(sx + 18, y + 94, lbl, 12, MUTED))
    y = 760
    b.append(text(40, y, "COST GUARDRAILS", 12, CONFLICT, 600, mono=True))
    guards = [
        "One model call per question, none without evidence",
        "Local ONNX embeddings: indexing makes no model calls",
        "60 questions / workspace / hour, counted in DynamoDB before any work",
        "Per-route API throttles; single-node OpenSearch",
        "Upload size and per-workspace document limits",
        "Teardown after judging (/aws-ship teardown)",
    ]
    for i, g in enumerate(guards):
        b.append(text(40 + (i % 2) * 560, y + 34 + (i // 2) * 28, "›  " + g, 14, TEXT))
    b.append(
        text(
            40,
            h - 60,
            "Cost is AWS Cost Explorer usage for 17-19 Sep 2026 (before credits): OpenSearch $1.75, Amplify $0.10, the rest under $0.01 each.",
            12,
            SUBTLE,
        )
    )
    b.append(
        text(
            40,
            h - 38,
            "Groq is billed outside AWS and is not included. Numbers: docs/BENCHMARKS.md.",
            12,
            SUBTLE,
        )
    )
    return svg(w, h, "\n".join(b), "CROWN-X AWS architecture poster")


# ---------------------------------------------------------------- banner
def banner() -> str:
    b = [
        text(56, 118, "CROWN-X", 64, TEXT, 700),
        text(
            58,
            160,
            "Ask your project documents a question, and see where they disagree.",
            20,
            MUTED,
        ),
    ]
    chips = [
        ("every sentence cites its passage", GROUNDED),
        ("code decides conflicts, never a model", CONFLICT),
        ("timelines show how a value changed", ACCENT),
    ]
    x = 58
    for label, color in chips:
        w = len(label) * 7.4 + 36
        b.append(
            f'<rect x="{x}" y="196" width="{w}" height="34" rx="17" fill="{SURFACE}" stroke="{BORDER_STRONG}"/>'
        )
        b.append(f'<circle cx="{x + 17}" cy="213" r="4" fill="{color}"/>')
        b.append(text(x + 29, 218, label, 13, TEXT, 500))
        x += w + 12
    cx = 800
    b.append(
        f'<rect x="{cx}" y="52" width="344" height="150" rx="12" fill="{SURFACE}" stroke="{CONFLICT}"/>'
    )
    b.append(
        text(cx + 20, 84, "SOURCES DISAGREE · submission deadline", 11, CONFLICT, 600, mono=True)
    )
    b.append(text(cx + 20, 118, "20 Sep 2026", 18, SUBTLE, 600, mono=True))
    b.append(
        f'<line x1="{cx + 152}" y1="112" x2="{cx + 186}" y2="112" stroke="{CONFLICT}" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#arrow)"/>'
    )
    b.append(text(cx + 196, 118, "22 Sep 2026", 18, TEXT, 700, mono=True))
    b.append(text(cx + 20, 148, "brief v1 (31 Aug)  vs  organiser update 3 (10 Sep)", 12, MUTED))
    b.append(text(cx + 20, 176, "current value chosen by: newest source date", 12, GROUNDED, 500))
    b.append(
        text(
            58,
            272,
            "AWS First Commit 2026 · Ship It · Amplify · API Gateway · Lambda · S3 · OpenSearch · DynamoDB · CloudWatch",
            12,
            SUBTLE,
            mono=True,
        )
    )
    return svg(
        1200, 300, "\n".join(b), "CROWN-X: evidence-first answers that show where sources disagree"
    )


def main() -> None:
    out = {
        "banner.svg": banner(),
        "architecture-overview.svg": architecture(),
        "retrieval-pipeline.svg": pipeline(),
        "benchmark-chart-recall.svg": recall_chart(),
        "benchmark-chart-mrr.svg": mrr_chart(),
        "benchmark-chart-latency.svg": latency_chart(),
        "workflow-benchmark.svg": workflow_chart(),
        "aws-architecture-poster.svg": poster(),
    }
    for name, body in out.items():
        (MEDIA / name).write_text(body, encoding="utf-8", newline="\n")
        print("wrote", name)


if __name__ == "__main__":
    main()
