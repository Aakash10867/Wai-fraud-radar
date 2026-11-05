from src.discover import discover_one, looks_right, target_years

GOOD = ["Reliance Infrastructure Limited  Annual Report 2018–19", "page two"]


def test_target_years_cover_six_fiscal_years():
    assert target_years(2019) == [2019, 2017, 2015]


def test_looks_right_accepts_matching_report():
    assert looks_right(GOOD, "Reliance Infrastructure", 2019)


def test_looks_right_rejects_wrong_company_year_or_doc():
    assert not looks_right(GOOD, "Reliance Industries", 2019)
    assert not looks_right(GOOD, "Reliance Infrastructure", 2017)
    assert not looks_right(["Reliance Infrastructure press release 2018-19"], "Reliance Infrastructure", 2019)


def test_discover_skips_bad_candidates_and_returns_first_verified():
    pages = {"http://a/blocked.pdf": None, "http://b/other.pdf": ["Some Other Co annual report 2018-19"],
             "http://c/right.pdf": GOOD}

    def fetcher(url):
        if pages[url] is None:
            raise ValueError("not a PDF")
        return pages[url]

    url, note = discover_one("Reliance Infrastructure", 2019,
                             finder=lambda c, fy: list(pages), fetcher=fetcher)
    assert url == "http://c/right.pdf" and note == "verified"


def test_discover_reports_failure_reason():
    url, note = discover_one("X Y", 2019, finder=lambda c, fy: [], fetcher=None)
    assert url is None and note == "no_candidates"


def test_parse_ddg_keeps_only_report_like_links():
    from src.discover import parse_ddg

    page = ('<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdocs%2FAR-2019.pdf&rut=abc">x</a>'
            '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fabout&rut=def">y</a>'
            '<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdocs%2FAR-2019.pdf&rut=ghi">z</a>')
    assert parse_ddg(page) == ["https://example.com/docs/AR-2019.pdf"]


def test_find_candidates_survives_dead_gemini_and_raises_only_when_all_routes_fail(monkeypatch):
    import src.discover as d

    monkeypatch.setattr(d, "_gemini_down", False)
    monkeypatch.setattr(d, "search_web", lambda c, fy: ["http://x/ar.pdf"])

    def boom(c, fy):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(d, "search_gemini", boom)
    assert d.find_candidates("A B", 2019) == ["http://x/ar.pdf"]  # web search carries on
    assert d._gemini_down is True
    monkeypatch.setattr(d, "search_web", boom)
    import pytest

    with pytest.raises(RuntimeError):
        d.find_candidates("A B", 2019)
