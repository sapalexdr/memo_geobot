
import os
from aiogram import executor
from aiogram.dispatcher.filters import Command

from scripts.handlers_funcs import mailing, show_stats, handle_start, refresh_buildings_info, handle_street_search_button, search_geo_by_street, show_next_building, chat, get_live_geo, send_geo, get_location, handle_any_location, back_from_street_search

from utils.utils import dp, UserStates

dp.message_handler(Command('start'))(handle_start)
dp.message_handler(Command('mailing_message'))(mailing)
dp.message_handler(Command('stats'))(show_stats)
dp.message_handler(Command('refresh_database'))(refresh_buildings_info)

dp.message_handler(text='🚏 Название места')(handle_street_search_button)
dp.message_handler(text='🗺️ Поделиться геопозицией')(handle_any_location)

dp.message_handler(state=UserStates.street_search)(search_geo_by_street)
dp.message_handler(content_types=['location'])(get_location)
dp.callback_query_handler(text="show_next_building")(show_next_building)
dp.callback_query_handler(text='back_from_street_search', state=UserStates.street_search)(
    back_from_street_search)

dp.message_handler(content_types=['photo', 'text', 'video', 'document',
                                     'video_note', 'voice', 'sticker', 'audio', 'contact'])(chat)

dp.edited_message_handler(content_types=["location"])(get_live_geo)

dp.callback_query_handler(text="send_geo")(send_geo)

if __name__ == "__main__":
    executor.start_polling(dp)
