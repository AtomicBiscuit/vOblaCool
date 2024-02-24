"""
Обработка сообщений между микросервисами
"""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus

import pika
import requests
from decouple import config
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import BasicProperties
from pika.spec import Basic
from telebot import asyncio_helper, apihelper
from telebot.async_telebot import AsyncTeleBot

YOUTUBE_LOADER_HOST = config('YOUTUBE_LOADER_HOST')
YOUTUBE_LOADER_PORT = config('YOUTUBE_LOADER_PORT')

RMQ_HOST = config('RMQ_HOST')
RMQ_PORT = config('RMQ_PORT')

DOWNLOADER_BOT_API_KEY = config('DOWNLOADER_BOT_API_KEY')

DOWNLOAD_CHAT_ID = config('DOWNLOAD_CHAT_ID')

TELEGRAM_SERVER_HOST = config('LOCAL_TELEGRAM_API_SERVER_HOST')
TELEGRAM_SERVER_PORT = config('LOCAL_TELEGRAM_API_SERVER_PORT')


class Worker:
    """
    Обрабатывает запросы на добавление видеозаписей и запускает параллельные процессы загрузки
    """

    def __init__(self):
        self.bot = AsyncTeleBot(DOWNLOADER_BOT_API_KEY)
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, heartbeat=0))
        self.channel = self.connection.channel()
        self.channel.queue_declare('task_queue')
        self.channel.basic_consume('task_queue', self.__process_task, auto_ack=True)
        self.__configure_bot()

    @staticmethod
    def __configure_bot():
        """
        Привязка бота к локальному серверу

        :return: None
        """
        apihelper.API_URL = f"http://{TELEGRAM_SERVER_HOST}:{TELEGRAM_SERVER_PORT}" + "/bot{0}/{1}"
        asyncio_helper.API_URL = f"http://{TELEGRAM_SERVER_HOST}:{TELEGRAM_SERVER_PORT}" + "/bot{0}/{1}"

    def __process_task(self, channel: BlockingChannel, method: Basic.Deliver, properties: BasicProperties,
                       body: bytes) -> None:
        """
        Обработка задач

        :return: None
        """
        payload = json.loads(body.decode("utf-8"))
        if payload['type'] == 'download':
            resp = self.pool.submit(self._download, payload)
            raise RuntimeError(resp.exception(20).args)

    def _download(self, payload):
        url = payload['url']
        video_id = payload['video_id']
        chat_id = payload['chat_id']
        message_id = payload['message_id']
        hosting = payload['hosting']
        response = None
        file_id = None
        error_code = None
        if hosting == 'youtube':
            response = requests.post(f'http://{YOUTUBE_LOADER_HOST}:{YOUTUBE_LOADER_PORT}/api/download',
                                     json={'url': url}, timeout=1000)
        if response.status_code == HTTPStatus.OK:
            path = response.text
            with open(path, 'rb') as f:
                file_id = asyncio.run(self.bot.send_video(DOWNLOAD_CHAT_ID, f)).video.file_id
        else:
            error_code = response.status_code
        con = pika.BlockingConnection(pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, heartbeat=0))
        ch = con.channel()
        ch.queue_declare('answer_queue')
        ch.basic_publish(
            exchange='',
            routing_key='answer_queue',
            body=json.dumps({
                'type': 'download',
                'file_id': file_id,
                'video_id': video_id,
                'chat_id': chat_id,
                'message_id': message_id,
                'hosting': hosting,
                'error_code': error_code
            })
        )
        # con.close()

    def run(self) -> None:
        """
        Запускает приложение

        :return: None
        """
        self.channel.start_consuming()


if __name__ == '__main__':
    app = Worker()
    app.run()
    app.connection.close()
