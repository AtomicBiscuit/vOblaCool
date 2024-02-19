"""
Обработка сообщений между микросервисами
"""
import json

import pika
from decouple import config
from pika.adapters.blocking_connection import BlockingChannel

YOUTUBE_LOADER_HOST = None
YOUTUBE_LOADER_PORT = None

DOWNLOADER_HOST = config('DOWNLOADER_HOST')
DOWNLOADER_PORT = config('DOWNLOADER_PORT')

RMQ_HOST = config('RMQ_HOST')
RMQ_PORT = config('RMQ_PORT')


class Worker:
    """
    Обрабатывает запросы на добавление видеозаписей и запускает параллельные процессы загрузки
    """
    hostings = {
        'youtube': [YOUTUBE_LOADER_HOST, YOUTUBE_LOADER_PORT],
    }

    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=RMQ_HOST, port=RMQ_PORT))
        self.channel = self.connection.channel()
        self.channel.queue_declare('download')
        self.channel.basic_consume('download', self.__process_task, auto_ack=True)
        #self.pool = ThreadPool

    def __process_task(self, channel: BlockingChannel, method, properties, body) -> None:
        """
        Обрабатывает запрос на начало загрузки

        :return: None
        """
        payload = json.loads(body.decode("utf-8"))
        url = payload['url']
        chat_id = payload['chat_id']
        message_id = payload['message_id']
        hosting = payload['hosting']
        print(url, chat_id, message_id, hosting)
        self.channel.basic_ack(delivery_tag=method.delivery_tag)

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
