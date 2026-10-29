from apex_rag_demo.rag.chroma_metrics import chroma_collection_metadata, distance_to_similarity


def test_collection_metadata_includes_hnsw_space():
    meta = chroma_collection_metadata({"description": "test"})
    assert meta.get("hnsw:space") == "cosine"
    assert meta.get("description") == "test"


def test_cosine_distance_to_similarity():
    assert distance_to_similarity(0.0, space="cosine") == 1.0
    assert distance_to_similarity(1.0, space="cosine") == 0.0
