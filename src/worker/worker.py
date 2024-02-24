"""
Обработка запросов на работу с Downloader-ми, загрузка видео на Local Telegram Server
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from threading import current_thread
from typing import Tuple, NoReturn

import pika
import requests
from decouple import config
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic
from pika.spec import BasicProperties
from telebot import asyncio_helper, apihelper, TeleBot

logger = logging.getLogger("Worker")

logger.setLevel(logging.INFO)

handler = logging.StreamHandler()

handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))

logger.addHandler(handler)

YOUTUBE_LOADER_HOST = config('YOUTUBE_LOADER_HOST')
YOUTUBE_LOADER_PORT = config('YOUTUBE_LOADER_PORT')

RMQ_HOST = config('RMQ_HOST')
RMQ_PORT = config('RMQ_PORT')

DOWNLOADER_BOT_API_KEY = config('DOWNLOADER_BOT_API_KEY')

DOWNLOAD_CHAT_ID = config('DOWNLOAD_CHAT_ID')

TELEGRAM_SERVER_HOST = config('LOCAL_TELEGRAM_API_SERVER_HOST')
TELEGRAM_SERVER_PORT = config('LOCAL_TELEGRAM_API_SERVER_PORT')

_locals = {}


def get_local() -> Tuple[TeleBot, pika.BlockingConnection, BlockingChannel]:
    """
    Возвращает список из объектов, требующих уникальное соединение для работы внутри потоков(non-thread-safe)
    Создаёт новые соединения, если таковых еще нет

    :return: Список локальных атрибутов рабочего потока
    """
    thread = current_thread()
    key = '_local.' + str(id(thread))
    if key not in _locals.keys():
        logger.info(f"New local generating")
        _bot = TeleBot(DOWNLOADER_BOT_API_KEY)
        _con = pika.BlockingConnection(pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, heartbeat=0))
        _ch = _con.channel()
        _ch.queue_declare('answer_queue')
        _locals[key] = [_bot, _con, _ch]
    return _locals[key]


class Worker:
    """
    Обрабатывает запросы на добавление видеозаписей и запускает параллельные процессы загрузки

    :param pool: Группа потоков для выполнения задач
    :type pool: :class: `concurrent.futures.thread.ThreadPoolExecutor`
    :param connection: Объект соединения с RabbitMQ
    :type connection: :class: `pika.BlockingConnection`
    :param channel: Канал для общения с RabbitMQ
    :type channel: :class: `pika.BlockingChannel`
    """

    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT, heartbeat=0))
        self.channel = self.connection.channel()
        self.channel.queue_declare('task_queue')
        self.channel.basic_consume('task_queue', self.__process_task, auto_ack=True)
        self.__configure_bot()

    @staticmethod
    def __configure_bot() -> NoReturn:
        """
        Привязка бота к локальному серверу

        :return: None
        """
        apihelper.API_URL = f"http://{TELEGRAM_SERVER_HOST}:{TELEGRAM_SERVER_PORT}" + "/bot{0}/{1}"
        asyncio_helper.API_URL = f"http://{TELEGRAM_SERVER_HOST}:{TELEGRAM_SERVER_PORT}" + "/bot{0}/{1}"

    def __process_task(self, channel: BlockingChannel, method: Basic.Deliver, properties: BasicProperties,
                       body: bytes) -> NoReturn:
        """
        Обрабатывает добавленные в очередь задачи
        """
        payload = json.loads(body.decode("utf-8"))
        logger.info(f"Receive message: {payload['type']}")
        if payload['type'] == 'download':
            self.pool.submit(self._download, payload)

    @staticmethod
    def _download(payload: dict) -> NoReturn:
        """
        Загружает видео на сервер telegram

        :param payload: Словарь с параметрами
        """
        bot, con, ch = get_local()
        url = payload['url']
        video_id = payload['video_id']
        chat_id = payload['chat_id']
        message_id = payload['message_id']
        hosting = payload['hosting']
        response = None
        file_id = None
        error_code = None
        if hosting == 'youtube':
            logger.info(f"Downloading url: {url}")
            response = requests.post(f'http://{YOUTUBE_LOADER_HOST}:{YOUTUBE_LOADER_PORT}/api/download',
                                     json={'url': url}, timeout=1000)
        if response.status_code == HTTPStatus.OK:
            path = response.text
            logger.info(f"Load complete, file_path: {path}")
            try:
                with open(path, 'rb') as f:
                    file_id = bot.send_video(DOWNLOAD_CHAT_ID, f, timeout=1000).video.file_id
            except Exception as e:
                logger.error(f"Fatal error: {e.__class__.__name__}, {e}, {e.args}")
        else:
            logger.warning(f"Load fail with status code: {response.status_code}")
            error_code = response.status_code
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
        logger.info(f"Reply-message send")

    def run(self) -> NoReturn:
        """
        Запускает приложение
        """
        logger.info("Worker start")
        self.channel.start_consuming()


if __name__ == '__main__':
    app = Worker()
    app.run()
    app.connection.close()
