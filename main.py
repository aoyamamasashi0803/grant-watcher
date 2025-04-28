import os
import json
import gspread
from google.oauth2 import service_account

# 環境変数から設定を取得
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
# Secrets（環境変数）からセット
GOOGLE_SERVICE_ACCOUNT = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
if GOOGLE_SERVICE_ACCOUNT is None:
    raise ValueError("GOOGLE_SERVICE_ACCOUNTが設定されていません。")
    
print("✅ 環境変数取得完了")

# スプレッドシートに接続
try:
    credentials_info = json.loads(GOOGLE_SERVICE_ACCOUNT)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    print("✅ 認証情報ロード成功")
except Exception as e:
    print(f"❌ 認証情報ロード失敗: {e}")

try:
    gc = gspread.authorize(credentials)
    print("✅ gspread認証成功")
except Exception as e:
    print(f"❌ gspread認証失敗: {e}")

try:
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
    print("✅ スプレッドシート接続成功")
except Exception as e:
    print(f"❌ スプレッドシート接続失敗: {e}")

# テスト書き込み
try:
    sheet.clear()
    print("✅ sheet.clear() 成功")
except Exception as e:
    print(f"❌ sheet.clear() 失敗: {e}")

try:
    sheet.append_row(["テスト書き込み成功！"])
    print("✅ sheet.append_row() 成功")
except Exception as e:
    print(f"❌ sheet.append_row() 失敗: {e}")
