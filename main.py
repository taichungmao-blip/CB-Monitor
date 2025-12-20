import os
import requests
import time
import urllib3
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# 🛑 1. 系統設定區
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ✅ 從環境變數讀取 Webhook (安全性修正)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

if not DISCORD_WEBHOOK_URL:
    print("❌ 錯誤：未設定 DISCORD_WEBHOOK_URL 環境變數")
    exit(1)

# ✅ 瀏覽器偽裝
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
    data = {
        "username": "CB 戰情室 (GitHub Action)",
        "embeds": [{
            "title": title,
            "description": msg,
            "color": color,
            "timestamp": datetime.now().isoformat()
        }]
    }
    try: session.post(DISCORD_WEBHOOK_URL, json=data, verify=False)
    except: pass

# ✅ 強制轉換為台灣時間 (GMT+8)
def get_tw_time():
    utc_now = datetime.now(timezone.utc)
    tw_now = utc_now.astimezone(timezone(timedelta(hours=8)))
    return tw_now

def get_target_date():
    now = get_tw_time()
    # 邏輯：下午 3 點 (15:00) 前執行，抓昨天；3 點後執行，抓今天
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
    # 只比較日期部分
    days_diff = (eff_dt.date() - today.date()).days
    
    if days_diff > 0: return "PHASE_1", f"⏳ **倒數 {days_diff} 天**"
    elif days_diff == 0: return "PHASE_2", f"🔥 **D-Day：今日生效！**"
    else: return "PHASE_3", f"🚀 **後續追蹤：第 {abs(days_diff)} 天**"

def check_material_info(sid, sname):
    found_news = []
    try:
        # 使用台灣時間年份
        tw_year = str(get_tw_time().year - 1911)
        url = "https://mops.twse.com.tw/mops/web/ajax_t05st01"
        payload = {
            'encodeURIComponent': '1', 'step': '1', 'firstin': '1', 'off': '1', 'queryName': 'co_id', 'inpuType': 'co_id', 'TYPEK': 'all', 'co_id': sid, 'year': tw_year
        }
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

    print(f"📥 下載 TWSE (上市) 資料...")
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

    print(f"📥 下載 TPEX (上櫃) 資料...")
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

def check_one_stock(target, all_chips, target_date_str):
    sid = target['id']
    sname = target['name']
    sdate = target['date']
    sstrat = target['strategy']
    sthreshold = target.get('threshold', 500)
    
    print(f"🔎 分析 {sid} {sname}...")
    phase_code, phase_text = get_battle_phase(sdate)
    
    f_buy = 0; t_buy = 0
    if sid in all_chips:
        f_buy = all_chips[sid]['foreign']
        t_buy = all_chips[sid]['trust']
    
    signal, text, color = get_strategy_analysis(sstrat, f_buy, t_buy, phase_code, sthreshold)
    
    news_list = check_material_info(sid, sname)
    news_text = ""
    if news_list:
        news_text = "\n\n🚨 **發現重訊：**\n" + "\n".join(news_list)
        if color == 0x808080: 
            color = 0xff00ff
            signal = "📰 重訊發布"
    
    msg = f"📅 **資料日期：{target_date_str}**\n{phase_text}\n----------------\n模式：{sstrat} (門檻:{sthreshold})\n👽 外資：`{f_buy}` 張\n🏦 投信：`{t_buy}` 張\n----------------\n💡 {signal}\n📜 {text}{news_text}"
    send_discord(f"📊 {sname} ({sid}) 戰報", msg, color)

if __name__ == "__main__":
    print("🚀 戰情室旗艦掃描器 (GitHub Action版) 啟動...")
    target_date = get_target_date()
    target_date_str = target_date.strftime("%Y-%m-%d")
    
    all_chips_map = fetch_all_chips(target_date)
    
    if not all_chips_map:
        print("\n😴 系統偵測：今日查無資料 (週末/假日)。休眠中。")
        exit(0)
        
    print(f"📊 成功獲取 {len(all_chips_map)} 筆籌碼資料，開始分析...")
    
    for target in TARGETS:
        check_one_stock(target, all_chips_map, target_date_str)
        time.sleep(1)
    print("✅ 完成！")
