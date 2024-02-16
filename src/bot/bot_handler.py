"""
Управление поведением телеграм-бота
"""

import asyncio

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

DOMAIN = config('TELEGRAM_BOT_HANDLER_HOST')

DOWNLOADER_HOST = config('DOWNLOADER_HOST')
DOWNLOADER_PORT = config('DOWNLOADER_PORT')

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
        apihelper.API_URL = f"http://{config('LOCAL_TELEGRAM_API_SERVER_HOST')}:{config('LOCAL_TELEGRAM_API_SERVER_PORT')}/bot{0}/{1}"
        asyncio_helper.API_URL = f"http://{config('LOCAL_TELEGRAM_API_SERVER_HOST')}:{config('LOCAL_TELEGRAM_API_SERVER_PORT')}/bot{0}/{1}"
        self.__configure_router()
        self.__configure_bot()

    def __configure_bot(self):
        """
        Настройка, добавление хэндлеров и веб-хуков бота

        :return: None
        """

        @self.bot.message_handler(commands=['start'])
        async def __t_on_start(message: Message):
            await self.bot.reply_to(message, 'Приветствую тебя, искатель. Команда /download чтобы загрузить видео.')

        @self.bot.message_handler(commands=['download'])
        async def __t_on_download(message: Message):
            await self.bot.set_state(message.from_user.id, DownloadVideoState.link, message.chat.id)
            await self.bot.reply_to(message, 'Введите ссылку: ')

        @self.bot.message_handler(state=DownloadVideoState.link)
        async def __t_on_download_link(message: Message):
            await self.bot.reply_to(message, f'Ссылка получена')
            await self.bot.delete_state(message.from_user.id, message.chat.id)
            async with aiohttp.ClientSession() as session:
                # TODO: Добавить очередь сообщений между TBotHandler и Loader
                async with session.post(f'http://{DOWNLOADER_HOST}:{DOWNLOADER_PORT}/api/download/start',
                                        json={'chat_id': message.chat.id, 'message_id': message.id,
                                              'url': message.text}) as response:
                    if response.status == 404:
                        await self.bot.reply_to(message, f'Некорректная ссылка')
                    elif response.status == 202:
                        await self.bot.reply_to(message, f'Загрузка началась')
                    elif response.status == 401:
                        await self.bot.reply_to(message, f'Невозможно загрузить видео без авторизации')

        @self.bot.message_handler(commands=['cancel'])
        async def __t_on_cancel(message: Message):
            await self.bot.delete_state(message.from_user.id, message.chat.id)
            await self.bot.reply_to(message, "Вернулись в начало")

        asyncio.run(self.__config_webhook())
        self.bot.add_custom_filter(asyncio_filters.StateFilter(self.bot))

    async def __config_webhook(self) -> bool:
        """
        Устанавливает веб-хук Телеграма на сервер `DOMAIN` с секретным ключом  `WEBHOOK_TOKEN`

        :return: True, если веб-хук был добавлен, иначе False
        """
        return await self.bot.set_webhook(url=DOMAIN, secret_token=WEBHOOK_TOKEN)

    async def __t_request_handler(self) -> Response:
        """
        Обрабатывает поступающие от Телеграма запросы, вызывает срабатывание хэндлеров

        :return: Response 200 в случае успеха, BadResponse 403 иначе
        """
        token_header_name = "X-Telegram-Bot-Api-Secret-Token"
        if request.headers.get(token_header_name) != WEBHOOK_TOKEN:
            return abort(403)
        await self.bot.process_new_updates([Update.de_json(request.json)])
        return Response()

    async def __main_page(self) -> Response:
        """
        Обрабатывает GET-запросы на главную страницу

        :return: Response 200
        """
        return Response(f'Everything is good', 200)

    async def __on_download_complete(self) -> Response:
        """
        Обрабатывает POST-запрос при завершении загрузки, отправляет пользователю загруженное видео

        :return: Response 200
        """
        payload = request.json
        chat_id = int(payload['chat_id'])
        message_id = int(payload['message_id'])
        file_path = payload['file_path']
        # TODO: Перенести выполнение в потоки
        await self.__download_and_send(chat_id, message_id, file_path)
        return Response()

    async def __download_and_send(self, chat_id: int, message_id: int, file_path: int) -> None:
        """
        Отправляет файл, находящийся в `file_path`, ответом на сообщение (`chat_id`, `message_id`)

        :param chat_id: id чата, из которого произошел вызов
        :param message_id: id сообщения-вызова
        :param file_path: Полный путь до отправляемого файла
        :return: None
        """
        await self.bot.send_video(chat_id, InputFile(file_path),
                                  reply_parameters=ReplyParameters(message_id, chat_id, True))

    def __configure_router(self) -> None:
        """
        Прописывает все пути для взаимодействия с Flask

        :return: None
        """
        self.app.add_url_rule('/', view_func=self.__main_page, methods=['GET'])
        self.app.add_url_rule('/', view_func=self.__t_request_handler, methods=['POST'])
        self.app.add_url_rule('/api/download/complete', view_func=self.__on_download_complete, methods=['POST'])

    def run(self, debug: bool = True) -> None:
        """
        Запускает приложение

        :param debug: Запуск приложения в debug режиме
        :return: None
        """
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False)


if __name__ == '__main__':
    botik = TBotHandler()
    asyncio.run(asyncio.sleep(2))
    botik.run()
    asyncio.run(botik.bot.close_session())
# ngrok http port
# Обновить домен
