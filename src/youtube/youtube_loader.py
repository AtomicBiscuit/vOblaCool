from http import HTTPStatus

import flask
from decouple import config
from flask import request, Response
from pytube import YouTube
from pytube.exceptions import AgeRestrictedError, VideoPrivate, PytubeError

import logging
import os

logger = logging.getLogger("YOUTUBE_LOADER")

logger.setLevel(logging.INFO)

handler = logging.StreamHandler()

handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))

logger.addHandler(handler)

sep = os.sep

# Временное решение
class YLoaderPrototype:
    def __init__(self):
        self.app = flask.Flask(__name__)
        self.host = config('YOUTUBE_LOADER_HOST')
        self.port = config('YOUTUBE_LOADER_PORT')
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
        try:
            videos = YouTube(url_raw).streams.filter(progressive=True, file_extension='mp4', resolution='720p').desc()
            file_path = videos.first().download('../media')
        except (AgeRestrictedError, VideoPrivate) as e:
            code = HTTPStatus.UNAUTHORIZED
        except PytubeError as e:
            code = HTTPStatus.BAD_REQUEST
        return Response(file_path, status=code)

    def configure_router(self):
        self.app.add_url_rule('/', view_func=self.main_page, methods=['GET'])
        self.app.add_url_rule('/api/download', view_func=self.download, methods=['POST'])

    def run(self, debug: bool = True) -> None:
        logger.info('Starting')
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False)


if __name__ == '__main__':
    app = YLoaderPrototype()
    app.run()
