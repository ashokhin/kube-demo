from typing import Optional

from pydantic import ConfigDict, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    log_level: str = "INFO"

    # Master mock switch — sets the default for all three subsystem flags below.
    mock_mode: bool = False

    # Per-subsystem mock flags. When None, falls back to mock_mode.
    kafka_mock_mode: Optional[bool] = None
    hdfs_mock_mode: Optional[bool] = None
    hive_mock_mode: Optional[bool] = None

    @model_validator(mode="after")
    def _resolve_mock_flags(self) -> "Settings":
        if self.kafka_mock_mode is None:
            self.kafka_mock_mode = self.mock_mode
        if self.hdfs_mock_mode is None:
            self.hdfs_mock_mode = self.mock_mode
        if self.hive_mock_mode is None:
            self.hive_mock_mode = self.mock_mode
        return self

    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_topic_risk_results: str = "risk-results"
    kafka_consumer_group: str = "stream-ingestor-group"

    # HDFS output — written as Parquet, partitioned by date
    hdfs_url: str = "hdfs://namenode.hadoop.internal:8020"
    hdfs_output_path: str = "/data/risk-aggregates"

    # Hive — aggregated summary table
    hive_host: str = "hive.hadoop.internal"
    hive_port: int = 10000
    hive_database: str = "risk"

    # Kerberos
    krb5ccname: str = "/tmp/krb5/tgt"
    krb5_keytab_path: str = "/keytab/stream-ingestor.keytab"
    krb5_principal: str = "stream-ingestor@EXAMPLE.COM"

    # Spark Structured Streaming micro-batch interval
    trigger_interval_seconds: int = 30

    # Prometheus metrics server port
    metrics_port: int = 9090

    model_config = ConfigDict(env_file=".env")


settings = Settings()
