from aiogram import executor
from aiogram.dispatcher.filters import Command
from scripts.handlers_funcs import (back_from_street_search, chat,
                                    get_live_geo, get_location,
                                    handle_any_location, handle_start,
                                    handle_street_search_button, mailing,
                                    refresh_buildings_info,
                                    save_builing_message, search_geo_by_street,
                                    send_geo, show_next_building,
                                    show_previous_building, show_stats)
from utils.utils import UserStates, dp, on_shutdown, on_startup

dp.message_handler(Command("start"))(handle_start)
dp.message_handler(
    Command(
        "mailing_message",
    )
)(mailing)
dp.message_handler(Command("stats"))(show_stats)
dp.message_handler(Command("refresh_database"))(refresh_buildings_info)

dp.message_handler(text="🚏 Название места")(handle_street_search_button)
dp.message_handler(text="🗺️ Поделиться геопозицией")(handle_any_location)
dp.edited_message_handler(content_types=["location"])(get_live_geo)

dp.message_handler(state=UserStates.street_search)(search_geo_by_street)
dp.message_handler(content_types=["location"])(get_location)
dp.message_handler(content_types=["photo", "text", "video_note", "voice"])(chat)

dp.callback_query_handler(text="show_next_building")(show_next_building)
dp.callback_query_handler(
    text="back_from_street_search", state=UserStates.street_search
)(back_from_street_search)
dp.callback_query_handler(text="send_geo")(send_geo)
dp.callback_query_handler(text="show_previous_building")(show_previous_building)
dp.callback_query_handler(text="save")(save_builing_message)


if __name__ == "__main__":
    executor.start_polling(dp, on_shutdown=on_shutdown, on_startup=on_startup)
