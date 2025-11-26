"""Unit tests for vp_generator.utils."""

from vp_generator.utils import make_date_list, truncate_summary


def test_make_date_list_inclusive():
    dates = make_date_list("2025-01-01", "2025-01-03")
    assert dates == ["2025-01-01", "2025-01-02", "2025-01-03"]


def test_truncate_summary_caps_sentences_and_words():
    text = "Sentence one is here. Sentence two is also here. Sentence three should be dropped."
    truncated = truncate_summary(text, max_words=10, max_sentences=2)
    assert truncated.count(".") <= 2
    assert len(truncated.split()) <= 10
