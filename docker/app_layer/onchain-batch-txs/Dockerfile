FROM python:3.8-slim-buster


ENV HADOOP_VERSION=3.1.1
ENV HADOOP_HOME='/opt/hadoop'
ENV HIVE_HOME='/opt/hive'
ENV JAVA_HOME='/usr/lib/jvm/java-1.11.0-openjdk-amd64'

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

ENV PATH ${HADOOP_HOME}/bin/:$PATH

WORKDIR /app

COPY ./requirements.txt /app
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

ENV PATH ${JAVA_HOME}/bin/:$PATH

COPY ./src /app


ENTRYPOINT [ "sleep", "infinity" ]