from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mock_mode: bool = False
    log_level: str = "INFO"

    # Job parameters — injected by risk-ui when creating the Kubernetes Job
    model_version: str = "v1.0"
    portfolio_id: str = "PORTFOLIO_DEFAULT"
    scenario: str = "base"

    # Spark deployment mode:
    #   submit   — spark-submit --master local[*] (in-pod, dev/small datasets)
    #   operator — SparkApplication CRD managed by Spark Operator
    #   yarn     — spark-submit --master yarn (external Hadoop YARN cluster)
    spark_mode: str = "submit"
    spark_master: str = "local[*]"
    spark_app_name: str = "spark-calculator"

    # Hive (input data)
    hive_host: str = "hive-server"
    hive_port: int = 10000
    hive_database: str = "risk"
    hive_table: str = "risk_results"

    # Oracle (output)
    oracle_dsn: str = "localhost:1521/ORCLPDB1"
    oracle_user: str = "risk_user"
    oracle_password: str = "CHANGEME"
    oracle_table: str = "spark_risk_results"

    # Kerberos (used by init container, path shared via emptyDir)
    krb5_keytab_path: str = "/keytab/spark-calculator.keytab"
    krb5_principal: str = "spark-calc@EXAMPLE.COM"
    krb5ccname: str = "/tmp/krb5/tgt"

    model_config = ConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
