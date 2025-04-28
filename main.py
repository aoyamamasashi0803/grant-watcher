import os
import json
import requests
import openai
import gspread
from bs4 import BeautifulSoup
from google.oauth2 import service_account

# --- 環境変数読み込み ---
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# --- OpenAI初期化 ---
openai.api_key = OPENAI_API_KEY

# --- Google認証 ---
try:
    credentials_info = json.loads(GOOGLE_SERVICE_ACCOUNT)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    gc = gspread.authorize(credentials)
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
    print("✅ スプレッドシート接続成功")
except Exception as e:
    print(f"❌ スプレッドシート接続失敗: {e}")
    exit(1)

# --- 関数定義 ---
def scrape_jnet21_grants():
    url = "https://j-net21.smrj.go.jp/public-support/"
    response = requests.get(url)
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")

    grants = []
    for item in soup.select(".c-list__item"):
        title_elem = item.select_one(".c-list__title a")
        if title_elem:
            title = title_elem.text.strip()
            link = title_elem.get("href")
            full_url = f"https://j-net21.smrj.go.jp{link}" if link.startswith("/") else link
            grants.append({"title": title, "url": full_url})
    return grants

def evaluate_grant_with_gpt(title, url):
    prompt = f"""
あなたは企業向け助成金アドバイザーです。
以下の助成金が、長野県塩尻市の情報通信業・従業員56名の中小企業にとって申請対象になるか、また申請優先度（高・中・低）を判定してください。

【助成金名】{title}
【詳細URL】{url}

回答形式は以下でお願いします：
---
対象かどうか: （はい／いいえ）
理由: （簡単に）
申請優先度: （高／中／低）
---
"""
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ GPT評価エラー: {str(e)}"

def send_to_google_chat(message, webhook_url):
    headers = {"Content-Type": "application/json"}
    payload = {"text": message}
    try:
        response = requests.post(webhook_url, headers=headers, json=payload)
        response.raise_for_status()
        print("✅ Google Chatに通知しました。")
    except Exception as e:
        print(f"❌ Google Chat送信エラー: {e}")

# --- メイン処理 ---
def main():
    print("✅ 助成金情報取得開始")
    grants = scrape_jnet21_grants()
    print(f"✅ 助成金件数: {len(grants)} 件")

    # スプレッドシート初期化
    sheet.clear()
    headers = ["No.", "タイトル", "URL", "対象かどうか", "理由", "申請優先度"]
    sheet.append_row(headers)

    full_message = "📢 助成金支援制度評価レポート\n\n"
    for i, grant in enumerate(grants[:5], start=1):  # ←本番運用は[:5]外して全件にしてOK
        title = grant["title"]
        url = grant["url"]

        result = evaluate_grant_with_gpt(title, url)
        print(f"✅ {i}件目 評価完了")

        # GPT回答の分解
        target = ""
        reason = ""
        priority = ""
        for line in result.splitlines():
            if "対象かどうか" in line:
                target = line.split(":")[1].strip()
            if "理由" in line:
                reason = line.split(":")[1].strip()
            if "申請優先度" in line:
                priority = line.split(":")[1].strip()

        sheet.append_row([i, title, url, target, reason, priority])

        full_message += f"【{i}. {title}】\n対象: {target}\n優先度: {priority}\n{url}\n\n"

    # Google Chatにまとめて通知
    send_to_google_chat(full_message, WEBHOOK_URL)

if __name__ == "__main__":
    main()
