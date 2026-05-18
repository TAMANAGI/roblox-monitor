import requests
import json
import time

USER_ID = 123456789

BROOKHAVEN_PLACE_ID = 4924922222

def get_presence():

    url = "https://presence.roblox.com/v1/presence/users"

    payload = {
        "userIds":[USER_ID]
    }

    r = requests.post(url,json=payload)

    return r.json()

while True:

    try:

        data = get_presence()

        user = data["userPresences"][0]

        state = user["userPresenceType"]

        place = user.get("placeId")

        status = "OFFLINE"
        game = ""

        if state == 1:
            status = "ONLINE"

        elif state == 2:

            if place == BROOKHAVEN_PLACE_ID:
                status = "IN GAME"
                game = "Brookhaven RP"

            else:
                status = "IN GAME"
                game = f"PlaceId {place}"

        output = {
            "status":status,
            "game":game
        }

        with open("status.json","w") as f:
            json.dump(output,f)

        print(output)

    except Exception as e:
        print(e)

    time.sleep(30)