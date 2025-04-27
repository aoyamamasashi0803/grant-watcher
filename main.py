import os
import json
import requests
import csv
import re
from io import StringIO
from bs4 import BeautifulSoup
from openai import OpenAI
import gspread
from google.oauth2 import service_account

# 環境変数から各種情報を取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")

MODEL_NAME = "gpt-3.5-turbo"

# OpenAIクライアント初期化
client = OpenAI(
    api_key=OPENAI_API_KEY,
    default_headers={"Content-Type": "application/json; charset=utf-8"}
)

# スプレッドシート接続設定
credentials_info = json.loads(GOOGLE_SERVICE_ACCOUNT)
credentials = service_account.Credentials.from_service_account_info(
    credentials_info,
    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# Google Chatにメッセージ送信
def send_to_google_chat(message, webhook_url):
    payload = {"text": message}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    response = requests.post(webhook_url, headers=headers, json=payload)
    if response.status_code == 200:
        print("✅ Google Chatに通知しました。")
    else:
        print(f"⚠️ Chat通知失敗: {response.status_code} - {response.text}")

# J-Net21支援制度情報を取得
def fetch_jnet21():
    url = "https://code4fukui.github.io/JNet21/j-net21_support-list.csv"
    response = requests.get(url)
    response.raise_for_status()
    lines = response.text.splitlines()
    reader = csv.DictReader(lines)
    grants = list(reader)
    print(f"✅ JNet21支援制度 {len(grants)}件取得済み")
    return grants

# ミラサポplusページ情報を取得
def fetch_mirasapo_text():
    url = "https://code4fukui.github.io/mirasapo/"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(separator="\n").strip()
    print("✅ ミラサポplusページテキスト取得済み")
    return text

# GPT評価共通関数
def evaluate_with_gpt(prompt, label):
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "あなたは補助金・助成金マッチングの専門家です。"},
                {"role": "user", "content": prompt}
            ]
        )
        answer = response.choices[0].message.content.strip()
        print(f"✅ {label} 評価完了")
        return answer
    except Exception as e:
        print(f"⚠️ {label} GPT評価失敗: {e}")
        return f"評価失敗: {e}"

# 優先度を抽出する関数
def extract_priority(text):
    match = re.search(r"申請優先度[：: ]*\s*(高|中|低)", text)
    if match:
        return match.group(1)  # 「高」「中」「低」を返す
    return None

# ================================
# Main 実行処理
# ================================

def main():
    grants = fetch_jnet21()
    mirasapo_text = fetch_mirasapo_text()

    priority_entries = []  # 高・中・低すべて保存対象
    high_priority_messages = []  # 高だけ通知対象

    company_info = "長野県塩尻市の情報通信業、従業員56名の中小企業"

    # 1. J-Net21支援制度の評価
    for idx, grant in enumerate(grants, 1):
        info = "\n".join([f"{k}: {v}" for k, v in grant.items() if v])
        label = f"JNet21 補助金 {idx}"

        prompt = f"""
以下は補助金支援制度の情報です。

{info}

想定企業: {company_info}

この企業はこの支援制度の申請対象となりますか？
理由と、申請優先度（高・中・低）も教えてください。
"""

        result = evaluate_with_gpt(prompt, label)
        priority = extract_priority(result)

        if priority in ["高", "中", "低"]:
            priority_entries.append([label, result])

        if priority == "高":
            high_priority_messages.append(f"【{label}】\n{result}")

    # 2. ミラサポplusページの評価
    prompt2 = f"""
以下はミラサポplusトップページの情報です。

{mirasapo_text}

想定企業: {company_info}

この企業に関連して申請可能な支援制度はありますか？
該当制度名と理由、申請優先度（高・中・低）も教えてください。
"""

    result2 = evaluate_with_gpt(prompt2, "ミラサポplus")
    priority2 = extract_priority(result2)

    if priority2 in ["高", "中", "低"]:
        priority_entries.append(["ミラサポplus", result2])

    if priority2 == "高":
        high_priority_messages.append(f"【ミラサポplus】\n{result2}")

    # 3. スプレッドシートに書き込み
    if priority_entries:
        sheet.clear()  # 既存内容をクリア
        sheet.append_row(["ラベル", "評価結果"])  # ヘッダー
        for entry in priority_entries:
            sheet.append_row(entry)
        print("✅ 評価結果をスプレッドシートに保存しました。")
    else:
        print("✅ 保存対象がありませんでした。")

    # 4. Chat通知
    if high_priority_messages:
        full_message = "📢 優先度高 支援制度一覧\n\n" + "\n\n".join(high_priority_messages)
        if len(full_message) > 4000:
            full_message = full_message[:3990] + "\n...続きはスプレッドシートを確認！"
        send_to_google_chat(full_message, WEBHOOK_URL)
    else:
        print("✅ Chat通知対象なし（スプレッドシート更新のみ）")

if __name__ == "__main__":
    main()
