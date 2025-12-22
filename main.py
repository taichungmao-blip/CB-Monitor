import os
import requests
import time
import urllib3
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# 🛑 1. 系統設定區
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ✅ 從環境變數讀取 Webhook
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# 本地測試時請解除下方註解並填入網址
# DISCORD_WEBHOOK_URL = "您的Discord_Webhook_網址"

if not DISCORD_WEBHOOK_URL:
    print("❌ 錯誤：未設定 DISCORD_WEBHOOK_URL")
    # exit(1) # 本地測試時可先註解此行以免直接跳出

# ✅ 瀏覽器偽裝 (全域設定)
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.tpex.org.tw/',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest', 
    'Connection': 'keep-alive'
})

# 🛑 2. 監控目標清單
TARGETS = [
    {"id": "2376", "name": "技嘉",     "date": "2026-01-02", "strategy": "ECB", "threshold": 500},
    {"id": "2455", "name": "全新",     "date": "2026-01-02", "strategy": "STD", "threshold": 200},
    {"id": "4714", "name": "永捷",     "date": "2026-01-16", "strategy": "STD", "threshold": 100},
    {"id": "2233", "name": "宇隆",     "date": "2025-12-31", "strategy": "STD", "threshold": 150},
    {"id": "6672", "name": "F-騰輝",   "date": "2025-12-30", "strategy": "STD", "threshold": 100},
    {"id": "6603", "name": "富強鑫",   "date": "2025-12-29", "strategy": "STD", "threshold": 100},
    {"id": "8210", "name": "勤誠",     "date": "2025-12-26", "strategy": "STD", "threshold": 300},
    {"id": "3706", "name": "神達",     "date": "2025-12-23", "strategy": "ECB", "threshold": 1000},
    {"id": "6101", "name": "寬魚國際", "date": "2026-01-07", "strategy": "ENT", "threshold": 100}, 
    {"id": "2745", "name": "五福",     "date": "2026-01-10", "strategy": "PRICED", "threshold": 100}, 
]

def send_discord(title, msg, color=0x00ff00):
    if not DISCORD_WEBHOOK_URL: return
    data = {
        "username": "CB 戰情室 (V9.1)",
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
    # 下午 3 點前抓昨天
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

# ✅ 修正版：抓取每日收盤行情 (修復 TPEX 上櫃報價)
def fetch_all_prices(target_date):
    price_map = {}
    date_str = target_date.strftime("%Y%m%d")
    ts = int(time.time())

    # --- 1. TWSE 上市行情 ---
    print(f"📥 下載 TWSE 股價行情...")
    try:
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_str}&type=ALLBUT0999&response=json&_={ts}"
        res = session.get(url, verify=False)
        js = res.json()
        if js['stat'] == 'OK':
            target_table = None
            for table in js.get('tables', []):
                if "收盤價" in table.get('fields', []):
                    target_table = table
                    break
            
            if target_table:
                for row in target_table['data']:
                    try:
                        sid = "".join(row[0].split())
                        close_price = row[8].replace(',', '')
                        
                        sign_html = row[9] 
                        diff = row[10].replace(',', '')
                        
                        if "red" in sign_html: sign = 1.0
                        elif "green" in sign_html: sign = -1.0
                        else: sign = 0.0
                        if "-" in sign_html: sign = -1.0 # 補強減號判斷
                        
                        try:
                            price_val = float(close_price)
                            change_val = float(diff) * sign
                            prev_price = price_val - change_val
                            pct = (change_val / prev_price) * 100 if prev_price != 0 else 0.0
                            
                            price_map[sid] = {'close': price_val, 'change': change_val, 'pct': pct}
                        except: pass
                    except: pass
    except Exception as e: print(f"❌ TWSE 報價錯誤: {e}")

    # --- 2. TPEX 上櫃行情 (關鍵修復) ---
    print(f"📥 下載 TPEX 股價行情...")
    try:
        date_str_ro = f"{target_date.year-1911}/{target_date.month:02d}/{target_date.day:02d}"
        # ⚠️ 關鍵：TPEX 股價 API 需要特定的 Referer，不能用首頁
        headers_tpex_price = session.headers.copy()
        headers_tpex_price.update({
            'Referer': 'https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote.php'
        })
        
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&d={date_str_ro}&o=json&_={ts}"
        res = session.get(url, headers=headers_tpex_price, verify=False)
        js = res.json()
        
        if 'aaData' in js:
            print(f"   ✅ TPEX 報價下載成功 (共 {len(js['aaData'])} 筆)")
            for row in js['aaData']:
                try:
                    sid = "".join(row[0].split())
                    close_price = row[2].replace(',', '')
                    diff = row[3].replace(',', '')
                    
                    # 處理 "---" (無成交)
                    if "---" in close_price: continue

                    try:
                        price_val = float(close_price)
                        change_val = float(diff)
                        
                        # TPEX 的 diff 已經包含正負號
                        prev_price = price_val - change_val
                        pct = (change_val / prev_price) * 100 if prev_price != 0 else 0.0
                        
                        price_map[sid] = {'close': price_val, 'change': change_val, 'pct': pct}
                    except: pass 
                except: pass
        else:
            print(f"   ⚠️ TPEX 報價無資料 (可能是 Referer 仍被擋或休市)")
    except Exception as e: print(f"❌ TPEX 報價錯誤: {e}")

    return price_map

def fetch_all_chips(target_date):
    all_data = {}
    date_str = target_date.strftime("%Y%m%d")
    ts = int(time.time())

    # TWSE 籌碼
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

    # TPEX 籌碼
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

def get_strategy_analysis(strategy, foreign, trust, phase_code, threshold):
    signal, text, color = "無訊號", "持續觀察", 0x808080
    limit = threshold if threshold else 500

    if strategy == "STD": 
        if phase_code == "PHASE_1":
            if trust > 0: 
                signal = "🔥 投信佈局"; text = "生效前夕投信買超，看好定價行情。"; color = 0xffa500
            elif foreign > limit: 
                signal = "💹 外資補貨"; text = "外資主力進場，籌碼轉強。"; color = 0x00ffff 
            elif foreign < -limit: 
                signal = "🛡️ 外資調節"; text = f"外資賣超逾 {limit} 張，短線有壓。"; color = 0x808080
            else:
                signal = "👀 盤整觀望"; text = "法人動作未達攻擊量，持續觀察。"; color = 0x808080
        elif phase_code in ["PHASE_2", "PHASE_3"]:
            if trust > 0 or foreign > limit: 
                signal = "🚀 定價攻勢"; text = "法人大單敲進，全力衝刺競拍價格。"; color = 0x00ff00
            
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
        if foreign > 0 or trust > 0: signal = "💹 溢價護盤"; text = "掛牌前夕法人買進。"; color = 0x00ff00
        elif foreign < -10: signal = "⚠️ 獲利調節"; text = "掛牌前外資轉賣，留意回檔。"; color = 0xffa500

    return signal, text, color

def check_one_stock(target, all_chips, all_prices, target_date_str):
    sid = target['id']
    sname = target['name']
    sdate = target['date']
    sstrat = target['strategy']
    sthreshold = target.get('threshold', 500)
    
    print(f"🔎 分析 {sid} {sname}...")
    phase_code, phase_text = get_battle_phase(sdate)
    
    # 籌碼數據
    f_buy = 0; t_buy = 0
    if sid in all_chips:
        f_buy = all_chips[sid]['foreign']
        t_buy = all_chips[sid]['trust']
    
    # 股價數據
    price_info = "無報價"
    if sid in all_prices:
        p_data = all_prices[sid]
        close = p_data['close']
        change = p_data['change']
        pct = p_data['pct']
        
        if change > 0: 
            emoji = "📈"
            change_str = f"+{change}"
            pct_str = f"+{pct:.1f}%"
        elif change < 0: 
            emoji = "📉"
            change_str = f"{change}"
            pct_str = f"{pct:.1f}%"
        else: 
            emoji = "➖"
            change_str = "0"
            pct_str = "0%"
        price_info = f"{emoji} {close} ({change_str} / {pct_str})"

    signal, text, color = get_strategy_analysis(sstrat, f_buy, t_buy, phase_code, sthreshold)
    
    news_list = check_material_info(sid, sname)
    news_text = ""
    if news_list:
        news_text = "\n\n🚨 **發現重訊：**\n" + "\n".join(news_list)
        if color == 0x808080: 
            color = 0xff00ff
            signal = "📰 重訊發布"
    
    msg = f"📅 **{target_date_str}**\n💰 收盤：{price_info}\n{phase_text}\n----------------\n模式：{sstrat} (門檻:{sthreshold})\n👽 外資：`{f_buy}` 張\n🏦 投信：`{t_buy}` 張\n----------------\n💡 {signal}\n📜 {text}{news_text}"
    
    send_discord(f"📊 {sname} ({sid}) 戰報", msg, color)

if __name__ == "__main__":
    print("🚀 戰情室旗艦掃描器 V9.1 (上櫃報價修復版) 啟動...")
    target_date = get_target_date()
    target_date_str = target_date.strftime("%Y-%m-%d")
    
    # 1. 抓籌碼
    all_chips_map = fetch_all_chips(target_date)
    if not all_chips_map:
        print("\n😴 系統偵測：今日查無籌碼資料 (休市)。休眠中。")
        exit(0)

    # 2. 抓股價
    all_prices_map = fetch_all_prices(target_date)
    
    print(f"📊 數據就緒，開始分析...")
    
    for target in TARGETS:
        check_one_stock(target, all_chips_map, all_prices_map, target_date_str)
        time.sleep(1)
    print("✅ 完成！")
