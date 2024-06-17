FROM bitnami/spark


WORKDIR /app

# COPY ./spark-submit.sh .

USER root
RUN install_packages curl


ENV SPARK_MASTER_URL="spark://spark-master:7077"
ENV SPARK_SUBMIT_ARGS=""
ENV SPARK_APPLICATION_ARGS=""

ENV KAFKA_CONNECTOR="org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"
ENV SCYLLA_CONNECTOR="com.datastax.spark:spark-cassandra-connector_2.12:3.5.0"



# Install the spark-cassandra-connector

RUN /opt/bitnami/spark/bin/spark-shell --packages $SCYLLA_CONNECTOR --repositories https://repo1.maven.org/maven2

# Install the spark-kafka-connector

RUN /opt/bitnami/spark/bin/spark-shell --packages $KAFKA_CONNECTOR --repositories https://repo1.maven.org/maven2

COPY ./src /app

ENTRYPOINT [ "sleep", "infinity" ]

