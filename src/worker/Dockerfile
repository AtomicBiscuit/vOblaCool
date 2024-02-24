FROM ubuntu:latest
FROM python:3.10-slim

LABEL t="message-queue"

WORKDIR /app
COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENTRYPOINT python worker.py
