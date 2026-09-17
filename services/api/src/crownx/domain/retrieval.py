"""OpenSearch request bodies. The workspace filter sits inside each query, never applied afterwards
(CLAUDE.md rule 4, SECURITY T2), so a result from another workspace can't reach the fusion step.
"""

from __future__ import annotations

from collections.abc import Sequence

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
]


def index_body(dimensions: int) -> dict:
    """Settings and mapping for `crownx-chunks` (M1 prompt, SRS §4, ADR-011)."""
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
            },
        },
    }


def _workspace_filter(workspace_id: str) -> dict:
    return {"term": {"workspace_id": workspace_id}}


def lexical_query(question: str, workspace_id: str, size: int) -> dict:
    return {
        "size": size,
        "_source": INDEX_FIELDS_WITHOUT_VECTOR,
        "query": {
            "bool": {
                "must": [{"match": {"text": {"query": question}}}],
                "filter": [_workspace_filter(workspace_id)],
            }
        },
    }


def semantic_query(vector: Sequence[float], workspace_id: str, size: int) -> dict:
    return {
        "size": size,
        "_source": INDEX_FIELDS_WITHOUT_VECTOR,
        "query": {
            "knn": {
                "embedding": {
                    "vector": list(vector),
                    "k": size,
                    "filter": _workspace_filter(workspace_id),
                }
            }
        },
    }
