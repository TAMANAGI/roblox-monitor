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
# USER ID
# =========================

def get_user_id(username):

    try:

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

        if (
            "data" not in data or
            len(data["data"]) == 0
        ):
            return None

        return data["data"][0]["id"]

    except:

        return None

# =========================
# PRESENCE
# =========================

def get_presence(user_id):

    try:

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

    except:

        return {}

# =========================
# USER INFO
# =========================

def get_user_info(user_id):

    try:

        url = f"https://users.roblox.com/v1/users/{user_id}"

        r = requests.get(
            url,
            verify=False
        )

        return r.json()

    except:

        return {}

# =========================
# AVATAR
# =========================

def get_avatar(user_id):

    try:

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

        if (
            "data" not in data or
            len(data["data"]) == 0
        ):
            return ""

        return data["data"][0].get(
            "imageUrl",
            ""
        )

    except:

        return ""

# =========================
# FRIENDS
# =========================

def get_friends_count(user_id):

    try:

        url = f"https://friends.roblox.com/v1/users/{user_id}/friends/count"

        r = requests.get(
            url,
            verify=False
        )

        return r.json().get(
            "count",
            0
        )

    except:

        return 0

# =========================
# FOLLOWERS
# =========================

def get_followers_count(user_id):

    try:

        url = f"https://friends.roblox.com/v1/users/{user_id}/followers/count"

        r = requests.get(
            url,
            verify=False
        )

        return r.json().get(
            "count",
            0
        )

    except:

        return 0

# =========================
# API
# =========================

@app.route("/status")
def status():

    try:

        username = request.args.get("username")

        if not username:

            return jsonify({
                "error": "username required"
            })

        user_id = get_user_id(username)

        if not user_id:

            return jsonify({
                "error": "user not found"
            })

        presence = get_presence(user_id)

        if (
            "userPresences" not in presence or
            len(presence["userPresences"]) == 0
        ):

            return jsonify({
                "error": "presence unavailable"
            })

        user = presence["userPresences"][0]

        state = user["userPresenceType"]

        place = user.get("placeId")

        status = "OFFLINE"
        game = ""

        # OFFLINE
        if state == 0:

            status = "OFFLINE"

        # ONLINE
        elif state == 1:

            status = "ONLINE"

        # IN GAME
        elif state == 2:

            status = "IN GAME"

            if place == BROOKHAVEN_PLACE_ID:

                game = "Brookhaven RP"

            else:

                game = f"PlaceId {place}"

        # STUDIO
        elif state == 3:

            status = "IN STUDIO"

        info = get_user_info(user_id)

        avatar = get_avatar(user_id)

        friends = get_friends_count(user_id)

        followers = get_followers_count(user_id)

        return jsonify({

            "username":
                info.get("name", username),

            "displayName":
                info.get("displayName", username),

            "userId":
                user_id,

            "avatar":
                avatar,

            "status":
                status,

            "game":
                game,

            "friends":
                friends,

            "followers":
                followers,

            "created":
                info.get("created", ""),

            "updated":
                time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        })