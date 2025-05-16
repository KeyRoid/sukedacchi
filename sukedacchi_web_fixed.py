# sukedacchi_web_secure.py
import os
import stat
import json
import sqlite3
from datetime import datetime

import streamlit as st
import pytz
from dateutil import parser
from appdirs import user_data_dir
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ─── 環境変数／Secrets 読込 ───
load_dotenv()
CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID") or st.secrets.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET") or st.secrets.get("GOOGLE_CLIENT_SECRET")
if not CLIENT_ID or not CLIENT_SECRET:
    st.error("🔑 Google API のクライアント情報が設定されていません。")
    st.stop()

# ─── ディレクトリ・ファイルパス設定 ───
DATA_DIR   = user_data_dir(appname="sukedacchi", appauthor="sukedacchi")
os.makedirs(DATA_DIR, exist_ok=True)
TOKEN_FILE = os.path.join(DATA_DIR, "token.json")
DB_FILE    = os.path.join(DATA_DIR, "templates.db")

# ─── OAuth クライアント設定 ───
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CLIENT_CONFIG = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uris": ["http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}

def secure_save_token(creds):
    """トークンファイルを安全に書き込み・パーミッション設定"""
    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())
    os.chmod(TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 600

def get_calendar_service():
    creds = None
    # 既存トークン読込
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            os.remove(TOKEN_FILE)  # 損傷時はリセット
            creds = None
    # トークン無効時の再認証
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
            creds = flow.run_local_server(port=0)
        secure_save_token(creds)
    return build('calendar', 'v3', credentials=creds)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT    NOT NULL,
            body  TEXT    NOT NULL
        );
    ''')
    conn.commit()
    conn.close()

JP_WEEKDAYS = ['月','火','水','木','金','土','日']
def format_datetime_jp(iso_str):
    dt = parser.parse(iso_str)
    local = dt.astimezone(pytz.timezone('Asia/Tokyo'))
    wd = JP_WEEKDAYS[local.weekday()]
    return f"{local.month}月{local.day}日（{wd}）{local.strftime('%H:%M')}〜"

def format_events_output(ng, audition):
    lines = []
    if ng:
        lines.append("NG日程:")
        for e in ng:
            start = e.split("：")[0]
            lines.append(f"・{format_datetime_jp(start)}")
    if audition:
        lines.append("\n案件日程:")
        for e in audition:
            start = e.split("：")[0]
            lines.append(f"・{format_datetime_jp(start)}")
    return "\n".join(lines)

def get_unavailable_info():
    service = get_calendar_service()
    now = datetime.now(pytz.timezone('Asia/Tokyo')).isoformat()
    ng, audition = [], []
    try:
        cals = service.calendarList().list().execute().get('items', [])
    except Exception as e:
        st.error(f"カレンダー一覧取得エラー: {e}")
        return ng, audition
    for cal in cals:
        cid = cal.get('id','')
        if 'holiday' in cid: continue
        try:
            evs = service.events().list(
                calendarId=cid,
                timeMin=now,
                singleEvents=True,
                orderBy='startTime'
            ).execute().get('items', [])
        except Exception:
            continue
        for ev in evs:
            s = ev['start'].get('dateTime', ev['start'].get('date'))
            t = ev.get('summary','').strip()
            if '案件' in t:
                audition.append(f"{s}：{t}")
            elif t:
                ng.append(f"{s}：{t}")
    return ng, audition

# ─── Streamlit UI ───
st.set_page_config(page_title="スケだっち☆", layout="centered")
st.title("📅 スケだっち☆ メール自動生成")

# 認証リセット機能
if st.sidebar.button("🔄 認証情報をリセット"):
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
    st.sidebar.success("再認証用トークンを削除しました。再起動してください。")

init_db()

with st.expander("📁 テンプレート操作"):
    t = st.text_input("件名")
    b = st.text_area("本文", value="お世話になっております。以下の予定をご確認ください。")
    if st.button("💾 保存"):
        if t and b:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO templates(title,body) VALUES(?,?)",(t,b))
            conn.commit()
            conn.close()
            st.success("保存しました。")
        else:
            st.warning("件名と本文を入力してください。")

st.subheader("📂 テンプレート一覧")
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT id,title FROM templates")
temps = c.fetchall()
conn.close()
choice = st.selectbox("選択", [f"{i}: {ttl}" for i,ttl in temps] if temps else ["(なし)"])
body = ""
if choice and choice!="(なし)":
    idx = int(choice.split(":")[0])
    conn = sqlite3.connect(DB_FILE)
    body = conn.cursor().execute("SELECT body FROM templates WHERE id=?", (idx,)).fetchone()[0]
    conn.close()

if st.button("✅ 生成"):
    ng, aud = get_unavailable_info()
    txt = format_events_output(ng,aud) or ""
    st.text_area("生成結果", f"{body}\n\n---\n{txt}", height=300)
    