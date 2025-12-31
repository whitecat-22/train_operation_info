import os
import json
import urllib.request
from datetime import datetime, timezone
import pytz
from slack_sdk import WebClient

# 環境変数
API_URL = os.getenv("METRO_API_URL")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

LINE_NAME_DICT = {
    "odpt.Railway:TokyoMetro.Ginza": "銀座線",
    "odpt.Railway:TokyoMetro.Marunouchi": "丸ノ内線",
    "odpt.Railway:TokyoMetro.MarunouchiBranch": "丸ノ内線(分岐線)",
    "odpt.Railway:TokyoMetro.Chiyoda": "千代田線",
    "odpt.Railway:TokyoMetro.Tozai": "東西線",
    "odpt.Railway:TokyoMetro.Yurakucho": "有楽町線",
    "odpt.Railway:TokyoMetro.Fukutoshin": "副都心線",
    "odpt.Railway:TokyoMetro.Hanzomon": "半蔵門線",
    "odpt.Railway:TokyoMetro.Hibiya": "日比谷線",
    "odpt.Railway:TokyoMetro.Namboku": "南北線",
}

def lambda_handler(event, context):
    print(f"Processor started: {json.dumps(event)}")

    # スラッシュコマンド経由か判定（Dispatcherから渡される response_url の有無）
    response_url = event.get("response_url")

    try:
        # 1. 運行情報取得
        req = urllib.request.Request(API_URL)
        with urllib.request.urlopen(req, timeout=10) as res:
            data_dict = json.loads(res.read().decode("utf-8"))

        # 2. 日時整形
        raw_date = data_dict[0].get("dc:date") if data_dict else None
        dt = datetime.fromisoformat(raw_date) if raw_date else datetime.now(timezone.utc)
        display_time = dt.astimezone(pytz.timezone('Asia/Tokyo')).strftime('%m/%d %H:%M')

        # 3. データの解析と色の決定
        fields = []
        is_any_delay = False # 全路線のうち一つでも遅延があるか保持

        for info in data_dict:
            rid = info.get("odpt:railway")
            if rid in LINE_NAME_DICT:
                status_text = info.get("odpt:trainInformationText", {}).get("ja", "情報なし")

                # 平常運転以外が含まれるか判定
                is_normal = "平常" in status_text
                if not is_normal:
                    is_any_delay = True

                icon = "✅" if is_normal else "⚠️"
                fields.append({
                    "title": f"{icon} {LINE_NAME_DICT[rid]}",
                    "value": status_text,
                    "short": False # 横並びにせず、1行ずつ表示
                })

        # 4. メッセージ全体の色の決定
        # 全体で一つでも遅延があれば「赤」、すべて平常なら「緑」
        attachment_color = "#ff0000" if is_any_delay else "#36a64f"

        # 5. Attachment構造の組み立て
        attachment = {
            "color": attachment_color,
            "title": f"東京メトロ運行情報 ({display_time}現在)",
            "fields": fields,
            "fallback": "東京メトロの最新運行情報をお届けします。"
        }

        # 6. 送信処理
        if response_url:
            # スラッシュコマンドへの応答
            payload = {
                "response_type": "in_channel",
                "attachments": [attachment]
            }
            send_post(response_url, payload)
        else:
            # 定期実行
            client = WebClient(token=SLACK_BOT_TOKEN)
            client.chat_postMessage(
                channel=SLACK_CHANNEL_ID,
                text="🔔 定期運行情報のお知らせ",
                attachments=[attachment]
            )

        return {'statusCode': 200}

    except Exception as e:
        print(f"Error: {str(e)}")
        return {'statusCode': 500}

def send_post(url, payload):
    """汎用POST関数"""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as res:
        return res.read().decode()
