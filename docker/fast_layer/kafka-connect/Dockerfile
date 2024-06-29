FROM confluentinc/cp-kafka-connect-base:latest

ENV CONNECT_PLUGIN_PATH="/usr/share/java,/usr/share/confluent-hub-components,/data/connect-jars"


RUN confluent-hub install --no-prompt confluentinc/kafka-connect-jdbc:10.0.0
RUN confluent-hub install --no-prompt confluentinc/kafka-connect-azure-blob-storage:latest
RUN confluent-hub install --no-prompt confluentinc/kafka-connect-s3:latest

# Instal scylla sink connector

RUN confluent-hub install --no-prompt confluentinc/kafka-connect-cassandra:latest
RUN confluent-hub install --no-prompt confluentinc/kafka-connect-hdfs3:latest