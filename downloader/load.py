import flask
from decouple import config
from flask import request, Response
from urllib.parse import urlparse

from pytube import extract, YouTube
from pytube.exceptions import RegexMatchError
import requests as req


class Loader:
    youtube_netlocs = [
        'www.youtube.com',
        'www.youtube-nocookie.com',
        'm.youtube.com'
        'youtube.com',
        'youtu.be'
    ]

    def __init__(self):
        self.video_id = 0
        self.app = flask.Flask(__name__)
        self.host = config('loader_host')
        self.port = int(config('loader_port'))
        self.__configure_router()

    async def __main_page(self):
        return f'Everything good'

    @staticmethod
    def validate_youtube(url_raw: str):
        url = urlparse(url_raw)
        if url.netloc not in Loader.youtube_netlocs:
            return False
        try:
            extract.video_id(url_raw)
            return True
        except RegexMatchError as e:
            return False

    async def __download_start(self):
        payload = request.json
        url_raw = payload['url']
        chat_id = payload['chat_id']
        message_id = payload['message_id']
        if self.validate_youtube(url_raw):
            path = YouTube(url_raw).streams.filter(resolution='720p').first().download(output_path='../media',
                                                                                       filename=str(self.video_id))
            self.video_id += 1
            req.post(f'http://localhost:{config("tbot_port")}/api/download-complete',
                     json={'chat_id': chat_id, 'message_id': message_id, 'file_path': path})
            return Response(status=202)
        return Response(status=404)

    def __configure_router(self):
        self.app.add_url_rule('/', view_func=self.__main_page, methods=['GET'])
        self.app.add_url_rule('/api/download/start', view_func=self.__download_start, methods=['POST'])

    def run(self, debug: bool = True) -> None:
        print(self.port)
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False, load_dotenv=False)


if __name__ == '__main__':
    app = Loader()
    app.run()
# ngrok http port
# Обновить домен
