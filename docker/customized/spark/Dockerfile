FROM bitnami/spark:3.5.3


WORKDIR /app


USER root
RUN install_packages curl wget

RUN /opt/bitnami/spark/bin/spark-shell --packages "org.apache.spark:spark-avro_2.12:3.5.1"                                        --repositories https://repo1.maven.org/maven2
RUN /opt/bitnami/spark/bin/spark-shell --packages "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1"                              --repositories https://repo1.maven.org/maven2
RUN /opt/bitnami/spark/bin/spark-shell --packages "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1"                       --repositories https://repo1.maven.org/maven2
RUN /opt/bitnami/spark/bin/spark-shell --packages "org.projectnessie.nessie-integrations:nessie-spark-extensions-3.5_2.12:0.99.0" --repositories https://repo1.maven.org/maven2
RUN /opt/bitnami/spark/bin/spark-shell --packages "org.apache.iceberg:iceberg-aws-bundle:1.6.1"                                   --repositories https://repo1.maven.org/maven2
