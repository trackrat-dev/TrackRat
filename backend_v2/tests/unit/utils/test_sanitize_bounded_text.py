"""Tests for bounded_text (issue #1725).

Moved out of services/gtfs.py (was the private `_bounded`) so the collectors
can bound upstream error bodies with the same helper rather than growing a
second copy. GTFS's two call sites keep using it, so these tests cover both
consumers.
"""

from trackrat.utils.sanitize import bounded_text


class TestBoundedText:
    def test_text_within_limit_is_returned_unchanged(self):
        """No annotation may be appended to something that already fits —
        GTFS stores these strings in error_message columns."""
        assert bounded_text("short", 100) == "short"

    def test_text_exactly_at_limit_is_not_truncated(self):
        """Boundary: the limit is inclusive."""
        text = "x" * 50
        assert bounded_text(text, 50) == text
        assert "truncated" not in bounded_text(text, 50)

    def test_text_one_over_limit_is_truncated(self):
        result = bounded_text("x" * 51, 50)
        assert result.startswith("x" * 50)
        assert result == "x" * 50 + "... [truncated 1 chars]"

    def test_truncation_reports_how_much_was_dropped(self):
        """A silently-cut string reads as a complete one; the count is what
        tells a reader the entry is partial."""
        result = bounded_text("y" * 20_000, 500)
        assert "[truncated 19500 chars]" in result
        assert len(result) < 600

    def test_leading_bytes_are_preserved(self):
        """For an HTML error page the opening tag / title is the diagnostic
        part, so truncation must keep the head, not the tail."""
        html = "<html><title>409 Conflict</title>" + ("z" * 5_000)
        result = bounded_text(html, 100)
        assert result.startswith("<html><title>409 Conflict</title>")

    def test_empty_string_is_returned_unchanged(self):
        assert bounded_text("", 100) == ""

    def test_zero_limit_truncates_everything_but_still_annotates(self):
        result = bounded_text("abc", 0)
        assert result == "... [truncated 3 chars]"
