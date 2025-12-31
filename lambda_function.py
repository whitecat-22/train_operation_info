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

        # 3. メッセージ構築
        header = f"🚉 *東京メトロ運行情報* ({display_time}現在)"
        info_lines = []
        for info in data_dict:
            rid = info.get("odpt:railway")
            if rid in LINE_NAME_DICT:
                txt = info.get("odpt:trainInformationText", {}).get("ja", "情報なし")
                icon = "✅" if "平常" in txt else "⚠️"
                info_lines.append(f"{icon} *{LINE_NAME_DICT[rid]}*: {txt}")

        full_message = f"{header}\n\n" + "\n".join(info_lines)

        # 4. 送信処理
        if response_url:
            # スラッシュコマンドへの非同期応答（response_urlへPOST）
            payload = {"text": full_message, "response_type": "in_channel"}
            req_slack = urllib.request.Request(
                response_url,
                data=json.dumps(payload).encode(),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req_slack)
        else:
            # 定期実行
            client = WebClient(token=SLACK_BOT_TOKEN)
            client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=full_message)

        return {'statusCode': 200}

    except Exception as e:
        print(f"Error: {str(e)}")
        return {'statusCode': 500}
