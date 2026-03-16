FROM apache/spark:3.5.8-scala2.12-java17-python3-ubuntu

USER root

RUN apt-get update && apt-get install -y --no-install-recommends curl wget python3-pip && \
    rm -rf /var/lib/apt/lists/*

# ── Pré-download dos pacotes Spark via spark-shell ───────────────────────────
# Spark 3.5.8 / Scala 2.12 — cada pacote num RUN separado para melhor cache.
# Os JARs são baixados via Ivy para ~/.ivy2/jars e disponibilizados no classpath.
# ─────────────────────────────────────────────────────────────────────────────

# Kafka connector
RUN /opt/spark/bin/spark-shell \
    --packages "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.8" \
    --repositories https://repo1.maven.org/maven2 \
    -i /dev/null 2>&1 | tail -5 || true

# Avro support
RUN /opt/spark/bin/spark-shell \
    --packages "org.apache.spark:spark-avro_2.12:3.5.8" \
    --repositories https://repo1.maven.org/maven2 \
    -i /dev/null 2>&1 | tail -5 || true

# S3A (Hadoop AWS) — needed for s3a:// checkpoint paths
RUN /opt/spark/bin/spark-shell \
    --packages "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262" \
    --repositories https://repo1.maven.org/maven2 \
    -i /dev/null 2>&1 | tail -5 || true

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

COPY ./src /app
RUN chmod +x /app/entrypoint.sh

COPY conf/spark-defaults.conf /opt/spark/conf/spark-defaults.conf

ENTRYPOINT ["sleep", "infinity"]
