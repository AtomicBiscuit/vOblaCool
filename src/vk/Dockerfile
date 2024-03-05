FROM ubuntu:latest
FROM python:3.10-slim

LABEL t="vk_loader"

WORKDIR /app
COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENTRYPOINT python vk_loader.py
