import aiogram
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from motor.motor_asyncio import AsyncIOMotorClient
from scripts.from_notion import increment_views_counter
from utils.db import MongoDB
from utils.utils import DYNAMIC_RADIUS, STATIC_RADIUS


async def handle_location(
    message: aiogram.types.Message,
    state: aiogram.dispatcher.storage.FSMContext,
    lat_user: float,
    lon_user: float,
    live=False,
):
    if live:
        start_point = await state.get_data()
        message_to_reply = start_point["message_to_reply"]
        previous_link = start_point.get("previous_link", None)
    else:
        start_point = None
        message_to_reply = message.message_id
        previous_link = None

    radius = STATIC_RADIUS if not live else DYNAMIC_RADIUS
    closest_buildings = await get_closest_buildings(
        lat_user, lon_user, radius, message_to_reply
    )

    if not closest_buildings:
        if live:
            return
        else:
            await handle_no_closest_building(
                message, lat_user, lon_user, message_to_reply, radius
            )
            return

    await state.update_data(
        {
            message.from_user.id: closest_buildings,
            "user_start_point": [lat_user, lon_user],
        }
    )

    name, distance, photo, link, text, item_id = get_building_properties(
        closest_buildings, index=0
    )
    choice_menu = create_keyboard(closest_buildings, 0, link)

    if live:
        await handle_live_location(
            message,
            state,
            previous_link,
            link,
            name,
            distance,
            photo,
            text,
            item_id,
            choice_menu,
        )
    else:
        await handle_static_location(
            message, name, distance, photo, text, item_id, choice_menu
        )


async def handle_no_closest_building(
    message, lat_user, lon_user, message_to_reply, radius
):
    closest_buildings = await get_closest_buildings(
        lat_user, lon_user, 20004, message_to_reply
    )
    distance = closest_buildings[0]["distance"]
    await message.reply(
        text=f"В радиусе {round((radius)*1000)} метров нет зданий! До ближайшего {round(distance)} км\n\nЖмите на кнопки!"
    )


async def handle_live_location(
    message,
    state,
    previous_link,
    link,
    name,
    distance,
    photo,
    text,
    item_id,
    choice_menu,
):
    if previous_link != link:
        views = await increment_views_counter(item_id)
        answer = f"<b>{name}</b>\n\n{text}\n\n{int(round(distance, 2) * 1000)} метров\n{views} 👀"
        sent_message = await message.reply_photo(
            photo, answer, reply_markup=choice_menu, parse_mode=ParseMode.HTML
        )
        previous_url = sent_message.reply_markup.inline_keyboard[0][0]["url"]
        await state.update_data({"previous_link": previous_url})


async def handle_static_location(
    message, name, distance, photo, text, item_id, choice_menu
):
    views = await increment_views_counter(item_id)

    answer = (
        f"<b>{name}</b>\n\n{text}\n\n{int(round(distance, 2) * 1000)} метров\n{views} 👀"
    )
    await message.reply_photo(
        photo, answer, reply_markup=choice_menu, parse_mode=ParseMode.HTML
    )


async def get_closest_buildings(
    latitude_user: float, longitude_user: float, radius: float, message_to_reply_id: int
) -> list[dict]:
    radius_in_meters = radius * 1000

    pipeline = create_mongo_pipeline(latitude_user, longitude_user, radius_in_meters)

    return await get_buildings_from_pipeline(
        pipeline, latitude_user, longitude_user, message_to_reply_id
    )


def create_mongo_pipeline(
    latitude_user: float, longitude_user: float, radius_in_meters: float
) -> list[dict]:
    return [
        {
            "$geoNear": {
                "near": {
                    "type": "Point",
                    "coordinates": [longitude_user, latitude_user],
                },
                "distanceField": "distance",
                "maxDistance": radius_in_meters,
                "includeLocs": "location",
                "spherical": True,
            }
        }
    ]


async def get_buildings_from_pipeline(
    pipeline: list[dict],
    latitude_user: float,
    longitude_user: float,
    message_to_reply_id: int,
) -> list[dict]:
    closest_buildings = []
    collection = await MongoDB().get_collection(
        "topos_memo_bot", "buildings_collection"
    )
    async for building in collection.aggregate(pipeline):
        distance = building["distance"] / 1000
        closest_buildings.append(
            create_building_dict(
                building, distance, latitude_user, longitude_user, message_to_reply_id
            )
        )

    return closest_buildings


def create_building_dict(
    building, distance, latitude_user, longitude_user, message_to_reply_id
):
    return {
        "distance": distance,
        "user_start_point": [latitude_user, longitude_user],
        "message_to_reply": message_to_reply_id,
        "building_data": {
            "id": building["id"],
            "name": building["name"],
            "layer": building["layer"],
            "text": building["text"],
            "location": building["location"],
            "image": building["image"],
            "link": building["link"],
            "views": int(building["views"]),
        },
    }


def get_building_properties(closest_buildings: list, index: int):
    """
    Retrieve the properties of the building in the given index of closest_buildings list of dictionaries.

    Args:
        closest_buildings (list): List of dictionaries, each containing information about a building.
        index (int): Index of the building to retrieve information from.

    Returns:
        tuple: A tuple containing the building's name, distance, photo, link, text, item_id.
    """

    name = closest_buildings[index]["building_data"]["name"]
    distance = closest_buildings[index]["distance"]
    photo = closest_buildings[index]["building_data"]["image"]
    link = closest_buildings[index]["building_data"]["link"]
    text = closest_buildings[index]["building_data"]["text"]
    item_id = closest_buildings[index]["building_data"]["id"]
    return name, distance, photo, link, text, item_id


def create_keyboard(
    closest_buildings: list, index: int, link: str
) -> InlineKeyboardMarkup:
    """
    Creates an InlineKeyboardMarkup object with buttons to display information about a building.

    Args:
        closest_buildings (list): List of dictionaries, each containing information about a building.
        index (int): Index of the building to display information about.
        link (str): URL to show more information about the building.

    Returns:
        InlineKeyboardMarkup: An InlineKeyboardMarkup object with buttons for the user to view more information or get directions to the building.
    """

    choice_menu = InlineKeyboardMarkup(row_width=1)
    street_choice = InlineKeyboardButton(
        text="Подробнее 📖",
        callback_data="get_link",
        url=link,
    )
    get_geo = InlineKeyboardButton(text="Как дойти? 🚏", callback_data="send_geo")
    next_building = InlineKeyboardButton(
        text=f"Cледующее здание ⏭️",
        callback_data="show_next_building",
    )
    counter = InlineKeyboardButton(
        text=f"{index+1} из {len(closest_buildings)}", callback_data="counter"
    )
    previous_building = InlineKeyboardButton(
        text="⏮️ Предыдущее здание", callback_data="show_previous_building"
    )
    next_building_short = InlineKeyboardButton(
        text="⏭️", callback_data="show_next_building"
    )
    previous_building_short = InlineKeyboardButton(
        text="⏮️", callback_data="show_previous_building"
    )

    save = InlineKeyboardButton(text="Сохранить 📥", callback_data="save")

    choice_menu.row(street_choice, get_geo)

    if len(closest_buildings) > 1 and index != 0:
        choice_menu.insert(previous_building)

    if len(closest_buildings) > 1 and index + 1 != len(closest_buildings):
        choice_menu.insert(next_building)

    if (
        len(closest_buildings) > 1
        and index != 0
        and index + 1 != len(closest_buildings)
    ):
        choice_menu.inline_keyboard.remove([next_building])
        choice_menu.inline_keyboard.remove([previous_building])
        choice_menu.row(previous_building_short, next_building_short)

    choice_menu.insert(save)
    choice_menu.insert(counter)

    return choice_menu


def create_keyboard_for_saved_message(
    closest_buildings: list, index: int, link: str
) -> InlineKeyboardMarkup:
    saved_message_menu = InlineKeyboardMarkup(row_width=2)
    street_choice = InlineKeyboardButton(
        text="Подробнее 📖",
        callback_data="get_link",
        url=link,
    )
    get_geo = InlineKeyboardButton(text="Как дойти? 🚏", callback_data="send_geo")
    saved_message_menu.row(street_choice, get_geo)
    return saved_message_menu


async def send_geo_by_coordinates(link: str):
    """
    Retrieves the latitude and longitude of a building based on its link.

    Args:
        link (str): The link of the building to retrieve coordinates for.

    Returns:
        tuple: A tuple of two floats, representing the latitude and longitude of the building.
    """

    collection = await MongoDB().get_collection(
        "topos_memo_bot", "buildings_collection"
    )
    building = await collection.find_one({"link": link})

    if building:
        coordinates = building["location"]["coordinates"]
        lon_d = coordinates[0]
        lat_d = coordinates[1]
        return lat_d, lon_d

    return None
