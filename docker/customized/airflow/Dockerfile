FROM apache/airflow:latest-python3.11

USER root
ENV JAVA_HOME='/usr/lib/jvm/java-17-openjdk-amd64'

# Instala dependências do Spark
RUN apt-get update && apt-get install -y \
    wget \
    default-jdk \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /opt
USER airflow


COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

# COPY mnt/dags /opt/airflow/dags
# COPY mnt/airflow.cfg /opt/airflow/airflow.cfg



