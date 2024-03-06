"""
Управление поведением телеграм-бота
"""

import asyncio
from http import HTTPStatus
from typing import NoReturn

import flask
from decouple import config
from flask import abort, Response, request
from telebot import asyncio_filters, apihelper, asyncio_helper
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_handler_backends import State, StatesGroup
from telebot.asyncio_helper import ApiTelegramException
from telebot.asyncio_storage import StateMemoryStorage
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

    :cvar `telebot.asyncio_handler_backends.State` link: Получение ссылки
    """
    link = State()


class TBotHandler:
    """
    Класс-оболочка над Телеграм ботом, реализующая API для взаимодействия.
    Определяет поведение бота, отправляет запросы на загрузку и обрабатывает ответы на них.

    :ivar `telebot.async_telebot.AsyncTeleBot` bot: Экземпляр бота
    :ivar `flask.app.Flask` app: Flask-приложение для общения с остальными модулями
    :ivar `str` host: Хост для запуска
    :ivar `int` port: Порт для запуска
    """

    def __init__(self):
        self.bot: AsyncTeleBot = AsyncTeleBot(API_KEY, state_storage=StateMemoryStorage())
        self.app = flask.Flask(__name__)
        self.host = config('TELEGRAM_BOT_HANDLER_HOST')
        self.port = int(config('TELEGRAM_BOT_HANDLER_PORT'))
        try:
            asyncio.run(self.bot.delete_webhook(timeout=30))
            asyncio.run(self.bot.log_out())
        except ApiTelegramException as e:
            pass
        self.configure_router()
        self.configure_bot()

    def configure_bot(self) -> NoReturn:
        """
        Добавление и настройка хэндлеров и веб-хуков бота
        """

        @self.bot.message_handler(commands=['start'])
        async def __t_on_start(message: Message):
            await self.bot.reply_to(message, 'Приветствую тебя, искатель. Команда /download чтобы загрузить видео.')

        @self.bot.message_handler(commands=['download'])
        async def __t_on_download(message: Message):
            await self.bot.set_state(message.from_user.id, DownloadVideoState.link, message.chat.id)
            await self.bot.reply_to(message, 'Введите ссылку: ')

        @self.bot.message_handler(commands=['cancel'])
        async def __t_on_cancel(message: Message):
            await self.bot.delete_state(message.from_user.id, message.chat.id)
            await self.bot.reply_to(message, "Вернулись в начало")

        @self.bot.message_handler(state=DownloadVideoState.link)
        async def __t_on_download_link(message: Message):
            await self.bot.reply_to(message, f'Ссылка получена')
            await self.bot.delete_state(message.from_user.id, message.chat.id)
            session = await asyncio_helper.session_manager.get_session()
            async with session.post(f'http://{DOWNLOADER_HOST}:{DOWNLOADER_PORT}/api/download/start',
                                    json={'chat_id': message.chat.id, 'message_id': message.id,
                                          'url': message.text}) as response:
                if response.status == HTTPStatus.NOT_FOUND:
                    text = 'Некорректная ссылка'
                elif response.status == HTTPStatus.OK:
                    text = 'Видео добавлено в очередь'
                else:
                    text = 'Непредвиденная ошибка'
            await self.bot.reply_to(message, text)

        apihelper.API_URL = f"http://{TELEGRAM_SERVER_HOST}:{TELEGRAM_SERVER_PORT}" + "/bot{0}/{1}"
        asyncio_helper.API_URL = f"http://{TELEGRAM_SERVER_HOST}:{TELEGRAM_SERVER_PORT}" + "/bot{0}/{1}"
        asyncio.run(self.config_webhook())
        self.bot.add_custom_filter(asyncio_filters.StateFilter(self.bot))

    async def config_webhook(self) -> bool:
        """
        Устанавливает веб-хук Telegram на сервер `DOMAIN` с секретным ключом  `WEBHOOK_TOKEN`

        :return: True, если веб-хук был добавлен, иначе False
        """
        return await self.bot.set_webhook(url=DOMAIN, secret_token=WEBHOOK_TOKEN)

    async def t_request_handler(self) -> Response:
        """
        Обрабатывает поступающие от Telegram запросы, вызывает срабатывание хэндлеров

        :return: Response 200 в случае успеха, BadResponse 403 иначе
        """
        token_header_name = "X-Telegram-Bot-Api-Secret-Token"
        if request.headers.get(token_header_name) != WEBHOOK_TOKEN:
            return abort(HTTPStatus.FORBIDDEN)
        await self.bot.process_new_updates([Update.de_json(request.json)])
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
            await self.bot.send_message(chat_id, message_text,
                                        reply_parameters=ReplyParameters(message_id, chat_id, True))
        else:
            text = f'[Видео]({video_url})' + (f' [Плейлист]({playlist_url})' if playlist_url else '')
            await self.bot.send_video(chat_id, file_id, caption=text, parse_mode='MarkdownV2',
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
        asyncio.run(botik.bot.close_session())
