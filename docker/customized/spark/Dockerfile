FROM bitnami/spark:3.5.1


WORKDIR /app

# COPY ./spark-submit.sh .

USER root
RUN install_packages curl wget

ENV AVRO_CONNECTOR="org.apache.spark:spark-avro_2.12:3.5.0"
ENV ICEBERG_CONNECTOR="org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.1"
ENV DELTA_CONNECTOR="io.delta:delta-core_2.12:1.2.1"

# Install the spark-cassandra-connector

RUN /opt/bitnami/spark/bin/spark-shell --packages $AVRO_CONNECTOR --repositories https://repo1.maven.org/maven2

RUN /opt/bitnami/spark/bin/spark-shell --packages $ICEBERG_CONNECTOR --repositories https://repo1.maven.org/maven2

RUN /opt/bitnami/spark/bin/spark-shell --packages $DELTA_CONNECTOR --repositories https://repo1.maven.org/maven2