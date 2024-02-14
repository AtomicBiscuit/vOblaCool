FROM ubuntu:20.04
FROM python:3.10-slim

RUN apt-get update && apt-get install -y make git zlib1g-dev libssl-dev gperf cmake g++

RUN git clone --recursive https://github.com/tdlib/telegram-bot-api.git

WORKDIR telegram-bot-api

RUN rm -rf build
RUN mkdir build
WORKDIR build

RUN cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX:PATH=.. ..
RUN cmake --build . --target install

WORKDIR ../..

EXPOSE 8081

# Честно не знаю как передать сюда переменные окружения, но здесь они должны быть TODO: Добавить
ENTRYPOINT telegram-bot-api/bin/telegram-bot-api --local --api-id= --api-hash=