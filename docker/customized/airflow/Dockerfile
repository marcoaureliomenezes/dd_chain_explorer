FROM apache/airflow:latest-python3.11

USER root


ENV HADOOP_VERSION=3.1.1
ENV SPARK_HOME='/opt/spark'
ENV HADOOP_HOME='/opt/hadoop'
ENV HIVE_HOME='/opt/hive'
ENV JAVA_HOME='/usr/lib/jvm/java-17-openjdk-amd64'

# Instala dependências do Spark
RUN apt-get update && apt-get install -y \
    wget \
    default-jdk \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/hadoop

# Baixando e instalando o Apache Hadoop
RUN wget -c -O hadoop.tar.gz https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz && \
tar xvf hadoop.tar.gz --directory=/opt/hadoop --exclude=hadoop-${HADOOP_VERSION}/share/doc --strip 1 && \
rm -rf hadoop.tar.gz && \
ln -s /opt/hadoop/etc/hadoop /etc/hadoop && \
mkdir /opt/hadoop/logs && \
mkdir /hadoop-data


WORKDIR /opt

RUN apt-get install -yqq \
    wget \
    procps && \
    wget -c -O hive.tar.gz https://archive.apache.org/dist/hive/hive-4.0.0-alpha-2/apache-hive-4.0.0-alpha-2-bin.tar.gz && \
    tar xvf hive.tar.gz && \
    rm hive.tar.gz && \
    mv apache-hive-4.0.0-alpha-2-bin hive && \
    wget -O ${HIVE_HOME}/lib/postgresql-jdbc.jar https://jdbc.postgresql.org/download/postgresql-42.2.14.jar && \
    apt-get --purge remove -yqq wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV PATH ${HIVE_HOME}/bin/:$PATH
ENV PATH ${HADOOP_HOME}/bin/:$PATH

USER airflow


COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

COPY mnt/dags /opt/airflow/dags
COPY mnt/airflow.cfg /opt/airflow/airflow.cfg



