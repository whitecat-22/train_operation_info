import os
import json
import boto3
import base64
from urllib.parse import parse_qs
from slack_sdk.signature import SignatureVerifier

# 環境変数
SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
PROCESSOR_FUNCTION_NAME = os.getenv("PROCESSOR_FUNCTION_NAME")

def lambda_handler(event, context):
    # 1. Bodyの取得とデコード
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        # API Gateway経由でBase64エンコードされている場合の処理
        body = base64.b64decode(body).decode("utf-8")

    # 署名検証には「生の文字列」のbodyが必要です
    if isinstance(body, bytes):
        body = body.decode("utf-8")

    # ヘッダーを小文字で統一して取得
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}

    # Slack特有のヘッダーを取得
    signature = headers.get("x-slack-signature")
    timestamp = headers.get("x-slack-request-timestamp")

    # 署名検証の実行
    verifier = SignatureVerifier(SIGNING_SECRET)
    if not verifier.is_valid(body, timestamp, signature):
        print(f"Verification failed. Signature: {signature}, Timestamp: {timestamp}")
        return {'statusCode': 403, 'body': 'Forbidden: Signature mismatch'}

    # 2. パラメータ解析 (Slackは application/x-www-form-urlencoded で送ってくる)
    params = {k: v[0] for k, v in parse_qs(body).items()}

    # 3. 実行用Lambdaを非同期 (Event) で呼び出し
    lambda_client = boto3.client('lambda')
    lambda_client.invoke(
        FunctionName=PROCESSOR_FUNCTION_NAME,
        InvocationType='Event',
        Payload=json.dumps({"response_url": params.get("response_url")})
    )

    # 4. Slackへ3秒以内に即時レスポンス
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({"text": "⏳ 運行情報を取得しています..."})
    }
