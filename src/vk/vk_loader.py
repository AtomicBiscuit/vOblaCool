"""
Модуль для взаимодействия с vk api
"""
import datetime
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


class VKLoader:
    """
    Класс для загрузки видео и получения информация о плейлистах Вконтакте
    """

    ydlp_opts = {
        'noplaylist': True,
        'paths': {'home': '../media'},
        'nocheckcertificate': True,
        'format': 'b[filesize_approx<501M]',
        'nopart': True,
        'noprogress': True,
        'quiet': True,
        'compat_opts': {'manifest-filesize-approx': True}
    }

    def __init__(self):
        self.app = flask.Flask(__name__)
        self.host = config('VK_LOADER_HOST')
        self.port = config('VK_LOADER_PORT')
        self.configure_router()

    @staticmethod
    async def main_page() -> Response:
        return Response(f'Ok', HTTPStatus.OK)

    @staticmethod
    async def download() -> Response:
        payload = request.json
        url_raw = payload['url']
        code = HTTPStatus.OK
        file_path = None
        name = str(datetime.datetime.now()) + '.%(ext)s'
        params = VKLoader.ydlp_opts | {'outtmpl': name}
        try:
            logger.info(f'Download start url: {url_raw}')
            with yt_dlp.YoutubeDL(params) as ydlp:
                ext = ydlp.extract_info(url_raw)['video_ext']
            file_path = os.getcwd() + f'..\\media\\{name[:-8]}.' + ext
            logger.info(f'Download complete, file: {file_path}')
        except DownloadError as e:
            logger.warning(f"Cath: {e.__class__.__name__}, {e}, {e.args}")
            code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        except YoutubeDLError as e:
            logger.error(f"Cath unexpected error: {e.__class__.__name__}, {e}, {e.args}")
            code = HTTPStatus.BAD_REQUEST
        return Response(file_path, status=code)

    @staticmethod
    async def get_playlist() -> Response:
        pass

    def configure_router(self):
        self.app.add_url_rule('/', view_func=self.main_page, methods=['GET'])
        self.app.add_url_rule('/api/download', view_func=self.download, methods=['POST'])
        self.app.add_url_rule('/api/get/playlist', view_func=self.get_playlist, methods=['GET'])

    def run(self, debug: bool = True) -> None:
        logger.info('Starting')
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False)


if __name__ == '__main__':
    app = VKLoader()
    app.run()
