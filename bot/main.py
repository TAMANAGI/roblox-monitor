from flask import Flask, jsonify
from flask_cors import CORS

import requests
import urllib3
import time

urllib3.disable_warnings()

app = Flask(__name__)

CORS(app)

# =========================
# 設定
# =========================

USERNAME = "Lawyes4"

BROOKHAVEN_PLACE_ID = 4924922222

# =========================

logs = []

# =========================
# USER_ID取得
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

USER_ID = get_user_id(USERNAME)

print("USER_ID =", USER_ID)

# =========================
# Presence取得
# =========================

def get_presence():

    url = "https://presence.roblox.com/v1/presence/users"

    payload = {
        "userIds": [USER_ID]
    }

    r = requests.post(
        url,
        json=payload,
        verify=False
    )

    return r.json()

# =========================
# API
# =========================

@app.route("/status")
def status():

    global logs

    data = get_presence()

    user = data["userPresences"][0]

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

    log = {
        "status": status,
        "game": game,
        "updated": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    logs.append(log)

    logs = logs[-30:]

    return jsonify({
        "username": USERNAME,
        "status": status,
        "game": game,
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "logs": logs
    })