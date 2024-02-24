"""
Управление поведением телеграм-бота
"""

import asyncio
from http import HTTPStatus
from typing import NoReturn

import aiohttp
import flask
from decouple import config
from flask import abort, Response, request
from telebot import asyncio_filters, apihelper, asyncio_helper
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_handler_backends import State, StatesGroup
from telebot.asyncio_helper import ApiTelegramException
from telebot.asyncio_storage import StateMemoryStorage
from telebot.types import InputFile, ReplyParameters
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

    :param link: Получение ссылки
    :type link: `telebot.asyncio_handler_backends.State`
    """
    link = State()


class TBotHandler:
    """
    Класс-оболочка над Телеграм ботом, реализующая API для взаимодействия.
    Определяет поведение бота, отправляет запросы на загрузку и обрабатывает ответы на них.

    :param bot: Экземпляр бота
    :type bot: :class: `telebot.async_telebot.AsyncTeleBot`
    :param app: Flask-приложения для общения с остальными модулями
    :type app: :class: `flask.app.Flask`
    :param host: Хост для запуска
    :type host: :class: `str`
    :param port: Порт для запуска
    :type port: :class: `int`
    """

    def __init__(self):
        self.bot = AsyncTeleBot(API_KEY, state_storage=StateMemoryStorage())
        self.app = flask.Flask(__name__)
        self.host = config('TELEGRAM_BOT_HANDLER_HOST')
        self.port = int(config('TELEGRAM_BOT_HANDLER_PORT'))
        try:
            asyncio.run(self.bot.delete_webhook(timeout=30))
            asyncio.run(self.bot.log_out())
        except ApiTelegramException as e:
            pass
        self.__configure_router()
        self.__configure_bot()

    def __configure_bot(self) -> NoReturn:
        """
        Добавление и настройка хэндлеров и веб-хуков бота

        :return: None
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
        asyncio.run(self.__config_webhook())
        self.bot.add_custom_filter(asyncio_filters.StateFilter(self.bot))

    async def __config_webhook(self) -> bool:
        """
        Устанавливает веб-хук Telegram на сервер `DOMAIN` с секретным ключом  `WEBHOOK_TOKEN`

        :return: True, если веб-хук был добавлен, иначе False
        """
        return await self.bot.set_webhook(url=DOMAIN, secret_token=WEBHOOK_TOKEN)

    async def __t_request_handler(self) -> Response:
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
    async def __main_page() -> Response:
        """
        Обрабатывает GET-запросы на главную страницу

        :return: Response 200
        """
        return Response(f'Everything is good', HTTPStatus.OK)

    async def __on_download_complete(self) -> Response:
        """
        Обрабатывает POST-запрос при завершении загрузки, отправляет пользователю загруженное видео

        :return: Response 200
        """
        payload: dict = request.json
        chat_id = int(payload.get('chat_id', 0))
        message_id = int(payload.get('message_id', 0))
        file_id = payload.get('file_id', None)
        error_code = payload.get('error_code', None)
        if error_code is not None:
            if error_code == HTTPStatus.UNAUTHORIZED:
                message_text = 'Загрузка невозможна: требуется авторизация'
            elif error_code == HTTPStatus.BAD_REQUEST:
                message_text = 'Загрузка невозможна'
            else:
                message_text = 'Непредвиденная ошибка при попытке загрузки'
            await self.bot.send_message(chat_id, message_text,
                                        reply_parameters=ReplyParameters(message_id, chat_id, True))
        else:
            await self.bot.send_video(chat_id, file_id,
                                      reply_parameters=ReplyParameters(message_id, chat_id, True))
        return Response(status=HTTPStatus.OK)

    def __configure_router(self) -> NoReturn:
        """
        Прописывает все пути для взаимодействия с Flask
        """
        self.app.add_url_rule('/', view_func=self.__main_page, methods=['GET'])
        self.app.add_url_rule('/', view_func=self.__t_request_handler, methods=['POST'])
        self.app.add_url_rule('/api/download/complete', view_func=self.__on_download_complete, methods=['POST'])

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
