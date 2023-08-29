from aiogram import types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.utils.exceptions import Throttled


class RateLimitingMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        user_id = message.from_user.id
        dp = Dispatcher.get_current()

        try:
            await dp.throttle(user_id, rate=1)
        except Throttled:
            await message.reply("Слишком много запросов")
            raise CancelHandler()