"""
Модуль для взаимодействия с youtube api
"""

from http import HTTPStatus

import flask
from decouple import config
from flask import request, Response
from pytube import YouTube, Playlist
from pytube.exceptions import AgeRestrictedError, VideoPrivate, PytubeError

import json
import logging
import os

logger = logging.getLogger("YOUTUBE_LOADER")

logger.setLevel(logging.INFO)

handler = logging.StreamHandler()

handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))

logger.addHandler(handler)

sep = os.sep

class YoutubeLoader:
    """
    Класс для загрузки видео и получения информация о плейлистах Youtube

    :param app: Flask-приложение для общения с другими модулями
    :type app: :class: `flask.app.Flask`
    :param host: Хост для запуска
    :type host: :class: `str`
    :param port: Порт для запуска
    :type port: :class: `int`
    """

    def __init__(self):
        self.app = flask.Flask(__name__)
        self.host = config('YOUTUBE_LOADER_HOST')
        self.port = config('YOUTUBE_LOADER_PORT')
        self.configure_router()

    @staticmethod
    async def main_page() -> Response:
        """
        Обрабатывает GET-запросы на главную страницу

        :return: Response 200
        """
        return Response(f'Ok', HTTPStatus.OK)

    @staticmethod
    async def download() -> Response:
        """
        Загружает видео с использованием библиотеки pytube

        :return: Response 200 с путём к файлу если загрузка удалась, BadResponse 413|400 иначе
        """
        payload = request.json
        url_raw = payload['url']
        code = HTTPStatus.OK
        file_path = None
        try:
            logger.info(f'Download start url: {url_raw}')
            videos = YouTube(url_raw).streams.filter(progressive=True, file_extension='mp4', resolution='720p').desc()
            file_path = videos.first().download('../media')
            logger.info(f'Download complete, file: {file_path}')
        except (AgeRestrictedError, VideoPrivate) as e:
            logger.warning(f"Cath: {e.__class__.__name__}, {e}, {e.args}")
            code = HTTPStatus.UNAUTHORIZED
        except PytubeError as e:
            logger.error(f"Cath unexpected error: {e.__class__.__name__}, {e}, {e.args}")
            code = HTTPStatus.BAD_REQUEST
        return Response(file_path, status=code)

    @staticmethod
    async def get_playlist() -> Response:
        """
        Возвращает информацию о всех видео в плейлисте с использованием библиотеки pytube

        :return: Response 200 со списком video_id если загрузка удалась, BadResponse 400 иначе
        """
        payload = request.json
        url = payload['url']
        video_ids = []
        code = HTTPStatus.OK
        if url is None:
            return Response(status=HTTPStatus.BAD_REQUEST)
        try:
            logger.info(f'Fetching all videos in {url}')
            for video in Playlist(url).videos:
                video_ids += [video.video_id]
            logger.info(f'Fetching complete, video_ids: {video_ids}')
        except PytubeError as e:
            logger.error(f"Cath unexpected error: {e.__class__.__name__}, {e}, {e.args}")
            code = HTTPStatus.BAD_REQUEST
        return Response(json.dumps({'video_ids': video_ids}), status=code)

    def configure_router(self):
        """
        Прописывает все пути для взаимодействия с Flask
        """
        self.app.add_url_rule('/', view_func=self.main_page, methods=['GET'])
        self.app.add_url_rule('/api/download', view_func=self.download, methods=['POST'])
        self.app.add_url_rule('/api/downloadPlaylist', view_func=self.get_playlist, methods=['POST'])

    def run(self, debug: bool = True) -> None:
        """
        Запускает приложение

        :param debug: Запуск приложения в debug режиме
        """
        logger.info('Starting')
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False)


if __name__ == '__main__':
    app = YoutubeLoader()
    app.run()
