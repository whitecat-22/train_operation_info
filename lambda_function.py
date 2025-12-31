import os
import json
import urllib.request
from datetime import datetime, timezone
import pytz

# ローカル環境の .env ファイルを読み込むための設定
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Lambda環境（本番）では環境変数が直接設定されるため、無視してOK
    pass

# slack_sdk から WebClient をインポート
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    # Lambda Layerの設定が未完了の場合の警告
    print("Warning: slack_sdk not found. Please add it to Lambda Layer.")

# 環境変数
API_URL = os.getenv("METRO_API_URL")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")  # xoxb- で始まるトークン
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")      # チャンネルID (例: C0123456789)

# 路線名マッピング
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
    """
    AWS Lambda ハンドラ関数
    """
    # ログ出力（デバッグ用）
    current_event = event if event is not None else {}
    print(f"Event received: {json.dumps(current_event)}")

    try:
        # 1. 東京メトロ運行情報の取得
        # urllibのRequestオブジェクトを明示的に作成（タイムアウト/ローカルエラー対策）
        req = urllib.request.Request(API_URL)
        with urllib.request.urlopen(req, timeout=10) as res:
            data_dict = json.loads(res.read().decode("utf-8"))

        # 2. 表示用日時の決定 (APIレスポンスの dc:date を優先)
        display_time_str = ""
        try:
            # APIレスポンスの最初の要素から日付を取得
            raw_date = data_dict[0].get("dc:date") if data_dict else None
            if raw_date:
                dt = datetime.fromisoformat(raw_date)
                # JST（日本時間）としてフォーマット
                display_time_str = dt.strftime('%m/%d %H:%M')
            else:
                raise ValueError("No date found in API response")
        except Exception as e:
            # APIから日時が取れない場合はシステム時刻で代用
            print(f"Date fallback due to: {e}")
            tokyo_tz = pytz.timezone('Asia/Tokyo')
            now_jst = datetime.now(timezone.utc).astimezone(tokyo_tz)
            display_time_str = now_jst.strftime('%m/%d %H:%M')

        # 3. 各路線の運行情報をメッセージに組み立て
        header = f"🚉 *東京メトロ運行情報* ({display_time_str}現在)"
        info_lines = []

        for info in data_dict:
            railway_id = info.get("odpt:railway")
            if railway_id in LINE_NAME_DICT:
                line_name = LINE_NAME_DICT[railway_id]
                # 運行情報のテキストを取得
                status_text = info.get("odpt:trainInformationText", {}).get("ja", "情報なし")

                # アイコンの判定（平常時以外は警告アイコン）
                icon = "✅" if "平常" in status_text else "⚠️"
                info_lines.append(f"{icon} *{line_name}*: {status_text}")

        # 万が一情報が1件もない場合のメッセージ
        if not info_lines:
            full_message = f"{header}\n現在、対象路線の運行情報を取得できませんでした。"
        else:
            full_message = f"{header}\n\n" + "\n".join(info_lines)

        # 4. Slackへ送信
        # 環境変数の存在チェック
        if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
            raise ValueError("Environment variables SLACK_BOT_TOKEN or SLACK_CHANNEL are missing.")

        client = WebClient(token=SLACK_BOT_TOKEN)
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=full_message
        )

        print(f"Post successful. Message TS: {response['ts']}")
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Success', 'ts': response['ts']})
        }

    except SlackApiError as e:
        error_msg = f"Slack API Error: {e.response['error']}"
        print(error_msg)
        return {'statusCode': 500, 'body': json.dumps(error_msg)}
    except Exception as e:
        import traceback
        error_msg = f"Unexpected Error: {str(e)}"
        print(error_msg)
        print(traceback.format_exc()) # エラーの詳細をログに出力
        return {'statusCode': 500, 'body': json.dumps(error_msg)}

# --- ローカル実行用 ---
if __name__ == "__main__":
    # ローカルで実行する場合、.envファイルがあることを前提に動きます
    print("Executing locally...")
    result = lambda_handler(event={}, context=None)
    print(f"Execution Result: {result}")
