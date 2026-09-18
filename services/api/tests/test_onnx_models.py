"""Local ONNX models (ADR-017) on tiny generated models: pooling, normalisation, prefixes, the pinned
sha256, the S3 cache and the cross-encoder. The real models are exercised only when downloaded
(`python scripts/fetch_models.py`); otherwise those tests skip."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

onnx = pytest.importorskip("onnx")
from onnx import TensorProto, helper, numpy_helper  # noqa: E402
from tokenizers import Tokenizer, models, pre_tokenizers  # noqa: E402

from crownx.adapters.onnx_models import (  # noqa: E402
    EMBEDDING_PROFILES,
    ModelIntegrityError,
    OnnxEmbedder,
    OnnxReranker,
    resolve_model_dir,
)

VOCAB = {"[PAD]": 0, "[UNK]": 1, "deadline": 2, "budget": 3, "query": 4, "passage": 5, ":": 6}
REAL = Path(__file__).resolve().parents[1] / ".models"


def _tokenizer(directory: Path) -> None:
    tokenizer = Tokenizer(models.WordLevel(vocab=VOCAB, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
    tokenizer.save(str(directory / "tokenizer.json"))


def _save(graph, directory: Path) -> str:
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    path = directory / "model.onnx"
    onnx.save(model, str(path))
    _tokenizer(directory)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tiny_embedder(directory: Path) -> str:
    """last_hidden_state = table[input_ids]: each token has a fixed 3-d vector."""
    table = np.zeros((len(VOCAB), 3), dtype=np.float32)
    table[VOCAB["[PAD]"]] = [50, 50, 50]  # huge, so counting padding would be obvious
    table[VOCAB["deadline"]] = [1, 0, 0]
    table[VOCAB["budget"]] = [0, 1, 0]
    table[VOCAB["query"]] = [0, 0, 1]
    table[VOCAB["passage"]] = [0, 0, -1]
    graph = helper.make_graph(
        [helper.make_node("Gather", ["table", "input_ids"], ["last_hidden_state"], axis=0)],
        "tiny-embedder",
        [
            helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["b", "s"]),
            helper.make_tensor_value_info("attention_mask", TensorProto.INT64, ["b", "s"]),
        ],
        [helper.make_tensor_value_info("last_hidden_state", TensorProto.FLOAT, ["b", "s", 3])],
        [numpy_helper.from_array(table, "table")],
    )
    return _save(graph, directory)


def tiny_reranker(directory: Path) -> str:
    """logits = sum of per-token weights: "deadline" is relevant, "budget" isn't."""
    weights = np.zeros((len(VOCAB), 1), dtype=np.float32)
    weights[VOCAB["deadline"]] = 2.0
    weights[VOCAB["budget"]] = -1.0
    graph = helper.make_graph(
        [
            helper.make_node("Gather", ["weights", "input_ids"], ["per_token"], axis=0),
            helper.make_node("ReduceSum", ["per_token", "axes"], ["logits"], keepdims=0),
        ],
        "tiny-reranker",
        [
            helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["b", "s"]),
            helper.make_tensor_value_info("attention_mask", TensorProto.INT64, ["b", "s"]),
        ],
        [helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["b", 1])],
        [
            numpy_helper.from_array(weights, "weights"),
            numpy_helper.from_array(np.array([1], dtype=np.int64), "axes"),
        ],
    )
    return _save(graph, directory)


@pytest.fixture
def embedder_dir(tmp_path) -> tuple[Path, str]:
    return tmp_path, tiny_embedder(tmp_path)


def test_mean_pooling_ignores_padding_and_vectors_are_unit_length(embedder_dir):
    directory, _ = embedder_dir
    embedder = OnnxEmbedder(directory, "tiny")  # unknown name: mean pooling, no prefixes
    assert embedder.dimensions == 3
    short, long = embedder.embed(["deadline", "deadline budget"])
    assert np.allclose(short, [1, 0, 0])  # the pad token (50, 50, 50) never counted
    assert np.allclose(long, np.array([1, 1, 0]) / np.sqrt(2))
    assert np.isclose(np.linalg.norm(long), 1.0)


def test_e5_prefixes_make_queries_and_passages_differ(embedder_dir):
    directory, _ = embedder_dir
    embedder = OnnxEmbedder(directory, "multilingual-e5-small-int8")
    [as_query] = embedder.embed(["deadline"], kind="query")
    [as_passage] = embedder.embed(["deadline"], kind="passage")
    assert as_query[2] > 0 > as_passage[2]  # "query:" and "passage:" tokens point opposite ways


def test_cls_pooling_uses_the_first_token_only(embedder_dir):
    directory, _ = embedder_dir
    profile = EMBEDDING_PROFILES["bge-small-en-v1.5-int8"]
    EMBEDDING_PROFILES["tiny-cls"] = type(profile)("cls", "", "")
    try:
        [vector] = OnnxEmbedder(directory, "tiny-cls").embed(["budget deadline"])
    finally:
        del EMBEDDING_PROFILES["tiny-cls"]
    assert np.allclose(vector, [0, 1, 0])


def test_a_model_that_does_not_match_its_pin_is_refused(embedder_dir):
    directory, digest = embedder_dir
    assert resolve_model_dir(str(directory), "tiny", digest) == directory
    with pytest.raises(ModelIntegrityError, match="doesn't match"):
        resolve_model_dir(str(directory), "tiny", "0" * 64)


class FakeS3:
    def __init__(self, source: Path) -> None:
        self.source = source
        self.downloads: list[tuple[str, str]] = []

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        self.downloads.append((bucket, key))
        Path(filename).write_bytes((self.source / key.rsplit("/", 1)[1]).read_bytes())


def test_s3_models_download_once_per_container_then_verify(
    embedder_dir, tmp_path_factory, monkeypatch
):
    source, digest = embedder_dir
    cache = tmp_path_factory.mktemp("cache")
    monkeypatch.setenv("CROWNX_MODEL_CACHE", str(cache))
    s3 = FakeS3(source)
    first = resolve_model_dir("s3://bucket/models/tiny/", "tiny", digest, s3)
    second = resolve_model_dir("s3://bucket/models/tiny/", "tiny", digest, s3)
    assert first == second == cache / "models" / "tiny"
    assert s3.downloads == [
        ("bucket", "models/tiny/model.onnx"),
        ("bucket", "models/tiny/tokenizer.json"),
    ]
    (first / "model.onnx").write_bytes(b"tampered")
    with pytest.raises(ModelIntegrityError):
        resolve_model_dir("s3://bucket/models/tiny/", "tiny", digest, s3)


def test_the_cross_encoder_scores_each_pair(tmp_path):
    tiny_reranker(tmp_path)
    reranker = OnnxReranker(tmp_path, "tiny-reranker")
    scores = reranker.scores("deadline", ["budget", "deadline", "unknown words"])
    assert scores[1] > scores[2] > scores[0]


# ---------------------------------------------------------------- the real models, when downloaded

DOCS = [
    "The submission deadline for Campus Build Sprint moves to 22 Sept.",
    "Budget cap: 50,000 rupees from the Innovation Cell grant.",
    "The team meets every Tuesday in lab 3.",
]


@pytest.mark.parametrize("name", ["multilingual-e5-small-int8", "bge-small-en-v1.5-int8"])
def test_real_embedders_rank_a_paraphrase_above_unrelated_text(name):
    directory = REAL / name
    if not (directory / "model.onnx").exists():
        pytest.skip("run scripts/fetch_models.py to test the real model")
    embedder = OnnxEmbedder(directory, name)
    assert embedder.dimensions == 384
    [question] = np.array(embedder.embed(["When is the last day to submit?"], kind="query"))
    similarities = np.array(embedder.embed(DOCS)) @ question
    assert int(np.argmax(similarities)) == 0


def test_the_real_reranker_puts_the_answer_first():
    directory = REAL / "ms-marco-MiniLM-L-6-v2-int8"
    if not (directory / "model.onnx").exists():
        pytest.skip("run scripts/fetch_models.py to test the real model")
    scores = OnnxReranker(directory, "ms-marco-MiniLM-L-6-v2-int8").scores(
        "When is the submission deadline?", DOCS
    )
    assert int(np.argmax(scores)) == 0


def test_the_router_builds_the_onnx_embedder_and_its_namespace_from_configuration(embedder_dir):
    from crownx.adapters.providers import ProviderRouter
    from crownx.config import Settings

    directory, digest = embedder_dir
    providers = ProviderRouter.build(
        Settings(
            aws_region="ap-south-1",
            documents_bucket="b",
            table_name="t",
            opensearch_endpoint="search.example.test",
            ingest_function_name="crownx-ingest",
            environment="test",
            answer_provider="mock",
            embedding_provider="onnx",
            onnx_model_name="multilingual-e5-small-int8",
            onnx_model_uri=str(directory),
            onnx_model_sha256=digest,
            embedding_version="2",
        ),
        session=None,
    )
    assert isinstance(providers.embedder, OnnxEmbedder)
    assert providers.namespace.fields() == {
        "embedding_provider": "onnx",
        "embedding_model": "multilingual-e5-small-int8",
        "embedding_version": "2",
        "vector_dim": 3,
    }
