import os
import json
import requests
import openai
import gspread
import datetime  # datetime モジュールを追加
import re  # 正規表現用のモジュールを追加
from bs4 import BeautifulSoup
from google.oauth2 import service_account

# --- 環境変数読み込み ---
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# 環境変数チェック
if not WEBHOOK_URL:
    print("❌ WEBHOOK_URL が設定されていません")
    exit(1)
else:
    # 最初の数文字だけをログに出す（セキュリティのため）
    webhook_preview = WEBHOOK_URL[:15] + "..." if len(WEBHOOK_URL) > 15 else WEBHOOK_URL
    print(f"✅ WEBHOOK_URL: {webhook_preview}")

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
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # エラーチェック
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        grants = []
        # 選択子を複数パターン試す（サイト構造が変わっている可能性があるため）
        selectors = [
            ".c-list__item",
            ".list-item",
            ".grant-item",
            ".support-list li",
            "article",
            ".entry"
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items:
                print(f"✅ セレクタ '{selector}' で {len(items)} 件見つかりました")
                for item in items:
                    # タイトルを探す複数パターン
                    title_elem = None
                    for title_selector in [".c-list__title a", "h3 a", "h2 a", ".title a", "a"]:
                        title_elem = item.select_one(title_selector)
                        if title_elem:
                            break
                    
                    if title_elem:
                        title = title_elem.text.strip()
                        link = title_elem.get("href")
                        if link:
                            full_url = f"https://j-net21.smrj.go.jp{link}" if link.startswith("/") else link
                            grants.append({"title": title, "url": full_url})
                
                # 見つかったらループを抜ける
                if grants:
                    break
        
        # デバッグ情報
        print(f"スクレイピング結果: {len(grants)} 件の助成金情報")
        if not grants:
            print(f"HTMLの内容: {response.text[:500]}...")  # 最初の500文字を表示
            
        return grants
    except Exception as e:
        print(f"❌ スクレイピングエラー: {e}")
        return []

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
    
    # シンプルなテキストメッセージ形式
    payload = {"text": f"📢 助成金支援制度評価レポート\n更新日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{message}"}
    
    try:
        response = requests.post(webhook_url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"✅ Google Chatに通知しました。ステータスコード: {response.status_code}")
    except Exception as e:
        print(f"❌ Google Chat送信エラー: {e}")
        print(f"リクエスト内容: {json.dumps(payload, ensure_ascii=False)}")

# --- メイン処理 ---
def main():
    print("✅ 助成金情報取得開始")
    grants = scrape_jnet21_grants()
    print(f"✅ 助成金件数: {len(grants)} 件")

    # スプレッドシート初期化
    sheet.clear()
    headers = ["No.", "タイトル", "URL", "対象かどうか", "理由", "申請優先度"]
    sheet.append_row(headers)

    # メッセージ内容を初期化
    full_message = ""
    
    # 助成金情報が取得できなかった場合
    if not grants:
        error_msg = "助成金情報が取得できませんでした。サイト構造が変更された可能性があります。"
        print(f"❌ {error_msg}")
        send_to_google_chat(error_msg, WEBHOOK_URL)
        return

    for i, grant in enumerate(grants[:5], start=1):  # ←本番運用は[:5]外して全件にしてOK
        title = grant["title"]
        url = grant["url"]

        print(f"⏳ {i}件目 評価中...")
        result = evaluate_grant_with_gpt(title, url)
        print(f"✅ {i}件目 評価完了")

        # GPT回答の分解（正規表現を使ってより堅牢に）
        target = re.search(r"対象かどうか:?\s*(.+)", result)
        target = target.group(1).strip() if target else "不明"
        
        reason = re.search(r"理由:?\s*(.+)", result)
        reason = reason.group(1).strip() if reason else "不明"
        
        priority = re.search(r"申請優先度:?\s*(.+)", result)
        priority = priority.group(1).strip() if priority else "不明"

        sheet.append_row([i, title, url, target, reason, priority])

        # 各助成金情報をメッセージに追加
        full_message += f"*{i}. {title}*\n"
        full_message += f"・対象: *{target}*\n"
        full_message += f"・優先度: *{priority}*\n"
        full_message += f"・URL: {url}\n\n"

    # メッセージが空でないことを確認してから送信
    if full_message:
        send_to_google_chat(full_message, WEBHOOK_URL)
    else:
        print("❌ 送信するメッセージがありません")
        send_to_google_chat("助成金情報の評価結果はありませんでした。", WEBHOOK_URL)

if __name__ == "__main__":
    main()
