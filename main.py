#!/usr/bin/env python
# coding: utf-8

import os
import json
import requests
import openai
import gspread
import datetime
import re
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

# --- 固定助成金情報 (長野県の情報通信業向け) ---
def get_grant_data():
    """長野県の情報通信業向けの補助金・助成金情報を取得する"""
    grants = [
        {
            "title": "IT導入補助金2025（通常枠）", 
            "url": "https://it-shien.smrj.go.jp/", 
            "description": "中小企業・小規模事業者向けにITツール導入を支援。業務効率化や売上向上に貢献するITツール導入費用の一部を補助（補助率1/2、最大450万円）。"
        },
        {
            "title": "IT導入補助金2025（セキュリティ対策推進枠）", 
            "url": "https://it-shien.smrj.go.jp/security/", 
            "description": "サイバーセキュリティ対策強化を目的としたITツール導入を支援。小規模事業者は補助率2/3、上限150万円まで補助。"
        },
        {
            "title": "長野県プラス補助金（中小企業経営構造転換促進事業）", 
            "url": "https://www.pref.nagano.lg.jp/keieishien/corona/kouzou-tenkan.html", 
            "description": "国の補助金に上乗せして支援。事業再構築や生産性向上に取り組む県内中小企業が対象。"
        },
        {
            "title": "長野県中小企業賃上げ・生産性向上サポート補助金", 
            "url": "https://www.pref.nagano.lg.jp/rodokoyo/seisanseisupport.html", 
            "description": "業務改善と賃金引上げに取り組む中小企業を支援。国の業務改善助成金の上乗せ補助を実施。"
        },
        {
            "title": "事業再構築補助金（第13回公募）", 
            "url": "https://jigyou-saikouchiku.go.jp/", 
            "description": "ポストコロナ・ウィズコロナ時代の経済社会変化に対応するための新分野展開や業態転換等を支援。"
        }
    ]
    return grants

def evaluate_grant_with_gpt(title, url, description):
    """助成金情報をGPTで評価"""
    prompt = f"""
あなたは企業向け助成金アドバイザーです。
以下の助成金が、長野県塩尻市の情報通信業・従業員56名の中小企業にとって申請対象になるか、また申請優先度（高・中・低）を判定してください。

【助成金名】{title}
【詳細URL】{url}
【概要】{description}

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
    """Google Chatに通知を送信"""
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
    grants = get_grant_data()
    print(f"✅ 助成金件数: {len(grants)} 件")

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
        description = grant["description"]

        print(f"⏳ {i}件目 評価中...")
        result = evaluate_grant_with_gpt(title, url, description)
        print(f"✅ {i}件目 評価完了")

        # GPT回答の分解（正規表現を使って堅牢に）
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
        full_message += f"・理由: {reason}\n"
        full_message += f"・URL: {url}\n\n"

    # メッセージが空でないことを確認してから送信
    if full_message:
        send_to_google_chat(full_message, WEBHOOK_URL)
    else:
        print("❌ 送信するメッセージがありません")
        send_to_google_chat("助成金情報の評価結果はありませんでした。", WEBHOOK_URL)

if __name__ == "__main__":
    main()
