from notion_client import Client
import json
from utils.utils import NOTION_API_TOKEN, NOTION_DB



def write_buildings_data_from_notion():
    """
    Fetches building data from a Notion database and writes it to a JSON file.

    Retrieves building data from the Notion database specified by the NOTION_DB constant.
    The data includes the building's ID, name, layer, text, coordinates, image, link, and views.
    This data is stored in a list of dictionaries, which is then written to a JSON file named "buildings_data.json".
    """
    notion = Client(auth=NOTION_API_TOKEN)

    results = []
    next_cursor = None

    while True:
        response = notion.databases.query(
            database_id=NOTION_DB, page_size=100, start_cursor=next_cursor)
        results += response.get("results")
        next_cursor = response.get("next_cursor")

        if not next_cursor:
            break

    buildings_list = []

    for notion_data in results:
        properties = notion_data["properties"]
        item_id = notion_data['id']

        if properties["properties.layer"]["select"] is not None:
            layer = properties["properties.layer"]["select"]["name"]
        else:
            continue

        topos_id = properties["properties.topos_id"]["number"]
        taxonomy_id = properties["properties.taxonomy_id"]["number"]
        link = f"https://topos.memo.ru/article/{topos_id}+{taxonomy_id}"

        views_counter = properties["views_counter"]["number"] or 0

        name_property = properties["properties.name"]
        name = name_property["rich_text"][0]["text"]["content"] if "rich_text" in name_property and name_property["rich_text"] else None

        coordinates_property = properties["geometry.coordinates"]
        coordinates = coordinates_property["title"][0]["text"][
            "content"] if "title" in coordinates_property and coordinates_property["title"] else None

        image_property = properties["properties.image"]
        image = image_property["files"][0]["name"] if "files" in image_property and image_property["files"] else None

        text_property = properties["properties.text"]
        text = text_property["rich_text"][0]["plain_text"] if "rich_text" in text_property and text_property["rich_text"] else ""

        buildings_list.append(
            {
                "id": item_id,
                "name": name,
                "layer": layer,
                "text": text,
                "coordinates": coordinates,
                "image": image,
                "link": link,
                "views": views_counter
            }
        )

    with open("data/buildings_data.json", "w") as f:
        json.dump(buildings_list, f, indent=4, ensure_ascii=False)
        
    return True


def increment_views_counter(page_id):
    notion = Client(auth=NOTION_API_TOKEN)
    page = notion.pages.retrieve(page_id)
    current_views_counter = page["properties"]["views_counter"]["number"]

    if current_views_counter is None:
        new_views_counter = 1
    else:
        new_views_counter = current_views_counter + 1

    notion.pages.update(
        page_id,
        properties={
            "views_counter": {
                "number": new_views_counter
            }
        }
    )
    return new_views_counter
