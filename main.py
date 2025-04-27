import os
import requests
import csv
from io import StringIO
from bs4 import BeautifulSoup
from openai import OpenAI

# 環境変数からAPIキーとWebhook URLを取得
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MODEL_NAME = "gpt-3.5-turbo"  # ★ gpt-3.5-turboに変更！

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

# J-Net21補助金情報を取得
def fetch_jnet21():
    url = "https://code4fukui.github.io/JNet21/j-net21_support-list.csv"
    response = requests.get(url)
    response.raise_for_status()
    lines = response.text.splitlines()
    reader = csv.DictReader(lines)
    grants = list(reader)
    print(f"✅ JNet21支援制度 {len(grants)}件取得済み")
    return grants

# ミラサポplusページテキストを取得
def fetch_mirasapo_text():
    url = "https://code4fukui.github.io/mirasapo/"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(separator="\n").strip()
    print("✅ ミラサポplusページテキスト取得済み")
    return text

# GPTで評価する共通関数
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

# ================================
# Main 実行処理
# ================================

def main():
    grants = fetch_jnet21()
    mirasapo_text = fetch_mirasapo_text()

    notifications = []  # 通知対象（優先度高）
    csv_results = []    # 全件記録用

    company_info = "長野県塩尻市の情報通信業、従業員56名の中小企業"

    # 1. JNet21支援制度の評価
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

        # 優先度を抽出する
        priority = ""
        if "優先度 高" in result or "優先度: 高" in result:
            priority = "高"
        elif "優先度 中" in result or "優先度: 中" in result:
            priority = "中"
        elif "優先度 低" in result or "優先度: 低" in result:
            priority = "低"

        # 優先度高だけ通知対象にする
        if priority == "高":
            notifications.append(f"【{label}】\n{result}\n")

        # CSV保存用に記録
        csv_results.append({
            "Label": label,
            "評価結果": result,
            "優先度": priority
        })

    # 2. ミラサポplusトップページ評価
    prompt2 = f"""
以下はミラサポplusトップページの情報です。

{mirasapo_text}

想定企業: {company_info}

この企業に関連して申請可能な支援制度はありますか？
該当制度名と理由、申請優先度（高・中・低）も教えてください。
"""

    result2 = evaluate_with_gpt(prompt2, "ミラサポplus")

    # ミラサポ結果も通知＆CSV保存
    if "優先度 高" in result2 or "優先度: 高" in result2:
        notifications.append(f"【ミラサポplus】\n{result2}\n")
    csv_results.append({
        "Label": "ミラサポplus",
        "評価結果": result2,
        "優先度": "高" if ("優先度 高" in result2 or "優先度: 高" in result2) else ""
    })

    # 3. 通知（優先度高のみ）
    if notifications:
        full_message = "📢 優先度高 支援制度通知\n\n" + "\n".join(notifications)
        send_to_google_chat(full_message, WEBHOOK_URL)
    else:
        print("✅ 優先度高の通知対象はありませんでした。")

    # 4. CSVに保存
    output_csv = "grant_evaluation_results.csv"
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["Label", "評価結果", "優先度"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in csv_results:
            writer.writerow(row)
    print(f"✅ 評価結果を {output_csv} に保存しました。")

if __name__ == "__main__":
    main()
