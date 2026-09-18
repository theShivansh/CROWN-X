"""Download the pinned local models (ADR-017) and optionally publish them for the Lambdas.

    python scripts/fetch_models.py                       # download into services/api/.models/
    python scripts/fetch_models.py --publish <bucket>    # also upload to s3://<bucket>/models/<name>/

Each model is pinned to a Hugging Face commit, so the bytes can't change underneath us. The script
prints each model.onnx sha256: pass it to `sam deploy` as OnnxModelSha256 / RerankerModelSha256; the
Lambdas refuse a file that doesn't match. Stdlib only, except boto3 for --publish.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "services" / "api" / ".models"

# name -> (repository, pinned commit, ONNX file in the repository)
MODELS: dict[str, tuple[str, str, str]] = {
    "multilingual-e5-small-int8": (
        "Xenova/multilingual-e5-small",
        "761b726dd34fb83930e26aab4e9ac3899aa1fa78",
        "onnx/model_int8.onnx",
    ),
    "bge-small-en-v1.5-int8": (
        "Xenova/bge-small-en-v1.5",
        "ea104dacec62c0de699686887e3f920caeb4f3e3",
        "onnx/model_int8.onnx",
    ),
    "ms-marco-MiniLM-L-6-v2-int8": (
        "Xenova/ms-marco-MiniLM-L-6-v2",
        "a09144355adeed5f58c8ed011d209bf8ee5a1fec",
        "onnx/model_int8.onnx",
    ),
}


def _download(url: str, destination: Path) -> None:
    if destination.exists():
        return
    partial = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as out:  # noqa: S310
        while block := response.read(1 << 20):
            out.write(block)
    partial.replace(destination)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(name: str) -> Path:
    repository, commit, onnx_file = MODELS[name]
    directory = TARGET / name
    directory.mkdir(parents=True, exist_ok=True)
    base = f"https://huggingface.co/{repository}/resolve/{commit}"
    _download(f"{base}/{onnx_file}", directory / "model.onnx")
    _download(f"{base}/tokenizer.json", directory / "tokenizer.json")
    return directory


def publish(directory: Path, bucket: str, name: str) -> None:
    import boto3

    s3 = boto3.client("s3")
    for filename in ("model.onnx", "tokenizer.json"):
        s3.upload_file(str(directory / filename), bucket, f"models/{name}/{filename}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", choices=sorted(MODELS), action="append")
    parser.add_argument("--publish", metavar="BUCKET")
    args = parser.parse_args()
    for name in args.only or sorted(MODELS):
        directory = fetch(name)
        digest = sha256_of(directory / "model.onnx")
        if args.publish:
            publish(directory, args.publish, name)
        where = f"s3://{args.publish}/models/{name}/" if args.publish else str(directory)
        print(f"{name}\t{digest}\t{where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
