"""
Kafka consumer for risk-engine.

Reads job requests from the `risk-jobs` topic published by risk-ui (/api/jobs/async).
For each message, runs the full risk calculation pipeline and publishes the result
to the `risk-results` topic (consumed by 005_stream-ingestor for streaming aggregation).

Consumer group: risk-engine-group
  - Enables horizontal scaling: multiple risk-engine pods share the partition load.
  - Offset is committed only after a successful calculation to avoid silent data loss.

Topic contract:
  risk-jobs   key=<portfolioId>:<modelVersion>  value=JobRequest JSON
  risk-results key=<portfolioId>               value=RiskResult JSON
"""
import json
import logging
import os
import threading
import time
from typing import Any

from src.metrics import (
    ACTIVE_CALCULATIONS,
    CALCULATION_DURATION,
    CALCULATIONS_TOTAL,
    KAFKA_CONSUMED_TOTAL,
    KAFKA_CONSUMER_LAG,
)

log = logging.getLogger(__name__)

# Shared flag — True while consumer is connected and polling. Read by /readyz.
kafka_connected: bool = False

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
CONSUMER_TOPIC = os.environ.get("KAFKA_TOPIC_RISK_JOBS", "risk-jobs")
PRODUCER_TOPIC = os.environ.get("KAFKA_TOPIC_RISK_RESULTS", "risk-results")
CONSUMER_GROUP = os.environ.get("KAFKA_CONSUMER_GROUP", "risk-engine-group")

_RECONNECT_DELAY_INITIAL = 5
_RECONNECT_DELAY_MAX = 60
_POLL_TIMEOUT = 1.0


def _run_calculation(message_value: dict[str, Any], hdfs_client: Any, hive_client: Any, risk_calculator: Any) -> dict[str, Any]:
    from src.risk_calculator import calculate

    portfolio_id = message_value.get("portfolioId", "unknown")
    model_version = message_value.get("modelVersion", "unknown")
    scenario = message_value.get("scenario", "baseline")

    ACTIVE_CALCULATIONS.inc()
    start = time.monotonic()
    try:
        portfolio = hdfs_client.read_portfolio(portfolio_id, f"/data/portfolios/{portfolio_id}.json")
        result = calculate(portfolio, model_version)
        hive_client.write_risk_result(result)

        elapsed = time.monotonic() - start
        CALCULATION_DURATION.labels(model_version=model_version).observe(elapsed)
        CALCULATIONS_TOTAL.labels(model_version=model_version, status="success").inc()

        return {
            "portfolioId": portfolio_id,
            "modelVersion": model_version,
            "scenario": scenario,
            "riskScore": result["risk_score"],
            "var95": result["var_95"],
            "var99": result["var_99"],
            "totalValue": result["total_value"],
            "durationSeconds": elapsed,
        }
    except Exception:
        CALCULATIONS_TOTAL.labels(model_version=model_version, status="error").inc()
        raise
    finally:
        ACTIVE_CALCULATIONS.dec()


def _mock_run(message_value: dict[str, Any]) -> dict[str, Any]:
    time.sleep(0.05)
    return {
        "portfolioId": message_value.get("portfolioId", "mock"),
        "modelVersion": message_value.get("modelVersion", "v1.0"),
        "scenario": message_value.get("scenario", "baseline"),
        "riskScore": 0.25,
        "var95": 10000.0,
        "var99": 15000.0,
        "totalValue": 1000000.0,
        "durationSeconds": 0.05,
        "mock": True,
    }


def start_consumer(hdfs_client: Any, hive_client: Any, risk_calculator: Any, mock_mode: bool = False) -> threading.Thread:
    """Start the Kafka consumer loop in a daemon thread."""
    thread = threading.Thread(
        target=_consumer_loop,
        args=(hdfs_client, hive_client, risk_calculator, mock_mode),
        daemon=True,
        name="kafka-consumer",
    )
    thread.start()
    log.info("Kafka consumer thread started topic=%s group=%s mock=%s", CONSUMER_TOPIC, CONSUMER_GROUP, mock_mode)
    return thread


def _consumer_loop(hdfs_client: Any, hive_client: Any, risk_calculator: Any, mock_mode: bool = False) -> None:
    if mock_mode:
        log.info("KAFKA_MOCK_MODE: Kafka consumer is simulated, no real broker connection")
        _mock_consumer_loop()
        return

    from confluent_kafka import Consumer, KafkaError, KafkaException, Producer  # type: ignore[import]

    global kafka_connected

    def _on_error(err: Any) -> None:
        global kafka_connected
        if err.code() in (KafkaError._ALL_BROKERS_DOWN, KafkaError._TRANSPORT):
            if kafka_connected:
                log.warning("Kafka broker unreachable: %s", err)
            kafka_connected = False

    consumer = Consumer({
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "error_cb": _on_error,
    })
    producer = Producer({
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "error_cb": _on_error,
    })

    consumer.subscribe([CONSUMER_TOPIC])
    log.info("Kafka consumer started bootstrap=%s topic=%s", KAFKA_BOOTSTRAP, CONSUMER_TOPIC)

    try:
        while True:
            msg = consumer.poll(timeout=_POLL_TIMEOUT)

            if msg is None:
                # poll() timed out — no message. Check if broker is reachable.
                try:
                    meta = consumer.list_topics(timeout=2.0)
                    kafka_connected = meta is not None
                except KafkaException:
                    kafka_connected = False
                continue

            if msg.error():
                err = msg.error()
                if err.code() == KafkaError._PARTITION_EOF:
                    kafka_connected = True
                    continue
                log.error("Kafka message error: %s", err)
                kafka_connected = False
                continue

            kafka_connected = True

            try:
                value = json.loads(msg.value().decode("utf-8"))
            except Exception as exc:
                log.error("Failed to decode message offset=%d: %s", msg.offset(), exc)
                consumer.commit(message=msg)
                continue

            log.debug(
                "Received job from Kafka topic=%s partition=%d offset=%d portfolioId=%s modelVersion=%s scenario=%s",
                msg.topic(), msg.partition(), msg.offset(),
                value.get("portfolioId"), value.get("modelVersion"), value.get("scenario"),
            )

            try:
                _, high = consumer.get_watermark_offsets(msg.topic_partition(), timeout=1.0)
                KAFKA_CONSUMER_LAG.set(max(0, high - msg.offset() - 1))
            except Exception:
                pass

            try:
                result = _run_calculation(value, hdfs_client, hive_client, risk_calculator)
                producer.produce(
                    PRODUCER_TOPIC,
                    key=result["portfolioId"].encode(),
                    value=json.dumps(result).encode(),
                )
                producer.flush()
                consumer.commit(message=msg)
                KAFKA_CONSUMED_TOTAL.labels(status="success").inc()
                log.info("Processed risk job portfolioId=%s offset=%d", result["portfolioId"], msg.offset())
            except Exception as exc:
                KAFKA_CONSUMED_TOTAL.labels(status="error").inc()
                log.exception("Failed to process message offset=%d: %s", msg.offset(), exc)
                # Do not commit — message will be redelivered on restart.

    except Exception as exc:
        log.exception("Unexpected error in consumer loop: %s", exc)
    finally:
        kafka_connected = False
        try:
            consumer.close()
        except Exception:
            pass


def _mock_consumer_loop() -> None:
    """Simulates periodic Kafka activity for local dev without a real broker."""
    import random

    counter = 0
    while True:
        time.sleep(10)
        counter += 1
        mock_msg = {
            "portfolioId": f"mock-portfolio-{counter % 5}",
            "modelVersion": random.choice(["v1.0", "v2.0"]),
            "scenario": "baseline",
        }
        result = _mock_run(mock_msg)
        KAFKA_CONSUMED_TOTAL.labels(status="success").inc()
        log.debug("MOCK kafka consumed portfolioId=%s result=%s", mock_msg["portfolioId"], result)
