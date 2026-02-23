FROM python:3.12-slim



WORKDIR /app

RUN echo "UI"

COPY ./requirements.txt /app
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    ln -sf /usr/local/bin/python3 /usr/local/bin/python


COPY ./src /app
