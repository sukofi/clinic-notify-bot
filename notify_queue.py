#!/usr/bin/env python3
"""
松尾こどもクリニック 番号通知スクリプト
指定した番号になったら LINE Notify と macOS 通知を送る
"""

import re
import os
import time
import subprocess
import sys
import urllib.request

URL = "https://ssc6.doctorqube.com/matsuokodomoclinic/"
INTERVAL_SECONDS = 30  # チェック間隔（秒）

# Discord Webhook URL をここに貼り付ける
# チャンネル設定 → 連携サービス → ウェブフック → URLをコピー
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")


def fetch_current_number():
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            html = res.read().decode("utf-8", errors="replace")

        match = re.search(r'class=["\']nowinfo["\'][^>]*>\s*<span>([\d０-９]+)</span>', html)
        if match:
            raw = match.group(1)
            return int(raw.translate(str.maketrans("０１２３４５６７８９", "0123456789")))

    except Exception as e:
        print(f"[エラー] ページ取得失敗: {e}")
    return None


def notify_macos(title: str, message: str):
    script = f'display notification "{message}" with title "{title}" sound name "Ping"'
    subprocess.run(["osascript", "-e", script])


def notify_discord(message: str):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        import json
        payload = json.dumps({"content": message})
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "-X", "POST", DISCORD_WEBHOOK_URL,
             "-H", "Content-Type: application/json",
             "-d", payload],
            capture_output=True, text=True
        )
        if result.stdout.strip() == "204":
            print("[Discord] 通知送信成功")
        else:
            print(f"[Discord] 通知送信失敗: HTTP {result.stdout.strip()}")
    except Exception as e:
        print(f"[Discord] 通知送信エラー: {e}")


def notify_all(title: str, message: str):
    notify_macos(title, message)
    notify_discord(f"【{title}】 {message}")


def main():
    if len(sys.argv) < 2:
        print("使い方: python3 notify_queue.py <通知したい番号>")
        print("例:     python3 notify_queue.py 5")
        sys.exit(1)

    target = int(sys.argv[1])

    if not DISCORD_WEBHOOK_URL:
        print("※ DISCORD_WEBHOOK_URL が未設定です。macOS 通知のみ送信します。")
        print("  スクリプト内の DISCORD_WEBHOOK_URL に Webhook URL を設定すると Discord にも通知されます。\n")

    print(f"監視開始: 現在の番号が {target} になったら通知します（{INTERVAL_SECONDS}秒ごとにチェック）")
    print("終了するには Ctrl+C を押してください\n")

    notified = False

    while True:
        current = fetch_current_number()
        if current is not None:
            print(f"[{time.strftime('%H:%M:%S')}] 現在の番号: {current}")
            if current >= target and not notified:
                msg = f"今{current}番が診察中ですよ〜"
                print(f">>> 通知: {msg}")
                notify_all("松尾こどもクリニック", msg)
                notified = True
            elif current < target:
                notified = False  # 番号がリセットされた場合に再通知できるようにする
        else:
            print(f"[{time.strftime('%H:%M:%S')}] 番号を取得できませんでした")

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
