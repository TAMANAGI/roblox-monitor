from flask import Flask, jsonify, request
from flask_cors import CORS

import os
import requests
import urllib3
import time
from concurrent.futures import ThreadPoolExecutor

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

# 無限待ちを避け、/status の体感を安定させる（connect, read）
ROBLOX_TIMEOUT = (5, 18)

ROBLOSECURITY = os.environ.get("ROBLOSECURITY", "").strip()
ROBLOX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
    "Origin": "https://www.roblox.com",
    "Referer": "https://www.roblox.com/",
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


def check_roblosecurity(roblosecurity):

    if not roblosecurity:
        return "missing", None, None

    session = roblox_session(roblosecurity)

    try:

        r = session.get(
            "https://users.roblox.com/v1/users/authenticated",
            verify=False,
            timeout=ROBLOX_TIMEOUT,
        )
        if r.status_code == 200:
            return "valid", r.json().get("id"), None

        if r.status_code == 401:
            return "invalid", None, 401

        return "unknown", None, r.status_code

    except Exception:

        return "unknown", None, None


def roblox_session(roblosecurity=""):

    session = requests.Session()
    session.headers.update(ROBLOX_HEADERS)
    session.trust_env = False

    if roblosecurity:
        session.cookies.set(
            ".ROBLOSECURITY",
            roblosecurity,
            domain=".roblox.com",
            path="/",
        )

    return session


def get_csrf_token(session):

    r = session.post(
        "https://presence.roblox.com/v1/presence/users",
        json={"userIds": [1]},
        verify=False,
        timeout=ROBLOX_TIMEOUT,
    )

    return r.headers.get("x-csrf-token", "")


def has_presence_data(presence):

    return (
        isinstance(presence, dict) and
        "userPresences" in presence and
        len(presence["userPresences"]) > 0
    )


def presence_int_field(value):

    if (
        value is None or
        value == ""
    ):

        return None

    try:

        return int(value)

    except (TypeError, ValueError):

        return None


def presence_game_instance_field(value):
    """Roblox Presence `gameId`: server JobId string (deeplink query gameInstanceId)."""

    if value is None:

        return None

    text = (
        str(
            value,
        ).strip()
    )

    return text if text else None


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
            verify=False,
            timeout=ROBLOX_TIMEOUT,
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


def roblox_wait_after_rate_limit(response, attempt):
    """429: prefer Retry-After (creator-docs rate-limits), else exp. backoff from 1s (Presence Open Cloud)."""

    ra = response.headers.get("Retry-After") or response.headers.get("retry-after")

    if ra is not None:

        try:

            sec = float(str(ra).strip())
            time.sleep(max(0.5, min(sec, 120.0)))
            return

        except ValueError:

            pass

    time.sleep(min(60.0, 1.0 * (2 ** attempt)))


def get_presence(user_id, roblosecurity="", retries=5):

    try:

        url = "https://presence.roblox.com/v1/presence/users"

        payload = {
            "userIds": [user_id]
        }

        session = roblox_session(roblosecurity)
        headers = {"Content-Type": "application/json"}

        no_cookie_boot = roblosecurity in ("", None)

        if roblosecurity:
            token = get_csrf_token(session)
            if token:
                headers["X-CSRF-TOKEN"] = token

        last_exc = None
        backoff = 0.6

        for attempt in range(retries):

            try:

                for _ in range(2):

                    r = session.post(
                        url,
                        json=payload,
                        headers=headers,
                        verify=False,
                        timeout=ROBLOX_TIMEOUT,
                    )

                    if (
                        r.status_code == 403 and
                        r.headers.get("x-csrf-token")
                    ):
                        headers["X-CSRF-TOKEN"] = r.headers["x-csrf-token"]
                        continue

                    break

                if r.status_code == 429 and attempt + 1 < retries:
                    roblox_wait_after_rate_limit(r, attempt)
                    continue

                try:
                    data = r.json()
                except ValueError:

                    fail = (
                        "[non-json body] "
                        + r.text.strip()[:200]
                    )

                    last_exc = fail

                    if attempt + 1 < retries:

                        if r.status_code == 429:

                            roblox_wait_after_rate_limit(r, attempt)

                        else:

                            time.sleep(backoff * (attempt + 1))

                        continue

                    return {
                        "error": {"message": fail},
                        "status_code": r.status_code,
                    }

                if r.status_code != 200:
                    last_exc = data

                    if attempt + 1 < retries:

                        if r.status_code == 429:

                            roblox_wait_after_rate_limit(r, attempt)

                        else:

                            time.sleep(backoff * (attempt + 1))

                        continue

                    return {
                        "error": data,
                        "status_code": r.status_code,
                    }

                if (
                    isinstance(data.get("userPresences"), list) and
                    len(data["userPresences"]) == 0 and
                    no_cookie_boot and
                    attempt + 1 < retries
                ):
                    time.sleep(backoff * (attempt + 1))
                    continue

                return data

            except (
                requests.Timeout,
                requests.ConnectionError,
            ) as exc:

                last_exc = str(exc)

                if attempt + 1 < retries:

                    time.sleep(backoff * (attempt + 1))

                    continue

                return {"error": str(exc)}

        return {"error": last_exc or "presence request failed"}

    except Exception as e:

        return {"error": str(e)}


def pick_richer_presence(left, right):

    la = has_presence_data(left)
    lb = has_presence_data(right)

    if lb and not la:

        return right

    if la and not lb:

        return left

    if (
        isinstance(left, dict) and
        isinstance(right, dict) and
        "userPresences" in left and
        "userPresences" in right and
        len(left["userPresences"]) > 0 and
        len(right["userPresences"]) > 0
    ):

        ua = left["userPresences"][0]
        ub = right["userPresences"][0]

        if ub.get(
            "userPresenceType",
            0,
        ) > ua.get(
            "userPresenceType",
            0,
        ):

            return right

        if (
            ua.get(
                "userPresenceType",
            ) ==
            ub.get(
                "userPresenceType",
            ) and
            (
                ua.get(
                    "placeId",
                ) is None and
                ub.get(
                    "placeId",
                )
            )
        ):

            return right

    return left


def get_universe_name(universe_id):

    if universe_id is None:
        return ""

    try:

        url = (
            "https://games.roblox.com/v1/games"
            "?universeIds=" +
            str(int(universe_id))
        )

        s = roblox_session("")
        r = s.get(url, verify=False, timeout=ROBLOX_TIMEOUT)
        payload = r.json()

        rows = payload.get(
            "data",
            [],
        )

        if len(rows) == 0:

            return ""

        return rows[0].get(
            "name",
            "",
        )

    except Exception:

        return ""


# =========================
# USER INFO
# =========================

def get_user_info(user_id):

    try:

        url = f"https://users.roblox.com/v1/users/{user_id}"

        r = requests.get(
            url,
            verify=False,
            timeout=ROBLOX_TIMEOUT,
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
            verify=False,
            timeout=ROBLOX_TIMEOUT,
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
            verify=False,
            timeout=ROBLOX_TIMEOUT,
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
            verify=False,
            timeout=ROBLOX_TIMEOUT,
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

    state, user_id, status_code = check_roblosecurity(
        roblosecurity,
    )

    if state == "valid":

        return jsonify({
            "state": "valid",
            "valid": True,
            "userId": user_id,
            "message": "ok",
        })

    if state == "invalid":

        return jsonify({
            "state": "invalid",
            "valid": False,
            "message": "token invalid or expired",
        })

    return jsonify({
        "state": "unknown",
        "valid": True,
        "message": (
            "could not verify from server"
            + (
                f" (HTTP {status_code})"
                if status_code
                else ""
            )
            + " — token will still be tried"
        ),
    })


@app.route("/status")
def status():

    try:

        username_arg = (
            request.args.get("username") or ""
        ).strip()

        user_id_raw = (
            request.args.get("userId") or ""
        ).strip()

        user_id = None

        if user_id_raw:

            try:

                user_id = int(user_id_raw)

                if user_id <= 0:

                    raise ValueError()

            except (ValueError, TypeError):

                return jsonify({
                    "error": "invalid userId",
                })

        else:

            if not username_arg:

                return jsonify({
                    "error": "username or userId required",
                })

            user_id = get_user_id(username_arg)

            if not user_id:

                return jsonify({
                    "error": "user not found",
                })

        roblosecurity = get_request_roblosecurity()

        cookie_val_pre = roblosecurity
        auth_state, _, auth_http = check_roblosecurity(roblosecurity)
        presence_note = ""
        unavailable = {}

        cookie_val = cookie_val_pre

        if auth_state == "invalid":
            cookie_val = ""

        presence = None
        ck_rsp = None

        if cookie_val:

            with ThreadPoolExecutor(max_workers=2) as pool:

                fut_pub = pool.submit(
                    get_presence,
                    user_id,
                    "",
                )
                fut_ck = pool.submit(
                    get_presence,
                    user_id,
                    cookie_val,
                )
                public_rsp = fut_pub.result()
                ck_rsp = fut_ck.result()

        else:

            public_rsp = get_presence(user_id, "")

        if isinstance(public_rsp, dict) and public_rsp.get("status_code"):
            unavailable["publicHttp"] = public_rsp["status_code"]

        if has_presence_data(public_rsp):
            presence = public_rsp

        if cookie_val:

            if isinstance(
                ck_rsp,
                dict,
            ) and ck_rsp.get(
                "status_code",
            ):

                unavailable["cookieHttp"] = ck_rsp["status_code"]

            if has_presence_data(ck_rsp):
                presence = pick_richer_presence(
                    presence if presence is not None else {},
                    ck_rsp,
                )
        status = "UNKNOWN"
        game = ""
        presence_error = ""
        last_location = ""
        universe_name = ""

        place_id_out = None
        root_place_id_out = None
        universe_id_out = None
        game_instance_id_out = None

        if has_presence_data(presence):

            user = presence["userPresences"][0]

            state = user["userPresenceType"]

            place = user.get("placeId")
            univ = user.get("universeId")

            place_id_out = presence_int_field(
                place,
            )
            root_place_id_out = presence_int_field(
                user.get("rootPlaceId"),
            )
            universe_id_out = presence_int_field(
                univ,
            )
            game_instance_id_out = presence_game_instance_field(
                user.get("gameId"),
            )

            last_location = user.get(
                "lastLocation",
                "",
            ) or ""

            # OFFLINE
            if state == 0:

                status = "OFFLINE"

            # ONLINE
            elif state == 1:

                status = "ONLINE"

            # IN GAME
            elif state == 2:

                status = "IN GAME"

                universe_name = get_universe_name(univ)

                if universe_name:

                    game = universe_name

                elif place == BROOKHAVEN_PLACE_ID:

                    game = "Brookhaven RP"

                else:

                    game = f"PlaceId {place}"

            # STUDIO
            elif state == 3:

                status = "IN STUDIO"

            if (
                (
                    status == "OFFLINE" or
                    status == "ONLINE"
                ) and not game and last_location
            ):

                game = last_location

        else:

            detail = ""

            detail += (
                "Presence API がこのサーバーから応答していません。"
            )

            detail += (
                " Roblox はクラウド（Render 等）からの Presence 取得をブロックすることがあります。"
            )

            pub_code = unavailable.get(
                "publicHttp",
            )

            if pub_code:

                detail += " (presence HTTP "
                detail += str(pub_code)
                detail += ")"

            presence_error = detail

            tips = ""

            ck_code = unavailable.get(
                "cookieHttp",
            )

            if ck_code:

                tips += (" cookie側 HTTP "
                         + str(ck_code))

            if (
                auth_http and
                auth_http not in (
                    None,
                    200,
                    401,
                )
            ):
                tips += (" 認証検証 HTTP "
                         + str(auth_http))

            if tips.strip():

                presence_note = tips.strip()

        if auth_state == "invalid":

            presence_note = (
                "Cookie は Roblox から拒否されています（401）。"
                " 新しい .ROBLOSECURITY を貼り直してください。"
                + (" | " + presence_note if presence_note else "")
            )

        with ThreadPoolExecutor(max_workers=4) as pool:

            info_fut = pool.submit(get_user_info, user_id)
            avatar_fut = pool.submit(get_avatar, user_id)
            friends_fut = pool.submit(get_friends_count, user_id)
            followers_fut = pool.submit(get_followers_count, user_id)

            info = info_fut.result()
            avatar = avatar_fut.result()
            friends = friends_fut.result()
            followers = followers_fut.result()

        name_fallback = ""

        if username_arg:

            name_fallback = username_arg

        else:

            name_fallback = str(user_id)

        roblox_name = info.get(
            "name",
            "",
        )

        roblox_dn = info.get(
            "displayName",
            "",
        )

        response = {

            "username":
                roblox_name or name_fallback,

            "displayName":
                roblox_dn or roblox_name or name_fallback,

            "userId":
                user_id,

            "avatar":
                avatar,

            "status":
                status,

            "game":
                game,

            "lastLocation":
                last_location,

            "universeName":
                universe_name,

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

            "placeId":
                place_id_out,

            "rootPlaceId":
                root_place_id_out,

            "universeId":
                universe_id_out,

            "gameInstanceId":
                game_instance_id_out,
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