"""Local ONNX models (ADR-017): sentence embeddings and a cross-encoder reranker, with no torch.

A model directory holds `model.onnx` and `tokenizer.json`. In AWS the files live in the documents
bucket under `models/<name>/` and are copied to `/tmp` once per container; the model file is checked
against its pinned sha256 before it's loaded, so a swapped or truncated file is refused rather than
silently producing different vectors. `scripts/fetch_models.py` publishes the files.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

MODEL_FILE = "model.onnx"
TOKENIZER_FILE = "tokenizer.json"
MAX_TOKENS = 512
BATCH = 16


class ModelIntegrityError(Exception):
    """The model file doesn't match its pinned sha256."""


@dataclass(frozen=True)
class EmbeddingProfile:
    """How a model family expects its input and pools its output."""

    pooling: str  # "mean" (E5) or "cls" (BGE)
    query_prefix: str
    passage_prefix: str


# Keyed by the configured model name. E5 needs its prefixes; BGE uses an instruction for queries only.
EMBEDDING_PROFILES: dict[str, EmbeddingProfile] = {
    "multilingual-e5-small-int8": EmbeddingProfile("mean", "query: ", "passage: "),
    "bge-small-en-v1.5-int8": EmbeddingProfile(
        "cls", "Represent this sentence for searching relevant passages: ", ""
    ),
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_model_dir(uri: str, name: str, expected_sha256: str, s3_client: Any = None) -> Path:
    """Return a local directory with a verified model. `uri` is `s3://bucket/prefix/` or a path."""
    if uri.startswith("s3://"):
        bucket, _, prefix = uri[len("s3://") :].partition("/")
        target = Path(os.environ.get("CROWNX_MODEL_CACHE", tempfile.gettempdir())) / "models" / name
        target.mkdir(parents=True, exist_ok=True)
        for filename in (MODEL_FILE, TOKENIZER_FILE):
            local = target / filename
            if not local.exists():
                partial = local.with_suffix(".part")
                s3_client.download_file(bucket, f"{prefix.rstrip('/')}/{filename}", str(partial))
                partial.replace(local)
        directory = target
    else:
        directory = Path(uri)
    actual = sha256_of(directory / MODEL_FILE)
    if actual != expected_sha256:
        raise ModelIntegrityError(f"{name}: model sha256 {actual} doesn't match the pinned value")
    return directory


def _session(directory: Path) -> Any:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
    return ort.InferenceSession(
        str(directory / MODEL_FILE), options, providers=["CPUExecutionProvider"]
    )


def _tokenizer(directory: Path, pad_id: int = 0) -> Any:
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(directory / TOKENIZER_FILE))
    tokenizer.enable_truncation(max_length=MAX_TOKENS)
    tokenizer.enable_padding(pad_id=tokenizer.padding["pad_id"] if tokenizer.padding else pad_id)
    return tokenizer


def _feeds(session: Any, encodings: list) -> dict[str, np.ndarray]:
    ids = np.array([e.ids for e in encodings], dtype=np.int64)
    mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    available = {
        "input_ids": ids,
        "attention_mask": mask,
        "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
    }
    return {i.name: available[i.name] for i in session.get_inputs() if i.name in available}


class OnnxEmbedder:
    """Sentence embeddings, L2-normalised, so cosine similarity is a dot product."""

    provider = "onnx"

    def __init__(self, directory: Path, model_name: str) -> None:
        self.model_id = model_name
        self._profile = EMBEDDING_PROFILES.get(model_name, EmbeddingProfile("mean", "", ""))
        self._session = _session(directory)
        self._tokenizer = _tokenizer(directory)
        probe = self._run(["dimension probe"])
        self.dimensions = int(probe.shape[1])

    def embed(self, texts: list[str], kind: str = "passage") -> list[list[float]]:
        prefix = self._profile.query_prefix if kind == "query" else self._profile.passage_prefix
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            batch = [prefix + text for text in texts[start : start + BATCH]]
            vectors.extend(self._run(batch).tolist())
        return vectors

    def _run(self, texts: list[str]) -> np.ndarray:
        encodings = self._tokenizer.encode_batch(texts)
        feeds = _feeds(self._session, encodings)
        hidden = self._session.run(None, feeds)[0]  # last_hidden_state: [batch, tokens, dim]
        if self._profile.pooling == "cls":
            pooled = hidden[:, 0, :]
        else:
            mask = feeds["attention_mask"][..., None].astype(hidden.dtype)
            pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return (pooled / np.clip(norms, 1e-12, None)).astype(np.float32)


class OnnxReranker:
    """A cross-encoder: scores each (question, passage) pair jointly; higher is more relevant."""

    provider = "onnx"

    def __init__(self, directory: Path, model_name: str) -> None:
        self.model_id = model_name
        self._session = _session(directory)
        self._tokenizer = _tokenizer(directory)

    def scores(self, question: str, passages: list[str]) -> list[float]:
        results: list[float] = []
        for start in range(0, len(passages), BATCH):
            pairs = [(question, p) for p in passages[start : start + BATCH]]
            encodings = self._tokenizer.encode_batch(pairs)
            logits = self._session.run(None, _feeds(self._session, encodings))[0]
            results.extend(float(row[0]) for row in np.asarray(logits).reshape(len(pairs), -1))
        return results
