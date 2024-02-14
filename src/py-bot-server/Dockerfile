FROM ubuntu:latest
FROM python:3.10-slim

LABEL t="local_telegram_api_server"

RUN apt-get update && apt-get install -y make git zlib1g-dev libssl-dev gperf cmake g++

RUN git clone --recursive https://github.com/tdlib/telegram-bot-api.git

WORKDIR telegram-bot-api

RUN rm -rf build
RUN mkdir build
WORKDIR build

RUN cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX:PATH=.. ..
RUN cmake --build . --target install

WORKDIR ../..

ENTRYPOINT telegram-bot-api/bin/telegram-bot-api --local --api-id=${LOCAL_TELEGRAM_API_ID} --api-hash=${LOCAL_TELEGRAM_API_HASH}
