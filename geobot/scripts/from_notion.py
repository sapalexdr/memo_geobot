import logging

from notion_client import Client
from pymongo import GEOSPHERE
from utils.db import MongoDB
from utils.utils import NOTION_API_TOKEN, NOTION_DB


async def get_buildings_from_notion():
    """
    Fetches building data from a Notion database and writes it to a MongoDB collection.

    Retrieves building data from the Notion database specified by the NOTION_DB constant.
    The data includes the building's ID, name, layer, text, coordinates, image, and link.
    The views counter is fetched from the current MongoDB collection.
    This data is stored in a list of dictionaries.
    """
    try:
        notion = Client(auth=NOTION_API_TOKEN)
    except Exception as e:
        logging.error(f"Failed to connect to Notion: {str(e)}")
        return

    try:
        collection = await MongoDB().get_collection(
            "topos_memo_bot", "buildings_collection"
        )
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB: {str(e)}")
        return

    results = []
    next_cursor = None
    try:
        while True:
            response = notion.databases.query(
                database_id=NOTION_DB, page_size=100, start_cursor=next_cursor
            )
            results += response.get("results")
            next_cursor = response.get("next_cursor")

            if not next_cursor:
                break
    except Exception as e:
        logging.error(f"Failed to gather data: {str(e)}")
        return

    buildings_list = []

    for notion_data in results:
        properties = notion_data["properties"]
        item_id = notion_data["id"]

        if properties["properties.layer"]["select"] is not None:
            layer = properties["properties.layer"]["select"]["name"]
        else:
            continue

        topos_id = properties["properties.topos_id"]["number"]
        taxonomy_id = properties["properties.taxonomy_id"]["number"]
        link = f"https://topos.memo.ru/article/{topos_id}+{taxonomy_id}"

        current_doc = await collection.find_one({"id": item_id})
        views_counter = current_doc["views"] if current_doc else 0
        name_property = properties["properties.name"]
        name = (
            name_property["rich_text"][0]["text"]["content"]
            if "rich_text" in name_property and name_property["rich_text"]
            else None
        )

        coordinates_property = properties["geometry.coordinates"]
        coordinates = (
            coordinates_property["title"][0]["text"]["content"]
            if "title" in coordinates_property and coordinates_property["title"]
            else None
        )

        image_property = properties["properties.image"]
        image = (
            image_property["files"][0]["name"]
            if "files" in image_property and image_property["files"]
            else None
        )

        text_property = properties["properties.text"]
        text = (
            text_property["rich_text"][0]["plain_text"]
            if "rich_text" in text_property and text_property["rich_text"]
            else ""
        )
        longitude, latitude = map(float, coordinates.strip("[]").split(","))

        buildings_list.append(
            {
                "id": item_id,
                "name": name,
                "layer": layer,
                "text": text,
                "location": {"type": "Point", "coordinates": [longitude, latitude]},
                "image": image,
                "link": link,
                "views": views_counter,
            }
        )

    return buildings_list


async def check_for_duplicates(buildings_list):
    pure_buildings_list = []

    for building in buildings_list:
        name = building["name"]
        link = building["link"]
        stripped_link = link.split("+")[0]

        if any(
            b["name"] == name and b["link"].split("+")[0] == stripped_link
            for b in pure_buildings_list
        ):
            continue

        pure_buildings_list.append(building)

    return pure_buildings_list


# async def make_viewbox():
#     collection = await MongoDB().get_collection('topos_memo_bot', 'buildings_collection')

#     max_longitude_doc = await collection.find().sort("location.coordinates.0", -1).limit(1).to_list(length=1)
#     min_longitude_doc = await collection.find().sort("location.coordinates.0", 1).limit(1).to_list(length=1)

#     max_latitude_doc = await collection.find().sort("location.coordinates.1", -1).limit(1).to_list(length=1)
#     min_latitude_doc = await collection.find().sort("location.coordinates.1", 1).limit(1).to_list(length=1)

#     # ensure you have the documents before accessing
#     if max_longitude_doc and min_longitude_doc and max_latitude_doc and min_latitude_doc:
#         max_longitude = max_longitude_doc[0]["location"]["coordinates"][0]
#         min_longitude = min_longitude_doc[0]["location"]["coordinates"][0]

#         max_latitude = max_latitude_doc[0]["location"]["coordinates"][1]
#         min_latitude = min_latitude_doc[0]["location"]["coordinates"][1]

#         top_left = Point(max_latitude, min_longitude)
#         bottom_right = Point(min_latitude, max_longitude)

#         viewbox = [top_left, bottom_right]
#         return viewbox


async def load_buildings_to_mongo(buildings_list):
    """
    Loads the list of building data into a MongoDB collection.

    For each building, if a record with the same 'id' exists in the collection,
    it updates the record with the new data if any parameters have changed.
    If no such record exists, it inserts the new data.
    After loading the data, it creates a geospatial index on the 'location' field for efficient querying.
    """
    try:
        collection = await MongoDB().get_collection(
            "topos_memo_bot", "buildings_collection"
        )
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB: {str(e)}")
        return False

    added_count = 0
    updated_count = 0

    try:
        operations = []

        for building in buildings_list:
            result = await collection.update_one(
                {"id": building["id"]}, {"$set": building}, upsert=True
            )

            if result.upserted_id is not None:
                added_count += 1
            elif result.modified_count > 0:
                updated_count += 1

        if operations:
            await collection.bulk_write(operations)

        if "location_2dsphere" not in await collection.index_information():
            await collection.create_index([("location", GEOSPHERE)])

    except Exception as e:
        logging.error(f"Failed to upsert building: {str(e)}")
        return False

    return added_count, updated_count


async def increment_views_counter(page_id):
    """
    Increments the view counter for a page in the MongoDB collection.

    If the page ID is found in the MongoDB collection, it increments the 'views' field for that page.
    If the page ID is not found, it returns None.
    """
    try:
        collection = await MongoDB().get_collection(
            "topos_memo_bot", "buildings_collection"
        )
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB: {str(e)}")
        return None

    try:
        result = await collection.update_one(
            {"id": page_id}, {"$inc": {"views": 1}}, upsert=False
        )

        if result.matched_count > 0:
            page = await collection.find_one({"id": page_id})
            new_views_counter = page["views"]
            return new_views_counter

    except Exception as e:
        logging.error(f"Failed to increment views counter: {str(e)}")
        return None
