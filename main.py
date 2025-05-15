import os
import json
import requests
import openai
import gspread
import datetime  # datetime モジュールを追加
import re  # 正規表現用のモジュールを追加
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from urllib.parse import urlparse

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
    # 複数の可能性のあるURLを試す
    possible_urls = [
        "https://j-net21.smrj.go.jp/snavi/articles?category%5B%5D=2",  # 補助金カテゴリのURL
        "https://j-net21.smrj.go.jp/support/",
        "https://j-net21.smrj.go.jp/snavi/support/",
        "https://j-net21.smrj.go.jp/",  # ベースURL
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for url in possible_urls:
        print(f"🔍 URL {url} にアクセス試行中...")
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                print(f"✅ URL {url} アクセス成功")
                response.encoding = response.apparent_encoding
                soup = BeautifulSoup(response.text, "html.parser")
                
                # デバッグ: HTML構造確認
                print(f"ページタイトル: {soup.title.text if soup.title else 'タイトルなし'}")
                
                grants = []
                # 選択子を複数パターン試す（サイト構造が変わっている可能性があるため）
                selectors = [
                    ".c-list__item",
                    ".list-item",
                    ".grant-item",
                    ".support-list li",
                    "article",
                    ".entry",
                    ".o-list__item",
                    ".o-panel-list__item",
                    ".o-block-list__item",
                    "li.o-list__item",
                    ".m-panel-article",
                    ".m-block-article",
                    "li"
                ]
                
                # デバッグ: 各セレクタの結果出力
                for selector in selectors:
                    items = soup.select(selector)
                    print(f"セレクタ '{selector}': {len(items)} 件")
                
                for selector in selectors:
                    items = soup.select(selector)
                    if items:
                        print(f"✅ セレクタ '{selector}' で {len(items)} 件見つかりました")
                        for item in items:
                            # タイトルを探す複数パターン
                            title_elem = None
                            for title_selector in [".c-list__title a", "h3 a", "h2 a", ".title a", "a", ".m-block-article__title a", ".o-panel-article__title", ".m-panel-article__title", "dt a", ".m-article-title"]:
                                title_elem = item.select_one(title_selector)
                                if title_elem:
                                    print(f"タイトル要素: {title_selector} で見つかりました")
                                    break
                            
                            if title_elem:
                                title = title_elem.text.strip()
                                print(f"タイトル: {title}")
                                link = title_elem.get("href")
                                if link:
                                    # 相対URLを絶対URLに変換
                                    if link.startswith("/"):
                                        # URLのドメイン部分を抽出
                                        parsed_url = urlparse(url)
                                        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                                        full_url = f"{base_url}{link}"
                                    else:
                                        full_url = link
                                    print(f"URL: {full_url}")
                                    grants.append({"title": title, "url": full_url})
                        
                        # 助成金情報を5件以上見つけたらループを抜ける
                        if len(grants) >= 5:
                            print(f"✅ 十分な助成金情報が見つかりました: {len(grants)} 件")
                            break
                
                # 助成金情報が見つかった場合
                if grants:
                    print(f"✅ URL {url} から {len(grants)} 件の助成金情報を取得しました")
                    return grants
            
            # 見つからなかった場合は次のURLを試す
            else:
                print(f"❌ URL {url} アクセス失敗 (ステータスコード: {response.status_code})")
                
        except Exception as e:
            print(f"❌ URL {url} 処理エラー: {e}")
    
    # すべてのURLで失敗した場合
    print("❌ すべてのURLでスクレイピングに失敗しました")
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
    if not message.strip():
        print("❌ 送信するメッセージが空です")
        message = "助成金情報を取得できませんでした。システム管理者に確認してください。"
    
    # URLの検証
    if not webhook_url or not webhook_url.startswith("https://"):
        print("❌ 無効なwebhook URLです")
        return
    
    headers = {"Content-Type": "application/json"}
    
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # シンプルなテキストメッセージ形式
    payload = {"text": f"📢 助成金支援制度評価レポート\n更新日時: {current_time}\n\n{message}"}
    
    try:
        print(f"⏳ Google Chatに送信中... ({webhook_url[:15]}...)")
        response = requests.post(webhook_url, headers=headers, json=payload)
        print(f"応答ステータスコード: {response.status_code}")
        print(f"応答本文: {response.text[:100]}")  # 最初の100文字だけ表示
        
        if response.status_code == 200:
            print(f"✅ Google Chatに通知しました。ステータスコード: {response.status_code}")
        else:
            print(f"❌ Google Chat送信エラー: ステータスコード {response.status_code}")
            print(f"応答本文: {response.text}")
    except Exception as e:
        print(f"❌ Google Chat送信エラー: {e}")
        print(f"リクエスト内容: {json.dumps(payload, ensure_ascii=False)[:200]}...")  # 最初の200文字だけ表示

# --- メイン処理 ---
def main():
    print("✅ 助成金情報取得開始")
    grants = scrape_jnet21_grants()
    print(f"✅ 助成金件数: {len(grants)} 件")

    # 助成金情報が取得できなかった場合、ダミーデータを使用（テスト用）
    if not grants:
        print("⚠️ 助成金情報が取得できませんでした。テスト用ダミーデータを使用します。")
        grants = [
            {"title": "【テスト】令和7年度 中小企業デジタル化支援補助金", "url": "https://example.com/digital"},
            {"title": "【テスト】事業再構築補助金（第10回）", "url": "https://example.com/saikouchiku"},
            {"title": "【テスト】ものづくり補助金 2025年度第1次公募", "url": "https://example.com/monodukuri"},
            {"title": "【テスト】小規模事業者持続化補助金", "url": "https://example.com/jizokuka"},
            {"title": "【テスト】IT導入補助金2025", "url": "https://example.com/it"}
        ]
        print(f"✅ テスト用ダミーデータ: {len(grants)} 件")

    # スプレッドシート初期化
    try:
        sheet.clear()
        headers = ["No.", "タイトル", "URL", "対象かどうか", "理由", "申請優先度"]
        sheet.append_row(headers)
        print("✅ スプレッドシート初期化完了")
    except Exception as e:
        print(f"❌ スプレッドシート操作エラー: {e}")
        # エラーメッセージ送信して終了
        send_to_google_chat("スプレッドシートの操作中にエラーが発生しました。", WEBHOOK_URL)
        return

    # メッセージ内容を初期化
    full_message = ""

    for i, grant in enumerate(grants, start=1):
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

        try:
            sheet.append_row([i, title, url, target, reason, priority])
            print(f"✅ {i}件目 スプレッドシート書き込み完了")
        except Exception as e:
            print(f"❌ スプレッドシート書き込みエラー: {e}")

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
