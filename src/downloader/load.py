"""
Управление состоянием загружаемых видеозаписей
"""
import json
import logging
import re
import threading
import time
from http import HTTPStatus
from typing import NoReturn, Optional
from urllib.parse import urlparse

import flask
import pika
import requests
import requests as req
import schedule
from decouple import config
from flask import request, Response
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import BasicProperties, Basic
from pytube import extract
from pytube.exceptions import RegexMatchError

from batadaze.src.main import DB

logger = logging.getLogger("Loader")

logger.setLevel(logging.INFO)

handler = logging.StreamHandler()

handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))

logger.addHandler(handler)

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

        def __on_return(payload: dict) -> None:
            file_id = DB.get_video(payload['video_id']).file_id
            if payload.get('playlist_id', None) is None:
                req.post(f'http://{TBOT_HOST}:{TBOT_PORT}/api/download/complete', json=payload | {'file_id': file_id})
            else:
                users = DB.get_subscribed_users(payload['playlist_id'])
                for user in users:
                    req.post(f'http://{TBOT_HOST}:{TBOT_PORT}/api/download/complete',
                             json=payload | {'file_id': file_id, 'chat_id': user})

        def __on_download(payload: dict) -> None:
            video_id = payload['video_id']
            if DB.get_video(video_id) is None:
                DB.add_video(video_id, payload['file_id'])
            else:
                DB.update_video(video_id, payload['file_id'])

            if payload.get('playlist_id', None) is None:
                req.post(f'http://{TBOT_HOST}:{TBOT_PORT}/api/download/complete', json=payload)
            else:
                users = DB.get_subscribed_users(payload['playlist_id'])
                for user in users:
                    req.post(f'http://{TBOT_HOST}:{TBOT_PORT}/api/download/complete', json=payload | {'chat_id': user})

        def __on_playlist(payload: dict) -> None:
            playlist_id = payload.get('playlist_id', '0')
            current_ids = DB.get_all_videos(playlist_id)
            new_ids = [_id for _id in payload['video_ids'] if _id not in current_ids]
            for _id in new_ids:
                video = DB.get_video(_id)
                if video is None:
                    DB.add_video(_id, None)
                DB.add_playlist_video(_id, playlist_id)
                task_type = 'return' if video and video.file_id else 'download'
                if payload.get('upload', None):
                    self.channel.basic_publish(exchange='', routing_key='task_queue',
                                               body=json.dumps(payload | {'type': task_type, 'video_id': _id}))
            DB.update_playlist_status(playlist_id, False)

        payload: dict = json.loads(body.decode("utf-8"))
        if payload['type'] == 'return':
            __on_return(payload)
        elif payload['type'] == 'download':
            __on_download(payload)
        elif payload['type'] == 'playlist':
            __on_playlist(payload)

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

        task_type = 'download'
        video = DB.get_video(video_id)
        if video and video.file_id is not None:
            task_type = 'return'

        self.channel.basic_publish(exchange='', routing_key='task_queue',
                                   body=json.dumps(
                                       payload | {'type': task_type, 'video_id': video_id, 'hosting': hosting}))

        return Response(status=HTTPStatus.OK)

    async def add_playlist(self) -> NoReturn:
        """
        Обрабатывает POST запрос на добавление плейлиста
        """
        payload = request.json
        url_raw = payload['url']
        playlist_id = None
        hosting = None
        if self.extract_playlist_id(url_raw, 'youtube'):
            playlist_id = self.extract_playlist_id(url_raw, 'youtube')
            hosting = 'youtube'
        elif self.extract_playlist_id(url_raw, 'vk'):
            playlist_id = self.extract_playlist_id(url_raw, 'vk')
            hosting = 'vk'

        if playlist_id is None:
            return Response(status=HTTPStatus.NOT_FOUND)

        if DB.get_user(payload['chat_id']) is None:
            DB.add_user(payload['chat_id'])
        if DB.get_playlist(playlist_id) is None:
            DB.add_playlist(playlist_id, hosting)
            await self._update_playlist(playlist_id, hosting, False)
        if payload['chat_id'] not in DB.get_subscribed_users(playlist_id):
            DB.add_playlist_user(payload['chat_id'], playlist_id)

        return Response(status=HTTPStatus.OK)

    async def _update_playlist(self, playlist_id: str, hosting: str, upload: bool) -> NoReturn:
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
            }),
        )

    async def update_playlist(self) -> NoReturn:
        """
        Обрабатывает POST запрос на обновление данных о плейлисте
        """
        payload = request.json
        playlist_id = payload['playlist_id']
        hosting = payload['hosting']
        upload = bool(payload['upload'])
        await self._update_playlist(playlist_id, hosting, upload)
        return Response(status=HTTPStatus.OK)

    def configure_router(self) -> NoReturn:
        """
        Прописывает все пути для взаимодействия с Flask
        """
        self.app.add_url_rule('/', view_func=self.main_page, methods=['GET'])
        self.app.add_url_rule('/api/download/start', view_func=self.download_start, methods=['POST'])
        self.app.add_url_rule('/api/playlist/add', view_func=self.add_playlist, methods=['POST'])
        self.app.add_url_rule('/api/playlist/update', view_func=self.update_playlist, methods=['POST'])

    def run(self, debug: bool = True) -> NoReturn:
        """
        Запускает приложение

        :param debug: Запуск приложения в debug режиме
        """
        threading.Thread(target=self.RPC_channel.start_consuming).start()
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False)


def update_all_playlists() -> NoReturn:
    logger.info("update_all process start")
    all_playlists = DB.select_playlists()
    for playlist in all_playlists:
        if playlist.is_updating:
            continue
        DB.update_playlist_status(playlist.id, True)
        requests.post(f'http://{config("DOWNLOADER_HOST")}:{config("DOWNLOADER_PORT")}/api/playlist/update',
                      json={'playlist_id': playlist.id, 'hosting': playlist.host, 'upload': True})
    logger.info("update_all process finish")


def schedule_tasks():
    logger.info("Generating schedule tasks")
    schedule.every(1).minutes.do(update_all_playlists)
    logger.info("Schedule pending start")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    app = Loader()
    threading.Thread(target=schedule_tasks).start()
    app.run(config('DEBUG', False))
    app.connection.close()
