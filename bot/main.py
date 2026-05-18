from flask import Flask, jsonify, request
from flask_cors import CORS

import os
import requests
import urllib3
import time

urllib3.disable_warnings()

app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    allow_headers=["Content-Type", "X-Roblox-Security"],
    expose_headers=["Content-Type"],
)

# =========================

BROOKHAVEN_PLACE_ID = 4924922222

ROBLOSECURITY = os.environ.get("ROBLOSECURITY", "").strip()

ROBLOX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def normalize_roblosecurity(raw):

    if not raw:
        return ""

    value = raw.strip()

    if value.lower().startswith(".roblosecurity="):
        value = value.split("=", 1)[1].strip()

    if (
        len(value) >= 2 and
        value[0] == value[-1] and
        value[0] in ("'", '"')
    ):
        value = value[1:-1].strip()

    return value


def get_request_roblosecurity():

    from_header = normalize_roblosecurity(
        request.headers.get("X-Roblox-Security", ""),
    )

    if from_header:
        return from_header

    return normalize_roblosecurity(ROBLOSECURITY)


def verify_roblosecurity(roblosecurity):

    session = roblox_session(roblosecurity)

    try:

        r = session.get(
            "https://users.roblox.com/v1/users/authenticated",
            verify=False,
            timeout=15,
        )

        if r.status_code != 200:
            return False, None

        data = r.json()

        return True, data.get("id")

    except Exception:

        return False, None


def roblox_session(roblosecurity=""):

    session = requests.Session()
    session.headers.update(ROBLOX_HEADERS)

    if roblosecurity:
        session.cookies.set(
            ".ROBLOSECURITY",
            roblosecurity,
            domain=".roblox.com",
        )

    return session


def get_csrf_token(session):

    r = session.post(
        "https://auth.roblox.com/v2/logout",
        verify=False,
        timeout=15,
    )

    token = r.headers.get("x-csrf-token", "")

    if token:
        return token

    r = session.post(
        "https://presence.roblox.com/v1/presence/users",
        json={"userIds": [1]},
        verify=False,
        timeout=15,
    )

    return r.headers.get("x-csrf-token", "")

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

def get_presence(user_id, roblosecurity=""):

    try:

        url = "https://presence.roblox.com/v1/presence/users"

        payload = {
            "userIds": [user_id]
        }

        session = roblox_session(roblosecurity)
        headers = {"Content-Type": "application/json"}

        if roblosecurity:
            token = get_csrf_token(session)
            if token:
                headers["X-CSRF-TOKEN"] = token

        for _ in range(2):

            r = session.post(
                url,
                json=payload,
                headers=headers,
                verify=False,
                timeout=15,
            )

            if (
                r.status_code == 403 and
                r.headers.get("x-csrf-token")
            ):
                headers["X-CSRF-TOKEN"] = r.headers["x-csrf-token"]
                continue

            break

        data = r.json()

        if r.status_code != 200:
            return {
                "error": data,
                "status_code": r.status_code,
            }

        return data

    except Exception as e:

        return {"error": str(e)}

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

@app.route("/health")
def health():

    return jsonify({
        "ok": True,
    })


@app.route("/auth/verify")
def auth_verify():

    roblosecurity = get_request_roblosecurity()

    if not roblosecurity:

        return jsonify({
            "valid": False,
            "message": "no token",
        })

    valid, user_id = verify_roblosecurity(roblosecurity)

    if not valid:

        return jsonify({
            "valid": False,
            "message": "token invalid or expired",
        })

    return jsonify({
        "valid": True,
        "userId": user_id,
        "message": "ok",
    })


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

        roblosecurity = get_request_roblosecurity()
        token_invalid = False

        if roblosecurity:
            valid, _ = verify_roblosecurity(roblosecurity)
            if not valid:
                token_invalid = True
                roblosecurity = ""

        presence = get_presence(user_id, roblosecurity)

        status = "UNKNOWN"
        game = ""
        presence_error = ""
        presence_note = ""

        if (
            "userPresences" in presence and
            len(presence["userPresences"]) > 0
        ):

            user = presence["userPresences"][0]

            state = user["userPresenceType"]

            place = user.get("placeId")

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

        else:

            if not roblosecurity:
                presence_error = (
                    "presence unavailable "
                    "(set .ROBLOSECURITY in Settings)"
                )
            else:
                presence_error = "presence unavailable"

        if token_invalid:
            presence_note = (
                "Saved token is invalid or expired — "
                "copy a fresh .ROBLOSECURITY from Roblox"
            )

        info = get_user_info(user_id)

        avatar = get_avatar(user_id)

        friends = get_friends_count(user_id)

        followers = get_followers_count(user_id)

        response = {

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
                ),
        }

        if presence_error:
            response["presenceError"] = presence_error

        if presence_note:
            response["presenceNote"] = presence_note

        return jsonify(response)

    except Exception as e:

        return jsonify({
            "error": str(e)
        })