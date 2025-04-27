import os
import json
import gspread
from google.oauth2 import service_account

# 環境変数から設定を取得
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")

# スプレッドシートに接続
credentials_info = json.loads(GOOGLE_SERVICE_ACCOUNT)
credentials = service_account.Credentials.from_service_account_info(
    credentials_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# 🔥 テスト書き込み
sheet.clear()  # 既存データクリア
sheet.append_row(["テスト書き込み成功！"])

print("✅ スプレッドシートにテスト書き込みできました！")
