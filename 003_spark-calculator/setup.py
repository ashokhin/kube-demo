# Build backend: setuptools
#
# setuptools is the oldest and most widely-used Python build system.
# Required when:
#   - Your project has C extensions (Cython, pybind11, cffi)
#   - You have a complex setup.py with custom build steps
#   - You're maintaining a legacy project that hasn't migrated to pyproject.toml
#
# Migration note: setuptools now supports pyproject.toml (PEP 517/518).
# This file uses the classic setup() call for maximum compatibility with
# legacy CI systems that still call `python setup.py install`.
#
# Modern equivalent: move all config to pyproject.toml + [tool.setuptools].

from setuptools import setup, find_packages

setup(
    name="spark-calculator",
    version="0.1.0",
    description="PySpark risk calculator — reads Hive, computes risk, writes to Oracle",
    python_requires=">=3.12",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pydantic-settings>=2.6.0",
        "pyspark>=3.5.0",
        # oracledb: official Oracle thin driver (no Oracle Client needed)
        "oracledb>=2.0.0",
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
            "pytest-asyncio>=0.24.0",
            "ruff>=0.8.0",
        ],
    },
)
