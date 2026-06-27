"""
Spark session factory.

Three deployment modes, selected by SPARK_MODE env var:

  submit   — spark-submit --master local[*]
             PySpark runs entirely inside the Kubernetes Job pod.
             Simple, no external dependencies. Best for dev and small datasets.

  operator — spark-submit --master k8s://...
             Spark Operator creates a Driver pod + Executor pods dynamically.
             The Job pod acts as the submit client and exits after submission.
             Executors are managed by the operator, not by the Job pod.
             See: 006_gitops/helm/spark-calculator/templates/spark-application.yaml

  yarn     — spark-submit --master yarn
             The Job pod submits to an external YARN ResourceManager.
             Executors run on YARN NodeManagers, not in Kubernetes.
             Useful during migration from a legacy Hadoop cluster to Kubernetes.
             Requires HADOOP_CONF_DIR pointing to core-site.xml / yarn-site.xml.
"""
import logging
import os

logger = logging.getLogger(__name__)


def create_spark_session(mode: str, app_name: str, mock_mode: bool = False):
    """
    Create a SparkSession configured for the given deployment mode.
    Returns None in mock mode.
    """
    if mock_mode:
        logger.info("MOCK: SparkSession not created (MOCK_MODE=true)")
        return None

    from pyspark.sql import SparkSession

    builder = SparkSession.builder.appName(app_name)

    if mode == "submit":
        # Local mode: all Spark processing in this pod, no cluster needed.
        builder = builder.master("local[*]")
        logger.info("Spark mode: local submit (master=local[*])")

    elif mode == "operator":
        # Spark Operator mode: Driver runs here, Executors are created dynamically.
        # The SparkApplication CRD in 006_gitops handles executor configuration.
        k8s_master = os.environ.get("SPARK_KUBERNETES_MASTER", "k8s://https://kubernetes.default.svc")
        image = os.environ.get("SPARK_EXECUTOR_IMAGE", "spark:3.5")
        namespace = os.environ.get("KUBERNETES_NAMESPACE", "hadoop-demo-dev")
        builder = (builder
                   .master(k8s_master)
                   .config("spark.executor.instances", "2")
                   .config("spark.kubernetes.container.image", image)
                   .config("spark.kubernetes.namespace", namespace)
                   .config("spark.kubernetes.authenticate.driver.serviceAccountName", "spark-calculator"))
        logger.info("Spark mode: operator (master=%s)", k8s_master)

    elif mode == "yarn":
        # YARN mode: submit to external Hadoop cluster.
        # Requires HADOOP_CONF_DIR with core-site.xml and yarn-site.xml mounted from ConfigMap.
        hadoop_conf = os.environ.get("HADOOP_CONF_DIR", "/etc/hadoop")
        builder = (builder
                   .master("yarn")
                   .config("spark.submit.deployMode", "cluster")
                   .config("spark.hadoop.security.authentication", "kerberos")
                   .config("spark.yarn.keytab", os.environ.get("KRB5_KEYTAB_PATH", ""))
                   .config("spark.yarn.principal", os.environ.get("KRB5_PRINCIPAL", "")))
        logger.info("Spark mode: YARN (HADOOP_CONF_DIR=%s)", hadoop_conf)

    else:
        raise ValueError(f"Unknown SPARK_MODE: {mode}. Expected: submit, operator, yarn")

    # Enable Hive support for reading Hive metastore tables
    spark = builder.enableHiveSupport().getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
