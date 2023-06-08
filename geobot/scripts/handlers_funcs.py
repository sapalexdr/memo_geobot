import json
import asyncio
import random

from aiogram import types
from aiogram.dispatcher.storage import FSMContext
from aiogram.types import CallbackQuery, ParseMode, Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode


from scripts.from_notion import (increment_views_counter,
                              write_buildings_data_from_notion)
from scripts.building_info_scripts import (create_keyboard,
                                           get_building_properties,
                                           handle_location,
                                           send_geo_by_coordinates)
from aiogram.types import ParseMode, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from utils.utils import dp, UserStates,ADMIN_GROUP_ID

from typing import Any, Dict


async def load_json_data(file_name: str) -> Dict[str, Any]:
    """
    Load data from a JSON file.

    Args:
        file_name: A string of the JSON file name.

    Returns:
        A dictionary of the JSON data.
    """
    with open(file_name, 'r') as f:
        return json.load(f)


async def save_json_data(file_name: str, data: Dict[str, Any]):
    """
    Save data to a JSON file.

    Args:
        file_name: A string of the JSON file name.
        data: A dictionary of the data to save.
    """
    with open(file_name, 'w') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


async def append_unique_user_id(users: Dict[str, Any], user_id: int):
    """
    Add a unique user ID to a dictionary and save it.

    Args:
        users: A dictionary of users.
        user_id: An integer of the user ID to add.
    """
    if user_id not in users['users']:
        users['users'].append(user_id)
        await save_json_data("geobot/data/users.json", users)


def menu_keyboard():
    street = KeyboardButton(text='🚏 Название места')
    geo = KeyboardButton(
        text='📍 Ваше местоположение', request_location=True)
    any_geo = KeyboardButton(text='🗺️ Поделиться геопозицией')
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(street, geo)
    keyboard.add(any_geo)
    return keyboard

async def send_welcome_message(message: types.Message):
    """
    Send a welcome message to a user.

    Args:
        message: An Aiogram types.Message object.
    """
    keyboard = menu_keyboard()
    await message.answer(
        'Примерный текст\n\nПривет!\n\nсмысловая часть\n\n Вы можете:\nВвести название улицы или места в Москве\nОтправить боту текущую геопозицию\nОтправить любую геопозицию или ее трансляцию',
        reply_markup=keyboard)
    

async def handle_start(message: types.Message):
    """
    Handles the start command, add a user ID to users and sends a welcome message.

    Args:
        message: An Aiogram types.Message object.
    """
    users = await load_json_data("geobot/data/users.json")
    await append_unique_user_id(users, message.from_user.id)
    await send_welcome_message(message)


async def handle_street_search_button(message: Message, state: FSMContext):
    """
    Handle street search queries.

    Args:
        call: An Aiogram CallbackQuery object.
        state: An Aiogram FSMContext object.
    """
    places = ["Дом на набережной", "Улица Солянка", "Андрониковский монастырь", "Бутырская тюрьма",
              "Камергерский переулок", "Лубянская площадь", "Большая Лубянка", "Площадь Труда",
              "Сквер в Полянке", "Таганская улица", "Петровка, 38", "Метро Чистые пруды"
              "Дом на улице Пречистенка", "Улица Воздвиженка", "Улица Крымский Вал", "Переулок Сивцев Вражек",
              "Волхонка", "Коммунистическая улица в Москве", "Большой Спасоглинищевский переулок", "Улица Шаболовка"]
    
    
    await state.set_state(UserStates.street_search)
    random_places = random.sample(places, 3)
    await message.answer(text=f'Напишите адрес в свободном формате.\n\nНапример: {random_places[0]}, {random_places[1]}, {random_places[2]}')


async def back_from_street_search(call: CallbackQuery, state:FSMContext):
    await dp.bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    await dp.bot.send_message(text='Используйте кнопки!', chat_id=call.from_user.id)
    await state.finish()

async def handle_any_location(message: types.Message, state: FSMContext):
    await message.answer(text='Выберите во вложениях обычную геопозицию или трансляцию геопозиции')

async def search_geo_by_street(message: types.Message, state: FSMContext):
    """
    Handles the search for a location based on a street name input by the user. Uses the 
    geopy's Nominatim geocoder to convert the street name into geographic coordinates. 
    If a location is found, the bot sends the location's coordinates to the user and invokes the
    handle_location function. If the geocoder encounters a timeout or unavailability error, 
    it informs the user to try again.

    Args:
        message: An Aiogram types.Message object that contains the user's message with the street name.
        state: An Aiogram FSMContext object for maintaining context-related information in a user's session.
        dp: Dispatcher object for sending and handling updates from and to the Telegram server.
    """
    
    back_from_search_kb = InlineKeyboardMarkup()
    back_button = InlineKeyboardButton(text='👈 Вернуться', callback_data='back_from_street_search')
    back_from_search_kb.insert(back_button)

    
    geolocator = Nominatim(user_agent="geoapiExercises")
    try:
        location = geolocator.geocode(f"{message.text}")
        await asyncio.sleep(1)

        if not location:
            await message.reply('Ничего не нашлось. Введите название еще раз или вернитесь назад',reply_markup=back_from_search_kb)
            return

        await dp.bot.send_location(chat_id=message.from_user.id, longitude=location.longitude, latitude=location.latitude)
        await state.finish()

        await handle_location(message, state, lat_user=location.latitude, lon_user=location.longitude)

    except (GeocoderTimedOut, GeocoderUnavailable):
        await message.reply('Что-то пошло не так, попробуйте еще раз')
        await state.finish()


async def refresh_buildings_info(message: types.Message):
    """
    Refresh buildings information.

    Args:
        message: An Aiogram types.Message object.
    """
    if message.chat.id == ADMIN_GROUP_ID:
        await message.answer('В процессе')
        update = write_buildings_data_from_notion()
        if update:
            await message.answer('Готово! ✅')
        else:
            await message.answer('Что-то пошло не так, попробуй еще раз')


async def show_stats(message: types.Message):
    """
    Show statistics.

    Args:
        message: An Aiogram types.Message object.
        dp: Dispatcher object.
    """

    stats = await load_json_data('geobot/data/users.json')
    total_users = len(stats['users'])
    stats_message = f"Пользуются ботом: {total_users}"

    await dp.bot.send_message(text=stats_message, chat_id=ADMIN_GROUP_ID)


async def get_location(message: types.Message, state: FSMContext):
    """
    Get location.

    Args:
        message: An Aiogram types.Message object.
        state: An Aiogram FSMContext object.
    """
    if not message.location.live_period:
        await handle_location(message, state, lat_user=message.location.latitude, lon_user=message.location.longitude)
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


async def get_live_geo(message: types.Message, state: FSMContext):
    """
    Get live location updates.

    Args:
        message: An Aiogram types.Message object.
        state: An Aiogram FSMContext object.
    """
    await handle_location(message, state, live=True, lat_user=message.location.latitude, lon_user=message.location.longitude)


async def send_geo(call: CallbackQuery, state: FSMContext):
    """
    Send geographical location.

    Args:
        call: An Aiogram CallbackQuery object.
        state: An Aiogram FSMContext object.
    """

    link = call.message.reply_markup.inline_keyboard[0][0].url
    lat_d, lon_d = send_geo_by_coordinates(link)
    await call.message.reply_location(
        latitude=lat_d, longitude=lon_d, disable_notification=True, 
    )
    await call.answer(cache_time=1)


async def show_next_building(call: CallbackQuery, state: FSMContext):
    """
    Processes the callback query for showing the next closest building to a user's location.
    It gets the user's data from the state, identifies the next building in the sorted list
    of buildings, and sends a detailed message about the building to the user. The message includes
    the building's name, distance from the user's location, an image of the building, and a
    choice menu to navigate through the buildings.

    Args:
        call: An Aiogram CallbackQuery object.
        state: An Aiogram FSMContext object.
        dp: Dispatcher object.
    """
    user_id = call.from_user.id

    user_data = await state.get_data(user_id)
    closest_buildings = user_data.get(user_id, None)

    if not closest_buildings:
        await call.answer(text="❌ Попробуйте заново отправить геопозицию", cache_time=5)
        return

    link = call.message.reply_markup.inline_keyboard[0][0].url

    for index, building in enumerate(closest_buildings, start=1):
        if link == building["building_data"]["link"]:
            name, distance, photo, link, text, building_id = get_building_properties(
                closest_buildings, index)
            views = increment_views_counter(building_id)

            choice_menu = create_keyboard(closest_buildings, index, link)

            await call.answer(text=f"{index} из {len(closest_buildings)} в радиусе 500 метров", cache_time=2)

            await dp.bot.send_photo(
                caption=f"<b>{name}</b>\n\n{text}\n\n{int(round(distance, 2) * 1000)} метров\n{views} 👀",
                chat_id=user_id,
                photo=photo,
                reply_markup=choice_menu,
                reply_to_message_id=building["message_to_reply"],
                parse_mode=ParseMode.HTML,
            )
            break


async def mailing(message: types.Message):
    """
    Handles a mailing task. When a message is received from the admin group, it prepares the text
    with correct HTML formatting and sends it to all the users. The user list is fetched from a
    JSON file. It then logs any exceptions and sends a message back to the admin about the
    number of users that received the message.

    Args:
        message: An Aiogram types.Message object.
        dp: Dispatcher object.
    """
    if message.chat.id == ADMIN_GROUP_ID:
        mailing_text = '\n'.join(message.text.split('\n')[1:])

        entities = message.entities
        for entity in entities:
            if entity.type == 'text_link':
                link_text = message.text[entity.offset:entity.offset + entity.length]
                mailing_text = mailing_text.replace(
                    link_text, f'<a href="{entity.url}">{link_text}</a>')

        user_list = await load_json_data('geobot/data/users.json')
        user_list = user_list['users']

        for user in user_list:
            try:
                await dp.bot.send_message(text=mailing_text, chat_id=user, parse_mode='HTML')
            except Exception as e:
                await message.answer(text=f'f""Failed to send message to user" {user}. Error: {e}"\n\n@sapalexdr')
        await message.answer(parse_mode='HTML', text=f"Юзеров получили сообщение: {len(user_list)}\n\n«{mailing_text}»")


async def chat(message: types.Message):
    """
    Handles chat messages between users and the bot admin. For a message from a user, it forwards
    the message to the admin group and saves the user's id with the forwarded message id.
    For a message from the admin that is a reply to a user's message, it fetches the user's id
    from the message id and sends the admin's message to the user.

    Args:
        message: An Aiogram types.Message object.
        dp: Dispatcher object.
    """
    if message.chat.id != ADMIN_GROUP_ID:
        user_id = message.from_user.id

        returend_message = await message.forward(ADMIN_GROUP_ID)
        chat_data = await load_json_data('geobot/data/chat_data.json')

        message_id = returend_message.message_id
        chat_data[message_id] = user_id
        await save_json_data('geobot/data/chat_data.json', chat_data)

    elif message.reply_to_message.from_user.is_bot:
        message_id = message.reply_to_message.message_id
        chat_data = await load_json_data('geobot/data/chat_data.json')
        user_id = int(chat_data[str(message_id)])
        await dp.bot.send_message(user_id, message.text)
