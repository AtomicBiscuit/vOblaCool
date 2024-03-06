"""
Управление состоянием загружаемых видеозаписей
"""
import json
import threading
import re
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

    :cvar `dict[list[str]]` netlocs: Список всех поддерживаемых доменов
    :ivar `flask.app.Flask` app: Flask-приложение для общения с другими модулями
    :ivar `str` host: Хост для запуска
    :ivar `int` port: Порт для запуска
    :ivar `pika.adapters.blocking_connection.BlockingConnection` connection: Объект соединения с RabbitMQ
    :ivar `pika.adapters.blocking_connection.BlockingChannel` channel: Канал для общения с RabbitMQ
    :ivar `pika.adapters.blocking_connection.BlockingConnection` RPC_connection: Объект соединения с RabbitMQ для\
    получения ответных сообщений. (Non-thread-safe) Использовать только внутри одного потока
    :ivar `pika.adapters.blocking_connection.BlockingChannel` RPC_channel: Канал для общения с RabbitMQ
    """
    netlocs = {
        'youtube': [
            'www.youtube.com',
            'www.youtube-nocookie.com',
            'm.youtube.com'
            'youtube.com',
            'youtu.be'
        ],
        'vk': [
            'vk.com',
            'vk.ru',
            'm.vk.com',
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
        self.RPC_channel.basic_consume('answer_queue', self.process_answer, auto_ack=True)
        self.configure_router()

    def process_answer(self, channel: BlockingChannel, method: Basic.Deliver, properties: BasicProperties,
                       body: bytes) -> NoReturn:
        """
        Обработка полученных от worker-а ответов
        """
        payload: dict = json.loads(body.decode("utf-8"))
        if payload['type'] == 'download':
            # TODO: Сохранять file_id в БД
            if payload.get('payload_id', None) is None:
                req.post(f'http://{TBOT_HOST}:{TBOT_PORT}/api/download/complete', json=payload)
            else:
                chats = []
                for chat in chats:
                    req.post(f'http://{TBOT_HOST}:{TBOT_PORT}/api/download/complete', json=payload | {'chat_id': chat})
        elif payload['type'] == 'playlist':
            # TODO: Сохранять все видео в БД
            current_ids = payload['video_ids']
            new_ids = [_id for _id in payload['video_ids'] if _id in current_ids]
            if payload['upload']:
                for _id in new_ids:
                    self.channel.basic_publish(
                        exchange='',
                        routing_key='task_queue',
                        body=json.dumps(payload | {
                            'type': 'download',
                            'video_id': _id,
                        }),
                    )

    @staticmethod
    async def main_page() -> Response:
        """
        Обрабатывает GET-запросы на главную страницу

        :return: Response 200
        """
        return Response(f'Ok', HTTPStatus.OK)

    @staticmethod
    def extract_video_id(url_raw: str, host: str) -> Optional[str]:
        """
        Проверяет ссылку на принадлежность домену и возвращает `video_id`

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
            elif host == 'vk':
                return re.split('[%?]', '_'.join(url_raw.split('video')[-1].split('_')[:2]))[0]
        except RegexMatchError as e:
            return None

    @staticmethod
    def extract_playlist_id(url_raw: str, host: str) -> Optional[str]:
        """
        Проверяет ссылку на принадлежность домену и возвращает `playlist_id`

        :param host: Видео-хостинг
        :param url_raw: url для проверки
        :return: video_id если ссылка корректна, иначе None
        """
        url = urlparse(url_raw)
        if url.netloc not in Loader.netlocs[host]:
            return None
        try:
            if host == 'youtube':
                return extract.playlist_id(url_raw)
            elif host == 'vk':
                return re.split('[%?]', '_'.join(url_raw.split('playlist/')[1].split('_')[:2]))[0]
        except RegexMatchError as e:
            return None
        except IndexError as e:
            return None

    async def download_start(self) -> Response:
        """
        Обрабатывает POST-запрос на начало загрузки, определяет видео-хостинг, добавляет задачу в очередь

        :return: Response 200 если ссылка верная, BadResponse 404 иначе
        """
        payload = request.json
        url_raw = payload['url']
        video_id = None
        hosting = None
        if self.extract_video_id(url_raw, 'youtube'):
            video_id = self.extract_video_id(url_raw, 'youtube')
            hosting = 'youtube'
        elif self.extract_video_id(url_raw, 'vk'):
            video_id = self.extract_video_id(url_raw, 'vk')
            hosting = 'vk'

        if video_id is None:
            return Response(status=HTTPStatus.NOT_FOUND)

        self.channel.basic_publish(
            exchange='',
            routing_key='task_queue',
            body=json.dumps(payload | {
                'type': 'download',
                'video_id': video_id,
                'hosting': hosting
            }),
        )
        return Response(status=HTTPStatus.OK)

    async def update_playlist(self, playlist_id: str, hosting: str, upload: bool, **kwargs) -> NoReturn:
        """
        Обновляет данные о плейлисте в базе данных

        :param playlist_id: Идентификатор плейлиста
        :param hosting: Имя хостинга
        :param upload: Если установленно True, то загружает на сервер новые видео
        """
        self.channel.basic_publish(
            exchange='',
            routing_key='task_queue',
            body=json.dumps({
                'type': 'playlist',
                'playlist_id': playlist_id,
                'hosting': hosting,
                'upload': upload,
                **kwargs
            }),
        )

    def configure_router(self) -> NoReturn:
        """
        Прописывает все пути для взаимодействия с Flask
        """
        self.app.add_url_rule('/', view_func=self.main_page, methods=['GET'])
        self.app.add_url_rule('/api/download/start', view_func=self.download_start, methods=['POST'])

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
