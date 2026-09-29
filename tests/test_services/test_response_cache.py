from src.services.response_cache import ResponseCache


def test_cache_is_namespaced_and_returns_a_copy():
    cache = ResponseCache(ttl_seconds=60, max_entries=10)
    value = {
        "intent": "tuition",
        "status": "answered",
        "response": "Mức học phí đã kiểm chứng",
        "reason_code": "grounded_answer",
        "confidence": 0.9,
        "grounded": True,
        "citations": [{"source_id": "source-1"}],
        "warnings": [],
        "handover_recommended": False,
    }
    cache.set("Học phí là bao nhiêu?", "dataset-v1", value)

    cached = cache.get("  HỌC PHÍ là bao nhiêu?  ", "dataset-v1")
    assert cached is not None
    cached["response"] = "changed"
    assert cache.get("Học phí là bao nhiêu?", "dataset-v1")["response"] == "Mức học phí đã kiểm chứng"
    assert cache.get("Học phí là bao nhiêu?", "dataset-v2") is None


def test_cache_rejects_personal_data():
    cache = ResponseCache(ttl_seconds=60, max_entries=10)
    assert cache.is_cacheable_query("Email của tôi là learner@example.com") is False


def test_cache_itself_rejects_unsafe_entries():
    cache = ResponseCache()
    cache.set("Học phí?", "v1", {"status": "answered", "grounded": False, "citations": [{}]})
    assert cache.get("Học phí?", "v1") is None


def test_cache_keys_preserve_decimals():
    assert ResponseCache._key("GPA 2.5", "v1") != ResponseCache._key("GPA 2 5", "v1")
