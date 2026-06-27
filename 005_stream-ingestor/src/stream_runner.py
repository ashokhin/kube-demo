"""
Spark Structured Streaming pipeline.

Data flow:
  Kafka topic `risk-results`
    └─► parse JSON (portfolioId, modelVersion, riskScore, var95, var99, totalValue)
        └─► write Parquet to HDFS   (raw, partitioned by dt=YYYY-MM-DD)
            └─► aggregate per dt/modelVersion
                └─► write aggregated summary to Hive (risk.risk_aggregates)

Trigger mode: ProcessingTime (micro-batch every N seconds).
Checkpoint is stored on HDFS to enable exactly-once delivery semantics.

Mock mode: replaces Kafka source with a Rate source (synthetic data every second).
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

from src.config import settings
from src.metrics import (
    BATCH_DURATION,
    BATCH_FAILURES,
    HDFS_WRITES,
    HIVE_WRITES,
    LAST_BATCH_TIMESTAMP,
    RECORDS_PROCESSED,
)

log = logging.getLogger(__name__)


def _create_spark(mock_mode: bool) -> SparkSession:
    from pyspark.sql import SparkSession  # noqa: PLC0415
    builder = (
        SparkSession.builder
        .appName("stream-ingestor")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.warehouse.dir", settings.hdfs_output_path)
    )
    if not mock_mode:
        builder = (
            builder
            .config("spark.hadoop.fs.defaultFS", settings.hdfs_url)
            .config("spark.hadoop.security.authentication", "kerberos")
            .config("spark.hadoop.security.authorization", "true")
            .enableHiveSupport()
        )
    return builder.getOrCreate()


def _kafka_source(spark: SparkSession) -> DataFrame:
    from pyspark.sql import functions as F  # noqa: PLC0415
    from pyspark.sql.types import (  # noqa: PLC0415
        DoubleType, StringType, StructField, StructType,
    )
    result_schema = StructType([
        StructField("portfolioId", StringType(), True),
        StructField("modelVersion", StringType(), True),
        StructField("scenario", StringType(), True),
        StructField("riskScore", DoubleType(), True),
        StructField("var95", DoubleType(), True),
        StructField("var99", DoubleType(), True),
        StructField("totalValue", DoubleType(), True),
        StructField("durationSeconds", DoubleType(), True),
    ])
    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", settings.kafka_topic_risk_results)
        .option("startingOffsets", "latest")
        .option("kafka.group.id", settings.kafka_consumer_group)
        .load()
        .select(
            F.col("key").cast("string").alias("kafka_key"),
            F.from_json(F.col("value").cast("string"), result_schema).alias("data"),
            F.col("timestamp").alias("kafka_timestamp"),
        )
        .select("kafka_key", "data.*", "kafka_timestamp")
        .withColumn("dt", F.date_format(F.col("kafka_timestamp"), "yyyy-MM-dd"))
    )


_MOCK_ROWS = [
    {"portfolioId": "p001", "modelVersion": "v1.0", "scenario": "baseline",
     "riskScore": 0.22, "var95": 9000.0, "var99": 13000.0, "totalValue": 900_000.0, "durationSeconds": 0.05},
    {"portfolioId": "p002", "modelVersion": "v2.0", "scenario": "stress",
     "riskScore": 0.38, "var95": 18000.0, "var99": 25000.0, "totalValue": 1_200_000.0, "durationSeconds": 0.05},
    {"portfolioId": "p003", "modelVersion": "v1.0", "scenario": "baseline",
     "riskScore": 0.15, "var95": 6000.0, "var99": 9000.0, "totalValue": 600_000.0, "durationSeconds": 0.05},
]


def _mock_source(spark: SparkSession) -> DataFrame:
    """Rate source that emits synthetic rows — no Kafka needed."""
    from pyspark.sql import functions as F  # noqa: PLC0415
    rows = spark.createDataFrame(
        [tuple(r[k] for k in ("portfolioId", "modelVersion", "scenario",
                               "riskScore", "var95", "var99", "totalValue"))
         for r in _MOCK_ROWS],
        schema=["portfolioId", "modelVersion", "scenario",
                "riskScore", "var95", "var99", "totalValue"],
    )
    return (
        rows
        .withColumn("durationSeconds", F.lit(0.05))
        .withColumn("dt", F.lit(time.strftime("%Y-%m-%d")))
    )


def _mock_batch(rows: list[dict]) -> None:
    """Pure-Python micro-batch for mock mode — no Spark/JVM required."""
    if not rows:
        return
    start = time.monotonic()
    count = len(rows)
    dt = time.strftime("%Y-%m-%d")
    # Group by (dt, modelVersion) and aggregate
    groups: dict[tuple, list] = {}
    for row in rows:
        key = (dt, row["modelVersion"])
        groups.setdefault(key, []).append(row)
    for (grp_dt, mv), grp_rows in groups.items():
        var99_vals = [r["var99"] for r in grp_rows]
        log.debug(
            "MOCK agg dt=%s modelVersion=%s count=%d avg_var99=%.0f max_var99=%.0f",
            grp_dt, mv, len(grp_rows),
            sum(var99_vals) / len(var99_vals),
            max(var99_vals),
        )
    elapsed = time.monotonic() - start
    RECORDS_PROCESSED.inc(count)
    BATCH_DURATION.observe(elapsed)
    LAST_BATCH_TIMESTAMP.set(time.time())
    log.info("MOCK micro-batch done count=%d duration=%.3fs", count, elapsed)


def _process_batch(batch_df: DataFrame, batch_id: int) -> None:
    from pyspark.sql import functions as F  # noqa: PLC0415
    if batch_df.isEmpty():
        log.debug("Micro-batch %d: empty, skipping", batch_id)
        return

    start = time.monotonic()
    count = batch_df.count()
    log.info("Micro-batch %d: processing %d records", batch_id, count)

    try:
        # Write raw results as Parquet to HDFS, partitioned by date.
        if not settings.hdfs_mock_mode:
            (
                batch_df.write
                .partitionBy("dt")
                .mode("append")
                .parquet(f"{settings.hdfs_output_path}/raw")
            )
            HDFS_WRITES.labels(status="success").inc()

        # Aggregate: min/max/avg VaR per (dt, modelVersion)
        agg_df = batch_df.groupBy("dt", "modelVersion").agg(
            F.count("*").alias("record_count"),
            F.avg("riskScore").alias("avg_risk_score"),
            F.avg("var95").alias("avg_var95"),
            F.avg("var99").alias("avg_var99"),
            F.max("var99").alias("max_var99"),
            F.sum("totalValue").alias("total_portfolio_value"),
        )

        if not settings.hive_mock_mode:
            agg_df.write.mode("append").insertInto(f"{settings.hive_database}.risk_aggregates")
            HIVE_WRITES.labels(status="success").inc()
        else:
            log.debug("MOCK: aggregated batch_id=%d\n%s", batch_id, agg_df.toPandas().to_string())

        elapsed = time.monotonic() - start
        RECORDS_PROCESSED.inc(count)
        BATCH_DURATION.observe(elapsed)
        LAST_BATCH_TIMESTAMP.set(time.time())
        log.info("Micro-batch %d done count=%d duration=%.2fs", batch_id, count, elapsed)

    except Exception as exc:
        BATCH_FAILURES.inc()
        HDFS_WRITES.labels(status="error").inc()
        log.exception("Micro-batch %d failed: %s", batch_id, exc)
        raise


def run_streaming(mock_mode: bool = False) -> None:
    if mock_mode:
        # Pure-Python path — no JVM required.
        # Loop indefinitely to keep the Deployment pod alive, emitting a
        # synthetic micro-batch every trigger_interval_seconds.
        log.info("MOCK streaming loop started interval=%ds", settings.trigger_interval_seconds)
        while True:
            _mock_batch(_MOCK_ROWS)
            time.sleep(settings.trigger_interval_seconds)
        return

    spark = _create_spark(mock_mode)

    df = _kafka_source(spark)

    query = (
        df.writeStream
        .foreachBatch(_process_batch)
        .trigger(processingTime=f"{settings.trigger_interval_seconds} seconds")
        .option("checkpointLocation", f"{settings.hdfs_output_path}/_checkpoints/stream-ingestor")
        .start()
    )
    log.info("Spark Structured Streaming query started trigger=%ds", settings.trigger_interval_seconds)
    query.awaitTermination()
