import asyncio

import flask
import requests as req
from decouple import config
from flask import abort, Response, request
from telebot import asyncio_filters
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_handler_backends import State, StatesGroup
from telebot.asyncio_storage import StateMemoryStorage
from telebot.types import Update, Message, ReplyParameters

API_KEY = config('tbot_apikey')

DOMAIN = config('tbot_url')

LOADER_HOST = config('loader_host')
LOADER_PORT = config('loader_port')

WEBHOOK_TOKEN = config('tbot_webhook_token')


class DownloadVideoState(StatesGroup):
    link = State()
    file = State()


class TBotHandler:
    def __init__(self):
        self.bot = AsyncTeleBot(API_KEY, state_storage=StateMemoryStorage())
        self.app = flask.Flask(__name__)
        self.host = '0.0.0.0'
        self.port = int(config('tbot_port'))
        self.__configure_router()
        self.__configure_bot()

    def __configure_bot(self):
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
            response = req.post(f'http://{LOADER_HOST}:{LOADER_PORT}/api/download/start',
                                json={'chat_id': message.chat.id, 'message_id': message.id, 'url': message.text})
            if response.status_code == 404:
                await self.bot.reply_to(message, f'Некорректная ссылка')
            elif response.status_code == 202:
                await self.bot.reply_to(message, f'Загрузка началась')

        @self.bot.message_handler(commands=['cancel'])
        async def __t_on_cancel(message: Message):
            await self.bot.delete_state(message.from_user.id, message.chat.id)
            await self.bot.reply_to(message, "Вернулись в начало")

        asyncio.run(self.__config_webhook())
        self.bot.add_custom_filter(asyncio_filters.StateFilter(self.bot))

    async def __config_webhook(self):
        result = await self.bot.delete_webhook(timeout=30)
        return await self.bot.set_webhook(url=DOMAIN, secret_token=WEBHOOK_TOKEN)

    async def __t_request_handler(self):
        token_header_name = "X-Telegram-Bot-Api-Secret-Token"
        if request.headers.get(token_header_name) != WEBHOOK_TOKEN:
            return abort(403)
        await self.bot.process_new_updates([Update.de_json(request.json)])
        return Response()

    async def __main_page(self):
        return f'Everything good'

    async def __download_complete(self):
        payload = request.json
        chat_id = int(payload['chat_id'])
        message_id = int(payload['message_id'])
        file_path = payload['file_path']
        with open(file_path, 'rb') as file:
            await self.bot.send_video(chat_id, file)
        return 'Ok'

    def __configure_router(self):
        self.app.add_url_rule('/', view_func=self.__main_page, methods=['GET'])
        self.app.add_url_rule('/', view_func=self.__t_request_handler, methods=['POST'])
        self.app.add_url_rule('/api/download-complete', view_func=self.__download_complete, methods=['POST'])

    def run(self, debug: bool = True) -> None:
        self.app.run(debug=debug, host=self.host, port=self.port, use_reloader=False)


if __name__ == '__main__':
    botik = TBotHandler()
    asyncio.run(asyncio.sleep(2))
    botik.run()
    asyncio.run(botik.bot.close_session())
# ngrok http port
# Обновить домен
