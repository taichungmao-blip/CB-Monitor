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
    # exit(1)

# ✅ 瀏覽器偽裝
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Connection': 'keep-alive'
})

# 🛑 2. 監控目標清單 (V10.0 新增衛司特)
TARGETS = [
    # --- 🔥 2026 1月生效 (重點戰區) ---
    {"id": "6894", "name": "衛司特",   "date": "2026-01-13", "strategy": "STD", "threshold": 50},   # NEW! 3億極致鎖碼/ESG煉金
    {"id": "6913", "name": "鴻呈",     "date": "2026-01-13", "strategy": "STD", "threshold": 100},  # 4.5億爆發型
    {"id": "2324", "name": "仁寶",     "date": "2026-01-12", "strategy": "ECB", "threshold": 1000}, # 核彈級ECB
    {"id": "3587", "name": "閎康",     "date": "2026-01-12", "strategy": "STD", "threshold": 150},  # 檢測精品
    {"id": "6515", "name": "穎崴",     "date": "2026-01-09", "strategy": "STD", "threshold": 50},   # 千金股
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
    data = {
        "username": "CB 戰情室 (V10.0)",
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

# ✅ MIS 系統查詢：抓取「價格」與「成交量」
def fetch_snapshot_prices(targets):
    print(f"📥 正在透過 MIS 系統查詢最新報價與成交量...")
    price_map = {}
    
    query_list = []
    for t in targets:
        sid = t['id']
        query_list.append(f"tse_{sid}.tw")
        query_list.append(f"otc_{sid}.tw")
    
    query_str = "|".join(query_list)
    ts = int(time.time() * 1000)
    
    try:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={query_str}&json=1&delay=0&_={ts}"
        res = session.get(url, verify=False)
        js = res.json()
        
        if 'msgArray' in js:
            for row in js['msgArray']:
                try:
                    sid = row['c']
                    price_str = row.get('z', '-')
                    y_str = row.get('y', '-')
                    vol_str = row.get('v', '0')
                    
                    if price_str == '-':
                        price_val = float(y_str)
                        change_val = 0.0
                        pct = 0.0
                    else:
                        price_val = float(price_str)
                        last_close = float(y_str)
                        change_val = price_val - last_close
                        pct = (change_val / last_close) * 100
                    
                    price_map[sid] = {
                        'close': price_val,
                        'change': change_val,
                        'pct': pct,
                        'vol': vol_str
                    }
                except: pass
            print(f"   ✅ 成功取得 {len(price_map)} 檔報價資訊")
        else:
            print(f"   ⚠️ MIS 回傳無資料")
            
    except Exception as e:
        print(f"❌ MIS 報價錯誤: {e}")
        
    return price_map

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
    
    # 籌碼
    f_buy = 0; t_buy = 0
    if sid in all_chips:
        f_buy = all_chips[sid]['foreign']
        t_buy = all_chips[sid]['trust']
    
    # 報價
    price_info = "無報價"
    if sid in all_prices:
        p_data = all_prices[sid]
        close = p_data['close']
        change = p_data['change']
        pct = p_data['pct']
        vol = p_data['vol']
        
        if change > 0: 
            emoji = "📈"
            change_str = f"+{change:.2f}"
            pct_str = f"+{pct:.2f}%"
        elif change < 0: 
            emoji = "📉"
            change_str = f"{change:.2f}"
            pct_str = f"{pct:.2f}%"
        else: 
            emoji = "➖"
            change_str = "0"
            pct_str = "0%"
        
        price_info = f"{emoji} {close} ({change_str} / {pct_str}) | 📦 量：{vol} 張"

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
    print("🚀 戰情室旗艦掃描器 V10.0 (ESG煉金術版) 啟動...")
    target_date = get_target_date()
    target_date_str = target_date.strftime("%Y-%m-%d")
    
    # 1. 抓籌碼
    all_chips_map = fetch_all_chips(target_date)
    if not all_chips_map:
        print("\n😴 系統偵測：今日查無籌碼資料 (休市)。休眠中。")
        exit(0)

    # 2. 抓報價
    all_prices_map = fetch_snapshot_prices(TARGETS)
    
    print(f"📊 數據就緒，開始分析...")
    
    for target in TARGETS:
        check_one_stock(target, all_chips_map, all_prices_map, target_date_str)
        time.sleep(1)
    print("✅ 完成！")
