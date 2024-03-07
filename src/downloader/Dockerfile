FROM ubuntu:latest
FROM python:3.10-slim

LABEL t="downloader"

WORKDIR /app
COPY batadaze batadaze
COPY src/downloader .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install -r ./batadaze/requirements.txt

ENTRYPOINT python load.py
