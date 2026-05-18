const BROOKHAVEN_PLACE_ID = 4924922222;

const UA = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  Accept: "application/json",
  "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
  Origin: "https://www.roblox.com",
  Referer: "https://www.roblox.com/",
};

function cookieHeaders(cookie) {
  if (!cookie || !cookie.trim()) {
    return {};
  }
  return { Cookie: ".ROBLOSECURITY=" + cookie.trim() };
}

async function postPresence(userId, cookie) {
  const url = "https://presence.roblox.com/v1/presence/users";
  const base = { "Content-Type": "application/json", ...UA, ...cookieHeaders(cookie) };
  let r = await fetch(url, {
    method: "POST",
    headers: base,
    body: JSON.stringify({ userIds: [userId] }),
  });
  let csrf = r.headers.get("x-csrf-token");
  if (r.status === 403 && csrf) {
    r = await fetch(url, {
      method: "POST",
      headers: { ...base, "X-CSRF-TOKEN": csrf },
      body: JSON.stringify({ userIds: [userId] }),
    });
  }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    return { _error: j, _http: r.status };
  }
  return j;
}

async function getUserId(username) {
  const r = await fetch("https://users.roblox.com/v1/usernames/users", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...UA },
    body: JSON.stringify({
      usernames: [username],
      excludeBannedUsers: false,
    }),
  });
  const j = await r.json();
  if (!r.ok || !j.data || j.data.length === 0) {
    return null;
  }
  return j.data[0].id;
}

async function getUserProfile(userId) {
  const r = await fetch("https://users.roblox.com/v1/users/" + userId, {
    headers: UA,
  });
  if (!r.ok) {
    return {};
  }
  return r.json();
}

async function getAvatarUrl(userId) {
  const u =
    "https://thumbnails.roblox.com/v1/users/avatar-headshot" +
    "?userIds=" +
    userId +
    "&size=420x420&format=Png&isCircular=false";
  const r = await fetch(u, { headers: UA });
  const j = await r.json();
  return j.data && j.data[0] ? j.data[0].imageUrl || "" : "";
}

async function getFriendsCount(userId) {
  const r = await fetch(
    "https://friends.roblox.com/v1/users/" + userId + "/friends/count",
    { headers: UA },
  );
  if (!r.ok) {
    return 0;
  }
  const j = await r.json();
  return j.count !== undefined ? j.count : 0;
}

async function getFollowersCount(userId) {
  const r = await fetch(
    "https://friends.roblox.com/v1/users/" + userId + "/followers/count",
    { headers: UA },
  );
  if (!r.ok) {
    return 0;
  }
  const j = await r.json();
  return j.count !== undefined ? j.count : 0;
}

async function getUniverseName(universeId) {
  if (universeId == null) {
    return "";
  }
  const r = await fetch(
    "https://games.roblox.com/v1/games?universeIds=" + universeId,
    { headers: UA },
  );
  if (!r.ok) {
    return "";
  }
  const j = await r.json();
  return j.data && j.data[0] ? j.data[0].name || "" : "";
}

function mapPresence(p, userId) {
  if (!p || p._error) {
    return {
      status: "UNKNOWN",
      game: "",
      note: p && p._error ? "presence HTTP " + p._http : "presence なし",
    };
  }
  const row = (p.userPresences || [])[0];
  if (!row) {
    return { status: "UNKNOWN", game: "", note: "userPresences 空" };
  }
  const t = row.userPresenceType;
  const place = row.placeId;
  const univ = row.universeId;
  const last = row.lastLocation || "";
  if (t === 0) {
    return { status: "OFFLINE", game: last || "", note: "" };
  }
  if (t === 1) {
    return { status: "ONLINE", game: last || "", note: "" };
  }
  if (t === 2) {
    return { status: "IN GAME", game: "", place, universeId: univ, note: "" };
  }
  if (t === 3) {
    return { status: "IN STUDIO", game: "", note: "" };
  }
  return { status: "UNKNOWN", game: "", note: "type " + t };
}

async function runMonitor(username, cookie) {
  const u = username.trim();
  if (!u) {
    return "username を入力してください。";
  }
  const id = await getUserId(u);
  if (!id) {
    return "ユーザーが見つかりません（@username を確認）。";
  }
  const pres = await postPresence(id, cookie);
  const info = mapPresence(pres, id);
  const profile = await getUserProfile(id);
  const display = profile.displayName || u;
  const name = profile.name || u;
  let gameLine = info.game;
  if (info.status === "IN GAME") {
    const title = await getUniverseName(info.universeId);
    if (title) {
      gameLine = title;
    } else if (info.place === BROOKHAVEN_PLACE_ID) {
      gameLine = "Brookhaven RP";
    } else if (info.place != null) {
      gameLine = "PlaceId " + info.place;
    } else {
      gameLine = "（場所は非表示の可能性）";
    }
  }
  const avatar = await getAvatarUrl(id);
  const friends = await getFriendsCount(id);
  const followers = await getFollowersCount(id);
  const lines = [
    display + " (@" + name + ")",
    "userId: " + id,
    "status: " + info.status,
    gameLine ? "game / location: " + gameLine : "",
    info.note ? "note: " + info.note : "",
    "friends: " + friends + "  followers: " + followers,
    avatar ? "avatar: " + avatar : "",
    "",
    "※ 友だちでないと「ゲーム中」が隠されることがあります。",
  ];
  return lines.filter(Boolean).join("\n");
}

async function loadSaved() {
  const s = await chrome.storage.local.get(["username", "cookie"]);
  if (s.username) {
    document.getElementById("u").value = s.username;
  }
  if (s.cookie) {
    document.getElementById("c").value = s.cookie;
  }
}

document.getElementById("go").addEventListener("click", async () => {
  const out = document.getElementById("out");
  out.textContent = "読み込み中…";
  const username = document.getElementById("u").value;
  const cookie = document.getElementById("c").value;
  try {
    out.textContent = await runMonitor(username, cookie);
    await chrome.storage.local.set({ username: username.trim() });
  } catch (e) {
    out.textContent = "エラー: " + (e && e.message ? e.message : String(e));
  }
});

document.getElementById("save").addEventListener("click", async () => {
  const cookie = document.getElementById("c").value.trim();
  await chrome.storage.local.set({ cookie });
  document.getElementById("out").textContent = cookie
    ? "Cookie を保存しました（この端末の拡張ストレージのみ）。"
    : "Cookie をクリアしました。";
});

loadSaved();
