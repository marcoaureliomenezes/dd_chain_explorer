FROM local/spark:3.5

WORKDIR /app
USER root

RUN install_packages curl wget

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# ── Pré-download dos pacotes Spark (Kafka + Avro) ────────────────────────────
# Spark 4.0.0 / Scala 2.13 — hadoop-aws + aws-sdk já estão na imagem base.
# Os JARs são baixados via Ivy para /opt/bitnami/spark/jars/ no build,
# evitando download a cada spark-submit.
# ─────────────────────────────────────────────────────────────────────────────
ENV SPARK_VERSION=4.0.0
ENV SCALA_SUFFIX=2.13

RUN echo "import sys; sys.exit(0)" > /tmp/dummy.py \
    && spark-submit --master local[1] \
         --packages "org.apache.spark:spark-sql-kafka-0-10_${SCALA_SUFFIX}:${SPARK_VERSION},org.apache.spark:spark-avro_${SCALA_SUFFIX}:${SPARK_VERSION}" \
         /tmp/dummy.py \
    && find /root/.ivy2.5.2/jars -name '*.jar' -exec cp {} /opt/bitnami/spark/jars/ \; \
    && rm -rf /root/.ivy2.5.2 /tmp/dummy.py

COPY ./src /app
RUN chmod +x /app/entrypoint.sh

COPY conf/spark-defaults.conf /opt/bitnami/spark/conf/spark-defaults.conf

ENTRYPOINT ["sleep", "infinity"]
