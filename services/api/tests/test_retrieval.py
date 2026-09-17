"""OpenSearch request bodies: the workspace filter is inside both retrieval clauses."""

from __future__ import annotations

from crownx.domain.retrieval import index_body, lexical_query, semantic_query

WS = "ws_AAAAAAAAAAAAAAAAAAAAAA"


def test_lexical_query_filters_by_workspace_inside_the_bool_query():
    body = lexical_query("What is the submission deadline?", WS, size=16)
    assert body["size"] == 16
    assert body["query"]["bool"]["filter"] == [{"term": {"workspace_id": WS}}]
    assert body["query"]["bool"]["must"] == [
        {"match": {"text": {"query": "What is the submission deadline?"}}}
    ]
    assert "embedding" not in body["_source"]


def test_semantic_query_filters_by_workspace_inside_the_knn_clause():
    body = semantic_query([0.1, 0.2, 0.3], WS, size=16)
    knn = body["query"]["knn"]["embedding"]
    assert knn["filter"] == {"term": {"workspace_id": WS}}
    assert knn["k"] == 16 and body["size"] == 16
    assert knn["vector"] == [0.1, 0.2, 0.3]
    assert set(body["query"]) == {"knn"}, "no post-filter wrapper around the k-NN clause"
    assert "embedding" not in body["_source"]


def test_index_body_matches_the_chunk_contract():
    body = index_body(1024)
    assert body["settings"]["index"]["knn"] is True
    properties = body["mappings"]["properties"]
    for field in ("workspace_id", "document_id", "chunk_id", "version_label", "page_or_section"):
        assert properties[field] == {"type": "keyword"}
    assert properties["text"] == {"type": "text"}
    assert properties["embedding"]["type"] == "knn_vector"
    assert properties["embedding"]["dimension"] == 1024
    assert properties["source_timestamp"]["type"] == properties["uploaded_at"]["type"] == "date"
    assert properties["char_start"]["type"] == properties["char_end"]["type"] == "integer"
    assert body["mappings"]["dynamic"] == "strict"
