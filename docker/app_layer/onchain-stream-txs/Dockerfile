FROM python:3.12-slim



WORKDIR /app

RUN echo "UI"

COPY ./requirements.txt /app
RUN pip install --upgrade pip && \
    pip install -r requirements.txt


COPY ./src /app


ENTRYPOINT [ "sleep", "infinity" ]