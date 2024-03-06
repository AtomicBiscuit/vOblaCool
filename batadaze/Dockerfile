FROM postgres:latest

ENV POSTGRES_USER docker
ENV POSTGRES_PASSWORD docker
ENV POSTGRES_DB DB

RUN apt-get update && apt-get install python3-pip -y && pip install --upgrade pip && $ pip install -r requirements.txt