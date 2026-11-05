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
