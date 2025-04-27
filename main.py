import os
import requests
import csv
from io import StringIO
from bs4 import BeautifulSoup
from openai import OpenAI

# 環境変数からAPIキーとWebhook URLを取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MODEL_NAME = "gpt-4"

# OpenAIクライアントの初期化
client = OpenAI(
    api_key=OPENAI_API_KEY,
    default_headers={"Content-Type": "application/json; charset=utf-8"}
)

# Google Chatにメッセージを送信する関数
def send_to_google_chat(message, webhook_url):
    payload = {"text": message}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    response = requests.post(webhook_url, headers=headers, json=payload)
    if response.status_code == 200:
        print("✅ Google Chatに通知しました。")
    else:
        print(f"⚠️ Chat通知失敗: {response.status_code} - {response.text}")

# J-Net21補助金情報を取得して上位5件をリスト化
def fetch_jnet21_top5():
    url = "https://code4fukui.github.io/JNet21/j-net21_support-list.csv"
    response = requests.get(url)
    response.raise_for_status()
    lines = response.text.splitlines()
    reader = csv.DictReader(lines)
    grants = list(reader)
    print(f"✅ JNet21支援制度 {len(grants)}件取得済み")
    return grants[:5]

# ミラサポplusトップページのテキストを取得
def fetch_mirasapo_text():
    url = "https://code4fukui.github.io/mirasapo/"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(separator="\n").strip()
    print("✅ ミラサポplusページテキスト取得済み")
    return text

# GPTで補助金情報を評価する
def evaluate_scheme_with_gpt(info, label):
    company_info = "長野県塩尻市の情報通信業、従業員56名の中小企業"
    prompt = f"""
以下は補助金支援制度の情報です。

{info}

想定企業: {company_info}

この企業はこの支援制度の申請対象となりますか？
理由と、申請優先度（高・中・低）も教えてください。
"""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "あなたは補助金・助成金支援の専門家です。"},
                {"role": "user", "content": prompt}
            ]
        )
        answer = response.choices[0].message.content.strip()
        print(f"✅ {label} 評価完了")
        return f"【{label}】\n{answer}\n"
    except Exception as e:
        print(f"⚠️ {label} GPT評価失敗: {e}")
        return f"【{label}】評価失敗: {e}\n"

# GPTでミラサポページを評価する
def evaluate_mirasapo_with_gpt(text):
    company_info = "長野県塩尻市の情報通信業、従業員56名の中小企業"
    prompt = f"""
以下はミラサポplusトップページの情報です。

{text}

想定企業: {company_info}

この企業に関連して申請可能な支援制度はありますか？
該当制度名と理由、申請優先度（高・中・低）も教えてください。
"""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "あなたは補助金・助成金支援の専門家です。"},
                {"role": "user", "content": prompt}
            ]
        )
        answer = response.choices[0].message.content.strip()
        print("✅ ミラサポplusページ評価完了")
        return f"【ミラサポplusトップページ】\n{answer}\n"
    except Exception as e:
        print(f"⚠️ ミラサポplus GPT評価失敗: {e}")
        return f"【ミラサポplusトップページ】評価失敗: {e}\n"

# ================================
# Main 実行処理
# ================================

def main():
    messages = []

    # 1. J-Net21データの評価
    grants = fetch_jnet21_top5()
    for i, grant in enumerate(grants, 1):
        info = "\n".join([f"{k}: {v}" for k, v in grant.items() if v])
        label = f"JNet21 補助金 {i}"
        result = evaluate_scheme_with_gpt(info, label)
        messages.append(result)

    # 2. ミラサポplusページの評価
    mirasapo_text = fetch_mirasapo_text()
    result = evaluate_mirasapo_with_gpt(mirasapo_text)
    messages.append(result)

    # 3. Google Chatにまとめて通知
    full_message = "📢 補助金支援制度評価レポート\n\n" + "\n".join(messages)
    send_to_google_chat(full_message, WEBHOOK_URL)

if __name__ == "__main__":
    main()
