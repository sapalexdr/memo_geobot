import asyncio
import random

from aiogram import types
from aiogram.dispatcher.storage import FSMContext
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, InputMediaPhoto,
                           KeyboardButton, Message, ParseMode,
                           ReplyKeyboardMarkup)
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from scripts.building_info_scripts import (create_keyboard,
                                           create_keyboard_for_saved_message,
                                           get_building_properties,
                                           handle_location,
                                           send_geo_by_coordinates)
from scripts.from_notion import (check_for_duplicates,
                                 get_buildings_from_notion,
                                 increment_views_counter,
                                 load_buildings_to_mongo)
from utils.db import MongoDB
from utils.utils import ADMIN_GROUP_ID, UserStates, dp


def menu_keyboard():
    street = KeyboardButton(text="🚏 Название места")
    geo = KeyboardButton(text="📍 Ваше местоположение", request_location=True)
    any_geo = KeyboardButton(text="🗺️ Поделиться геопозицией")
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(street, geo)
    keyboard.add(any_geo)
    return keyboard


async def send_welcome_message(message: types.Message):
    """
    Send a welcome message to a user

    Args:
        message: An Aiogram types.Message object.
    """
    keyboard = menu_keyboard()
    await message.answer(
        "Примерный текст\n\nПривет!\n\nсмысловая часть\n\n Вы можете:\nВвести название улицы или места в Москве\nОтправить боту текущую геопозицию\nОтправить любую геопозицию или ее трансляцию",
        reply_markup=keyboard,
    )


async def add_new_user_to_mongo(user_id):
    collection = await MongoDB().get_collection("topos_memo_bot", "users")
    existing_user = await collection.find_one({"id": user_id})

    if existing_user is None:
        user_data = {"id": user_id}
        await collection.insert_one(user_data)

    return True


async def handle_start(message):
    await add_new_user_to_mongo(message.from_user.id)
    await send_welcome_message(message)


async def handle_street_search_button(message: Message, state: FSMContext):
    """
    Handle street search queries.

    Args:
        call: An Aiogram CallbackQuery object.
        state: An Aiogram FSMContext object.
    """
    places = [
        "Улица Солянка, Москва",
        "Даниловский монастырь",
        "Бутырская тюрьма",
        "Камергерский переулок, 2",
        "Лубянская площадь",
        "Таганская улица",
        "Петровка, 38",
        "Метро Чистые пруды",
        "МГУ",
        "Улица Воздвиженка",
    ]

    await state.set_state(UserStates.street_search)
    random_places = random.sample(places, 3)
    await message.answer(
        text=f"Напишите адрес в свободном формате.\n\nНапример\n{random_places[0]}\n{random_places[1]}\n{random_places[2]}"
    )


async def back_from_street_search(call: CallbackQuery, state: FSMContext):
    await dp.bot.delete_message(
        chat_id=call.from_user.id, message_id=call.message.message_id
    )
    await dp.bot.send_message(text="Используйте кнопки!", chat_id=call.from_user.id)
    await state.finish()


async def handle_any_location(message: types.Message, state: FSMContext):
    await message.answer(
        text="Выберите во вложениях обычную геопозицию или трансляцию геопозиции"
    )


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
    back_button = InlineKeyboardButton(
        text="👈 Вернуться", callback_data="back_from_street_search"
    )
    back_from_search_kb.insert(back_button)

    # viewbox = await make_viewbox()
    geolocator = Nominatim(user_agent="geoapiExercises")
    try:
        location = geolocator.geocode(
            f"{message.text}", namedetails=1, country_codes="ru"
        )
        await asyncio.sleep(1)

        if not location:
            await message.reply(
                "Ничего не нашлось. Введите название еще раз или вернитесь назад",
                reply_markup=back_from_search_kb,
            )
            return

        await dp.bot.send_location(
            chat_id=message.from_user.id,
            longitude=location.longitude,
            latitude=location.latitude,
            reply_to_message_id=message.message_id,
        )
        await dp.bot.send_message(
            chat_id=message.from_user.id,
            text=f"🔎\n\nВаш запрос превратился в <b>{location.address}</b>\n\nЕсли запрос неправильный – попробуйте еще раз через кнопки!",
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.message_id,
        )
        await state.finish()

        await handle_location(
            message, state, lat_user=location.latitude, lon_user=location.longitude
        )

    except (GeocoderTimedOut, GeocoderUnavailable):
        await message.reply("Что-то пошло не так, попробуйте еще раз")
        await state.finish()


async def refresh_buildings_info(message: types.Message):
    """
    Refresh buildings information.

    Args:
        message: An Aiogram types.Message object.
    """

    if message.chat.id == ADMIN_GROUP_ID:

        status_message = await message.reply(
            "Обновление займет примерно 1.5 минуты ⏳\n\nПо заверешению придет тэг"
        )

        buildings_list = await get_buildings_from_notion()

        pure_buildings_list = await check_for_duplicates(buildings_list)

        added_count, updated_count = await load_buildings_to_mongo(pure_buildings_list)

        # VIEWBOX = await make_viewbox()

        if added_count or updated_count:
            await status_message.edit_text(
                text=f"✅\n\nДобавлено: {added_count}\nОбновлено: {updated_count}"
            )
        else:
            await status_message.edit_text(text=f"Обновлений нет 🤷‍♂️")

        await dp.bot.send_message(
            text=f"@{message.from_user.username}", chat_id=ADMIN_GROUP_ID
        )


async def show_stats(message: types.Message):
    """
    Show statistics.

    Args:
        message: An Aiogram types.Message object.
        dp: Dispatcher object.
    """
    if message.chat.id == ADMIN_GROUP_ID:
        collection = await MongoDB().get_collection("topos_memo_bot", "users")
        total_users = await collection.count_documents({})
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
        await handle_location(
            message,
            state,
            lat_user=message.location.latitude,
            lon_user=message.location.longitude,
        )
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
    await handle_location(
        message,
        state,
        live=True,
        lat_user=message.location.latitude,
        lon_user=message.location.longitude,
    )


async def send_geo(call: CallbackQuery, state: FSMContext):
    """
    Send geographical location.

    Args:
        call: An Aiogram CallbackQuery object.
        state: An Aiogram FSMContext object.
    """

    link = call.message.reply_markup.inline_keyboard[0][0].url
    lat_d, lon_d = await send_geo_by_coordinates(link)
    await call.message.reply_location(
        latitude=lat_d,
        longitude=lon_d,
        disable_notification=True,
    )
    await call.answer(cache_time=1)


async def get_user_and_building_data_from_cache(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id

    user_data = await state.get_data(user_id)
    closest_buildings = user_data.get(user_id, None)

    if not closest_buildings:
        await call.answer(text="❌ Попробуйте заново отправить геопозицию", cache_time=5)
        return

    link = call.message.reply_markup.inline_keyboard[0][0].url

    return closest_buildings, link


async def find_building_and_execute(
    call: CallbackQuery, state: FSMContext, operation: str, offset=0
):
    closest_buildings, link = await get_user_and_building_data_from_cache(call, state)

    for index, building in enumerate(closest_buildings, start=1):
        if link == building["building_data"]["link"]:

            if operation == "show":
                (
                    name,
                    distance,
                    photo,
                    link,
                    text,
                    building_id,
                ) = get_building_properties(closest_buildings, index + offset)
                choice_menu = create_keyboard(closest_buildings, index + offset, link)
                views = await increment_views_counter(building_id)
                await dp.bot.edit_message_media(
                    media=InputMediaPhoto(
                        photo,
                        caption=f"<b>{name}</b>\n\n{text}\n\n{int(round(distance, 2) * 1000)} метров\n{views} 👀",
                        parse_mode=ParseMode.HTML,
                    ),
                    chat_id=call.from_user.id,
                    message_id=call.message.message_id,
                    reply_markup=choice_menu,
                )

            elif operation == "save":

                (
                    name,
                    distance,
                    photo,
                    link,
                    text,
                    building_id,
                ) = get_building_properties(closest_buildings, index + offset)

                saved_message_menu = create_keyboard_for_saved_message(
                    closest_buildings, index, link
                )

                saved_message = await dp.bot.send_photo(
                    caption=f"<b>{name}</b>\n\n{text}",
                    chat_id=call.from_user.id,
                    photo=photo,
                    reply_markup=saved_message_menu,
                    reply_to_message_id=building["message_to_reply"],
                    parse_mode=ParseMode.HTML,
                )
                await dp.bot.pin_chat_message(
                    call.from_user.id,
                    saved_message.message_id,
                    disable_notification=True,
                )

            break


async def show_building(call: CallbackQuery, state: FSMContext, direction: str):
    offset = -2 if direction == "previous" else 0
    await find_building_and_execute(call, state, "show", offset)


async def show_next_building(call: CallbackQuery, state: FSMContext):
    await show_building(call, state, direction="next")


async def show_previous_building(call: CallbackQuery, state: FSMContext):
    await show_building(call, state, direction="previous")


async def save_builing_message(call: CallbackQuery, state: FSMContext):
    offset = -1
    await find_building_and_execute(call, state, "save", offset)


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
        mailing_text = "\n".join(message.text.split("\n")[1:])

        entities = message.entities
        for entity in entities:
            if entity.type == "text_link":
                link_text = message.text[entity.offset : entity.offset + entity.length]
                mailing_text = mailing_text.replace(
                    link_text, f'<a href="{entity.url}">{link_text}</a>'
                )

        collection = await MongoDB().get_collection("topos_memo_bot", "users")
        total_users = await collection.count_documents({})

        cursor = collection.find({}, {"_id": 0, "id": 1})

        for user in await cursor.to_list(length=None):
            chat_id = user["id"]
            try:
                await dp.bot.send_message(
                    text=mailing_text, chat_id=chat_id, parse_mode="HTML"
                )
            except Exception as e:
                await message.answer(
                    text=f'Failed to send message to user" {user}. Error: {e}"\n\n@sapalexdr'
                )
        await message.answer(
            parse_mode="HTML",
            text=f"Юзеров получили сообщение: {(total_users)}\n{mailing_text}",
        )


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
    collection = await MongoDB().get_collection("topos_memo_bot", "chat")

    if message.chat.id != ADMIN_GROUP_ID:
        user_id = message.from_user.id

        returned_message = await message.forward(ADMIN_GROUP_ID)

        message_id = returned_message.message_id
        await collection.insert_one({"_id": message_id, "user_id": user_id})

    elif message.reply_to_message and message.reply_to_message.from_user.is_bot:
        message_id = message.reply_to_message.message_id
        chat_data = await collection.find_one({"_id": message_id})

        if chat_data:
            user_id = chat_data["user_id"]
            await dp.bot.send_message(user_id, message.text)
