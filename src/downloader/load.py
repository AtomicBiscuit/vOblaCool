"""
Управление состоянием загружаемых видеозаписей
"""
import json
import threading
from http import HTTPStatus
from typing import NoReturn, Optional
from urllib.parse import urlparse

import flask
import pika
import requests as req
from decouple import config
from flask import request, Response
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import BasicProperties, Basic
from pytube import extract
from pytube.exceptions import RegexMatchError

TBOT_HOST = config('TELEGRAM_BOT_HANDLER_HOST')
TBOT_PORT = config('TELEGRAM_BOT_HANDLER_PORT')

RMQ_HOST = config('RMQ_HOST')
RMQ_PORT = config('RMQ_PORT')


class Loader:
    """
    Проверяет url на корректность, определяет класс-загрузчик, общается с TBotHandler

    :param video_id: Уникальный идентификатор видеозаписи
    :type video_id: :class: `int`
    :param netlocs: Список всех поддерживаемых доменов
    :type netlocs: :class: `Dict[List[str]]`
    :param app: Flask-приложение для общения с другими модулями
    :type app: :class: `flask.app.Flask`
    :param host: Хост для запуска
    :type host: :class: `str`
    :param port: Порт для запуска
    :type port: :class: `int`
    :param connection: Объект соединения с RabbitMQ
    :type connection: :class: `pika.BlockingConnection`
    :param channel: Канал для общения с RabbitMQ
    :type channel: :class: `pika.BlockingChannel`
    :param RPC_connection: Объект соединения с RabbitMQ для получения ответных сообщений
    :param RPC_connection: (non-thread-safe) Использовать только внутри одного потока
    :type RPC_connection: :class: `pika.BlockingConnection`
    :param RPC_channel: Канал для общения с RabbitMQ
    :type RPC_channel: :class: `pika.BlockingChannel`
    """
    netlocs = {
        'youtube': [
            'www.youtube.com',
            'www.youtube-nocookie.com',
            'm.youtube.com'
            'youtube.com',
            'youtu.be'
        ]
    }

    def __init__(self):
        self.app = flask.Flask(__name__)
        self.host = config('DOWNLOADER_HOST')
        self.port = int(config('DOWNLOADER_PORT'))
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, heartbeat=0))
        self.RPC_connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, heartbeat=0))
        self.channel = self.connection.channel()
        self.RPC_channel = self.RPC_connection.channel()
        self.channel.queue_declare('task_queue')
        self.RPC_channel.queue_declare('answer_queue')
        self.RPC_channel.basic_consume('answer_queue', self.__process_answer, auto_ack=True)
        self.__configure_router()

    @staticmethod
    def __process_answer(channel: BlockingChannel, method: Basic.Deliver, properties: BasicProperties,
                         body: bytes) -> NoReturn:
        """
        Обработка полученных от worker-а ответов
        """
        payload = json.loads(body.decode("utf-8"))
        if payload['type'] == 'download':
            # TODO: Сохранять file_id в БД
            req.post(f'http://{TBOT_HOST}:{TBOT_PORT}/api/download/complete', json=payload)

    @staticmethod
    async def __main_page() -> Response:
        """
        Обрабатывает GET-запросы на главную страницу

        :return: Response 200
        """
        return Response(f'Ok', HTTPStatus.OK)

    @staticmethod
    def extract_id(url_raw: str, host: str) -> Optional[str]:
        """
        Проверяет ссылку на принадлежность домену

        :param host: Видео-хостинг
        :param url_raw: url для проверки
        :return: video_id если ссылка корректна, иначе None
        """
        url = urlparse(url_raw)
        if url.netloc not in Loader.netlocs[host]:
            return None
        try:
            if host == 'youtube':
                return extract.video_id(url_raw)
        except RegexMatchError as e:
            return None

    async def __download_start(self) -> Response:
        """
        Обрабатывает POST-запрос на начало загрузки, определяет видео-хостинг, добавляет задачу в очередь

        :return: Response 200 если ссылка верная, BadResponse 404 иначе
        """
        payload = request.json
        url_raw = payload['url']
        chat_id = payload['chat_id']
        message_id = payload['message_id']
        video_id = None
        hosting = None
        if self.extract_id(url_raw, 'youtube'):
            video_id = self.extract_id(url_raw, 'youtube')
            hosting = 'youtube'
        if video_id is None:
            return Response(status=HTTPStatus.NOT_FOUND)
        self.channel.basic_publish(
            exchange='',
            routing_key='task_queue',
            body=json.dumps({
                'type': 'download',
                'url': url_raw,
                'video_id': video_id,
                'chat_id': chat_id,
                'message_id': message_id,
                'hosting': hosting
            }),
        )
        return Response(status=HTTPStatus.OK)

    def __configure_router(self) -> NoReturn:
        """
        Прописывает все пути для взаимодействия с Flask
        """
        self.app.add_url_rule('/', view_func=self.__main_page, methods=['GET'])
        self.app.add_url_rule('/api/download/start', view_func=self.__download_start, methods=['POST'])

    def run(self, debug: bool = True) -> NoReturn:
        """
        Запускает приложение

        :param debug: Запуск приложения в debug режиме
        """
        threading.Thread(target=self.RPC_channel.start_consuming).start()
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False)


if __name__ == '__main__':
    app = Loader()
    app.run()
    app.connection.close()
