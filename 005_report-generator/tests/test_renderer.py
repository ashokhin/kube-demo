"""
Tests for report-generator renderer functions.

render_json() and render_csv() are pure functions: they take an OrderSummary
and write files to a directory. No DB, no network — easy to test directly.

This is the ideal case for unit testing: side-effect-free functions that
can be verified by reading the output files.
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.renderer import render_json, render_csv, render_html
from src.repository import OrderSummary


@pytest.fixture()
def summary() -> OrderSummary:
    return OrderSummary(
        total_orders=10,
        pending=3,
        confirmed=6,
        cancelled=1,
        period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2024, 1, 8, tzinfo=timezone.utc),
    )


def test_render_json_creates_file(tmp_path, summary):
    filepath = render_json(summary, str(tmp_path))
    assert Path(filepath).exists()


def test_render_json_content(tmp_path, summary):
    filepath = render_json(summary, str(tmp_path))
    data = json.loads(Path(filepath).read_text())

    assert data["total_orders"] == 10
    assert data["by_status"]["pending"] == 3
    assert data["by_status"]["confirmed"] == 6
    assert data["by_status"]["cancelled"] == 1


def test_render_json_filename_contains_dates(tmp_path, summary):
    # Date range in filename makes the report idempotent: re-running on the
    # same day overwrites the file instead of accumulating duplicates.
    filepath = render_json(summary, str(tmp_path))
    assert "2024-01-01" in Path(filepath).name
    assert "2024-01-08" in Path(filepath).name


def test_render_csv_creates_file(tmp_path, summary):
    filepath = render_csv(summary, str(tmp_path))
    assert Path(filepath).exists()


def test_render_csv_content(tmp_path, summary):
    filepath = render_csv(summary, str(tmp_path))
    rows = list(csv.reader(Path(filepath).read_text().splitlines()))

    # First row is the header
    assert rows[0] == ["metric", "value"]

    # Convert to dict for easier assertions
    data = {row[0]: row[1] for row in rows[1:]}
    assert data["total_orders"] == "10"
    assert data["pending"] == "3"
    assert data["confirmed"] == "6"
    assert data["cancelled"] == "1"


def test_render_html_creates_file_with_correct_content(tmp_path, summary):
    filepath = render_html(summary, str(tmp_path))

    # Returned path must point to an HTML file.
    assert filepath.endswith(".html")
    assert Path(filepath).exists()

    content = Path(filepath).read_text(encoding="utf-8")

    # Page title / heading
    assert "Order Summary Report" in content

    # Period dates appear in the rendered output
    assert "2024-01-01" in content
    assert "2024-01-08" in content

    # All three order statuses must be present
    assert "pending" in content
    assert "confirmed" in content
    assert "cancelled" in content

    # Total orders count
    assert "10" in content


def test_render_creates_output_directory_if_missing(tmp_path, summary):
    # mkdir -p behaviour: output_path may not exist on first CronJob run.
    nested_path = tmp_path / "reports" / "2024" / "january"
    render_json(summary, str(nested_path))
    assert nested_path.exists()
