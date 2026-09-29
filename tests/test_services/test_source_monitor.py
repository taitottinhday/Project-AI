from src.services.source_monitor import allowed_source_url, observation


def test_source_monitor_only_accepts_official_https_urls():
    assert allowed_source_url("https://vinuni.edu.vn/admissions")
    assert allowed_source_url("https://admissions.vinuni.edu.vn/page")
    assert not allowed_source_url("http://vinuni.edu.vn/admissions")
    assert not allowed_source_url("https://vinuni.edu.vn.evil.example/page")
    assert not allowed_source_url("https://user:password@vinuni.edu.vn/page")
    assert not allowed_source_url("https://vinuni.edu.vn:8443/page")


def test_changed_or_unavailable_source_requires_human_review():
    first = observation({}, digest="first")
    assert first["state"] == "first_observation"
    assert first["baseline_sha256"] == "first"
    assert first["review_required"] is False

    unchanged = observation(first, digest="first")
    assert unchanged["state"] == "unchanged"
    assert unchanged["review_required"] is False

    changed = observation(unchanged, digest="second")
    assert changed["state"] == "changed"
    assert changed["baseline_sha256"] == "first"
    assert changed["review_required"] is True

    unavailable = observation(unchanged, digest=None, error="ConnectError")
    assert unavailable["state"] == "unavailable"
    assert unavailable["review_required"] is True
