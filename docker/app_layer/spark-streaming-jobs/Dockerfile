FROM marcoaureliomenezes/dm-spark-base:1.0.0



WORKDIR /app

# COPY ./spark-submit.sh .
COPY ./src /app


ENV SPARK_MASTER_URL="spark://spark-master:7077"
ENV SPARK_SUBMIT_ARGS=""
ENV SPARK_APPLICATION_ARGS=""

ENV KAFKA_CONNECTOR="org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"
ENV SCYLLA_CONNECTOR="com.datastax.spark:spark-cassandra-connector_2.12:3.5.0"



ENTRYPOINT [ "sleep", "infinity" ]

