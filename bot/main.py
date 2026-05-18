from flask import Flask, jsonify, request
from flask_cors import CORS

import requests
import urllib3
import time

urllib3.disable_warnings()

app = Flask(__name__)

CORS(app)

# =========================

BROOKHAVEN_PLACE_ID = 4924922222

# =========================

def get_user_id(username):

    url = "https://users.roblox.com/v1/usernames/users"

    payload = {
        "usernames": [username],
        "excludeBannedUsers": False
    }

    r = requests.post(
        url,
        json=payload,
        verify=False
    )

    data = r.json()

    return data["data"][0]["id"]

# =========================

def get_presence(user_id):

    url = "https://presence.roblox.com/v1/presence/users"

    payload = {
        "userIds": [user_id]
    }

    r = requests.post(
        url,
        json=payload,
        verify=False
    )

    return r.json()

# =========================

def get_user_info(user_id):

    url = f"https://users.roblox.com/v1/users/{user_id}"

    r = requests.get(
        url,
        verify=False
    )

    return r.json()

# =========================

def get_avatar(user_id):

    url = (
        "https://thumbnails.roblox.com/v1/users/avatar-headshot"
        f"?userIds={user_id}"
        "&size=420x420"
        "&format=Png"
        "&isCircular=false"
    )

    r = requests.get(
        url,
        verify=False
    )

    data = r.json()

    return data["data"][0]["imageUrl"]

# =========================

def get_friends_count(user_id):

    url = f"https://friends.roblox.com/v1/users/{user_id}/friends/count"

    r = requests.get(
        url,
        verify=False
    )

    return r.json()["count"]

# =========================

def get_followers_count(user_id):

    url = f"https://friends.roblox.com/v1/users/{user_id}/followers/count"

    r = requests.get(
        url,
        verify=False
    )

    return r.json()["count"]

# =========================

@app.route("/status")
def status():

    username = request.args.get("username")

    if not username:

        return jsonify({
            "error": "username required"
        })

    user_id = get_user_id(username)

    presence = get_presence(user_id)

    user = presence["userPresences"][0]

    state = user["userPresenceType"]

    place = user.get("placeId")

    status = "OFFLINE"
    game = ""

    if state == 1:

        status = "ONLINE"

    elif state == 2:

        status = "IN GAME"

        if place == BROOKHAVEN_PLACE_ID:

            game = "Brookhaven RP"

        else:

            game = f"PlaceId {place}"

    elif state == 3:

        status = "IN STUDIO"

    info = get_user_info(user_id)

    avatar = get_avatar(user_id)

    friends = get_friends_count(user_id)

    followers = get_followers_count(user_id)

    return jsonify({

        "username": info["name"],
        "displayName": info["displayName"],
        "userId": user_id,

        "avatar": avatar,

        "status": status,
        "game": game,

        "friends": friends,
        "followers": followers,

        "created": info["created"],

        "updated": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    })