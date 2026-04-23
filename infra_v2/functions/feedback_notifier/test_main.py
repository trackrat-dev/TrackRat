"""Tests for feedback_notifier Cloud Function formatting logic."""

import base64
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from main import format_github_issue


def test_issue_report_formatting():
    """format_github_issue produces correct title and body for issue reports."""
    payload = {
        "message": "Train 3961 shows wrong arrival time at Hoboken",
        "origin_code": "NY",
        "destination_code": "HB",
        "screen": "train_details",
        "train_id": "3961",
        "device_model": "iPhone 15 Pro",
        "app_version": "2.3.1",
        "timestamp": "2026-04-23T01:00:00Z",
    }

    title, body = format_github_issue(payload)

    assert title == "[User Feedback] Train 3961 shows wrong arrival time at Hoboken"
    assert "## Issue Report" in body
    assert "> Train 3961 shows wrong arrival time at Hoboken" in body
    assert "| **Route** | NY → HB |" in body
    assert "| **Screen** | train_details |" in body
    assert "| **Train** | 3961 |" in body
    assert "| **Device** | iPhone 15 Pro |" in body
    assert "| **App Version** | 2.3.1 |" in body
    assert "| **Submitted** | 2026-04-23T01:00:00Z |" in body
    assert "Automatically created from in-app feedback" in body
    print("PASS: test_issue_report_formatting")


def test_improvement_suggestion_formatting():
    """format_github_issue detects [Improvement Suggestion] prefix and adjusts heading."""
    payload = {
        "message": "[Improvement Suggestion] Add dark mode to the map view",
        "origin_code": "?",
        "destination_code": "?",
        "screen": "congestion_map",
        "app_version": "2.3.1",
    }

    title, body = format_github_issue(payload)

    assert title == "[User Feedback] Add dark mode to the map view"
    assert "[Improvement Suggestion]" not in title
    assert "## Improvement Suggestion" in body
    assert "> Add dark mode to the map view" in body
    assert "| **Route** | N/A |" in body
    print("PASS: test_improvement_suggestion_formatting")


def test_long_message_truncation():
    """format_github_issue truncates title to 80 chars but keeps full body."""
    long_msg = "A" * 120
    payload = {
        "message": long_msg,
        "origin_code": "NY",
        "destination_code": "TR",
        "screen": "train_list",
    }

    title, body = format_github_issue(payload)

    assert len(title) < 100
    assert title.endswith("...")
    assert f"> {long_msg}" in body
    print("PASS: test_long_message_truncation")


def test_missing_optional_fields():
    """format_github_issue handles missing optional fields gracefully."""
    payload = {
        "message": "Something is broken",
        "screen": "train_list",
    }

    title, body = format_github_issue(payload)

    assert title == "[User Feedback] Something is broken"
    assert "| **Train** | N/A |" in body
    assert "| **App Version** | unknown |" in body
    assert "| **Device** | unknown |" in body
    assert "| **Submitted** | unknown |" in body
    print("PASS: test_missing_optional_fields")


def test_newlines_in_message_stripped_from_title():
    """format_github_issue replaces newlines in title but preserves them in body."""
    payload = {
        "message": "Line one\nLine two\nLine three",
        "origin_code": "NY",
        "destination_code": "HB",
        "screen": "train_details",
    }

    title, body = format_github_issue(payload)

    assert "\n" not in title
    assert "Line one Line two Line three" in title
    assert "Line one\nLine two\nLine three" in body
    print("PASS: test_newlines_in_message_stripped_from_title")


def test_partial_route_info():
    """format_github_issue shows route even if only origin or destination is set."""
    payload = {
        "message": "Departures not loading",
        "origin_code": "NY",
        "destination_code": "?",
        "screen": "train_list",
    }

    title, body = format_github_issue(payload)

    assert "| **Route** | NY → ? |" in body
    print("PASS: test_partial_route_info")


if __name__ == "__main__":
    test_issue_report_formatting()
    test_improvement_suggestion_formatting()
    test_long_message_truncation()
    test_missing_optional_fields()
    test_newlines_in_message_stripped_from_title()
    test_partial_route_info()
    print("\nAll tests passed!")
