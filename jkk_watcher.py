#!/usr/bin/env python3
"""JKKねっとでコーシャハイム千石の募集住戸を監視する。"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path


PROPERTY_NAME = "コーシャハイム千石"
PROPERTY_TOKEN = "30B330FC30B730E330CF30A430E030BB30F330B430AF"
BASE_URL = "https://jhomes.to-kousya.or.jp"
SEARCH_URL = f"{BASE_URL}/search/jkknet/service/akiyaJyokenDirect"
PUBLIC_SEARCH_URL = f"{SEARCH_URL}?jutaku_name={PROPERTY_TOKEN}&sen_flg=1"
DETAIL_URL = f"{BASE_URL}/search/jkknet/service/akiyaSenDet"
STATE_PATH = Path(__file__).with_name("state.json")
NO_VACANCY_TEXT = "ご希望の住宅、またはご希望の条件の空室はございませんでした"
USER_AGENT = "Mozilla/5.0 (compatible; personal JKK vacancy checker; +https://github.com/)"


def normalize(value: str) -> str:
    value = re.sub(r"<script\b.*?</script>", "", value, flags=re.I | re.S)
    value = re.sub(r"<style\b.*?</style>", "", value, flags=re.I | re.S)
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = unescape(value).replace("\u3000", " ")
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", value).strip()


def post(opener: urllib.request.OpenerDirector, url: str, fields: dict[str, str]) -> str:
    data = urllib.parse.urlencode(fields).encode("ascii")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with opener.open(request, timeout=40) as response:
                raw = response.read()
            return raw.decode("cp932", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    raise RuntimeError(f"JKKねっとへの接続に3回失敗しました: {last_error}")


def new_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def extract_summary_rows(page: str) -> list[dict[str, str | int]]:
    summaries: list[dict[str, str | int]] = []
    row_blocks = re.findall(
        r'<tr\s+class="ListTXT[12]"[^>]*>(.*?)</tr>', page, flags=re.I | re.S
    )
    for block in row_blocks:
        cells = [normalize(x) for x in re.findall(r"<td\b[^>]*>(.*?)</td>", block, re.I | re.S)]
        action = re.search(
            r"senPage\('([^']*)','([^']*)','([^']*)','([^']*)'\)", block
        )
        if len(cells) < 10 or not action or cells[1] != PROPERTY_NAME:
            continue
        count_text = re.sub(r"\D", "", cells[9])
        if not count_text:
            raise RuntimeError("募集戸数を読み取れませんでした")
        summaries.append(
            {
                "application_code": action.group(2),
                "housing_code": action.group(3),
                "priority_code": action.group(4),
                "layout": cells[5],
                "area": cells[6],
                "rent": cells[7],
                "fee": cells[8],
                "count": int(count_text),
            }
        )
    return summaries


def extract_detail_rooms(page: str, summary: dict[str, str | int]) -> list[dict[str, str]]:
    rooms: list[dict[str, str]] = []
    row_blocks = re.findall(r'<tr\s+align="center"[^>]*>(.*?)</tr>', page, re.I | re.S)
    for block in row_blocks:
        cells = [normalize(x) for x in re.findall(r"<td\b[^>]*>(.*?)</td>", block, re.I | re.S)]
        if len(cells) < 11 or not re.fullmatch(r"\d+-\d+", cells[1]):
            continue
        app_code = str(summary["application_code"])
        room_number = cells[1]
        rooms.append(
            {
                "key": f"{app_code}:{room_number}",
                "room": room_number,
                "layout": cells[4],
                "direction": cells[5],
                "rent": cells[6],
                "fee": cells[8],
                "available": cells[10],
                "application_code": app_code,
            }
        )
    return rooms


def fetch_rooms() -> list[dict[str, str]]:
    opener = new_opener()
    search_page = post(
        opener,
        SEARCH_URL,
        {
            "redirect": "true",
            "url": SEARCH_URL,
            "jutaku_name": PROPERTY_TOKEN,
            "sen_flg": "1",
        },
    )
    if NO_VACANCY_TEXT in search_page:
        return []
    if "先着順あき家の検索結果" not in search_page:
        raise RuntimeError("JKKねっとの検索結果形式が想定と異なります")

    summaries = extract_summary_rows(search_page)
    if not summaries:
        raise RuntimeError(f"{PROPERTY_NAME}の募集情報を読み取れませんでした")

    token_match = re.search(
        r"function\s+senPage\b[\s\S]*?xyz\.value\s*=\s*\"([A-F0-9]+)\"",
        search_page,
    )
    if not token_match:
        raise RuntimeError("詳細画面用トークンを読み取れませんでした")
    detail_token = token_match.group(1)

    rooms: list[dict[str, str]] = []
    for summary in summaries:
        detail_page = post(
            opener,
            DETAIL_URL,
            {
                "xyz": detail_token,
                "akiyaRefRM.akiyaDatM.boshuNo": "",
                "akiyaRefRM.akiyaDatM.mskKbn": str(summary["application_code"]),
                "akiyaRefRM.akiyaDatM.jyutakuCd": str(summary["housing_code"]),
                "akiyaRefRM.akiyaDatM.yusenKbn": str(summary["priority_code"]),
            },
        )
        details = extract_detail_rooms(detail_page, summary)
        if len(details) != int(summary["count"]):
            raise RuntimeError(
                f"{summary['application_code']}の募集戸数が一致しません "
                f"(一覧{summary['count']}戸 / 詳細{len(details)}戸)"
            )
        rooms.extend(details)
        time.sleep(0.5)
    return sorted(rooms, key=lambda room: room["key"])


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"initialized": False, "rooms": []}
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"state.jsonを読み込めません: {exc}") from exc
    if not isinstance(state.get("rooms", []), list):
        raise RuntimeError("state.jsonの形式が不正です")
    return state


def save_state(rooms: list[dict[str, str]]) -> None:
    state = {
        "initialized": True,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rooms": rooms,
    }
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def send_ntfy(topic: str, title: str, message: str, *, priority: int = 5) -> None:
    payload = json.dumps(
        {
            "topic": topic,
            "title": title,
            "message": message,
            "priority": priority,
            "tags": ["house"],
            "click": PUBLIC_SEARCH_URL,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://ntfy.sh",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Androidへの通知送信に失敗しました: {exc}") from exc


def format_notification(rooms: list[dict[str, str]]) -> str:
    lines = [f"{PROPERTY_NAME}に新しい募集住戸が出ました。"]
    for room in rooms[:10]:
        lines.append(
            f"・{room['room']}号室 / {room['layout']} / 家賃{room['rent']}円 "
            f"(共益費{room['fee']}円)"
        )
    if len(rooms) > 10:
        lines.append(f"ほか{len(rooms) - 10}戸")
    lines.append("通知をタップしてJKKねっとを確認してください。")
    return "\n".join(lines)


def run(*, dry_run: bool, test_notification: bool) -> int:
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not dry_run and not topic:
        raise RuntimeError("GitHubのSecret『NTFY_TOPIC』が設定されていません")

    if test_notification:
        send_ntfy(
            topic,
            "JKK空室通知（テスト）",
            "通知設定は正常です。これはコーシャハイム千石のテスト通知です。",
            priority=3,
        )
        print("テスト通知を送信しました")
        return 0

    current_rooms = fetch_rooms()
    state = load_state()
    previous_by_key = {room["key"]: room for room in state.get("rooms", [])}
    new_or_changed = [
        room
        for room in current_rooms
        if room["key"] not in previous_by_key or previous_by_key[room["key"]] != room
    ]

    print(f"{PROPERTY_NAME}: 募集住戸 {len(current_rooms)}戸")
    for room in current_rooms:
        print(f"  {room['room']}号室 {room['layout']} {room['rent']}円")

    if dry_run:
        return 0

    if new_or_changed:
        send_ntfy(topic, "🏠 JKK空室通知", format_notification(new_or_changed))
        print(f"新規・変更 {len(new_or_changed)}戸を通知しました")

    if (not state.get("initialized")) or state.get("rooms", []) != current_rooms:
        save_state(current_rooms)
        print("state.jsonを更新しました")
    else:
        print("前回から変化はありません")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="取得のみ行い通知・状態更新をしない")
    parser.add_argument("--test-notification", action="store_true", help="テスト通知だけを送る")
    args = parser.parse_args()
    try:
        return run(dry_run=args.dry_run, test_notification=args.test_notification)
    except Exception as exc:  # Actionsのログへ明確に残す
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
