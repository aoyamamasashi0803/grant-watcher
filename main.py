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

# --- ヘルパー関数 ---
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
    
    return text

def generate_simple_title(original_title, index):
    """タイトルが文字化けしているか不適切な場合に、シンプルなタイトルを生成する"""
    # 文字化けや不適切な文字が含まれているかチェック
    if re.search(r'[^\w\s\d\u3000-\u9FFF\u3040-\u309F\u30A0-\u30FF,.?!:;\-()[\]{}「」『』（）［］｛｝、。？！：；]', original_title):
        # 主要なカテゴリに基づいてタイトルを割り当て
        if "IT" in original_title or "導入" in original_title:
            return f"IT導入補助金 (#{index})"
        elif "事業再構築" in original_title or "再構築" in original_title:
            return f"事業再構築補助金 (#{index})"
        elif "長野県" in original_title and "プラス" in original_title:
            return f"長野県プラス補助金 (#{index})"
        elif "長野県" in original_title and ("賃上げ" in original_title or "生産性" in original_title):
            return f"長野県中小企業賃上げ・生産性向上サポート補助金 (#{index})"
        elif "セキュリティ" in original_title:
            return f"IT導入補助金(セキュリティ対策推進枠) (#{index})"
        else:
            return f"助成金情報 (#{index})"
    else:
        # 問題なければそのまま返す
        return original_title

# --- スクレイピング関数 ---
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
                                                                                 '沖縄']) and '長野' not in title
                        
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

# --- 全国向け助成金情報取得関数 ---
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
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
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

# --- 追加情報ソース関数 ---
def scrape_additional_sources():
    """追加の情報ソースから助成金情報を取得する（改善版）"""
    additional_grants = []
    previous_grants = 0
    
    # ミラサポplus（中小企業庁の総合支援サイト）から情報取得
    try:
        print("🔍 ミラサポplusの情報を取得中...")
        mirasapo_url = "https://mirasapo-plus.go.jp/subsidy/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(mirasapo_url, headers=headers, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 補助金・助成金の一覧を取得
            subsidy_items = soup.select(".subsidy-item") or soup.select(".list_subsidy li") or soup.select(".contents-list li")
            
            for item in subsidy_items:
                title_elem = item.select_one(".subsidy-item-title") or item.select_one("h3") or item.select_one("a") or item.select_one(".title")
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                
                # URLを取得
                link_elem = title_elem if title_elem.name == "a" else title_elem.find("a") or item.find("a")
                if not link_elem or not link_elem.get("href"):
                    continue
                    
                url = link_elem.get("href")
                if not url.startswith("http"):
                    url = urljoin("https://mirasapo-plus.go.jp", url)
                
                # 詳細ページの情報を取得してみる
                try:
                    details = scrape_grant_details(url)
                    description = details.get("description", "")
                    deadline = details.get("deadline", "")
                    amount = details.get("amount", "")
                    ratio = details.get("ratio", "")
                except:
                    # 詳細ページの取得に失敗した場合は、リスト内の情報だけで進める
                    description = ""
                    deadline = ""
                    amount = ""
                    ratio = ""
                
                # リスト内の情報を取得（詳細ページの取得に失敗した場合の代替情報）
                if not description:
                    desc_elem = item.select_one(".subsidy-item-description") or item.select_one("p") or item.select_one(".text")
                    if desc_elem:
                        description = desc_elem.text.strip()
                
                # 締め切りを取得
                if not deadline:
                    deadline_elem = item.select_one(".subsidy-item-deadline") or item.select_one(".date") or item.select_one(".period")
                    if deadline_elem:
                        deadline = deadline_elem.text.strip()
                
                # 金額情報を取得
                if not amount:
                    amount_elem = item.select_one(".subsidy-item-amount") or item.select_one(".money") or item.select_one(".price")
                    if amount_elem:
                        amount = amount_elem.text.strip()
                
                # 詳細情報が取得できなかった場合のフォールバック
                if not description:
                    description = f"{title}に関する補助金・助成金制度"
                if not deadline:
                    deadline = "詳細はWebサイトで確認"
                if not amount:
                    amount = "詳細はWebサイトで確認"
                if not ratio:
                    ratio = "詳細はWebサイトで確認"
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": description,
                    "deadline": deadline,
                    "amount": amount,
                    "ratio": ratio
                })
            
            print(f"✅ ミラサポplusから{len(additional_grants)}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ ミラサポplus情報取得エラー: {e}")
    
    # 経済産業省の補助金総合サイトから情報取得 - 改善版
    try:
        print("🔍 経済産業省の補助金情報を取得中...")
        meti_urls = [
            "https://www.meti.go.jp/policy/hojyokin/index.html",
            "https://www.meti.go.jp/information/publicoffer/kobo.html"  # 公募情報のページも追加
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        previous_grants = len(additional_grants)
        
        for meti_url in meti_urls:
            try:
                response = requests.get(meti_url, headers=headers, timeout=30)
                if response.status_code == 200:
                    response.encoding = 'utf-8'  # 経産省サイトは文字コード指定が必要な場合がある
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # 補助金・助成金の一覧を取得（経産省サイトの構造に合わせて調整）
                    subsidy_links = soup.select("a[href*='hojyo']") or soup.select("a[href*='subsidy']") or soup.select("a[href*='kobo']") or soup.select(".subsidy") or soup.select(".news-list a")
                    
                    for link in subsidy_links:
                        title = link.text.strip()
                        if not title or len(title) < 5:  # 短すぎるタイトルは除外
                            continue
                        
                        # 助成金・補助金に関連するキーワードが含まれるものだけを対象にする
                        if not any(keyword in title.lower() for keyword in ['補助', '助成', '支援', '給付', '交付', '公募', '募集']):
                            continue
                        
                        url = link.get("href")
                        if not url:
                            continue
                            
                        if not url.startswith("http"):
                            url = urljoin("https://www.meti.go.jp", url)
                        
                        # 詳細ページの情報を取得してみる
                        try:
                            details = scrape_grant_details(url)
                            description = details.get("description", "")
                            deadline = details.get("deadline", "")
                            amount = details.get("amount", "")
                            ratio = details.get("ratio", "")
                        except:
                            # 詳細ページの取得に失敗した場合
                            description = "経済産業省の助成金・補助金制度"
                            deadline = "詳細はWebサイトで確認"
                            amount = "詳細はWebサイトで確認"
                            ratio = "詳細はWebサイトで確認"
                        
                        # 詳細情報が取得できなかった場合のフォールバック
                        if not description:
                            description = "経済産業省の助成金・補助金制度"
                        if not deadline:
                            deadline = "詳細はWebサイトで確認"
                        if not amount:
                            amount = "詳細はWebサイトで確認"
                        if not ratio:
                            ratio = "詳細はWebサイトで確認"
                        
                        # 助成金情報を追加
                        additional_grants.append({
                            "title": title,
                            "url": url,
                            "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                            "description": description,
                            "deadline": deadline,
                            "amount": amount,
                            "ratio": ratio
                        })
            except Exception as e:
                print(f"❌ 経済産業省情報取得エラー ({meti_url}): {e}")
        
        print(f"✅ 経済産業省から{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ 経済産業省情報取得エラー: {e}")
        
    # GビズIDポータルから助成金情報を取得
    try:
        print("🔍 GビズIDポータルの情報を取得中...")
        gbiz_url = "https://gbiz-id.go.jp/subsidies/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(gbiz_url, headers=headers, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            previous_grants = len(additional_grants)
            
            # 補助金・助成金の一覧を取得
            subsidy_items = soup.select(".subsidy-item") or soup.select(".subsidy-list li") or soup.select("li.subsidy") or soup.select("div.subsidy")
            
            for item in subsidy_items:
                title_elem = item.select_one(".subsidy-title") or item.select_one("h3") or item.select_one("strong") or item.select_one("a")
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                
                # URLを取得
                link_elem = item.select_one("a") or (title_elem if title_elem.name == "a" else None)
                if not link_elem or not link_elem.get("href"):
                    continue
                    
                url = link_elem.get("href")
                if not url.startswith("http"):
                    url = urljoin("https://gbiz-id.go.jp", url)
                
                # 詳細ページの情報を取得してみる
                try:
                    details = scrape_grant_details(url)
                    description = details.get("description", "")
                    deadline = details.get("deadline", "")
                    amount = details.get("amount", "")
                    ratio = details.get("ratio", "")
                except:
                    # 詳細ページの取得に失敗した場合
                    description = ""
                    deadline = ""
                    amount = ""
                    ratio = ""
                
                # リスト内の情報を取得
                if not description:
                    desc_elem = item.select_one(".subsidy-description") or item.select_one("p") or item.select_one(".description")
                    if desc_elem:
                        description = desc_elem.text.strip()
                
                # 締め切りを取得
                if not deadline:
                    deadline_elem = item.select_one(".deadline") or item.select_one(".subsidy-deadline") or item.select_one(".date")
                    if deadline_elem:
                        deadline = deadline_elem.text.strip()
                
                # 金額情報を取得
                if not amount:
                    amount_elem = item.select_one(".subsidy-amount") or item.select_one(".amount")
                    if amount_elem:
                        amount = amount_elem.text.strip()
                
                # 詳細情報が取得できなかった場合のフォールバック
                if not description:
                    description = f"GビズID対応の{title}に関する助成金制度"
                if not deadline:
                    deadline = "詳細はWebサイトで確認"
                if not amount:
                    amount = "詳細はWebサイトで確認"
                if not ratio:
                    ratio = "詳細はWebサイトで確認"
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": description,
                    "deadline": deadline,
                    "amount": amount,
                    "ratio": ratio
                })
            
            print(f"✅ GビズIDポータルから{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ GビズIDポータル情報取得エラー: {e}")
    
    # 長野県中小企業振興センターの情報取得
    try:
        print("🔍 長野県中小企業振興センターの情報を取得中...")
        nagano_center_urls = [
            "https://www.nice-nagano.or.jp/topics/",
            "https://www.nice-nagano.or.jp/business/"  # ビジネス支援情報も追加
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        previous_grants = len(additional_grants)
        
        for nagano_center_url in nagano_center_urls:
            try:
                response = requests.get(nagano_center_url, headers=headers, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # 補助金・助成金の一覧を取得（サイト構造に合わせて調整）
                    subsidy_items = soup.select(".topics-list li") or soup.select(".news-list li") or soup.select("article") or soup.select(".post")
                    
                    for item in subsidy_items:
                        # 補助金・助成金に関連する項目のみを抽出
                        item_text = item.text.lower()
                        if not any(keyword in item_text for keyword in ['補助', '助成', '支援金', '給付金', '助金']):
                            continue
                        
                        title_elem = item.select_one("h3") or item.select_one("h4") or item.select_one("a") or item.select_one("strong") or item.select_one(".title")
                        if not title_elem:
                            continue
                        
                        title = title_elem.text.strip()
                        
                        # URLを取得
                        link_elem = title_elem if title_elem.name == "a" else item.select_one("a")
                        if not link_elem or not link_elem.get("href"):
                            continue
                            
                        url = link_elem.get("href")
                        if not url.startswith("http"):
                            url = urljoin("https://www.nice-nagano.or.jp", url)
                        
                        # 詳細情報を取得
                        description = item.text.strip()
                        if title in description:
                            description = description.replace(title, "").strip()
                        
                        # 日付を抽出
                        date_elem = item.select_one(".date") or item.select_one("time") or item.select_one(".publish-date")
                        date_text = date_elem.text.strip() if date_elem else ""
                        
                        # 締め切りを抽出（詳細ページから取得を試みる）
                        try:
                            details = scrape_grant_details(url)
                            detail_description = details.get("description", "")
                            if detail_description:
                                description = detail_description  # 詳細ページからの説明を使用
                            
                            deadline = details.get("deadline", "")
                            amount = details.get("amount", "")
                            ratio = details.get("ratio", "")
                        except:
                            # 詳細ページの取得に失敗した場合
                            deadline = ""
                            amount = ""
                            ratio = ""
                        
                        # リスト内のテキストから締め切りを探す（詳細ページから取得できなかった場合）
                        if not deadline:
                            deadline_match = re.search(r'([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日).*(締切|締め切り|〆切|まで)', description)
                            if deadline_match:
                                deadline = deadline_match.group(1)
                            else:
                                deadline = "詳細はWebサイトで確認"
                        
                        # 詳細情報が取得できなかった場合のフォールバック
                        if not amount:
                            amount = "詳細はWebサイトで確認"
                        if not ratio:
                            ratio = "詳細はWebサイトで確認"
                        
                        # 助成金情報を追加
                        additional_grants.append({
                            "title": title,
                            "url": url,
                            "date": date_text if date_text else datetime.datetime.now().strftime('%Y年%m月%d日'),
                            "description": description[:200] + "..." if len(description) > 200 else description,
                            "deadline": deadline,
                            "amount": amount,
                            "ratio": ratio
                        })
            except Exception as e:
                print(f"❌ 長野県中小企業振興センター情報取得エラー ({nagano_center_url}): {e}")
        
        print(f"✅ 長野県中小企業振興センターから{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ 長野県中小企業振興センター情報取得エラー: {e}")
    
    # 日本商工会議所の情報取得
    try:
        print("🔍 日本商工会議所の助成金情報を取得中...")
        jcci_urls = [
            "https://www.jcci.or.jp/news/",
            "https://www.jcci.or.jp/sme/"  # 中小企業支援情報も追加
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        previous_grants = len(additional_grants)
        
        for jcci_url in jcci_urls:
            try:
                response = requests.get(jcci_url, headers=headers, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # ニュース一覧から補助金・助成金関連の情報を取得
                    news_items = soup.select(".news-list li") or soup.select(".news-item") or soup.select("article") or soup.select(".post")
                    
                    for item in news_items:
                        # 補助金・助成金に関連する項目のみを抽出
                        item_text = item.text.lower()
                        if not any(keyword in item_text for keyword in ['補助', '助成', '支援金', '給付金', '公募']):
                            continue
                        
                        # タイトルを取得
                        title_elem = item.select_one("h3") or item.select_one("h4") or item.select_one("a") or item.select_one(".title")
                        if not title_elem:
                            continue
                        
                        title = title_elem.text.strip()
                        
                        # URLを取得
                        link_elem = title_elem if title_elem.name == "a" else item.select_one("a")
                        if not link_elem or not link_elem.get("href"):
                            continue
                            
                        url = link_elem.get("href")
                        if not url.startswith("http"):
                            url = urljoin("https://www.jcci.or.jp", url)
                        
                        # 詳細ページから情報を取得
                        try:
                            details = scrape_grant_details(url)
                            description = details.get("description", "")
                            deadline = details.get("deadline", "")
                            amount = details.get("amount", "")
                            ratio = details.get("ratio", "")
                        except:
                            # 詳細ページの取得に失敗した場合
                            description = "日本商工会議所からの情報提供"
                            deadline = "詳細はWebサイトで確認"
                            amount = "詳細はWebサイトで確認"
                            ratio = "詳細はWebサイトで確認"
                        
                        # 詳細情報が取得できなかった場合のフォールバック
                        if not description:
                            description = "日本商工会議所からの情報提供"
                        if not deadline:
                            deadline = "詳細はWebサイトで確認"
                        if not amount:
                            amount = "詳細はWebサイトで確認"
                        if not ratio:
                            ratio = "詳細はWebサイトで確認"
                        
                        # 日付を取得
                        date_elem = item.select_one(".date") or item.select_one("time")
                        date_text = date_elem.text.strip() if date_elem else datetime.datetime.now().strftime('%Y年%m月%d日')
                        
                        # 助成金情報を追加
                        additional_grants.append({
                            "title": title,
                            "url": url,
                            "date": date_text,
                            "description": description,
                            "deadline": deadline,
                            "amount": amount,
                            "ratio": ratio
                        })
            except Exception as e:
                print(f"❌ 日本商工会議所情報取得エラー ({jcci_url}): {e}")
        
        print(f"✅ 日本商工会議所から{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ 日本商工会議所情報取得エラー: {e}")
    
    # ものづくり補助金公式サイトの情報取得
    try:
        print("🔍 ものづくり補助金の情報を取得中...")
        monodukuri_url = "https://portal.monodukuri-hojo.jp/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(monodukuri_url, headers=headers, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            previous_grants = len(additional_grants)
            
            # 公募情報を取得
            info_blocks = soup.select(".info-block") or soup.select(".news-block") or soup.select("article")
            
            if not info_blocks:
                # 公募情報が見つからない場合は、デフォルト情報を追加
                additional_grants.append({
                    "title": "ものづくり・商業・サービス生産性向上促進補助金",
                    "url": "https://portal.monodukuri-hojo.jp/",
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": "中小企業・小規模事業者等が取り組む革新的サービス開発・試作品開発・生産プロセスの改善を行うための設備投資等を支援する補助金制度",
                    "deadline": "詳細はWebサイトで確認",
                    "amount": "最大1,000万円～2,000万円（類型による）",
                    "ratio": "1/2〜2/3（小規模事業者は2/3）"
                })
            else:
                for block in info_blocks:
                    title_elem = block.select_one("h3") or block.select_one("h4") or block.select_one(".title")
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    if "公募" in title or "募集" in title or "申請" in title:
                        # 公募に関する情報を抽出
                        description = block.text.strip()
                        if title in description:
                            description = description.replace(title, "").strip()
                        
                        # リンクを取得
                        link_elem = block.select_one("a")
                        if link_elem and link_elem.get("href"):
                            url = link_elem.get("href")
                            if not url.startswith("http"):
                                url = urljoin("https://portal.monodukuri-hojo.jp/", url)
                        else:
                            url = "https://portal.monodukuri-hojo.jp/"
                        
                        # 締め切りを抽出
                        deadline_match = re.search(r'([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日).*(締切|締め切り|〆切|まで)', description)
                        deadline = deadline_match.group(1) if deadline_match else "詳細はWebサイトで確認"
                        
                        # 助成金情報を追加
                        additional_grants.append({
                            "title": "ものづくり・商業・サービス生産性向上促進補助金（" + title + "）",
                            "url": url,
                            "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                            "description": description[:200] + "..." if len(description) > 200 else description,
                            "deadline": deadline,
                            "amount": "最大1,000万円～2,000万円（類型による）",
                            "ratio": "1/2〜2/3（小規模事業者は2/3）"
                        })
            
            print(f"✅ ものづくり補助金から{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ ものづくり補助金情報取得エラー: {e}")
    
    # 重複を排除して返す
    unique_grants = []
    urls = set()
    titles = set()
    
    for grant in additional_grants:
        # URLとタイトルの両方が重複していない場合のみ追加
        url_key = grant["url"].split("?")[0]  # クエリパラメータを除外
        title_key = normalize_text(grant["title"])
        
        if url_key not in urls and title_key not in titles:
            urls.add(url_key)
            titles.add(title_key)
            unique_grants.append(grant)
    
    print(f"✅ 追加情報ソースから合計{len(unique_grants)}件の助成金情報を取得しました")
    return unique_grants

# --- フィルタリングとGPT評価関数 ---
def filter_grants_for_target_business(grants, location="長野県塩尻市", industry="情報通信業", employees=56):
    """対象企業に適した助成金情報にフィルタリングする（改善版）"""
    # 情報通信業向け助成金に関連するキーワード
    it_keywords = ['IT', 'システム', 'デジタル', '情報通信', 'DX', 'セキュリティ', 'アプリ', 'ソフトウェア', 
                  'ICT', 'クラウド', 'AI', 'IoT', '技術', 'テクノロジー', 'オンライン', 'データ']
    
    # 一次フィルタリング（プログラム的にフィルタリング）
    filtered_grants = []
    
    for grant in grants:
        # 基本的にすべての全国向け助成金は含める
        include = True
        
        title = grant["title"].lower()
        desc = grant.get("description", "").lower()
        
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
                                               '沖縄']) and not any(keyword in title for keyword in ['長野', '全国', '全て', 'すべて']):
            include = False
        
        # 特定の業種限定で、情報通信業が対象外の場合は除外
        # 例：農業、漁業のみ対象で、かつIT関連のキーワードが含まれていない場合
        if (('農業' in title or '農林' in title or '漁業' in title or '林業' in title) and 
            not any(kw.lower() in title.lower() or kw.lower() in desc.lower() for kw in it_keywords)):
            include = False
        
        # 明示的に除外されるキーワード
        exclude_keywords = ['終了しました', '募集終了', '受付終了', '募集は締め切りました']
        if any(exclude_kw in title or exclude_kw in desc for exclude_kw in exclude_keywords):
            include = False
        
        # 地域や業種に関わらず、IT系のキーワードが含まれている場合は含める
        if any(kw.lower() in title.lower() or kw.lower() in desc.lower() for kw in it_keywords):
            include = True
        
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

# --- Google Chat通知関数 ---
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
    
    # メッセージを短くまとめる
    summarized_message = f"📢 助成金支援制度評価レポート\n更新日時: {current_time}\n\n"
    
    # メッセージを行ごとに分割
    lines = message.strip().split('\n\n')
    grant_count = 0
    
    for i, grant_block in enumerate(lines):
        if not grant_block.strip():
            continue
            
        grant_count += 1
        # 助成金ブロックの行を分割
        block_lines = grant_block.split('\n')
        if len(block_lines) < 2:
            continue
        
        # タイトル行を抽出・処理（最初の行）
        title_line = block_lines[0].replace('*', '')
        # タイトルの番号を取得
        title_num = re.search(r'^([0-9]+)\.', title_line)
        title_num = title_num.group(1) if title_num else str(grant_count)
        
        # タイトルテキストを抽出（番号の後の部分）
        title_text = re.sub(r'^[0-9]+\.\s*', '', title_line).strip()
        
        # 文字化けしているタイトルを修正
        safe_title = generate_simple_title(title_text, title_num)
        
        # 対象と優先度行を抽出（通常2行目と3行目）
        target_line = next((line for line in block_lines if '・対象:' in line), "・対象: 不明")
        priority_line = next((line for line in block_lines if '・優先度:' in line), "・優先度: 不明")
        deadline_line = next((line for line in block_lines if '・申請期限:' in line), "・申請期限: 要確認")
        amount_line = next((line for line in block_lines if '・助成金額:' in line), "・助成金額: 要確認")
        ratio_line = next((line for line in block_lines if '・補助割合:' in line), "・補助割合: 要確認")
        
        # URL行を抽出（通常最後の行）
        url_line = next((line for line in block_lines if '・URL:' in line), "")
        
        # 簡潔なメッセージに整形
        summarized_message += f"{title_num}. {safe_title}\n{target_line}\n{priority_line}\n{deadline_line}\n{amount_line}\n{ratio_line}\n{url_line}\n\n"
    
    # ペイロードの作成
    payload = {"text": summarized_message}
    
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
        print(f"リクエスト内容: {encoded_payload[:200].decode('utf-8')}...")

# --- メイン処理 ---
def main():
    print("✅ 助成金情報取得開始")
    
    # J-Net21から助成金情報を取得
    grants = scrape_jnet21_grants()
    print(f"✅ J-Net21から助成金情報取得: {len(grants)} 件")
    
    # 追加情報ソースから助成金情報を取得（改善版関数を使用）
    additional_grants = scrape_additional_sources()
    print(f"✅ 追加情報ソースから助成金情報取得: {len(additional_grants)} 件")
    
    # 助成金情報をマージ
    grants.extend(additional_grants)
    
    # URLベースで重複を排除
    unique_grants = []
    urls = set()
    titles = set()
    
    for grant in grants:
        # URLとタイトルの両方が重複していない場合のみ追加
        url_key = grant["url"].split("?")[0]  # クエリパラメータを除外
        title_key = normalize_text(grant["title"])
        
        if url_key not in urls and title_key not in titles:
            urls.add(url_key)
            titles.add(title_key)
            unique_grants.append(grant)
    
    grants = unique_grants
    print(f"✅ 重複排除後の助成金件数: {len(grants)} 件")
    
    # 対象企業向けのフィルタリング（改善版関数を使用）
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
        # タイトルの文字化けチェックと修正
        title = normalize_text(grant["title"])
        # 必要に応じてシンプルなタイトルに置き換え
        title = generate_simple_title(title, i)
        
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
        full_message += f"・助成金額: {amount}\n"  # 助成金額も表示
        full_message += f"・補助割合: {ratio}\n"   # 補助割合も表示
        # 長すぎる説明文は簡潔にする
        short_reason = reason[:100] + "..." if len(reason) > 100 else reason
        full_message += f"・理由: {short_reason}\n"
        full_message += f"・URL: {url}\n\n"

    # メッセージが空でないことを確認してから送信
    if full_message:
        send_to_google_chat(full_message, WEBHOOK_URL)
    else:
        print("❌ 送信するメッセージがありません")
        send_to_google_chat("助成金情報の評価結果はありませんでした。", WEBHOOK_URL)

if __name__ == "__main__":
    main()
