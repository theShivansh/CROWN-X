"""OpenSearch request bodies. The workspace filter sits inside each query, never applied afterwards
(CLAUDE.md rule 4, SECURITY T2), so a result from another workspace can't reach the fusion step.

One index holds every chunk (ADR-011). Each chunk also carries its embedding namespace (ADR-016):
provider, model, version and vector dimension. Both retrieval clauses filter on it, so chunks embedded
by the mock provider and by Bedrock never answer each other's questions, and a vector is only ever
compared with vectors from the same model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

NAMESPACE_FIELDS = ("embedding_provider", "embedding_model", "embedding_version", "vector_dim")

INDEX_FIELDS_WITHOUT_VECTOR = [
    "workspace_id",
    "document_id",
    "chunk_id",
    "version_label",
    "page_or_section",
    "text",
    "source_timestamp",
    "uploaded_at",
    "char_start",
    "char_end",
    *NAMESPACE_FIELDS,
]


@dataclass(frozen=True)
class EmbeddingNamespace:
    provider: str  # "bedrock" | "mock"
    model: str
    version: str
    dimensions: int

    def fields(self) -> dict:
        """The namespace as stored on every chunk."""
        return {
            "embedding_provider": self.provider,
            "embedding_model": self.model,
            "embedding_version": self.version,
            "vector_dim": self.dimensions,
        }


def index_body(dimensions: int) -> dict:
    """Settings and mapping for `crownx-chunks` (M1 prompt, SRS §4, ADR-011, ADR-016)."""
    keyword = {"type": "keyword"}
    return {
        "settings": {"index": {"knn": True, "number_of_shards": 1, "number_of_replicas": 0}},
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "workspace_id": keyword,
                "document_id": keyword,
                "chunk_id": keyword,
                "version_label": keyword,
                "page_or_section": keyword,
                "text": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dimensions,
                    # Lucene HNSW: filtered k-NN without native memory on a small node.
                    "method": {"name": "hnsw", "engine": "lucene", "space_type": "cosinesimil"},
                },
                "source_timestamp": {"type": "date"},
                "uploaded_at": {"type": "date"},
                "char_start": {"type": "integer"},
                "char_end": {"type": "integer"},
                "embedding_provider": keyword,
                "embedding_model": keyword,
                "embedding_version": keyword,
                "vector_dim": {"type": "integer"},
            },
        },
    }


def scope_filters(workspace_id: str, namespace: EmbeddingNamespace) -> list[dict]:
    """Workspace first; then the embedding namespace. Every clause is an exact term match."""
    return [
        {"term": {"workspace_id": workspace_id}},
        {"term": {"embedding_provider": namespace.provider}},
        {"term": {"embedding_model": namespace.model}},
        {"term": {"embedding_version": namespace.version}},
    ]


def lexical_query(
    question: str, workspace_id: str, size: int, namespace: EmbeddingNamespace
) -> dict:
    return {
        "size": size,
        "_source": INDEX_FIELDS_WITHOUT_VECTOR,
        "query": {
            "bool": {
                "must": [{"match": {"text": {"query": question}}}],
                "filter": scope_filters(workspace_id, namespace),
            }
        },
    }


def semantic_query(
    vector: Sequence[float], workspace_id: str, size: int, namespace: EmbeddingNamespace
) -> dict:
    return {
        "size": size,
        "_source": INDEX_FIELDS_WITHOUT_VECTOR,
        "query": {
            "knn": {
                "embedding": {
                    "vector": list(vector),
                    "k": size,
                    "filter": {"bool": {"filter": scope_filters(workspace_id, namespace)}},
                }
            }
        },
    }
