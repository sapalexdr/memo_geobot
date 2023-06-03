import json
import logging
import os

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.storage import FSMContext
from aiogram.types import CallbackQuery, ParseMode
from dotenv.main import load_dotenv
from notion_client import Client

from data.from_notion import (increment_views_counter,
                              write_buildings_data_from_notion)
from scripts.building_info_scripts import (create_keyboard,
                                           get_building_properties,
                                           handle_location,
                                           send_geo_by_coordinates)

logging.basicConfig(
    level=logging.DEBUG, 
    filename='bot.log', 
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
load_dotenv()
BOT_API_TOKEN = os.getenv("BOT_API_TOKEN")
storage = MemoryStorage()
bot = Bot(token=BOT_API_TOKEN)
dp = Dispatcher(bot, storage=storage)
admin_group_id = int(os.getenv("ADMIN_GROUP_ID"))

# Add new users to dictionary to count the anount of them and send welcome message
@dp.message_handler(Command('start'))
async def update_stats(message: types.Message):
    with open('data/stats.json', 'r') as f:
        stats = json.load(f)

    if message.from_user.id not in stats['users']:
        stats['users'].append(message.from_user.id)
        with open("data/stats.json", "w") as f:
            json.dump(
                stats,
                f,
                indent=4,
                ensure_ascii=False
            )
    await message.answer('Привет! _________________ Чтобы воспользоваться ботом, нужно отправить ему геопозицию или трансляцию геопозиции')

# refresh buildings_info from Notion database
@dp.message_handler(Command('refresh_database'), state=None)
async def refresh_buildings_info(message: types.Message):
    if message.chat.id == admin_group_id:
        await message.answer('В процессе')
        update = write_buildings_data_from_notion()
        if update == True:
            await message.answer('Готово! ✅')
        else:
            await message.answer('Что-то пошло не так, попробуй еще раз')

# Get amount of users to groupchat
@dp.message_handler(Command('stats'))
async def show_stats(message: types.Message):

    with open('data/stats.json', 'r') as f:
        stats = json.load(f)
    total_users = len(stats['users'])
    # with open('data/buildings_data.json') as f:
    #     buildings_data = json.load(f)
    # total_views = 0
    # for view in (buildings_data):
    #     total_views += view['views']

    # stats['total_views'] = total_views
    # stats['total_buildings'] = len(buildings_data)

    # with open("data/stats.json", "w") as f:
    #     json.dump(
    #         stats,
    #         f,
    #         indent=4,
    #         ensure_ascii=False
    #     )

    # stats_message = f"📈Статистика\n\nПользователей: {total_users}\nПросмотров: {total_views}, Всего зданий: {len(buildings_data)}"
    stats_message = f"Пользуются ботом: {total_users}"

    await dp.bot.send_message(text=stats_message, chat_id=admin_group_id)

# handle static location
@dp.message_handler(content_types=["location"])
async def get_location(message: types.Message, state: FSMContext):
    if not message.location.live_period:
        await handle_location(message, state)
    else:
        await state.update_data(
            {
                "user_start_point": [
                    message.location.latitude,
                    message.location.longitude,
                ],
                "message_to_reply": message.message_id,
            }
        )

@dp.edited_message_handler(content_types=["location"])
async def get_live_geo(message: types.Message, state: FSMContext):
    await handle_location(message, state, live=True)

# handle user's click on "как дойти?" button
@dp.callback_query_handler(text="send_geo")
async def send_geo(call: CallbackQuery, state: FSMContext):

    link = call.message.reply_markup.inline_keyboard[0][0].url
    lat_d, lon_d = send_geo_by_coordinates(link)
    await call.message.reply_location(
        latitude=lat_d, longitude=lon_d, disable_notification=True
    )
    await call.answer(cache_time=1)

# handle user's click on «показать следуюее здание» button
@dp.callback_query_handler(text="show_next_building")
async def show_next_building(call: CallbackQuery, state: FSMContext):

    closest_buildings = await state.get_data(call.from_user.id)
    closest_buildings = closest_buildings.get(call.from_user.id, None)

    if not closest_buildings:
        await call.answer(text="❌ Попробуйте заново отправить геопозицию")
        return

    link = call.message.reply_markup.inline_keyboard[0][0].url

    for index, item in enumerate(closest_buildings):
        if link == item["building_data"]["link"]:
            name, distance, photo, link, text, item_id = get_building_properties(
                closest_buildings, index + 1
            )
            views = increment_views_counter(item_id)

            choice_menu = create_keyboard(closest_buildings, index + 1, link)

            await call.answer(
                text=f"{index + 1 + 1} из {len(closest_buildings)} в радиусе 500 метров"
            )

            await dp.bot.send_photo(
                caption=f"<b>{name}</b>\n\n{text}\n\n{int(round(distance, 2) * 1000)} метров\n{views} 👀",
                chat_id=call.from_user.id,
                photo=photo,
                reply_markup=choice_menu,
                reply_to_message_id=item["message_to_reply"],
                parse_mode=ParseMode.HTML,
            )
            break

# handle user's message to bot and forward them to groupchat with the ability to answer by reply
@dp.message_handler(content_types=['photo', 'text', 'video', 'document','video_note', 'voice', 'sticker', 'audio', 'contact'])
async def chat(message: types.Message):
    if message.chat.id != admin_group_id:

        user_id = message.from_user.id

        returend_message = await message.forward(admin_group_id)
        with open('data/message_user.json', 'r') as j:
            message_id_and_user_id = json.load(j)

        message_id = returend_message.message_id
        message_id_and_user_id[message_id] = user_id

        with open('data/message_user.json', 'w') as json_file:
            json.dump(
                message_id_and_user_id,
                json_file,
                indent=4,
                ensure_ascii=False,
                separators=(",", ": "),
            )

    elif message.reply_to_message:
        try:
            await dp.bot.send_message(message.reply_to_message.forward_from.id, message.text)
        except AttributeError:
            message_id = message.reply_to_message.message_id
            with open('data/message_user.json', 'r') as j:
                message_id_and_user_id = json.load(j)
            user_id = int(message_id_and_user_id[str(message_id)])
            await dp.bot.send_message(user_id, message.text)


if __name__ == "__main__":
    executor.start_polling(dp)
