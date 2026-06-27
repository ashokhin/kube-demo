"""
Tests for stream-ingestor in mock mode.

Uses MOCK_MODE=true so no Spark, Kafka, HDFS, or Hive is required.
The mock path is pure Python — no JVM needed.
"""
import pytest


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")


def test_run_streaming_mock_does_not_raise():
    from src.stream_runner import run_streaming
    run_streaming(mock_mode=True)


def test_metrics_records_processed_incremented():
    from src import metrics
    from src.stream_runner import run_streaming

    before = metrics.RECORDS_PROCESSED._value.get()
    run_streaming(mock_mode=True)
    after = metrics.RECORDS_PROCESSED._value.get()
    assert after > before


def test_mock_batch_empty_is_noop():
    from src.stream_runner import _mock_batch
    from src import metrics

    before = metrics.RECORDS_PROCESSED._value.get()
    _mock_batch([])
    assert metrics.RECORDS_PROCESSED._value.get() == before
