"""
Управление поведением телеграм-бота
"""

from http import HTTPStatus
from typing import NoReturn

import flask
import requests
from decouple import config
from flask import abort, Response, request
from telebot import apihelper, asyncio_helper, TeleBot
from telebot.apihelper import ApiTelegramException
from telebot.handler_backends import State, StatesGroup
from telebot.custom_filters import StateFilter
from telebot.types import ReplyParameters
from telebot.types import Update, Message

API_KEY = config('TELEGRAM_BOT_API_KEY')

DOMAIN = config('TELEGRAM_BOT_HANDLER_PROXY')

DOWNLOADER_HOST = config('DOWNLOADER_HOST')
DOWNLOADER_PORT = config('DOWNLOADER_PORT')

TELEGRAM_SERVER_HOST = config('LOCAL_TELEGRAM_API_SERVER_HOST')
TELEGRAM_SERVER_PORT = config('LOCAL_TELEGRAM_API_SERVER_PORT')

WEBHOOK_TOKEN = config('TELEGRAM_BOT_WEBHOOK_TOKEN')


class DownloadVideoState(StatesGroup):
    """
    Состояния нужные для скачивания видео

    :cvar `telebot.handler_backends.State` link: Получение ссылки
    """
    link = State()


class AddPlaylistState(StatesGroup):
    """
    Состояния нужные для добавления плейлиста

    :cvar `telebot.handler_backends.State` link: Получение ссылки
    """
    link = State()


class TBotHandler:
    """
    Класс-оболочка над Телеграм ботом, реализующая API для взаимодействия.
    Определяет поведение бота, отправляет запросы на загрузку и обрабатывает ответы на них.

    :ivar `telebot.TeleBot` bot: Экземпляр бота
    :ivar `flask.app.Flask` app: Flask-приложение для общения с остальными модулями
    :ivar `str` host: Хост для запуска
    :ivar `int` port: Порт для запуска
    """

    def __init__(self):
        self.bot: TeleBot = TeleBot(API_KEY, threaded=False)
        self.app = flask.Flask(__name__)
        self.host = config('TELEGRAM_BOT_HANDLER_HOST')
        self.port = int(config('TELEGRAM_BOT_HANDLER_PORT'))
        try:
            self.bot.delete_webhook(timeout=30)
            self.bot.log_out()
        except ApiTelegramException as e:
            pass
        self.configure_router()
        self.configure_bot()

    def configure_bot(self) -> NoReturn:
        """
        Добавление и настройка хэндлеров и веб-хуков бота
        """

        @self.bot.message_handler(commands=['start'])
        def __t_on_start(message: Message):
            self.bot.reply_to(message, 'Приветствую тебя, искатель. Команда /download чтобы загрузить видео.')

        @self.bot.message_handler(commands=['download'])
        def __t_on_download(message: Message):
            self.bot.set_state(message.from_user.id, DownloadVideoState.link, message.chat.id)
            self.bot.reply_to(message, 'Введите ссылку: ')

        @self.bot.message_handler(commands=['cancel'])
        def __t_on_cancel(message: Message):
            self.bot.delete_state(message.from_user.id, message.chat.id)
            self.bot.reply_to(message, "Вернулись в начало")

        @self.bot.message_handler(state=DownloadVideoState.link)
        def __t_on_download_link(message: Message):
            self.bot.delete_state(message.from_user.id, message.chat.id)
            response = requests.post(f'http://{DOWNLOADER_HOST}:{DOWNLOADER_PORT}/api/download/start',
                                     json={'chat_id': message.chat.id, 'message_id': message.id,
                                           'url': message.text})
            if response.status_code == HTTPStatus.NOT_FOUND:
                text = 'Некорректная ссылка'
            elif response.status_code == HTTPStatus.OK:
                text = 'Видео добавлено в очередь'
            else:
                text = 'Непредвиденная ошибка'
            self.bot.reply_to(message, text)

        @self.bot.message_handler(commands=['add_playlist'])
        def __t_on_add_playlist(message: Message):
            self.bot.set_state(message.from_user.id, AddPlaylistState.link, message.chat.id)
            self.bot.reply_to(message, 'Введите ссылку: ')

        @self.bot.message_handler(state=AddPlaylistState.link)
        def __t_on_add_playlist_link(message: Message):
            self.bot.delete_state(message.from_user.id, message.chat.id)
            response = requests.post(f'http://{DOWNLOADER_HOST}:{DOWNLOADER_PORT}/api/playlist/add',
                                     json={'chat_id': message.chat.id, 'url': message.text})
            if response.status_code == HTTPStatus.NOT_FOUND:
                text = 'Некорректная ссылка'
            elif response.status_code == HTTPStatus.OK:
                text = 'Успешная подписка на обновления'
            else:
                text = 'Непредвиденная ошибка'
            self.bot.reply_to(message, text)

        apihelper.API_URL = f"http://{TELEGRAM_SERVER_HOST}:{TELEGRAM_SERVER_PORT}" + "/bot{0}/{1}"
        asyncio_helper.API_URL = f"http://{TELEGRAM_SERVER_HOST}:{TELEGRAM_SERVER_PORT}" + "/bot{0}/{1}"
        self.config_webhook()
        self.bot.add_custom_filter(StateFilter(self.bot))

    def config_webhook(self) -> bool:
        """
        Устанавливает веб-хук Telegram на сервер `DOMAIN` с секретным ключом  `WEBHOOK_TOKEN`

        :return: True, если веб-хук был добавлен, иначе False
        """
        return self.bot.set_webhook(url=DOMAIN, secret_token=WEBHOOK_TOKEN)

    async def t_request_handler(self) -> Response:
        """
        Обрабатывает поступающие от Telegram запросы, вызывает срабатывание хэндлеров

        :return: Response 200 в случае успеха, BadResponse 403 иначе
        """
        token_header_name = "X-Telegram-Bot-Api-Secret-Token"
        if request.headers.get(token_header_name) != WEBHOOK_TOKEN:
            return abort(HTTPStatus.FORBIDDEN)
        self.bot.process_new_updates([Update.de_json(request.json)])
        return Response(status=HTTPStatus.OK)

    @staticmethod
    async def main_page() -> Response:
        """
        Обрабатывает GET-запросы на главную страницу

        :return: Response 200
        """
        return Response(f'Everything is good', HTTPStatus.OK)

    async def on_download_complete(self) -> Response:
        """
        Обрабатывает POST-запрос при завершении загрузки, отправляет пользователю загруженное видео

        :return: Response 200
        """
        payload: dict = request.json
        chat_id = int(payload.get('chat_id', 0))
        message_id = int(payload.get('message_id', 0))
        file_id = payload.get('file_id', None)
        playlist_url = payload.get('playlist_url', None)
        video_url = payload.get('video_url', None)
        error_code = payload.get('error_code', None)
        if error_code is not None:
            if error_code == HTTPStatus.UNAUTHORIZED:
                message_text = 'Загрузка невозможна: требуется авторизация'
            elif error_code == HTTPStatus.BAD_REQUEST:
                message_text = 'Загрузка невозможна'
            elif error_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE:
                message_text = ('Загрузка невозможна: любая доступная конфигурация видео-аудио потоков весит больше '
                                '500МБ')
            else:
                message_text = 'Непредвиденная ошибка при попытке загрузки'
            self.bot.send_message(chat_id, message_text,
                                  reply_parameters=ReplyParameters(message_id, chat_id, True))
        else:
            text = f'[Видео]({video_url})' + (f' [Плейлист]({playlist_url})' if playlist_url else '')
            self.bot.send_video(chat_id, file_id, caption=text, parse_mode='MarkdownV2',
                                reply_parameters=ReplyParameters(message_id, chat_id, True))

        return Response(status=HTTPStatus.OK)

    def configure_router(self) -> NoReturn:
        """
        Прописывает все пути для взаимодействия с Flask
        """
        self.app.add_url_rule('/', view_func=self.main_page, methods=['GET'])
        self.app.add_url_rule('/', view_func=self.t_request_handler, methods=['POST'])
        self.app.add_url_rule('/api/download/complete', view_func=self.on_download_complete, methods=['POST'])

    def run(self, debug: bool = True) -> NoReturn:
        """
        Запускает приложение

        :param debug: Запуск приложения в debug режиме
        """
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False)


if __name__ == '__main__':
    botik = TBotHandler()
    botik.run()
