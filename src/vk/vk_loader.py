"""
Модуль для взаимодействия с vk api
"""
import datetime
import json
import os
from http import HTTPStatus

import flask
import yt_dlp
from decouple import config
from flask import Response, request
from yt_dlp.utils import YoutubeDLError, DownloadError

import logging

logger = logging.getLogger("VK_LOADER")

logger.setLevel(logging.INFO)

handler = logging.StreamHandler()

handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))

logger.addHandler(handler)

sep = os.sep


class VKLoader:
    """
    Класс для загрузки видео и получения информация о плейлистах Вконтакте

    :ivar `flask.app.Flask` app: Flask-приложение для общения с другими модулями
    :ivar `str` host: Хост для запуска
    :ivar `int` port: Порт для запуска
    """

    def __init__(self):
        self.app = flask.Flask(__name__)
        self.host = config('VK_LOADER_HOST')
        self.port = int(config('VK_LOADER_PORT'))
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
        Загружает видео с использованием библиотеки youtube_dlp

        :return: Response 200 с путём к файлу если загрузка удалась, BadResponse 413|401|400 иначе
        """
        payload = request.json
        url_raw = payload['url']
        code = HTTPStatus.OK
        file_path = None
        name = str(datetime.datetime.now()) + '.%(ext)s'
        params = {
            'paths': {'home': '../media'},
            'nocheckcertificate': True,
            'format': 'b[filesize_approx<999M]',
            'nopart': True,
            'noprogress': True,
            'quiet': True,
            'compat_opts': {'manifest-filesize-approx': True},
            'outtmpl': name,
            'noplaylist': True
        }
        try:
            logger.info(f'Download start url: {url_raw}')
            with yt_dlp.YoutubeDL(params) as ydlp:
                ext = ydlp.extract_info(url_raw)['video_ext']
            file_path = os.getcwd() + f'{sep}..{sep}media{sep}{name[:-8]}.' + ext
            logger.info(f'Download complete, file: {file_path}')
        except DownloadError as e:
            logger.warning(f"Cath: {e.__class__.__name__}, {e}, {e.args}")
            if 'Sign up' in e.msg:
                code = HTTPStatus.UNAUTHORIZED
            else:
                code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        except YoutubeDLError as e:
            logger.error(f"Catch unexpected error: {e.__class__.__name__}, {e}, {e.args}")
            code = HTTPStatus.BAD_REQUEST
        return Response(file_path, status=code)

    @staticmethod
    async def get_playlist() -> Response:
        """
        Возвращает информацию о всех видео в плейлисте с использованием библиотеки youtube_dlp

        :return: Response 200 со списком video_id если загрузка удалась, BadResponse 400|404 иначе
        """
        url = request.args.get('url', None)
        video_ids = []
        code = HTTPStatus.OK
        if url is None:
            return Response(status=HTTPStatus.BAD_REQUEST)
        try:
            logger.info(f'Fetching all videos in playlist {url}')
            with yt_dlp.YoutubeDL({'quiet': True, 'nocheckcertificate': True}) as ydlp:
                ent = ydlp.extract_info(url, download=False, process=False).get('entries', [])
                video_ids = list(x for x in map(lambda x: x.get('id', None), list(ent)) if x is not None)
        except KeyError as e:
            logger.error(f"Cath KeyError: {e} ")
            code = HTTPStatus.BAD_REQUEST
        except YoutubeDLError as e:
            logger.error(f"Catch unexpected error: {e.__class__.__name__}, {e}, {e.args}")
            code = HTTPStatus.BAD_REQUEST
        return Response(json.dumps({'video_ids': video_ids}), status=code)

    def configure_router(self):
        """
        Прописывает все пути для взаимодействия с Flask
        """
        self.app.add_url_rule('/', view_func=self.main_page, methods=['GET'])
        self.app.add_url_rule('/api/download', view_func=self.download, methods=['POST'])
        self.app.add_url_rule('/api/get/playlist', view_func=self.get_playlist, methods=['GET'])

    def run(self, debug: bool = True) -> None:
        """
        Запускает приложение

        :param debug: Запуск приложения в debug режиме
        """
        logger.info('Starting')
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False)


if __name__ == '__main__':
    app = VKLoader()
    app.run(config('DEBUG', False))
