from typing import Optional

from pydantic import ConfigDict, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # HTTP server
    port: int = 8081
    log_level: str = "INFO"

    # Master mock switch — sets the default for all three subsystem flags below.
    # Individual flags override it when set explicitly.
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

    # HDFS connection
    hdfs_url: str = "hdfs://namenode:8020"
    hdfs_input_path: str = "/data/risk/input"
    hdfs_output_path: str = "/data/risk/output"

    # Hive connection
    hive_host: str = "hive-server"
    hive_port: int = 10000
    hive_database: str = "risk"

    # Kerberos — paths are mounted from Secrets and ConfigMap in Kubernetes.
    # In local mock mode these are not used.
    krb5_keytab_path: str = "/keytab/risk-engine.keytab"
    krb5_principal: str = "risk-engine@EXAMPLE.COM"
    # KRB5CCNAME points to the ticket cache shared with the krb5-renewer sidecar.
    krb5ccname: str = "/tmp/krb5/tgt"

    model_config = ConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
