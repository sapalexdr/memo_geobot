import math
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
import aiogram
import json
from scripts.from_notion import increment_views_counter

    
async def handle_location(message: aiogram.types.Message, state: aiogram.dispatcher.storage.FSMContext, lat_user: float, lon_user: float, live =False):
    """
    Handles user location messages and sends information about the closest building.

    Args:
    - message (Message): The incoming message containing the user's location.
    - state (FSMContext): The state of the user in the finite state machine.
    - live (bool, optional): If True, it is assumed that the user is sharing live location updates. Default is False.

    This function calculates the distance from the user's location to the closest building in the data.
    It then sends a message to the user with information about the closest building, including its name,
    description, distance, and the number of views. The user is also provided with an inline keyboard to
    view more details, get directions, or view the next building.
    """
    if live:
        start_point = await state.get_data()
        message_to_reply = start_point["message_to_reply"]
        previous_link = start_point.get("previous_link", None)
        
    else:
        start_point = None
        message_to_reply = message.message_id
        previous_link = None

    radius = 0.5 if not live else 0.1

    closest_buildings = get_closest_buildings(
        lat_user, lon_user, radius, message_to_reply)
    
    if not closest_buildings and live:
        return

    if not closest_buildings and not live:
        closest_buildings = get_closest_buildings(
            lat_user, lon_user, 6371, message_to_reply)
        distance = closest_buildings[0]["distance"]
        await message.reply(text=f"В радиусе {round((radius)*1000)} метров нет зданий! До ближайшего {round(distance)} км\n\nЖмите на кнопки!")
        return


    await state.update_data(
        {message.from_user.id: closest_buildings,
            "user_start_point": [lat_user, lon_user]}
    )

    name, distance, photo, link, text, item_id = get_building_properties(
        closest_buildings, index=0)
    choice_menu = create_keyboard(closest_buildings, 0, link)

    if live and previous_link != link:
        views = increment_views_counter(item_id)
        answer = f"<b>{name}</b>\n\n{text}\n\n{int(round(distance, 2) * 1000)} метров\n{views} 👀"
        sent_message = await message.reply_photo(photo, answer, reply_markup=choice_menu,  parse_mode=ParseMode.HTML)
        previous_url = sent_message.reply_markup.inline_keyboard[0][0]["url"]
        await state.update_data({"previous_link": previous_url})
        return

    elif live and previous_link == link:
        return
    
    elif not live:
        views = increment_views_counter(item_id)
        answer = f"<b>{name}</b>\n\n{text}\n\n{int(round(distance, 2) * 1000)} метров\n{views} 👀"
        await message.reply_photo(photo, answer, reply_markup=choice_menu, parse_mode=ParseMode.HTML)
        return


def get_closest_buildings(latitude_user: float, longitude_user: float, radius: float, message_to_reply_id: int) -> list[dict]:
    """
    Get the closest buildings within a given radius from a given location.

    Args:
        latitude_user (float): Latitude in decimal degrees of the user's location.
        longitude_user (float): Longitude in decimal degrees of the user's location.
        radius (float): The radius to search for buildings in kilometers.

    Returns:
        list[dict]: A list of dictionaries, each containing the distance to a building and the building data. The list is sorted by distance.
    """
    with open("data/buildings_data.json") as f:
        buildings_dictionary = json.load(f)
    closest_buildings = []
    for building in buildings_dictionary:
        coordinates = building["coordinates"]
        longitude_building, latitude_building = map(
            float, coordinates.strip("[]").split(",")
        )
        distance = haversine_distance(
            latitude_user, longitude_user, latitude_building, longitude_building
        )
        if distance <= radius * 1.1:
            closest_buildings.append(
                {"distance": distance, "user_start_point": [latitude_user, latitude_building],"message_to_reply": message_to_reply_id,  "building_data": building})
    closest_buildings.sort(key=lambda x: x["distance"])

    return closest_buildings


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


def create_keyboard(closest_buildings: list, index: int, link: str) -> InlineKeyboardMarkup:
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
    get_geo = InlineKeyboardButton(
        text="Как дойти? 🚏", callback_data="send_geo")
    next_building = InlineKeyboardButton(
        text=f"{index+1} из {len(closest_buildings)} | Cледующее здание ⏭️",
        callback_data="show_next_building",
    )
    choice_menu.insert(street_choice)
    choice_menu.insert(get_geo)

    if len(closest_buildings) > 1 and index + 1 != len(closest_buildings):
        choice_menu.insert(next_building)

    return choice_menu


def send_geo_by_coordinates(link: str):
    """
    Retrieves the latitude and longitude of a building based on its link.

    Args:
        link (str): The link of the building to retrieve coordinates for.

    Returns:
        tuple: A tuple of two floats, representing the latitude and longitude of the building.
    """
    with open("data/buildings_data.json") as f:
        buildings_dictionary = json.load(f)
    
    for building in buildings_dictionary:
        if building["link"] == link:
            coordinates_str = str(building["coordinates"])
            coordinates_list = [
                float(x) for x in coordinates_str.strip("[]").split(",")
            ]
            lon_d = float(coordinates_list[0])
            lat_d = float(coordinates_list[1])
    return lat_d, lon_d


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float):
    """
    Calculates the Haversine distance between two points on the earth.

    Args:
        lat1 (float): Latitude of the first point.
        lon1 (float): Longitude of the first point.
        lat2 (float): Latitude of the second point.
        lon2 (float): Longitude of the second point.

    Returns:
        float: The Haversine distance between the two points, in kilometers.
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * \
        math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371
    return c * r
