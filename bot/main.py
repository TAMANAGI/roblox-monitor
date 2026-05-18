import requests
import json
import time
import subprocess
import urllib3

urllib3.disable_warnings()

# =========================
# 設定
# =========================

USERNAME = "Lawyes4"

# Brookhaven PlaceId
BROOKHAVEN_PLACE_ID = 4924922222

CHECK_INTERVAL = 30

# =========================

last_status = None
last_game = None

# =========================
# ユーザー名 → USER_ID
# =========================

def get_user_id(username):

    url = "https://users.roblox.com/v1/usernames/users"

    payload = {
        "usernames": [username],
        "excludeBannedUsers": False
    }

    # r = requests.post(url, json=payload)
    r = requests.post(
    url,
    json=payload,
    verify=False
)

    data = r.json()

    return data["data"][0]["id"]

# =========================
# Presence取得
# =========================

def get_presence(user_id):

    url = "https://presence.roblox.com/v1/presence/users"

    payload = {
        "userIds":[user_id]
    }

    # r = requests.post(url, json=payload)
    r = requests.post(
    url,
    json=payload,
    verify=False
)

    return r.json()

# =========================
# Git Push
# =========================

def git_push():

    subprocess.run(["git", "add", "."])

    subprocess.run([
        "git",
        "commit",
        "-m",
        "auto update"
    ])

    subprocess.run(["git", "push"])

# =========================
# USER_ID取得
# =========================

USER_ID = get_user_id(USERNAME)

print("USER_ID =", USER_ID)

print("監視開始")

# =========================
# メインループ
# =========================

while True:

    try:

        data = get_presence(USER_ID)

        user = data["userPresences"][0]

        state = user["userPresenceType"]

        place = user.get("placeId")

        status = "OFFLINE"
        game = ""

        # Offline
        if state == 0:

            status = "OFFLINE"

        # Online
        elif state == 1:

            status = "ONLINE"

        # In Game
        elif state == 2:

            status = "IN GAME"

            if place == BROOKHAVEN_PLACE_ID:

                game = "Brookhaven RP"

            else:

                game = f"PlaceId {place}"

        # Studio
        elif state == 3:

            status = "IN STUDIO"

        # =========================
        # 状態変化時のみ更新
        # =========================

        if status != last_status or game != last_game:

            output = {
                "status": status,
                "game": game,
                "username": USERNAME,
                "updated": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            with open("../docs/status.json", "w") as f:

                json.dump(output, f)

            print(output)

            git_push()

            last_status = status
            last_game = game

        else:

            print("変化なし")

    except Exception as e:

        print("ERROR:", e)

    time.sleep(CHECK_INTERVAL)