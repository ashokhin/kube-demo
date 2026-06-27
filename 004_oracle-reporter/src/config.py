from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mock_mode: bool = False
    log_level: str = "INFO"

    # Oracle (input data)
    oracle_dsn: str = "localhost:1521/ORCLPDB1"
    oracle_user: str = "reporter_user"
    oracle_password: str = "CHANGEME"
    oracle_source_table: str = "spark_risk_results"

    # HDFS (output — report files)
    hdfs_url: str = "hdfs://namenode:8020"
    hdfs_output_path: str = "/data/reports"

    # Kerberos (init container writes TGT here before main container starts)
    krb5_keytab_path: str = "/keytab/oracle-reporter.keytab"
    krb5_principal: str = "oracle-reporter@EXAMPLE.COM"
    krb5ccname: str = "/tmp/krb5/tgt"

    # Report configuration
    report_lookback_days: int = 30

    model_config = ConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
