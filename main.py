import os
import requests
import time
import urllib3
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# 🛑 1. 系統設定區
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Connection': 'keep-alive'
})

# 🛑 2. 監控目標清單
TARGETS = [
    # --- 🔥 2026 1月生效 ---
    {"id": "6894", "name": "衛司特",   "date": "2026-01-13", "strategy": "STD", "threshold": 50},
    {"id": "6913", "name": "鴻呈",     "date": "2026-01-13", "strategy": "STD", "threshold": 100},
    {"id": "2324", "name": "仁寶",     "date": "2026-01-12", "strategy": "ECB", "threshold": 1000},
    {"id": "3587", "name": "閎康",     "date": "2026-01-12", "strategy": "STD", "threshold": 150},
    {"id": "6515", "name": "穎崴",     "date": "2026-01-09", "strategy": "STD", "threshold": 50},
    {"id": "2329", "name": "華泰",     "date": "2026-01-09", "strategy": "STD", "threshold": 500},
    {"id": "4923", "name": "力士",     "date": "2026-01-09", "strategy": "STD", "threshold": 100},

    # --- 1月初生效 ---
    {"id": "2376", "name": "技嘉",     "date": "2026-01-02", "strategy": "ECB", "threshold": 500},
    {"id": "2455", "name": "全新",     "date": "2026-01-02", "strategy": "STD", "threshold": 200},
    {"id": "4714", "name": "永捷",     "date": "2026-01-16", "strategy": "STD", "threshold": 100},
    {"id": "6101", "name": "寬魚國際", "date": "2026-01-07", "strategy": "ENT", "threshold": 100}, 
    {"id": "2745", "name": "五福",     "date": "2026-01-10", "strategy": "PRICED", "threshold": 100}, 

    # --- 2025 12月底衝刺 ---
    {"id": "2233", "name": "宇隆",     "date": "2025-12-31", "strategy": "STD", "threshold": 150},
    {"id": "6672", "name": "F-騰輝",   "date": "2025-12-30", "strategy": "STD", "threshold": 100},
    {"id": "6603", "name": "富強鑫",   "date": "2025-12-29", "strategy": "STD", "threshold": 100},
    {"id": "8210", "name": "勤誠",     "date": "2025-12-26", "strategy": "STD", "threshold": 300},
    {"id": "3706", "name": "神達",     "date": "2025-12-23", "strategy": "ECB", "threshold": 1000},
]

def send_discord(title, msg, color=0x00ff00):
    if not DISCORD_WEBHOOK_URL: return
    data = {"username": "CB 戰情室 (V10.5)", "embeds": [{"title": title, "description": msg, "color": color, "timestamp": datetime.now().isoformat()}]}
    try: session.post(DISCORD_WEBHOOK_URL, json=data, verify=False)
    except: pass

def get_tw_time():
    utc_now = datetime.now(timezone.utc)
    return utc_now.astimezone(timezone(timedelta(hours=8)))

def get_target_date():
    now = get_tw_time()
    if now.hour < 15: 
        target = now - timedelta(days=1)
        print(f"🕒 台灣時間 {now.strftime('%H:%M')} (盤中)，自動抓取【昨天 {target.strftime('%Y-%m-%d')}】資料")
        return target
    else: 
        print(f"🕒 台灣時間 {now.strftime('%H:%M')} (盤後)，抓取【今天 {now.strftime('%Y-%m-%d')}】資料")
        return now

def get_battle_phase(eff_date):
    eff_dt = datetime.strptime(eff_date, "%Y-%m-%d").replace(tzinfo=timezone(timedelta(hours=8)))
    today = get_tw_time()
    days_diff = (eff_dt.date() - today.date()).days
    if days_diff > 0: return "PHASE_1", f"⏳ **倒數 {days_diff} 天**"
    elif days_diff == 0: return "PHASE_2", f"🔥 **D-Day：今日生效！**"
    else: return "PHASE_3", f"🚀 **後續追蹤：第 {abs(days_diff)} 天**"

# 1. MIS 查價 (打底用)
def fetch_mis_prices(targets):
    print(f"   ⚡ 啟動 MIS 即時查價 (確保有資料)...")
    price_map = {}
    chunk_size = 20
    all_queries = []
    temp_q = []
    for t in targets:
        temp_q.append(f"tse_{t['id']}.tw"); temp_q.append(f"otc_{t['id']}.tw")
        if len(temp_q) >= chunk_size: all_queries.append("|".join(temp_q)); temp_q = []
    if temp_q: all_queries.append("|".join(temp_q))
    ts = int(time.time() * 1000)
    for q_str in all_queries:
        try:
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={q_str}&json=1&delay=0&_={ts}"
            res = session.get(url, verify=False)
            js = res.json()
            if 'msgArray' in js:
                for row in js['msgArray']:
                    sid = row['c']
                    price_str = row.get('z', '-'); y_str = row.get('y', '-'); vol_str = row.get('v', '0')
                    if price_str == '-': price_val = float(y_str); change_val = 0.0; pct = 0.0
                    else: price_val = float(price_str); last_close = float(y_str); change_val = price_val - last_close; pct = (change_val / last_close) * 100
                    price_map[sid] = {'close': price_val, 'change': change_val, 'pct': pct, 'vol': vol_str, 'src': 'MIS'}
        except: pass
    return price_map

# 2. 官方表查價 (覆蓋用)
def fetch_official_close_prices(target_date):
    print(f"   📜 啟動 官方結算報價 (嘗試覆蓋)...")
    price_map = {}
    date_str = target_date.strftime("%Y%m%d"); ts = int(time.time())
    
    # TWSE
    try:
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_str}&type=ALLBUT0999&response=json&_={ts}"
        res = session.get(url, verify=False); js = res.json()
        if js['stat'] == 'OK':
            target_table = None
            for table in js.get('tables', []):
                if "收盤價" in table.get('fields', []): target_table = table; break
            if target_table:
                for row in target_table['data']:
                    sid = row[0]
                    if len(sid) > 4: continue
                    try:
                        close = float(row[8].replace(',', ''))
                        sign = 1.0 if "red" in row[9] else (-1.0 if "green" in row[9] else 0.0)
                        if "-" in row[9]: sign = -1.0 
                        diff = float(row[10].replace(',', '')) * sign
                        vol = int(row[2].replace(',', '')) // 1000 
                        prev = close - diff; pct = (diff / prev) * 100 if prev != 0 else 0.0
                        price_map[sid] = {'close': close, 'change': diff, 'pct': pct, 'vol': vol, 'src': 'TWSE'}
                    except: pass
    except: pass
    
    # TPEX
    try:
        date_str_ro = f"{target_date.year-1911}/{target_date.month:02d}/{target_date.day:02d}"
        headers = session.headers.copy(); headers['Referer'] = 'https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote.php'
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&d={date_str_ro}&o=json&_={ts}"
        res = session.get(url, headers=headers, verify=False); js = res.json()
        if 'aaData' in js:
            for row in js['aaData']:
                sid = row[0]
                if len(sid) > 4: continue
                try:
                    close = float(row[2].replace(',', '')); diff = float(row[3].replace(',', ''))
                    vol = int(row[8].replace(',', '')) // 1000
                    prev = close - diff; pct = (diff / prev) * 100 if prev != 0 else 0.0
                    price_map[sid] = {'close': close, 'change': diff, 'pct': pct, 'vol': vol, 'src': 'TPEX'}
                except: pass
    except: pass
    return price_map

# ✅ V10.5 核心修復：混合校正策略
def get_best_prices(targets, target_date):
    # 1. 不管怎樣，先抓 MIS (保證五福一定有資料，至少是 105.5)
    mis_prices = fetch_mis_prices(targets)
    
    # 2. 如果是盤後，嘗試抓官方表來"覆蓋"
    if get_tw_time().hour >= 15:
        official_prices = fetch_official_close_prices(target_date)
        if official_prices:
            print(f"   ✨ 取得官方報價 {len(official_prices)} 筆，進行校正覆蓋...")
            # 用官方資料更新 MIS 資料 (如果官方表只有 TWSE，那 TPEX 的五福會保留 MIS 的值，不會消失)
            mis_prices.update(official_prices)
        else:
            print("   ⚠️ 官方表尚未產出或連線失敗，維持使用 MIS。")
            
    return mis_prices

def check_material_info(sid, sname):
    found_news = []
    try:
        tw_year = str(get_tw_time().year - 1911)
        url = "https://mops.twse.com.tw/mops/web/ajax_t05st01"
        payload = {'encodeURIComponent': '1', 'step': '1', 'firstin': '1', 'off': '1', 'queryName': 'co_id', 'inpuType': 'co_id', 'TYPEK': 'all', 'co_id': sid, 'year': tw_year}
        res = session.post(url, data=payload, verify=False)
        res.encoding = 'utf8'
        soup = BeautifulSoup(res.text, 'html.parser')
        keywords = ["轉換價格", "訂價", "競價拍賣", "生效", "上櫃", "掛牌", "海外", "Euro", "擔保"]
        for row in soup.find_all('tr'):
            text = row.text.strip()
            if any(k in text for k in keywords): clean_text = " ".join(text.split()); found_news.append(clean_text[:80] + "..."); break 
    except: pass
    return found_news

def fetch_all_chips(target_date):
    all_data = {}
    date_str = target_date.strftime("%Y%m%d"); ts = int(time.time())
    try:
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json&_={ts}"
        res = session.get(url, verify=False); js = res.json()
        if js['stat'] == 'OK':
            for row in js['data']:
                try:
                    sid = "".join(row[0].split()); f_net = int(row[4].replace(',', '')) // 1000; t_net = int(row[10].replace(',', '')) // 1000
                    all_data[sid] = {'foreign': f_net, 'trust': t_net}
                except: pass
    except: pass
    try:
        if 'tpex_visited' not in session.cookies: session.get("https://www.tpex.org.tw/web/", verify=False); session.cookies.set('tpex_visited', 'true')
        date_str_ro = f"{target_date.year-1911}/{target_date.month:02d}/{target_date.day:02d}"
        url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&t=D&d={date_str_ro}&_={ts}"
        res = session.get(url, verify=False); js = res.json()
        data_list = []
        if 'tables' in js and len(js['tables']) > 0: data_list = js['tables'][0]['data']
        elif 'aaData' in js: data_list = js['aaData']
        for row in data_list:
            try:
                sid = "".join(row[0].split()); f_net = int(row[10].replace(',', '')) // 1000; t_net = int(row[13].replace(',', '')) // 1000
                all_data[sid] = {'foreign
