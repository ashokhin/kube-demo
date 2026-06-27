"""Tests for HTML report rendering."""
import os
import tempfile
import pytest
from datetime import date

from src.report_renderer import render_html

SAMPLE_ROWS = [
    {"portfolio_id": "PORTFOLIO_A", "model_version": "v1.0", "scenario": "base",
     "risk_score": 0.25, "var_95": 125_000.0, "var_99": 210_000.0,
     "calculated_date": date.today().isoformat()},
    {"portfolio_id": "PORTFOLIO_B", "model_version": "v1.0", "scenario": "stress",
     "risk_score": 0.41, "var_95": 320_000.0, "var_99": 540_000.0,
     "calculated_date": date.today().isoformat()},
]


def test_render_html_creates_file():
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        path = tmp.name
    try:
        result = render_html(SAMPLE_ROWS, path)
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0
    finally:
        os.unlink(path)


def test_render_html_contains_portfolio_data():
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        path = tmp.name
    try:
        render_html(SAMPLE_ROWS, path)
        content = open(path).read()
        assert "PORTFOLIO_A" in content
        assert "PORTFOLIO_B" in content
        assert "stress" in content
    finally:
        os.unlink(path)


def test_render_html_high_risk_gets_css_class():
    # risk_score > 0.35 should get risk-high CSS class
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        path = tmp.name
    try:
        render_html(SAMPLE_ROWS, path)
        content = open(path).read()
        assert "risk-high" in content  # PORTFOLIO_B has 0.41 > 0.35
    finally:
        os.unlink(path)


def test_render_html_empty_rows():
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        path = tmp.name
    try:
        render_html([], path)
        content = open(path).read()
        assert "Risk Summary Report" in content
    finally:
        os.unlink(path)
