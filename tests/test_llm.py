from src.llm import is_model_unavailable, rank_models

GEN = ["generateContent"]


def test_newest_stable_flash_first_and_junk_excluded():
    models = [
        ("models/gemini-2.5-flash", GEN),
        ("models/gemini-3-flash-preview", GEN),
        ("models/gemini-3-flash", GEN),
        ("models/gemini-3-flash-lite", GEN),
        ("models/gemini-2.0-flash-image", GEN),
        ("models/gemini-3-pro", GEN),
        ("models/gemini-3-flash-embedding", ["embedContent"]),
    ]
    assert rank_models(models) == ["gemini-3-flash", "gemini-3-flash-preview", "gemini-2.5-flash"]


def test_models_without_generate_content_are_skipped():
    assert rank_models([("models/gemini-3-flash", ["embedContent"])]) == []


def test_unknown_actions_are_allowed():
    assert rank_models([("models/gemini-3-flash", [])]) == ["gemini-3-flash"]


def test_retired_model_error_detected():
    err = Exception("404 NOT_FOUND. This model models/x is no longer available to new users")
    assert is_model_unavailable(err)
    assert not is_model_unavailable(Exception("429 RESOURCE_EXHAUSTED quota"))


def test_transient_errors_and_retry_delay():
    from src.llm import is_transient, retry_delay

    assert is_transient(Exception("503 UNAVAILABLE. high demand"))
    assert is_transient(Exception("429 RESOURCE_EXHAUSTED"))
    assert not is_transient(Exception("400 INVALID_ARGUMENT"))
    assert retry_delay(Exception("Please retry in 12.5s.")) == 13.5
    assert retry_delay(Exception("'retryDelay': '600s'")) == 45.0
    assert retry_delay(Exception("no hint")) == 20.0
