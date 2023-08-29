import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv.main import load_dotenv
from utils.db import MongoDB
from utils.middleware import RateLimitingMiddleware

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL")


BOT_API_TOKEN = os.getenv("BOT_API_TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID"))

NOTION_API_TOKEN = os.getenv("NOTION_API_TOKEN")
NOTION_DB = os.getenv("NOTION_DB")

storage = MemoryStorage()
bot = Bot(token=BOT_API_TOKEN)
dp = Dispatcher(bot, storage=storage)


class UserStates(StatesGroup):
    street_search = State()
    
DYNAMIC_RADIUS = 0.1
STATIC_RADIUS = 0.5


async def on_startup(dp):
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG, filename="bot.log", filemode="a"
    )
    await MongoDB().connect()
    dp.middleware.setup(RateLimitingMiddleware())
    await dp.bot.send_message(
        chat_id=ADMIN_GROUP_ID, text="бот поднялся", disable_notification=True
    )


async def on_shutdown(dp):
    await MongoDB().close()
    await dp.bot.send_message(
        chat_id=ADMIN_GROUP_ID, text="бот упал", disable_notification=True
    )
