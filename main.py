# --- フィルタリングとGPT評価関数 ---
def filter_grants_for_target_business(grants, location="長野県塩尻市", industry="情報通信業", employees=56):
    """対象企業に適した助成金情報にフィルタリングする"""
    # 情報通信業向け助成金に関連するキーワード
    it_keywords = ['IT', 'システム', 'デジタル', '情報通信', 'DX', 'セキュリティ', 'アプリ', 'ソフトウェア', 'ICT', 'クラウド', 'AI', 'IoT']
    
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
        return f"❌ GPT評価エラー: {str(e)}"# --- 追加情報ソース関数 ---
def scrape_additional_sources():
    """追加の情報ソースから助成金情報を取得する"""
    additional_grants = []
    
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
            subsidy_items = soup.select(".subsidy-item")
            
            for item in subsidy_items:
                title_elem = item.select_one(".subsidy-item-title")
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                
                # URLを取得
                link_elem = title_elem.find("a")
                if not link_elem or not link_elem.get("href"):
                    continue
                    
                url = link_elem.get("href")
                if not url.startswith("http"):
                    url = urljoin("https://mirasapo-plus.go.jp", url)
                
                # 詳細情報を取得
                description = ""
                desc_elem = item.select_one(".subsidy-item-description")
                if desc_elem:
                    description = desc_elem.text.strip()
                
                # 締め切りを取得
                deadline = "要確認"
                deadline_elem = item.select_one(".subsidy-item-deadline")
                if deadline_elem:
                    deadline = deadline_elem.text.strip()
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": description,
                    "deadline": deadline,
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ ミラサポplusから{len(additional_grants)}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ ミラサポplus情報取得エラー: {e}")
    
    # 経済産業省の補助金総合サイトから情報取得
    try:
        print("🔍 経済産業省の補助金情報を取得中...")
        meti_url = "https://www.meti.go.jp/policy/hojyokin/index.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(meti_url, headers=headers, timeout=30)
        if response.status_code == 200:
            response.encoding = 'utf-8'  # 経産省サイトは文字コード指定が必要な場合がある
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 補助金・助成金の一覧を取得（経産省サイトの構造に合わせて調整）
            subsidy_links = soup.select("a[href*='hojyo']") or soup.select("a[href*='subsidy']") or soup.select(".subsidy")
            previous_grants = len(additional_grants)
            
            for link in subsidy_links:
                title = link.text.strip()
                if not title or len(title) < 5:  # 短すぎるタイトルは除外
                    continue
                
                url = link.get("href")
                if not url:
                    continue
                    
                if not url.startswith("http"):
                    url = urljoin("https://www.meti.go.jp", url)
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": "経済産業省の助成金・補助金制度",
                    "deadline": "詳細はWebサイトで確認",
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
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
            subsidy_items = soup.select(".subsidy-item") or soup.select(".subsidy-list li")
            
            for item in subsidy_items:
                title_elem = item.select_one(".subsidy-title") or item.select_one("h3") or item.select_one("strong")
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                
                # URLを取得
                link_elem = item.select_one("a")
                if not link_elem or not link_elem.get("href"):
                    continue
                    
                url = link_elem.get("href")
                if not url.startswith("http"):
                    url = urljoin("https://gbiz-id.go.jp", url)
                
                # 詳細情報を取得
                description = ""
                desc_elem = item.select_one(".subsidy-description") or item.select_one("p")
                if desc_elem:
                    description = desc_elem.text.strip()
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": description,
                    "deadline": "詳細はWebサイトで確認",
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ GビズIDポータルから{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ GビズIDポータル情報取得エラー: {e}")
    
    # 長野県中小企業振興センターの情報取得
    try:
        print("🔍 長野県中小企業振興センターの情報を取得中...")
        nagano_center_url = "https://www.nice-nagano.or.jp/topics/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(nagano_center_url, headers=headers, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            previous_grants = len(additional_grants)
            
            # 補助金・助成金の一覧を取得（サイト構造に合わせて調整）
            subsidy_items = soup.select(".topics-list li") or soup.select(".news-list li")
            
            for item in subsidy_items:
                # 補助金・助成金に関連する項目のみを抽出
                item_text = item.text.lower()
                if not any(keyword in item_text for keyword in ['補助', '助成', '支援金', '給付金']):
                    continue
                
                title_elem = item.select_one("h3") or item.select_one("h4") or item.select_one("a") or item.select_one("strong")
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
                date_elem = item.select_one(".date") or item.select_one("time")
                date_text = date_elem.text.strip() if date_elem else ""
                
                # 締め切りを抽出
                deadline_match = re.search(r'([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日).*(締切|締め切り|〆切)', description)
                deadline = deadline_match.group(1) if deadline_match else "詳細はWebサイトで確認"
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": date_text if date_text else datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": description[:200] + "..." if len(description) > 200 else description,
                    "deadline": deadline,
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ 長野県中小企業振興センターから{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ 長野県中小企業振興センター情報取得エラー: {e}")
    
    # 日本商工会議所の情報取得
    try:
        print("🔍 日本商工会議所の助成金情報を取得中...")
        jcci_url = "https://www.jcci.or.jp/news/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(jcci_url, headers=headers, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            previous_grants = len(additional_grants)
            
            # ニュース一覧から補助金・助成金関連の情報を取得
            news_items = soup.select(".news-list li") or soup.select(".news-item")
            
            for item in news_items:
                # 補助金・助成金に関連する項目のみを抽出
                item_text = item.text.lower()
                if not any(keyword in item_text for keyword in ['補助', '助成', '支援金', '給付金']):
                    continue
                
                # タイトルを取得
                title_elem = item.select_one("h3") or item.select_one("h4") or item.select_one("a")
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
                
                # 日付を取得
                date_elem = item.select_one(".date") or item.select_one("time")
                date_text = date_elem.text.strip() if date_elem else datetime.datetime.now().strftime('%Y年%m月%d日')
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": date_text,
                    "description": "日本商工会議所からの情報提供",
                    "deadline": "詳細はWebサイトで確認",
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ 日本商工会議所から{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ 日本商工会議所情報取得エラー: {e}")
    
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
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": description,
                    "deadline": deadline,
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ ミラサポplusから{len(additional_grants)}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ ミラサポplus情報取得エラー: {e}")
    
    # 経済産業省の補助金総合サイトから情報取得
    try:
        print("🔍 経済産業省の補助金情報を取得中...")
        meti_url = "https://www.meti.go.jp/policy/hojyokin/index.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(meti_url, headers=headers, timeout=30)
        if response.status_code == 200:
            response.encoding = 'utf-8'  # 経産省サイトは文字コード指定が必要な場合がある
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 補助金・助成金の一覧を取得（経産省サイトの構造に合わせて調整）
            subsidy_links = soup.select("a[href*='hojyo']") or soup.select("a[href*='subsidy']") or soup.select(".subsidy")
            previous_grants = len(additional_grants)
            
            for link in subsidy_links:
                title = link.text.strip()
                if not title or len(title) < 5:  # 短すぎるタイトルは除外
                    continue
                
                url = link.get("href")
                if not url:
                    continue
                    
                if not url.startswith("http"):
                    url = urljoin("https://www.meti.go.jp", url)
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": "経済産業省の助成金・補助金制度",
                    "deadline": "詳細はWebサイトで確認",
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
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
            subsidy_items = soup.select(".subsidy-item") or soup.select(".subsidy-list li")
            
            for item in subsidy_items:
                title_elem = item.select_one(".subsidy-title") or item.select_one("h3") or item.select_one("strong")
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                
                # URLを取得
                link_elem = item.select_one("a")
                if not link_elem or not link_elem.get("href"):
                    continue
                    
                url = link_elem.get("href")
                if not url.startswith("http"):
                    url = urljoin("https://gbiz-id.go.jp", url)
                
                # 詳細情報を取得
                description = ""
                desc_elem = item.select_one(".subsidy-description") or item.select_one("p")
                if desc_elem:
                    description = desc_elem.text.strip()
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": description,
                    "deadline": "詳細はWebサイトで確認",
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ GビズIDポータルから{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ GビズIDポータル情報取得エラー: {e}")
    
    # 長野県中小企業振興センターの情報取得
    try:
        print("🔍 長野県中小企業振興センターの情報を取得中...")
        nagano_center_url = "https://www.nice-nagano.or.jp/topics/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(nagano_center_url, headers=headers, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            previous_grants = len(additional_grants)
            
            # 補助金・助成金の一覧を取得（サイト構造に合わせて調整）
            subsidy_items = soup.select(".topics-list li") or soup.select(".news-list li")
            
            for item in subsidy_items:
                # 補助金・助成金に関連する項目のみを抽出
                item_text = item.text.lower()
                if not any(keyword in item_text for keyword in ['補助', '助成', '支援金', '給付金']):
                    continue
                
                title_elem = item.select_one("h3") or item.select_one("h4") or item.select_one("a") or item.select_one("strong")
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
                date_elem = item.select_one(".date") or item.select_one("time")
                date_text = date_elem.text.strip() if date_elem else ""
                
                # 締め切りを抽出
                deadline_match = re.search(r'([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日).*(締切|締め切り|〆切)', description)
                deadline = deadline_match.group(1) if deadline_match else "詳細はWebサイトで確認"
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": date_text if date_text else datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": description[:200] + "..." if len(description) > 200 else description,
                    "deadline": deadline,
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ 長野県中小企業振興センターから{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ 長野県中小企業振興センター情報取得エラー: {e}")
    
    # 日本商工会議所の情報取得
    try:
        print("🔍 日本商工会議所の助成金情報を取得中...")
        jcci_url = "https://www.jcci.or.jp/news/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(jcci_url, headers=headers, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            previous_grants = len(additional_grants)
            
            # ニュース一覧から補助金・助成金関連の情報を取得
            news_items = soup.select(".news-list li") or soup.select(".news-item")
            
            for item in news_items:
                # 補助金・助成金に関連する項目のみを抽出
                item_text = item.text.lower()
                if not any(keyword in item_text for keyword in ['補助', '助成', '支援金', '給付金']):
                    continue
                
                # タイトルを取得
                title_elem = item.select_one("h3") or item.select_one("h4") or item.select_one("a")
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
                
                # 日付を取得
                date_elem = item.select_one(".date") or item.select_one("time")
                date_text = date_elem.text.strip() if date_elem else datetime.datetime.now().strftime('%Y年%m月%d日')
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": date_text,
                    "description": "日本商工会議所からの情報提供",
                    "deadline": "詳細はWebサイトで確認",
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ 日本商工会議所から{len(additional_grants) - previous_grants}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ 日本商工会議所情報取得エラー: {e}")
    
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
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ ミラサポplusから{len(additional_grants)}件の助成金情報を取得しました")
    except Exception as e:
        print(f"❌ ミラサポplus情報取得エラー: {e}")
    
    # 経済産業省の補助金総合サイトから情報取得
    try:
        print("🔍 経済産業省の補助金情報を取得中...")
        meti_url = "https://www.meti.go.jp/policy/hojyokin/index.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(meti_url, headers=headers, timeout=30)
        if response.status_code == 200:
            response.encoding = 'utf-8'  # 経産省サイトは文字コード指定が必要な場合がある
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 補助金・助成金の一覧を取得（経産省サイトの構造に合わせて調整）
            subsidy_links = soup.select("a[href*='hojyo']")
            
            for link in subsidy_links:
                title = link.text.strip()
                if not title or len(title) < 5:  # 短すぎるタイトルは除外
                    continue
                
                url = link.get("href")
                if not url:
                    continue
                    
                if not url.startswith("http"):
                    url = urljoin("https://www.meti.go.jp", url)
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": "経済産業省の助成金・補助金制度",
                    "deadline": "詳細はWebサイトで確認",
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ 経済産業省から{len(additional_grants) - len(previous_grants)}件の助成金情報を取得しました")
            previous_grants = len(additional_grants)
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
            
            # 補助金・助成金の一覧を取得
            subsidy_items = soup.select(".subsidy-item")
            
            for item in subsidy_items:
                title_elem = item.select_one(".subsidy-title")
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                
                # URLを取得
                link_elem = item.select_one("a")
                if not link_elem or not link_elem.get("href"):
                    continue
                    
                url = link_elem.get("href")
                if not url.startswith("http"):
                    url = urljoin("https://gbiz-id.go.jp", url)
                
                # 詳細情報を取得
                description = ""
                desc_elem = item.select_one(".subsidy-description")
                if desc_elem:
                    description = desc_elem.text.strip()
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": description,
                    "deadline": "詳細はWebサイトで確認",
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ GビズIDポータルから{len(additional_grants) - len(previous_grants)}件の助成金情報を取得しました")
            previous_grants = len(additional_grants)
    except Exception as e:
        print(f"❌ GビズIDポータル情報取得エラー: {e}")
    
    # 長野県中小企業振興センターの情報取得
    try:
        print("🔍 長野県中小企業振興センターの情報を取得中...")
        nagano_center_url = "https://www.nice-nagano.or.jp/subsidy/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(nagano_center_url, headers=headers, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 補助金・助成金の一覧を取得（サイト構造に合わせて調整）
            subsidy_items = soup.select(".subsidy-list li") or soup.select(".subsidy-info")
            
            for item in subsidy_items:
                title_elem = item.select_one("h3") or item.select_one("h4") or item.select_one("strong")
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                
                # URLを取得
                link_elem = item.select_one("a")
                if not link_elem or not link_elem.get("href"):
                    continue
                    
                url = link_elem.get("href")
                if not url.startswith("http"):
                    url = urljoin("https://www.nice-nagano.or.jp", url)
                
                # 詳細情報を取得
                description = item.text.strip()
                if title in description:
                    description = description.replace(title, "").strip()
                
                # 締め切りを抽出
                deadline_match = re.search(r'([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日).*(締切|締め切り|〆切)', description)
                deadline = deadline_match.group(1) if deadline_match else "詳細はWebサイトで確認"
                
                # 助成金情報を追加
                additional_grants.append({
                    "title": title,
                    "url": url,
                    "date": datetime.datetime.now().strftime('%Y年%m月%d日'),
                    "description": description[:200] + "..." if len(description) > 200 else description,
                    "deadline": deadline,
                    "amount": "詳細はWebサイトで確認",
                    "ratio": "詳細はWebサイトで確認"
                })
            
            print(f"✅ 長野県中小企業振興センターから{len(additional_grants) - len(previous_grants)}件の助成金情報を取得しました")
            previous_grants = len(additional_grants)
    except Exception as e:
        print(f"❌ 長野県中小企業振興センター情報取得エラー: {e}")
    
    # 重複を排除して返す
    unique_grants = []
    urls = set()
    
    for grant in additional_grants:
        if grant["url"] not in urls:
            urls.add(grant["url"])
            unique_grants.append(grant)
    
    print(f"✅ 追加情報ソースから合計{len(unique_grants)}件の助成金情報を取得しました")
    return unique_grants

# --- メイン関数の修正 ---
def main():
    print("✅ 助成金情報取得開始")
    
    # J-Net21から助成金情報を取得
    grants = scrape_jnet21_grants()
    print(f"✅ J-Net21から助成金情報取得: {len(grants)} 件")
    
    # 追加情報ソースから助成金情報を取得
    additional_grants = scrape_additional_sources()
    print(f"✅ 追加情報ソースから助成金情報取得: {len(additional_grants)} 件")
    
    # 助成金情報をマージ
    grants.extend(additional_grants)
    
    # URLベースで重複を排除
    unique_grants = []
    urls = set()
    
    for grant in grants:
        if grant["url"] not in urls:
            urls.add(grant["url"])
            unique_grants.append(grant)
    
    grants = unique_grants
    print(f"✅ 重複排除後の助成金件数: {len(grants)} 件")
    
    # 対象企業向けのフィルタリング
    grants = filter_grants_for_target_business(grants)
    
    # 取得できた件数が少ない場合はバックアップデータを使用
    if len(grants) < 3:
        print("⚠️ 取得できた助成金情報が少ないため、バックアップデータを使用")
        backup_grants = get_national_grants()
        grants = backup_grants
    
    print(f"✅ 最終助成金件数: {len(grants)} 件")

    # 以下は既存のコードと同じ...
