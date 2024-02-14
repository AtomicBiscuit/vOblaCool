"""
Управление состоянием загружаемых видеозаписей
"""

import threading
from queue import Queue
from urllib.parse import urlparse

import flask
import requests as req
from decouple import config
from flask import request, Response
from pytube import extract, YouTube
from pytube.exceptions import RegexMatchError

TBOT_URL = 'http://localhost'
TBOT_PORT = config('tbot_port')


# TODO: Заменить полноценной очередью
class QueueImitator:
    def __init__(self):
        self.queue = Queue(-1)

    def add_task(self, url, chat_id, message_id):
        self.queue.put_nowait((url, chat_id, message_id))
        self.start_task()

    def start_task(self):
        threading.Thread(target=self.download).start()

    def download(self):
        if self.queue.empty():
            return
        item = self.queue.get_nowait()
        videos = YouTube(item[0]).streams.filter(progressive=True, file_extension='mp4', resolution='720p').desc()
        file_path = videos.first().download('../../media', filename_prefix=str(Loader.video_id) + '_')
        Loader.video_id += 1
        res = req.post(f'{TBOT_URL}:{TBOT_PORT}/api/download/complete',
                       json={'chat_id': item[1], 'message_id': item[2], 'file_path': file_path})
        self.queue.task_done()


class Loader:
    """
    Проверяет url на корректность, определяет класс-загрузчик, общается с TBotHandler

    :param video_id: (не) Уникальный идентификатор видеозаписи
    :type video_id: :class: `int`
    :param youtube_netlocs: Список всех доменов youtube
    :type youtube_netlocs: :class: `List[str]`
    :param app: Flask-приложения для общения с остальными модулями
    :type app: :class: `flask.app.Flask`
    :param host: Хост для запуска
    :type host: :class: `str`
    :param port: Порт для запуска
    :type port: :class: `int`
    """
    # TODO: Убрать video_id, заменить на primary_key в БД
    video_id = 0
    youtube_netlocs = [
        'www.youtube.com',
        'www.youtube-nocookie.com',
        'm.youtube.com'
        'youtube.com',
        'youtu.be'
    ]

    def __init__(self):
        self.app = flask.Flask(__name__)
        self.queue = QueueImitator()  # TODO: Убрать
        self.host = config('loader_host')
        self.port = int(config('loader_port'))
        self.__configure_router()

    async def __main_page(self) -> Response:
        """
        Обрабатывает GET-запросы на главную страницу

        :return: Response 200
        """
        return Response(f'Everything good', 200)

    @staticmethod
    def validate_youtube(url_raw: str):
        """
        Проверяет ссылку на принадлежность домену youtube

        :param url_raw: url для проверки
        :return: True если ссылка корректна, False иначе
        """
        url = urlparse(url_raw)
        if url.netloc not in Loader.youtube_netlocs:
            return False
        try:
            extract.video_id(url_raw)
            return True
        except RegexMatchError as e:
            return False

    async def __download_start(self) -> Response:
        """
        Обрабатывает POST-запрос на начало заргрузки, определяет видео-хостинг, запускает процесс загрузки

        :return: Response 200 если ссылка верна, BadResponse 404 иначе
        """
        payload = request.json
        url_raw = payload['url']
        chat_id = payload['chat_id']
        message_id = payload['message_id']
        if self.validate_youtube(url_raw):
            self.queue.add_task(url_raw, chat_id, message_id)
            return Response(status=200)
        return Response(status=404)

    def __configure_router(self):
        """
        Прописывает все пути для взаимодействия с Flask

        :return: None
        """
        self.app.add_url_rule('/', view_func=self.__main_page, methods=['GET'])
        self.app.add_url_rule('/api/download/start', view_func=self.__download_start, methods=['POST'])

    def run(self, debug: bool = True) -> None:
        """
        Запускает приложение

        :param debug: Запуск приложения в debug режиме
        :return: None
        """
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False)


if __name__ == '__main__':
    app = Loader()
    app.run()