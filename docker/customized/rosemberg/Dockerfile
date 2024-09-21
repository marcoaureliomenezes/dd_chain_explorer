FROM bitnami/spark:3.5.1

WORKDIR /app
USER root
RUN install_packages curl

ENV AVRO_CONNECTOR="org.apache.spark:spark-avro_2.12:3.5.1"
ENV ICEBERG_CONNECTOR="org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1"
ENV NESSIE_EXTENSIONS="org.projectnessie.nessie-integrations:nessie-spark-extensions-3.5_2.12:0.95.0"
ENV S3_BUNDLE_CONECTOR="software.amazon.awssdk:bundle:2.17.178"
ENV S3_SDK_CONECTOR="software.amazon.awssdk:url-connection-client:2.17.178"


RUN /opt/bitnami/spark/bin/spark-shell --packages $AVRO_CONNECTOR --repositories https://repo1.maven.org/maven2
RUN /opt/bitnami/spark/bin/spark-shell --packages $ICEBERG_CONNECTOR --repositories https://repo1.maven.org/maven2
RUN /opt/bitnami/spark/bin/spark-shell --packages $NESSIE_EXTENSIONS --repositories https://repo1.maven.org/maven2
RUN /opt/bitnami/spark/bin/spark-shell --packages $S3_BUNDLE_CONECTOR --repositories https://repo1.maven.org/maven2
RUN /opt/bitnami/spark/bin/spark-shell --packages $S3_SDK_CONECTOR --repositories https://repo1.maven.org/maven2

COPY conf/spark-defaults.conf /opt/bitnami/spark/conf/spark-defaults.conf

COPY requirements.txt .
RUN pip install -r requirements.txt

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root",  "--NotebookApp.token=''"]
