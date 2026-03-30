#!/usr/bin/env python3
"""
松尾こどもクリニック 番号通知 Discord Bot
キーワードマッチングで自然言語対応
"""

import re
import os
import asyncio
import urllib.request
import discord

# ===== 設定 =====
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
CHECK_INTERVAL = 30  # チェック間隔（秒）
CLINIC_URL = "https://ssc6.doctorqube.com/matsuokodomoclinic/"
# ================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 監視タスク: {channel_id: {"target": int, "task": asyncio.Task}}
watching: dict = {}

ZENKAKU = str.maketrans("０１２３４５６７８９", "0123456789")


def fetch_current_number():
    try:
        req = urllib.request.Request(CLINIC_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            html = res.read().decode("utf-8", errors="replace")
        match = re.search(r'class=["\']nowinfo["\'][^>]*>\s*<span>([\d０-９]+)</span>', html)
        if match:
            return int(match.group(1).translate(ZENKAKU))
    except Exception as e:
        print(f"[エラー] ページ取得失敗: {e}")
    return None


def parse_number(text: str):
    """テキストから番号を抽出（全角・漢数字対応）"""
    # 全角→半角
    text = text.translate(ZENKAKU)
    # 漢数字変換（簡易）
    kanji = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
             "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
             "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20}
    for k, v in kanji.items():
        text = text.replace(k, str(v))
    match = re.search(r'\d+', text)
    return int(match.group()) if match else None


def parse_intent(text: str):
    """メッセージの意図を判定"""
    t = text.lower()

    # キャンセル
    if re.search(r'キャンセル|やめ|止め|停止|cancel', t):
        return "cancel", None

    # 現在番号確認
    if re.search(r'今|現在|いま|何番|なんばん|status', t):
        return "status", None

    # 通知設定（番号が含まれている）
    number = parse_number(text)
    if number and re.search(r'通知|教え|知らせ|呼んで|なったら|になったら|番.*教|番.*通', t):
        return "notify", number

    # 番号だけ言った場合も通知設定とみなす
    if number:
        return "notify", number

    return "unknown", None


async def monitor(channel: discord.TextChannel, target: int):
    notified = False
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        current = await asyncio.get_event_loop().run_in_executor(None, fetch_current_number)
        if current is None:
            continue
        print(f"[監視] 現在:{current} 目標:{target}")
        if current >= target and not notified:
            await channel.send(f"今{current}番が診察中ですよ〜")
            notified = True
        elif current < target:
            notified = False


@client.event
async def on_ready():
    print(f"Bot 起動: {client.user}")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    channel = message.channel
    channel_id = channel.id
    text = message.content.strip()

    action, number = parse_intent(text)

    if action == "notify":
        async with channel.typing():
            current = await asyncio.get_event_loop().run_in_executor(None, fetch_current_number)

        if channel_id in watching:
            watching[channel_id]["task"].cancel()

        task = asyncio.create_task(monitor(channel, number))
        watching[channel_id] = {"target": number, "task": task}

        current_str = f"（今は{current}番）" if current else ""
        await message.reply(f"{number}番になったら通知しますね！{current_str}")

    elif action == "status":
        async with channel.typing():
            current = await asyncio.get_event_loop().run_in_executor(None, fetch_current_number)
        if current:
            await message.reply(f"今{current}番が診察中ですよ〜")
        else:
            await message.reply("番号を取得できませんでした。")

    elif action == "cancel":
        if channel_id in watching:
            watching[channel_id]["task"].cancel()
            del watching[channel_id]
            await message.reply("監視をキャンセルしました！")
        else:
            await message.reply("今は何も監視していませんよ。")

    else:
        watching_info = f"\n今は{watching[channel_id]['target']}番を監視中です。" if channel_id in watching else ""
        await message.reply(
            f"こんにちは！クリニックの番号をお知らせするボットです。{watching_info}\n"
            "・「今何番？」→ 現在の番号を確認\n"
            "・「5番になったら教えて」→ 通知設定\n"
            "・「キャンセル」→ 通知をやめる"
        )


client.run(BOT_TOKEN)
