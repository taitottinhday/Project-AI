from src.services.knowledge_base import get_knowledge_base, normalize_text


def test_normalize_text_preserves_vietnamese_d_stroke_as_d():
    assert normalize_text("Điều kiện trao đổi quốc tế là gì?") == "dieu kien trao doi quoc te la gi"


def test_knowledge_base_loads_canonical_manifest_only():
    knowledge = get_knowledge_base(reload=True)

    assert knowledge.ready is True
    assert knowledge.document_count == 12
    assert len(knowledge.sources) == 62
    assert len(knowledge.chunks) >= 138
    assert knowledge.load_errors == []


def test_record_lists_are_chunked_individually():
    knowledge = get_knowledge_base()
    quota_chunks = [chunk for chunk in knowledge.chunks if "program level admission quotas" in chunk.section]

    assert len(quota_chunks) == 1
    assert quota_chunks[0].flags == ("not_publicly_verified",)


def test_tuition_retrieval_has_official_source_ids():
    knowledge = get_knowledge_base()
    hits = knowledge.search("hoc phi cu nhan 2026-2027", top_k=20)
    tuition_hits = [hit for hit in hits if hit.chunk.document.startswith("tuition/")]

    assert tuition_hits
    assert all(hit.chunk.source_ids for hit in tuition_hits)
    assert all(source_id in knowledge.sources for hit in tuition_hits for source_id in hit.chunk.source_ids)
