def normalize_text(text):
    """テキストの正規化と文字化け防止処理"""
    if not text:
        return ""
        
    # 制御文字や特殊文字の除去
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
    
    # 全角スペースを半角に変換
    text = text.replace('\u3000', ' ')
    
    # 連続する空白を1つにまとめる
    text = re.sub(r'\s+', ' ', text)
    
    # 前後の空白を削除
    text = text.strip()
    
    return text#!/usr/bin/env python
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
from urllib.parse import urlparse, urljoin

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

def scrape_jnet21_grants():
    """J-Net21から長野県の補助金・助成金情報を取得する"""
    base_url = "https://j-net21.smrj.go.jp/snavi/articles"
    params = {
        "category[]": 2,  # 補助金・助成金・融資カテゴリ
        "order": "DESC",
        "perPage": 50,  # より多くの結果を取得
        "page": 1
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # 長野県関連キーワード
    nagano_keywords = ['長野県', '長野市', '松本市', '上田市', '岡谷市', '飯田市', '諏訪市', '須坂市', '小諸市', 
                     '伊那市', '駒ヶ根市', '中野市', '大町市', '飯山市', '茅野市', '塩尻市', '佐久市', '千曲市', 
                     '東御市', '安曇野市', '長野']
    
    print(f"🔍 J-Net21の補助金情報を検索中...")
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            print(f"✅ J-Net21サイトアクセス成功")
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, "html.parser")
            
            grants = []
            
            # 記事アイテムを探す
            article_items = soup.select(".m-panel-article")
            
            if article_items:
                print(f"✅ 補助金・助成金記事: {len(article_items)} 件見つかりました")
                
                for item in article_items:
                    # 記事タイトルを取得
                    title_elem = item.select_one(".m-panel-article__title")
                    
                    if title_elem and title_elem.text:
                        title = title_elem.text.strip()
                        
                        # 長野県関連かどうか判定
                        is_nagano_related = any(keyword in title for keyword in nagano_keywords)
                        is_national = not any(prefecture in title for prefecture in ['北海道', '青森', '岩手', '宮城', '秋田', 
                                                                                 '山形', '福島', '茨城', '栃木', '群馬', 
                                                                                 '埼玉', '千葉', '東京', '神奈川', '新潟', 
                                                                                 '富山', '石川', '福井', '山梨', '岐阜', 
                                                                                 '静岡', '愛知', '三重', '滋賀', '京都', 
                                                                                 '大阪', '兵庫', '奈良', '和歌山', '鳥取', 
                                                                                 '島根', '岡山', '広島', '山口', '徳島', 
                                                                                 '香川', '愛媛', '高知', '福岡', '佐賀', 
                                                                                 '長崎', '熊本', '大分', '宮崎', '鹿児島', 
                                                                                 '沖縄'])
                        
                        # 全国対象または長野県関連の補助金のみ抽出
                        if is_nagano_related or is_national:
                            # 日付要素を取得
                            date_elem = item.select_one(".m-panel-article__date")
                            date_text = date_elem.text.strip() if date_elem else "日付不明"
                            
                            # リンクを取得
                            link_elem = title_elem.find("a")
                            if link_elem and link_elem.get("href"):
                                link = link_elem.get("href")
                                
                                # 相対URLを絶対URLに変換
                                full_url = urljoin("https://j-net21.smrj.go.jp", link)
                                
                                # 詳細ページから情報を取得
                                grant_details = scrape_grant_details(full_url)
                                
                                grant_info = {
                                    "title": title,
                                    "url": full_url,
                                    "date": date_text,
                                    "description": grant_details.get("description", "詳細は要確認"),
                                    "deadline": grant_details.get("deadline", "要確認"),
                                    "amount": grant_details.get("amount", "要確認"),
                                    "ratio": grant_details.get("ratio", "要確認")
                                }
                                
                                grants.append(grant_info)
                                print(f"抽出: {title}")
            
            # 全国向け一般的な助成金情報も追加
            national_grants = get_national_grants()
            grants.extend(national_grants)
            
            return grants
        else:
            print(f"❌ J-Net21サイトアクセス失敗 (ステータスコード: {response.status_code})")
    except Exception as e:
        print(f"❌ J-Net21サイト処理エラー: {e}")
    
    # エラー時にはバックアップとして国の一般的な助成金情報を返す
    print("⚠️ J-Net21からの取得に失敗。一般的な助成金情報を使用します。")
    return get_national_grants()

def scrape_grant_details(url):
    """補助金の詳細ページから情報を取得する"""
    details = {
        "description": "",
        "deadline": "要確認",
        "amount": "要確認",
        "ratio": "要確認"
    }
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 詳細説明を取得
            content_elem = soup.select_one(".m-article__content")
            if content_elem:
                details["description"] = content_elem.text.strip()[:200] + "..."  # 長すぎる場合は切り詰める
            
            # 締切日を探す
            deadline_patterns = [
                r'締切.*?[：:]\s*(.*?[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)',
                r'申込期限.*?[：:]\s*(.*?[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)', 
                r'募集期間.*?[：:]\s*(.*?まで)',
                r'受付期間.*?[：:]\s*(.*?まで)',
                r'([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日).*(締切|締め切り|〆切)',
                r'([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日.*?まで)'
            ]
            
            text_content = response.text
            for pattern in deadline_patterns:
                match = re.search(pattern, text_content)
                if match:
                    details["deadline"] = match.group(1).strip()
                    break
            
            # 補助金額を探す
            amount_patterns = [
                r'補助額.*?[：:]\s*(.*?円)',
                r'助成額.*?[：:]\s*(.*?円)',
                r'補助金額.*?[：:]\s*(.*?円)',
                r'上限.*?([0-9,]+万円)',
                r'上限額.*?([0-9,]+万円)',
                r'([0-9,]+万円).*?上限'
            ]
            
            for pattern in amount_patterns:
                match = re.search(pattern, text_content)
                if match:
                    details["amount"] = match.group(1).strip()
                    break
            
            # 補助率を探す
            ratio_patterns = [
                r'補助率.*?[：:]\s*(.*?分の.*?)',
                r'助成率.*?[：:]\s*(.*?分の.*?)',
                r'([0-9]/[0-9]以内)',
                r'([0-9]分の[0-9]以内)',
                r'補助率.*(最大[0-9]{1,2}%)'
            ]
            
            for pattern in ratio_patterns:
                match = re.search(pattern, text_content)
                if match:
                    details["ratio"] = match.group(1).strip()
                    break
            
    except Exception as e:
        print(f"❌ 詳細ページの取得エラー: {e}")
    
    return details

def get_national_grants():
    """全国向けの主要助成金情報をWebサイトから動的に取得する"""
    national_grants = []
    
    # IT導入補助金の情報を取得
    try:
        print("🔍 IT導入補助金の情報を取得中...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # IT導入補助金2025の情報を取得
        it_hojo_url = "https://it-shien.smrj.go.jp/schedule/"
        response = requests.get(it_hojo_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # スケジュール情報を取得
            schedule_tables = soup.select(".schedule-table")
            deadlines = []
            
            for table in schedule_tables:
                deadline_rows = table.select("tr")
                for row in deadline_rows:
                    if "締切日" in row.text:
                        deadline_cells = row.select("td")
                        if deadline_cells:
                            deadlines.append(deadline_cells[0].text.strip())
            
            # ニュース情報からも詳細を取得
            news_url = "https://it-shien.smrj.go.jp/news/20287"  # IT導入補助金2025概要ニュース
            news_response = requests.get(news_url, headers=headers, timeout=30)
            
            if news_response.status_code == 200:
                news_soup = BeautifulSoup(news_response.text, "html.parser")
                news_content = news_soup.select_one(".m-article__content")
                
                if news_content:
                    content_text = news_content.text
                    
                    # 通常枠の情報を抽出
                    normal_amount = re.search(r'通常枠.*?([0-9]+万円)', content_text)
                    normal_ratio = re.search(r'通常枠.*?補助率.*?「([^」]+)」', content_text)
                    
                    # セキュリティ枠の情報を抽出
                    security_amount = re.search(r'セキュリティ対策推進枠.*?([0-9]+万円)', content_text)
                    security_ratio = re.search(r'セキュリティ対策推進枠.*?補助率.*?「([^」]+)」', content_text)
                    
                    deadline = deadlines[0] if deadlines else "2025年6月頃（要確認）"
                    
                    # 通常枠の情報を追加
                    national_grants.append({
                        "title": "IT導入補助金2025（通常枠）", 
                        "url": "https://it-shien.smrj.go.jp/", 
                        "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                        "description": "中小企業・小規模事業者向けにITツール導入を支援。業務効率化や売上向上に貢献するITツール導入費用の一部を補助。",
                        "deadline": deadline,
                        "amount": normal_amount.group(1) if normal_amount else "5万円～450万円",
                        "ratio": normal_ratio.group(1) if normal_ratio else "1/2（最低賃金近傍の事業者は2/3）"
                    })
                    
                    # セキュリティ対策推進枠の情報を追加
                    national_grants.append({
                        "title": "IT導入補助金2025（セキュリティ対策推進枠）", 
                        "url": "https://it-shien.smrj.go.jp/security/", 
                        "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                        "description": "サイバーセキュリティ対策強化を目的としたITツール導入を支援。",
                        "deadline": deadline,
                        "amount": security_amount.group(1) if security_amount else "5万円～150万円",
                        "ratio": security_ratio.group(1) if security_ratio else "1/2（小規模事業者は2/3）"
                    })
        
        # 事業再構築補助金の情報を取得
        jigyou_saikouchiku_url = "https://jigyou-saikouchiku.go.jp/"
        response = requests.get(jigyou_saikouchiku_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # ニュース情報からデッドラインを取得
            news_items = soup.select(".news-list li")
            latest_news = ""
            
            for item in news_items:
                if "公募" in item.text and "開始" in item.text:
                    latest_news = item.text.strip()
                    break
            
            # 事業再構築補助金の情報を追加
            national_grants.append({
                "title": "事業再構築補助金（最新公募）", 
                "url": "https://jigyou-saikouchiku.go.jp/", 
                "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                "description": "ポストコロナ・ウィズコロナ時代の経済社会変化に対応するための新分野展開や業態転換等を支援。",
                "deadline": latest_news if latest_news else "最新情報はWebサイトで要確認",
                "amount": "最大1億円（枠によって異なる）",
                "ratio": "1/2～3/4（企業規模や申請枠によって異なる）"
            })
        
        print(f"✅ 全国向け助成金情報取得完了: {len(national_grants)}件")
        
    except Exception as e:
        print(f"❌ 全国向け助成金情報の取得エラー: {e}")
    
    # 取得できた全国向け助成金情報が少ない場合は、最低限のデフォルト情報を追加
    if len(national_grants) < 2:
        print("⚠️ 全国向け助成金情報の取得が不十分なため、基本情報を補完します")
        
        # 最低限のIT導入補助金情報
        if not any("IT導入補助金" in grant["title"] for grant in national_grants):
            national_grants.append({
                "title": "IT導入補助金2025（通常枠）", 
                "url": "https://it-shien.smrj.go.jp/", 
                "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                "description": "中小企業・小規模事業者向けにITツール導入を支援。業務効率化や売上向上に貢献するITツール導入費用の一部を補助。",
                "deadline": "2025年6月頃（詳細はWebサイトで要確認）",
                "amount": "5万円～450万円",
                "ratio": "1/2（最低賃金近傍の事業者は2/3）"
            })
    
    # 長野県の基本助成金情報もWebから取得
    try:
        print("🔍 長野県の助成金情報を取得中...")
        
        # 長野県のWebサイトから情報取得
        nagano_urls = [
            "https://www.pref.nagano.lg.jp/keieishien/corona/kouzou-tenkan.html",  # 長野県プラス補助金
            "https://www.pref.nagano.lg.jp/rodokoyo/seisanseisupport.html"  # 賃上げ・生産性向上サポート補助金
        ]
        
        for url in nagano_urls:
            try:
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # タイトルを取得
                    title_elem = soup.select_one("h1") or soup.select_one("h2")
                    title = title_elem.text.strip() if title_elem else "長野県補助金"
                    
                    # 内容を取得
                    content_elem = soup.select_one("#main-contents") or soup.select_one("#tmp_contents")
                    content_text = content_elem.text if content_elem else ""
                    
                    # 締め切りを検索
                    deadline_patterns = [
                        r'締切.*?[：:]\s*(.*?[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)',
                        r'申込期限.*?[：:]\s*(.*?[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)', 
                        r'募集期間.*?[：:]\s*(.*?まで)',
                        r'受付期間.*?[：:]\s*(.*?まで)',
                        r'([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日).*(締切|締め切り|〆切)'
                    ]
                    
                    deadline = "要確認"
                    for pattern in deadline_patterns:
                        match = re.search(pattern, content_text)
                        if match:
                            deadline = match.group(1).strip()
                            break
                    
                    # 補助金額を検索
                    amount_patterns = [
                        r'補助額.*?[：:]\s*(.*?円)',
                        r'助成額.*?[：:]\s*(.*?円)',
                        r'補助金額.*?[：:]\s*(.*?円)',
                        r'上限.*?([0-9,]+万円)'
                    ]
                    
                    amount = "要確認"
                    for pattern in amount_patterns:
                        match = re.search(pattern, content_text)
                        if match:
                            amount = match.group(1).strip()
                            break
                    
                    # 補助率を検索
                    ratio_patterns = [
                        r'補助率.*?[：:]\s*(.*?分の.*?)',
                        r'助成率.*?[：:]\s*(.*?分の.*?)',
                        r'([0-9]/[0-9]以内)',
                        r'([0-9]分の[0-9]以内)'
                    ]
                    
                    ratio = "要確認"
                    for pattern in ratio_patterns:
                        match = re.search(pattern, content_text)
                        if match:
                            ratio = match.group(1).strip()
                            break
                    
                    # 説明文を生成
                    description = content_text[:200].replace("\n", " ").strip() + "..." if content_text else "長野県の補助金制度"
                    
                    # 助成金情報を追加
                    nagano_grant = {
                        "title": title,
                        "url": url,
                        "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                        "description": description,
                        "deadline": deadline,
                        "amount": amount,
                        "ratio": ratio
                    }
                    
                    # タイトルを整形（長すぎる場合）
                    if len(nagano_grant["title"]) > 50:
                        if "プラス補助金" in nagano_grant["title"]:
                            nagano_grant["title"] = "長野県プラス補助金（中小企業経営構造転換促進事業）"
                        elif "賃上げ" in nagano_grant["title"] or "生産性向上" in nagano_grant["title"]:
                            nagano_grant["title"] = "長野県中小企業賃上げ・生産性向上サポート補助金"
                        else:
                            nagano_grant["title"] = nagano_grant["title"][:50] + "..."
                    
                    national_grants.append(nagano_grant)
            
            except Exception as e:
                print(f"❌ 長野県助成金情報の取得エラー ({url}): {e}")
        
        print(f"✅ 長野県助成金情報取得完了: {len(national_grants)}件")
        
    except Exception as e:
        print(f"❌ 長野県助成金情報の取得エラー: {e}")
    
    return national_grants

def filter_grants_for_target_business(grants, location="長野県塩尻市", industry="情報通信業", employees=56):
    """対象企業に適した助成金情報にフィルタリングする"""
    # 情報通信業向け助成金に関連するキーワード
    it_keywords = ['IT', 'システム', 'デジタル', '情報通信', 'DX', 'セキュリティ', 'アプリ', 'ソフトウェア', 'ICT', 'クラウド', 'AI', 'IoT']
    
    # 業種フィルタリング用クエリの構築
    filter_query = f"""
以下の助成金情報が、{location}の{industry}（従業員{employees}名の中小企業）に適用可能かどうかを判断してください。
適用可能な場合は「はい」、そうでない場合は「いいえ」と回答してください。

{json.dumps(grants, ensure_ascii=False, indent=2)}

回答形式: はい/いいえ
"""
    
    # 一次フィルタリング（プログラム的にフィルタリング）
    filtered_grants = []
    
    for grant in grants:
        # 基本的にすべての全国向け助成金は含める
        include = True
        
        title = grant["title"].lower()
        desc = grant["description"].lower() if "description" in grant else ""
        
        # 特定の地域限定で、かつ対象地域でない場合は除外
        if any(prefecture in title for prefecture in ['北海道', '青森', '岩手', '宮城', '秋田', 
                                                 '山形', '福島', '茨城', '栃木', '群馬', 
                                                 '埼玉', '千葉', '東京', '神奈川', '新潟', 
                                                 '富山', '石川', '福井', '山梨', '岐阜', 
                                                 '静岡', '愛知', '三重', '滋賀', '京都', 
                                                 '大阪', '兵庫', '奈良', '和歌山', '鳥取', 
                                                 '島根', '岡山', '広島', '山口', '徳島', 
                                                 '香川', '愛媛', '高知', '福岡', '佐賀', 
                                                 '長崎', '熊本', '大分', '宮崎', '鹿児島', 
                                                 '沖縄']) and '長野' not in title:
            include = False
        
        # 特定の業種限定で、情報通信業が対象外の場合は除外
        if (('農業' in title or '農林' in title or '漁業' in title) and 
            not any(kw.lower() in title.lower() or kw.lower() in desc.lower() for kw in it_keywords)):
            include = False
        
        if include:
            filtered_grants.append(grant)
    
    print(f"📊 フィルタリング後の助成金件数: {len(filtered_grants)} 件")
    return filtered_grants

def evaluate_grant_with_gpt(title, url, description, deadline, amount, ratio):
    """助成金情報をGPTで評価"""
    prompt = f"""
あなたは企業向け助成金アドバイザーです。
以下の助成金が、長野県塩尻市の情報通信業・従業員56名の中小企業にとって申請対象になるか、また申請優先度（高・中・低）を判定してください。

【助成金名】{title}
【詳細URL】{url}
【概要】{description}
【申請期限】{deadline}
【助成金額】{amount}
【補助割合】{ratio}

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
    
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # 文字化け防止のための前処理
    # 特殊文字や制御文字を除去
    clean_message = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', message)
    
    # シンプルなテキストメッセージ形式
    payload = {"text": f"📢 助成金支援制度評価レポート\n更新日時: {current_time}\n\n{clean_message}"}
    
    try:
        print(f"⏳ Google Chatに送信中... ({webhook_url[:15]}...)")
        encoded_payload = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        response = requests.post(
            webhook_url, 
            headers=headers, 
            data=encoded_payload
        )
        print(f"応答ステータスコード: {response.status_code}")
        print(f"応答本文: {response.text[:100]}")  # 最初の100文字だけ表示
        
        if response.status_code == 200:
            print(f"✅ Google Chatに通知しました。ステータスコード: {response.status_code}")
        else:
            print(f"❌ Google Chat送信エラー: ステータスコード {response.status_code}")
            print(f"応答本文: {response.text}")
    except Exception as e:
        print(f"❌ Google Chat送信エラー: {e}")
        print(f"リクエスト内容: {encoded_payload[:200].decode('utf-8')}...")  # 最初の200文字だけ表示

# --- メイン処理 ---
def main():
    print("✅ 助成金情報取得開始")
    
    # J-Net21から助成金情報を取得
    grants = scrape_jnet21_grants()
    print(f"✅ 助成金情報取得: {len(grants)} 件")
    
    # 対象企業向けのフィルタリング
    grants = filter_grants_for_target_business(grants)
    
    # 取得できた件数が少ない場合はバックアップデータを使用
    if len(grants) < 3:
        print("⚠️ 取得できた助成金情報が少ないため、バックアップデータを使用")
        backup_grants = get_national_grants()
        grants = backup_grants
    
    print(f"✅ 最終助成金件数: {len(grants)} 件")

    # スプレッドシート初期化
    try:
        sheet.clear()
        headers = ["No.", "タイトル", "URL", "申請期限", "助成金額", "補助割合", "対象かどうか", "理由", "申請優先度"]
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
        title = normalize_text(grant["title"])
        url = grant["url"]
        description = normalize_text(grant.get("description", ""))
        deadline = normalize_text(grant.get("deadline", "要確認"))
        amount = normalize_text(grant.get("amount", "要確認"))
        ratio = normalize_text(grant.get("ratio", "要確認"))

        print(f"⏳ {i}件目 評価中...")
        result = evaluate_grant_with_gpt(title, url, description, deadline, amount, ratio)
        print(f"✅ {i}件目 評価完了")

        # GPT回答の分解（正規表現を使って堅牢に）
        target = re.search(r"対象かどうか:?\s*(.+)", result)
        target = normalize_text(target.group(1).strip() if target else "不明")
        
        reason = re.search(r"理由:?\s*(.+)", result)
        reason = normalize_text(reason.group(1).strip() if reason else "不明")
        
        priority = re.search(r"申請優先度:?\s*(.+)", result)
        priority = normalize_text(priority.group(1).strip() if priority else "不明")

        try:
            sheet.append_row([i, title, url, deadline, amount, ratio, target, reason, priority])
            print(f"✅ {i}件目 スプレッドシート書き込み完了")
        except Exception as e:
            print(f"❌ スプレッドシート書き込みエラー: {e}")

        # 各助成金情報をメッセージに追加
        full_message += f"*{i}. {title}*\n"
        full_message += f"・対象: *{target}*\n"
        full_message += f"・優先度: *{priority}*\n"
        full_message += f"・申請期限: {deadline}\n"
        full_message += f"・助成金額: {amount}\n"
        full_message += f"・補助割合: {ratio}\n"
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
