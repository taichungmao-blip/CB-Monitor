import os
import requests
import time
import re
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

# 🛑 2. 監控目標清單 (V10.7)
TARGETS = [
    # --- 🔥 2026 1月生效 ---
    {"id": "6894", "name": "衛司特",   "date": "2026-01-13", "strategy": "STD", "threshold": 50,  "mkt": "otc"},
    {"id": "6913", "name": "鴻呈",     "date": "2026-01-13", "strategy": "STD", "threshold": 100, "mkt": "otc"},
    {"id": "2324", "name": "仁寶",     "date": "2026-01-12", "strategy": "ECB", "threshold": 1000,"mkt": "tse"},
    {"id": "3587", "name": "閎康",     "date": "2026-01-12", "strategy": "STD", "threshold": 150, "mkt": "otc"},
    {"id": "6515", "name": "穎崴",     "date": "2026-01-09", "strategy": "STD", "threshold": 50,  "mkt": "tse"},
    {"id": "2329", "name": "華泰",     "date": "2026-01-09", "strategy": "STD", "threshold": 500, "mkt": "tse"},
    {"id": "4923", "name": "力士",     "date": "2026-01-09", "strategy": "STD", "threshold": 100, "mkt": "otc"},

    # --- 1月初生效 ---
    {"id": "2376", "name": "技嘉",     "date": "2026-01-02", "strategy": "ECB", "threshold": 500, "mkt": "tse"},
    {"id": "2455", "name": "全新",     "date": "2026-01-02", "strategy": "STD", "threshold": 200, "mkt": "tse"},
    {"id": "4714", "name": "永捷",     "date": "2026-01-16", "strategy": "STD", "threshold": 100, "mkt": "otc"},
    {"id": "6101", "name": "寬魚國際", "date": "2026-01-07", "strategy": "ENT", "threshold": 100, "mkt": "otc"}, 
    {"id": "2745", "name": "五福",     "date": "2026-01-10", "strategy": "PRICED", "threshold": 100,"mkt": "otc"}, 

    # --- 2025 12月底衝刺 ---
    {"id": "2233", "name": "宇隆",     "date": "2025-12-31", "strategy": "STD", "threshold": 150, "mkt": "tse"},
    {"id": "6672", "name": "F-騰輝",   "date": "2025-12-30", "strategy": "STD", "threshold": 100, "mkt": "tse"},
    {"id": "6603", "name": "富強鑫",   "date": "2025-12-29", "strategy": "STD", "threshold": 100, "mkt": "tse"},
    {"id": "8210", "name": "勤誠",     "date": "2025-12-26", "strategy": "STD", "threshold": 300, "mkt": "tse"},
    {"id": "3706", "name": "神達",     "date": "2025-12-23", "strategy": "ECB", "threshold": 1000,"mkt": "tse"},
]

def send_discord(title, msg, color=0x00ff00):
    if not DISCORD_WEBHOOK_URL: return
    data = {
        "username": "CB 戰情室 (V10.7)",
        "embeds": [{
            "title": title,
            "description": msg,
            "color": color,
            "timestamp": datetime.now().isoformat()
        }]
    }
    try: session.post(DISCORD_WEBHOOK_URL, json=data, verify=False)
    except: pass

def get_tw_time():
    utc_now = datetime.now(timezone.utc)
    tw_now = utc_now.astimezone(timezone(timedelta(hours=8)))
    return tw_now

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

# ✅ 引擎：官方盤後結算表 (權威數據，解決上櫃誤差)
def fetch_official_daily_close(target_date):
    print(f"🏛️ 啟動「官方盤後結算引擎」 (100% 準確)...")
    price_map = {}
    date_str = target_date.strftime("%Y%m%d")
    date_str_ro = f"{target_date.year-1911}/{target_date.month:02d}/{target_date.day:02d}"

    # 1. 上市 (TWSE) 結算表
    try:
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_str}&type=ALLBUT0999&response=json"
        res = session.get(url, verify=False)
        js = res.json()
        target_table = None
        if js['stat'] == 'OK':
            # 尋找包含股價的表格
            for table in js.get('tables', []):
                if "收盤價" in table.get('fields', []): target_table = table; break
            
            if target_table:
                for row in target_table['data']:
                    sid = row[0]
                    try:
                        # 處理 "106.00" 這種格式
                        close = float(row[8].replace(',', ''))
                        
                        # 處理漲跌 (+/-)
                        sign = -1 if "green" in row[9] or "-" in row[9] else 1
                        diff = float(row[10].replace(',', '')) * sign
                        
                        vol = int(row[2].replace(',', '')) // 1000
                        prev = close - diff
                        pct = (diff / prev * 100) if prev != 0 else 0
                        
                        price_map[sid] = {'close': close, 'change': diff, 'pct': pct, 'vol': str(vol)}
                    except: pass
        print(f"   ✅ 上市結算資料下載完成")
    except Exception as e: print(f"   ⚠️ 上市資料錯誤: {e}")

    # 2. 上櫃 (TPEX) 結算表 - 這是抓到五福 106.0 的關鍵！
    try:
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=json&d={date_str_ro}&s=0,asc,0"
        res = session.get(url, verify=False)
        js = res.json()
        if 'aaData' in js:
            for row in js['aaData']:
                sid = row[0]
                try:
                    # 上櫃格式：代號, 名稱, 收盤, 漲跌...
                    close = float(row[2].replace(',', ''))
                    diff = float(row[3].replace(',', ''))
                    vol = int(row[8].replace(',', '')) // 1000
                    prev = close - diff
                    pct = (diff / prev * 100) if prev != 0 else 0
                    
                    price_map[sid] = {'close': close, 'change': diff, 'pct': pct, 'vol': str(vol)}
                except: pass
        print(f"   ✅ 上櫃結算資料下載完成")
    except Exception as e: print(f"   ⚠️ 上櫃資料錯誤: {e}")

    return price_map

# ✅ 引擎：MIS (盤中用)
def fetch_mis_prices(targets):
    print(f"📥 正在透過 MIS 系統查詢 (盤中模式)...")
    price_map = {}
    try: session.get("https://mis.twse.com.tw/stock/fibest.jsp?lang=zh_tw", timeout=5)
    except: pass
    query_list = []
    for t in targets:
        key = f"{t['mkt']}_{t['id']}.tw"
        query_list.append(key)
    query_str = "|".join(query_list)
    ts = int(time.time() * 1000)
    try:
        headers = {'Referer': 'https://mis.twse.com.tw/stock/fibest.jsp?lang=zh_tw'}
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={query_str}&json=1&delay=0&_={ts}"
        res = session.get(url, headers=headers, verify=False)
        js = res.json()
        if 'msgArray' in js:
            for row in js['msgArray']:
                try:
                    sid = row['c']
                    price_str = row.get('z', '-'); y_str = row.get('y', '-'); vol_str = row.get('v', '0')
                    if price_str == '-':
                        if y_str != '-': price_val = float(y_str); change_val = 0.0; pct = 0.0
                        else: continue
                    else:
                        price_val = float(price_str); last_close = float(y_str)
                        change_val = price_val - last_close; pct = (change_val / last_close) * 100
                    price_map[sid] = {'close': price_val, 'change': change_val, 'pct': pct, 'vol': vol_str}
                except: pass
    except: pass
    return price_map

# ✅ 智能分流主控台
def get_best_prices(targets, target_date):
    now = get_tw_time()
    # 如果是下午 2 點後，強制使用「官方結算表」
    if now.hour >= 14:
        return fetch_official_daily_close(target_date)
    else:
        # 盤中只用 MIS
        return fetch_mis_prices(targets)

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
            if any(k in text for k in keywords):
                clean_text = " ".join(text.split())
                found_news.append(clean_text[:80] + "...")
                break 
    except: pass
    return found_news

def fetch_all_chips(target_date):
    all_data = {}
    date_str = target_date.strftime("%Y%m%d")
    ts = int(time.time())
    # TWSE
    try:
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json&_={ts}"
        res = session.get(url, verify=False)
        js = res.json()
        if js['stat'] == 'OK':
            for row in js['data']:
                try:
                    sid = "".join(row[0].split())
                    f_net = int(row[4].replace(',', '')) // 1000
                    t_net = int(row[10].replace(',', '')) // 1000
                    all_data[sid] = {'foreign': f_net, 'trust': t_net}
                except: pass
    except: pass
    # TPEX
    try:
        if 'tpex_visited' not in session.cookies:
            session.get("https://www.tpex.org.tw/web/", verify=False)
            session.cookies.set('tpex_visited', 'true')
        date_str_ro = f"{target_date.year-1911}/{target_date.month:02d}/{target_date.day:02d}"
        url = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&t=D&d={date_str_ro}&_={ts}"
        res = session.get(url, verify=False)
        js = res.json()
        data_list = []
        if 'tables' in js and len(js['tables']) > 0: data_list = js['tables'][0]['data']
        elif 'aaData' in js: data_list = js['aaData']
        for row in data_list:
            try:
                sid = "".join(row[0].split())
                if len(row) > 13: 
                    f_net = int(row[10].replace(',', '')) // 1000
                    t_net = int(row[13].replace(',', '')) // 1000
                else: 
                    f_net = int(row[7].replace(',', '')) // 1000
                    t_net = int(row[10].replace(',', '')) // 1000
                all_data[sid] = {'foreign': f_net, 'trust': t_net}
            except: pass
    except: pass
    return all_data

# ✅ V10.7 策略邏輯 (保留 V10.6 的修正)
def get_strategy_analysis(strategy, foreign, trust, phase_code, threshold):
    signal, text, color = "無訊號", "持續觀察", 0x808080
    limit = threshold if threshold else 500

    if (foreign > limit and trust < -limit) or (foreign < -limit and trust > limit):
        signal = "⚔️ 土洋對作"; text = f"外資與投信方向相反且金額巨大(>{limit})，籌碼混亂。"; color = 0xffa500
        return signal, text, color

    if strategy == "STD": 
        if phase_code == "PHASE_1":
            if foreign < -limit: 
                signal = "🛡️ 外資調節"; text = f"外資賣超逾 {limit} 張，短線有壓，需留意回檔。"; color = 0x808080
            elif trust > 10: 
                signal = "🔥 投信佈局"; text = "生效前夕投信買超，看好定價行情。"; color = 0xffa500
            elif foreign > limit: 
                signal = "💹 外資補貨"; text = "外資主力進場，籌碼轉強。"; color = 0x00ffff 
            else:
                signal = "👀 盤整觀望"; text = "法人動作未達攻擊量，持續觀察。"; color = 0x808080
        
        elif phase_code in ["PHASE_2", "PHASE_3"]:
            if trust > 0 and foreign > 0: 
                signal = "🚀 定價攻勢"; text = "法人合力買超，全力衝刺競拍價格。"; color = 0x00ff00
            elif trust > 0 and foreign < 0: 
                signal = "🛡️ 投信護盤"; text = "投信單獨買超支撐股價，但外資有賣壓。"; color = 0xffa500
            elif foreign > limit: 
                signal = "💹 外資拉抬"; text = "外資大單敲進，看好後市。"; color = 0x00ff00
            
    elif strategy == "ECB": 
        if phase_code in ["PHASE_1", "PHASE_2"]:
            if foreign < -limit: 
                signal = "🛡️ 外資鎖單"; text = "ECB 訂價前避險賣壓。"; color = 0x808080
            elif foreign > limit: 
                signal = "🔥 強力看好"; text = "不需避險直接大買，基本面極強。"; color = 0xffa500
            else:
                signal = "⚖️ 多空平衡"; text = "外資無明顯避險或拉抬動作。"; color = 0xcccccc 
        elif phase_code == "PHASE_3" and foreign > limit: 
            signal = "🚀 認錯回補"; text = "訂價完成，避險空單回補。"; color = 0x00ff00
            
    elif strategy == "ENT":
        if abs(foreign) > 20 or abs(trust) > 5: signal = "🎭 籌碼波動"; text = "法人進出，留意消息面。"; color = 0xff00ff

    elif strategy == "PRICED": 
        if foreign > limit or trust > limit: 
            signal = "💹 溢價護盤"; text = "掛牌前夕法人買進。"; color = 0x00ff00
        elif foreign < -limit: 
            signal = "⚠️ 獲利調節"; text = "掛牌前外資轉賣，留意回檔。"; color = 0xffa500
        else:
            signal = "👀 盤整觀望"; text = f"法人買賣未達攻擊量(門檻:{limit})，持續觀察。"; color = 0x808080

    return signal, text, color

def check_one_stock(target, all_chips, all_prices, target_date_str):
    sid = target['id']; sname = target['name']
    sdate = target['date']; sstrat = target['strategy']; sthreshold = target.get('threshold', 500)
    
    print(f"🔎 分析 {sid} {sname}...")
    phase_code, phase_text = get_battle_phase(sdate)
    f_buy = 0; t_buy = 0
    if sid in all_chips:
        f_buy = all_chips[sid]['foreign']; t_buy = all_chips[sid]['trust']
    
    price_info = "無報價"
    if sid in all_prices:
        p_data = all_prices[sid]
        close = p_data['close']; change = p_data['change']; pct = p_data['pct']; vol = p_data['vol']
        if change > 0: emoji = "📈"; change_str = f"+{change:.2f}"; pct_str = f"+{pct:.2f}%"
        elif change < 0: emoji = "📉"; change_str = f"{change:.2f}"; pct_str = f"{pct:.2f}%"
        else: emoji = "➖"; change_str = "0"; pct_str = "0%"
        price_info = f"{emoji} {close} ({change_str} / {pct_str}) | 📦 量：{vol} 張"

    signal, text, color = get_strategy_analysis(sstrat, f_buy, t_buy, phase_code, sthreshold)
    
    news_list = check_material_info(sid, sname)
    news_text = ""
    if news_list:
        news_text = "\n\n🚨 **發現重訊：**\n" + "\n".join(news_list)
        if color == 0x808080: color = 0xff00ff; signal = "📰 重訊發布"
    
    msg = f"📅 **{target_date_str}**\n💰 收盤：{price_info}\n{phase_text}\n----------------\n模式：{sstrat} (門檻:{sthreshold})\n👽 外資：`{f_buy}` 張\n🏦 投信：`{t_buy}` 張\n----------------\n💡 {signal}\n📜 {text}{news_text}"
    send_discord(f"📊 {sname} ({sid}) 戰報", msg, color)

if __name__ == "__main__":
    print("🚀 戰情室旗艦掃描器 V10.7 (官方結算權威版) 啟動...")
    target_date = get_target_date()
    target_date_str = target_date.strftime("%Y-%m-%d")
    
    all_chips_map = fetch_all_chips(target_date)
    if not all_chips_map:
        print("\n😴 系統偵測：今日查無籌碼資料 (休市)。休眠中。"); exit(0)
    
    # 智能分流：盤後自動切換到官方結算表
    all_prices_map = get_best_prices(TARGETS, target_date)
    
    print(f"📊 數據就緒，開始分析...")
    for target in TARGETS:
        check_one_stock(target, all_chips_map, all_prices_map, target_date_str)
        time.sleep(1)
    print("✅ 完成！")
