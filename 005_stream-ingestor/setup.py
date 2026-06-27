"""
Build backend: setuptools with classic setup().

Chosen to demonstrate a third Python packaging style alongside
poetry (002_risk-engine) and requirements.txt (004_oracle-reporter).
For new projects prefer pyproject.toml + setuptools or poetry.
"""
from setuptools import setup, find_packages

setup(
    name="stream-ingestor",
    version="0.1.0",
    description="Spark Structured Streaming: Kafka risk-results → HDFS Parquet + Hive",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.12",
    install_requires=[
        # PySpark — Structured Streaming with Kafka source
        "pyspark>=3.5.0",
        # Config and observability
        "pydantic-settings>=2.6.0",
        "prometheus-client>=0.21.0",
    ],
    extras_require={
        # Hadoop/Hive/SASL deps require C extensions (libsasl2-dev, libkrb5-dev, g++).
        # In MOCK_MODE=true these are never imported.
        # Install with: pip install -e ".[hadoop]"
        "hadoop": [
            "PyHive[hive]>=0.7.0",
            "sasl>=0.3.1",
            "thrift>=0.16.0",
            "thrift-sasl>=0.4.3",
        ],
        "dev": [
            "pytest>=8.0.0",
            "ruff>=0.8.0",
        ],
    },
)
