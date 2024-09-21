FROM bitnami/spark:3.5.1

WORKDIR /app
USER root
RUN install_packages curl

ENV AVRO_CONNECTOR="org.apache.spark:spark-avro_2.12:3.5.0"
ENV ICEBERG_RUNTIME_CONNECTOR="org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.1"
ENV ICEBERG_EXTENSIONS_CONNECTOR="org.apache.iceberg:iceberg-spark-extensions-3.5_2.12:1.4.1"

RUN /opt/bitnami/spark/bin/spark-shell --packages $AVRO_CONNECTOR --repositories https://repo1.maven.org/maven2
RUN /opt/bitnami/spark/bin/spark-shell --packages $ICEBERG_RUNTIME_CONNECTOR --repositories https://repo1.maven.org/maven2
RUN /opt/bitnami/spark/bin/spark-shell --packages $ICEBERG_EXTENSIONS_CONNECTOR --repositories https://repo1.maven.org/maven2

COPY ./src /app
COPY conf/spark-defaults.conf /opt/bitnami/spark/conf/spark-defaults.conf

ENTRYPOINT [ "sleep", "infinity" ]