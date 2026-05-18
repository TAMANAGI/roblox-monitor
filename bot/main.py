import requests
import urllib3
import json
import time
import subprocess

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

    r = requests.post(
        url,
        json=payload,
        verify=False
    )

    data = r.json()

    print(data)

    if len(data["data"]) == 0:
        raise Exception("ユーザーが見つからない！")

    return data["data"][0]["id"]

# =========================
# Presence取得
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

        print(data)

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

            # 過去ログ取得
            logs = []

            try:

                with open("../docs/status.json", "r") as f:

                    old_data = json.load(f)

                    logs = old_data.get("logs", [])

            except:

                pass

            new_log = {
                "status": status,
                "game": game,
                "username": USERNAME,
                "updated": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            logs.append(new_log)

            # 最新50件のみ保持
            logs = logs[-50:]

            output = {
                "status": status,
                "game": game,
                "username": USERNAME,
                "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "logs": logs
            }

            with open("../docs/status.json", "w") as f:

                json.dump(output, f, indent=2)

            print(output)

            git_push()

            last_status = status
            last_game = game

        else:

            print("変化なし")

    except Exception as e:

        print("ERROR:", e)

    time.sleep(CHECK_INTERVAL)