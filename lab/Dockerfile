# Lab image: Spark 3.5 (local mode) + Iceberg 1.12 + DuckDB + marimo, all talking to Horizon.
# python:3.12-slim is Debian trixie (no OpenJDK 17), so pin bookworm. setuptools: PySpark 3.5 still imports distutils.
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*
ARG ICEBERG=1.12.0
RUN mkdir -p /opt/jars && cd /opt/jars \
    && curl -sSfLO https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-3.5_2.12/${ICEBERG}/iceberg-spark-runtime-3.5_2.12-${ICEBERG}.jar \
    && curl -sSfLO https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-gcp-bundle/${ICEBERG}/iceberg-gcp-bundle-${ICEBERG}.jar
RUN pip install --no-cache-dir setuptools "pyspark==3.5.9" "duckdb>=2.0" "marimo>=0.9" pandas pyarrow pytest \
    "snowflake-connector-python>=3.12" cryptography
# Pre-install DuckDB extensions so notebooks work offline-ish.
RUN python -c "import duckdb; c=duckdb.connect(); c.install_extension('httpfs'); c.install_extension('iceberg')"
ENV ICEBERG_JARS=/opt/jars PYTHONPATH=/workspace/src:/workspace PYTHONWARNINGS=ignore
WORKDIR /workspace
EXPOSE 2718
# Token required: the lab can reach your Snowflake account, so other local pages must not drive it.
CMD ["sh", "-c", "exec marimo edit --host 0.0.0.0 --port 2718 --headless --token-password \"$LAB_TOKEN\" lab/notebooks"]
