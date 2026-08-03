import streamlit as st
import json
import re
import io
import os
import time
import difflib
import hashlib
import traceback
import statistics
import requests
import urllib.parse
import pandas as pd
import psycopg2
from datetime import date
from audio_recorder_streamlit import audio_recorder
from openai import OpenAI


TABLE_NAME = "shipmentsdb"
COL_ORIGIN = "Origin"
COL_DEST = "Destination"
COL_SHIP_DATE = "Ship/Date"
COL_LINE_HAUL = "Line Haul"
COL_ADDL_CHARGES = "Additional Charges"
COL_CARRIER_PAY = "Carrier Pay"
COL_NET_PROFIT = "Net Profit"
COL_PCT = "%"

GEOCODE_CACHE_PATH = "geocode_cache.json"
DISTANCE_CACHE_PATH = "distance_cache.json"
USERS_STORE_PATH = "users.json"

DEFAULT_CREDENTIALS = {"admin": "trucker2026"}

US_STATE_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "district of columbia": "DC",
}

st.set_page_config(page_title="Line Haul Voice Lookup", page_icon="🚚", layout="wide")


def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

        :root{
            --bg-page:#0a0b0d;
            --bg-panel:#131519;
            --bg-panel-2:#1a1d22;
            --bg-panel-3:#20242b;
            --border:#23262c;
            --border-bright:#383e46;
            --text-primary:#eef0f2;
            --text-secondary:#838a94;
            --text-tertiary:#565c66;

            --amber:#ffb300;
            --amber-dim:#8a6100;
            --teal:#00c2a8;
            --teal-dim:#036a5c;
            --red:#ff5a5a;

            --font-display:'Space Grotesk', sans-serif;
            --font-body:'Inter', sans-serif;
            --font-mono:'JetBrains Mono', monospace;
        }

        @media (prefers-reduced-motion: reduce){
            *{ animation-duration: .001ms !important; animation-iteration-count: 1 !important; transition-duration: .001ms !important; }
        }

        html, body, .stApp{
            background:
                radial-gradient(ellipse 900px 500px at 12% -10%, rgba(0,194,168,.08), transparent 60%),
                radial-gradient(ellipse 900px 500px at 100% 0%, rgba(255,179,0,.06), transparent 55%),
                var(--bg-page) !important;
            color: var(--text-primary) !important;
            font-family: var(--font-body) !important;
        }
        .stApp::before{
            content:"";
            position: fixed; inset: 0;
            pointer-events: none;
            z-index: 0;
            opacity: .035;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='90' height='90'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
        }

        [data-testid="stHeader"]{ background: transparent !important; }
        .block-container{ padding-top: 1.6rem; max-width: 1180px; }

        ::-webkit-scrollbar{ width: 10px; height: 10px; }
        ::-webkit-scrollbar-track{ background: var(--bg-page); }
        ::-webkit-scrollbar-thumb{ background: var(--border-bright); border-radius: 8px; border: 2px solid var(--bg-page); }
        ::-webkit-scrollbar-thumb:hover{ background: var(--teal-dim); }

        *:focus-visible{ outline: 2px solid var(--teal) !important; outline-offset: 2px; }

        h1,h2,h3,h4{ font-family: var(--font-display) !important; font-weight: 600 !important; color: var(--text-primary) !important; letter-spacing: -.01em; }
        h3, .stMarkdown h3{ font-size: 1.05rem !important; text-transform: uppercase; letter-spacing: .04em !important; color: var(--text-secondary) !important; font-weight: 600 !important; }
        p, span, label, .stMarkdown, .stCaption{ color: var(--text-primary); }
        [data-testid="stCaptionContainer"]{ color: var(--text-secondary) !important; font-size: .82rem; }

        [data-testid="stSidebar"]{
            background: linear-gradient(180deg, var(--bg-panel) 0%, var(--bg-page) 100%) !important;
            border-right: 1px solid var(--border);
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3{
            color: var(--text-secondary) !important;
            text-transform: uppercase;
            font-size: .78rem;
            letter-spacing: .1em;
            font-family: var(--font-mono) !important;
        }

        input, textarea, [data-baseweb="select"] > div, [data-baseweb="base-input"]{
            background: var(--bg-panel-2) !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border-bright) !important;
            border-radius: 7px !important;
            transition: border-color .15s ease, box-shadow .15s ease;
        }
        input:focus, textarea:focus{
            border-color: var(--teal) !important;
            box-shadow: 0 0 0 3px rgba(0,194,168,.14) !important;
        }
        [data-testid="stWidgetLabel"] p{
            color: var(--text-secondary) !important;
            font-size: .78rem !important;
            text-transform: uppercase;
            letter-spacing: .05em;
        }

        .stButton>button, .stFormSubmitButton>button{
            background: linear-gradient(180deg, #ffc633, var(--amber)) !important;
            color: #14100a !important;
            font-weight: 700 !important;
            font-family: var(--font-body) !important;
            border: none !important;
            border-radius: 7px !important;
            padding: .55rem 1.2rem !important;
            letter-spacing: .01em;
            box-shadow: 0 1px 0 rgba(255,255,255,.35) inset, 0 6px 16px -6px rgba(255,179,0,.55);
            transition: transform .12s ease, box-shadow .12s ease, filter .12s ease;
        }
        .stButton>button:hover, .stFormSubmitButton>button:hover{
            filter: brightness(1.06);
            transform: translateY(-1px);
            box-shadow: 0 1px 0 rgba(255,255,255,.4) inset, 0 10px 22px -8px rgba(255,179,0,.65);
        }
        .stButton>button:active, .stFormSubmitButton>button:active{ transform: translateY(0); }

        [data-testid="stMetric"]{
            background: linear-gradient(180deg, var(--bg-panel-3), var(--bg-panel));
            border: 1px solid var(--border);
            border-radius: 9px;
            padding: .8rem .95rem;
            position: relative;
            overflow: hidden;
        }
        [data-testid="stMetric"]::before{
            content:""; position:absolute; top:0; left:0; right:0; height:2px;
            background: linear-gradient(90deg, var(--teal), transparent);
        }
        [data-testid="stMetricValue"]{ font-family: var(--font-mono) !important; color: var(--text-primary) !important; font-size: 1.3rem !important; font-weight: 600 !important; }
        [data-testid="stMetricLabel"]{ color: var(--text-secondary) !important; text-transform: uppercase; font-size: .66rem; letter-spacing: .08em; }
        [data-testid="stMetricDelta"]{ font-family: var(--font-mono) !important; }

        [data-testid="stAlert"]{ background: var(--bg-panel) !important; border: 1px solid var(--border) !important; border-left: 3px solid var(--amber) !important; border-radius: 8px !important; }
        [data-testid="stSpinner"] p{ color: var(--teal) !important; font-family: var(--font-mono); font-size: .82rem; letter-spacing: .02em; }
        [data-testid="stSpinner"] svg{ color: var(--teal) !important; }

        [data-testid="stVerticalBlockBorderWrapper"]{
            background: linear-gradient(180deg, var(--bg-panel), #101216) !important;
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            box-shadow: 0 20px 40px -24px rgba(0,0,0,.7);
        }

        [data-testid="stDataFrame"]{
            border: 1px solid var(--border);
            border-radius: 9px;
            overflow: hidden;
        }

        hr{ border-color: var(--border) !important; }

        /* ---------- header + route strip signature ---------- */
        .app-header{
            padding-bottom: 1.1rem;
            margin-bottom: 1.6rem;
            position: relative;
        }
        .app-header .eyebrow{
            font-family: var(--font-mono);
            font-size: .68rem;
            letter-spacing: .18em;
            text-transform: uppercase;
            color: var(--teal);
            margin-bottom: .3rem;
        }
        .app-header h1{
            margin: 0;
            font-size: 1.85rem;
            display: inline-flex;
            align-items: baseline;
            gap: .5rem;
        }
        .app-header .sub{
            color: var(--text-secondary);
            font-size: .92rem;
            margin-top: .25rem;
            font-family: var(--font-body);
        }
        .route-strip{
            margin-top: 1rem;
            display: flex;
            align-items: center;
            gap: .7rem;
            height: 20px;
        }
        .route-strip .stop{
            font-family: var(--font-mono);
            font-size: .62rem;
            letter-spacing: .1em;
            color: var(--text-tertiary);
            white-space: nowrap;
        }
        .route-strip .dot{
            width: 7px; height: 7px; border-radius: 50%;
            background: var(--teal);
            box-shadow: 0 0 8px var(--teal);
            flex-shrink: 0;
        }
        .route-strip .dot.end{ background: var(--amber); box-shadow: 0 0 8px var(--amber); }
        .route-strip .track{
            flex: 1;
            position: relative;
            height: 1px;
            background-image: linear-gradient(90deg, var(--border-bright) 0 6px, transparent 6px 12px);
            background-size: 12px 1px;
            overflow: visible;
        }
        .route-strip .runner{
            position: absolute;
            top: 50%; left: 0;
            transform: translate(-50%,-50%);
            font-size: .8rem;
            animation: run-lane 5.5s linear infinite;
        }
        @keyframes run-lane{
            0%{ left: 0%; opacity: 0; }
            8%{ opacity: 1; }
            92%{ opacity: 1; }
            100%{ left: 100%; opacity: 0; }
        }
        .hazard-rule{
            height: 3px;
            margin-top: 1rem;
            border-radius: 2px;
            background: repeating-linear-gradient(135deg, var(--amber) 0 10px, #0a0b0d 10px 20px);
            opacity: .55;
        }

        /* ---------- record panel ---------- */
        .record-panel{
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 1.4rem 1rem 1.1rem 1rem;
            text-align: center;
            margin-bottom: 1.2rem;
            background: radial-gradient(circle at 50% 0%, rgba(0,194,168,.08), var(--bg-panel) 65%);
            position: relative;
        }
        .record-panel .rec-label{
            font-family: var(--font-mono);
            font-size: .68rem;
            letter-spacing: .16em;
            text-transform: uppercase;
            color: var(--text-tertiary);
            margin-bottom: .8rem;
        }
        .record-panel .rec-ring{
            width: 64px; height: 64px;
            margin: 0 auto .6rem auto;
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            position: relative;
        }
        .record-panel .rec-ring::before, .record-panel .rec-ring::after{
            content: "";
            position: absolute; inset: 0;
            border-radius: 50%;
            border: 1px solid rgba(0,194,168,.45);
            animation: pulse-ring 2.6s ease-out infinite;
        }
        .record-panel .rec-ring::after{ animation-delay: 1.3s; }
        @keyframes pulse-ring{
            0%{ transform: scale(.55); opacity: .8; }
            100%{ transform: scale(1.9); opacity: 0; }
        }
        .record-panel audio{ margin-top: .8rem; width: 100%; }

        /* ---------- badges: manifest stamp style ---------- */
        .badge{
            display: inline-flex;
            align-items: center;
            gap: .35rem;
            font-family: var(--font-mono);
            font-size: .66rem;
            font-weight: 600;
            padding: .22rem .6rem .22rem .5rem;
            border-radius: 4px;
            letter-spacing: .06em;
            text-transform: uppercase;
            margin: .1rem .35rem .6rem 0;
            border: 1px dashed;
        }
        .badge::before{
            content: "";
            width: 5px; height: 5px; border-radius: 50%;
            background: currentColor;
        }
        .badge-verified{ background: rgba(0,194,168,.08); color: var(--teal); border-color: rgba(0,194,168,.4); }
        .badge-estimate{ background: rgba(255,179,0,.08); color: var(--amber); border-color: rgba(255,179,0,.4); }
        .badge-unavailable{ background: rgba(255,90,90,.08); color: var(--red); border-color: rgba(255,90,90,.4); }

        /* ---------- panel top accent bars ---------- */
        .panel-topbar{
            height: 3px;
            margin: -1rem -1rem 1rem -1rem;
            border-radius: 11px 11px 0 0;
        }
        .panel-topbar.teal{ background: linear-gradient(90deg, var(--teal), transparent 130%); box-shadow: 0 0 14px -2px var(--teal); }
        .panel-topbar.amber{ background: linear-gradient(90deg, var(--amber), transparent 130%); box-shadow: 0 0 14px -2px var(--amber); }

        /* ---------- readout / ledger digits ---------- */
        .readout-panel{
            background:
                linear-gradient(180deg, var(--bg-panel-3), var(--bg-panel-2));
            border: 1px solid var(--border);
            border-radius: 11px;
            padding: 1.1rem 1.3rem;
            display: flex;
            flex-wrap: wrap;
            gap: 1.8rem;
            margin-bottom: .9rem;
            position: relative;
        }
        .readout-item{ text-align: center; }
        .readout-value{
            font-family: var(--font-mono);
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--text-primary);
            font-variant-numeric: tabular-nums;
        }
        .readout-value.avg{
            font-size: 2.1rem;
            color: var(--teal);
            text-shadow: 0 0 22px rgba(0,194,168,.4);
        }
        .readout-label{
            color: var(--text-secondary);
            font-size: .64rem;
            text-transform: uppercase;
            letter-spacing: .09em;
            margin-top: .2rem;
            font-family: var(--font-mono);
        }

        /* ---------- login ---------- */
        .login-hero{
            background:
                radial-gradient(ellipse 500px 300px at 30% 0%, rgba(0,194,168,.14), transparent 65%),
                radial-gradient(ellipse 500px 300px at 90% 100%, rgba(255,179,0,.10), transparent 60%),
                linear-gradient(180deg, var(--bg-panel), #0d0f13);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2.2rem 2rem;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .login-hero .eyebrow{
            font-family: var(--font-mono);
            font-size: .68rem;
            letter-spacing: .18em;
            text-transform: uppercase;
            color: var(--teal);
            margin-bottom: .6rem;
        }
        .login-hero h2{
            font-size: 1.7rem !important;
            text-transform: none !important;
            letter-spacing: -.01em !important;
            color: var(--text-primary) !important;
            margin: 0 0 .7rem 0;
        }
        .login-hero p{
            color: var(--text-secondary);
            font-size: .92rem;
            line-height: 1.55;
            max-width: 34ch;
        }
        .login-hero .stat-row{
            display: flex;
            gap: 1.6rem;
            margin-top: 1.6rem;
            padding-top: 1.4rem;
            border-top: 1px solid var(--border);
        }
        .login-hero .stat-num{
            font-family: var(--font-mono);
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--amber);
        }
        .login-hero .stat-lbl{
            font-size: .64rem;
            color: var(--text-tertiary);
            text-transform: uppercase;
            letter-spacing: .07em;
        }

        .login-card [data-baseweb="tab-list"]{ gap: .4rem; border-bottom: 1px solid var(--border); }
        .login-card [data-baseweb="tab"]{
            text-transform: uppercase;
            font-size: .74rem;
            letter-spacing: .06em;
            color: var(--text-secondary);
            font-family: var(--font-mono);
        }
        .login-card [aria-selected="true"]{ color: var(--teal) !important; }
        .login-card [data-baseweb="tab-highlight"]{ background-color: var(--teal) !important; }

        .login-card{
            background: linear-gradient(180deg, var(--bg-panel), #101216);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.8rem 1.8rem .5rem 1.8rem;
            box-shadow: 0 24px 48px -28px rgba(0,0,0,.75);
            position: relative;
            overflow: hidden;
        }
        .login-card::before{
            content:""; position:absolute; top:0; left:0; right:0; height:3px;
            background: linear-gradient(90deg, var(--teal), var(--amber));
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(subtitle="Say a lane, get a rate."):
    st.markdown(
        f"""
        <div class="app-header">
            <div class="eyebrow">Dispatch Terminal</div>
            <h1>Line&nbsp;Haul Voice Lookup</h1>
            <div class="sub">{subtitle}</div>
            <div class="route-strip">
                <span class="stop">ORIGIN</span>
                <span class="dot"></span>
                <div class="track"><span class="runner">🚚</span></div>
                <span class="dot end"></span>
                <span class="stop">DESTINATION</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text, kind="estimate"):
    st.markdown(f'<span class="badge badge-{kind}">{text}</span>', unsafe_allow_html=True)


def panel_topbar(kind="teal"):
    st.markdown(f'<div class="panel-topbar {kind}"></div>', unsafe_allow_html=True)


inject_css()


def load_json_cache(path):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_json_cache(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


if "geocode_cache" not in st.session_state:
    st.session_state.geocode_cache = load_json_cache(GEOCODE_CACHE_PATH)
if "distance_cache" not in st.session_state:
    st.session_state.distance_cache = load_json_cache(DISTANCE_CACHE_PATH)
if "trigger" not in st.session_state:
    st.session_state.trigger = 0
if "last_run_trigger" not in st.session_state:
    st.session_state.last_run_trigger = -1
if "audio_hash" not in st.session_state:
    st.session_state.audio_hash = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "geocode_failed_this_session" not in st.session_state:
    st.session_state.geocode_failed_this_session = set()


def get_credentials_table():
    creds = st.secrets.get("credentials", None)
    if not creds:
        return DEFAULT_CREDENTIALS
    return creds


def using_default_credentials():
    return not st.secrets.get("credentials", None)


def load_users():
    return load_json_cache(USERS_STORE_PATH)


def save_users(users):
    save_json_cache(USERS_STORE_PATH, users)


def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return salt, digest


def register_user(name, email, password):
    users = load_users()
    key = email.strip().lower()
    salt, digest = hash_password(password)
    users[key] = {
        "name": name.strip(),
        "email": email.strip(),
        "salt": salt,
        "hash": digest,
    }
    save_users(users)


def verify_registered_user(email, password):
    users = load_users()
    record = users.get(email.strip().lower())
    if not record:
        return None
    _, digest = hash_password(password, record.get("salt", ""))
    if digest == record.get("hash"):
        return record.get("name") or record.get("email")
    return None


def authenticate(identifier, password):
    if not identifier or not password:
        return None

    display_name = verify_registered_user(identifier, password)
    if display_name:
        return display_name

    creds = get_credentials_table()
    if identifier in creds and str(creds[identifier]) == password:
        return identifier

    return None


def render_login_page():
    st.markdown(
        """
        <div class="app-header">
            <div class="eyebrow">Dispatch Terminal</div>
            <h1>Line&nbsp;Haul Voice Lookup</h1>
            <div class="sub">Sign in to continue.</div>
        </div>
        <div class="hazard-rule"></div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    hero, form = st.columns([1, 1], gap="large")
    with hero:
        st.markdown(
            """
            <div class="login-hero">
                <div class="eyebrow">Say a lane. Get a rate.</div>
                <h2>Voice in, verified rate out.</h2>
                <p>Speak an origin and destination. The terminal checks your own
                shipment history first — and only reaches for an AI estimate
                when no verified record exists.</p>
                <div class="route-strip">
                    <span class="stop">ORIGIN</span>
                    <span class="dot"></span>
                    <div class="track"><span class="runner">🚚</span></div>
                    <span class="dot end"></span>
                    <span class="stop">DEST</span>
                </div>
                <div class="stat-row">
                    <div>
                        <div class="stat-num">DB</div>
                        <div class="stat-lbl">Verified first</div>
                    </div>
                    <div>
                        <div class="stat-num">AI</div>
                        <div class="stat-lbl">Fallback estimate</div>
                    </div>
                    <div>
                        <div class="stat-num">Live</div>
                        <div class="stat-lbl">Route + weather</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with form:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        tab_signin, tab_signup = st.tabs(["Sign In", "Create Account"])

        with tab_signin:
            if using_default_credentials():
                st.caption(
                    "No `[credentials]` table in secrets — the demo login "
                    "`admin` / `trucker2026` also works."
                )
            with st.form("login_form"):
                identifier = st.text_input("Email or Username")
                signin_password = st.text_input("Password", type="password", key="signin_password")
                signin_submitted = st.form_submit_button("Sign In")

        with tab_signup:
            st.caption(
                "Creates an account stored locally in `users.json` with a "
                "hashed password. This is a lightweight store, not a "
                "production auth system — it can reset if the app's storage "
                "is wiped on redeploy."
            )
            with st.form("signup_form"):
                new_name = st.text_input("Full Name")
                new_email = st.text_input("Email")
                new_password = st.text_input("Password", type="password", key="signup_password")
                confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm")
                signup_submitted = st.form_submit_button("Create Account")

        st.markdown("</div>", unsafe_allow_html=True)

    if signin_submitted:
        display_name = authenticate(identifier, signin_password)
        if display_name:
            st.session_state.authenticated = True
            st.session_state.username = display_name
            st.rerun()
        else:
            with form:
                st.markdown(
                    '<div class="badge badge-unavailable">'
                    "Incorrect email/username or password</div>",
                    unsafe_allow_html=True,
                )

    if signup_submitted:
        error = None
        if not new_name.strip() or not new_email.strip() or not new_password:
            error = "Please fill in all fields."
        elif "@" not in new_email or "." not in new_email.split("@")[-1]:
            error = "Enter a valid email address."
        elif new_password != confirm_password:
            error = "Passwords don't match."
        elif len(new_password) < 6:
            error = "Password should be at least 6 characters."
        elif new_email.strip().lower() in load_users():
            error = "An account with that email already exists — sign in instead."

        if error:
            with form:
                st.markdown(
                    f'<div class="badge badge-unavailable">{error}</div>',
                    unsafe_allow_html=True,
                )
        else:
            register_user(new_name, new_email, new_password)
            st.session_state.authenticated = True
            st.session_state.username = new_name.strip()
            st.rerun()


if not st.session_state.authenticated:
    render_login_page()
    st.stop()


with st.sidebar:
    badge(f"{st.session_state.username}", kind="verified")
    if st.button("Log out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()
    st.divider()
    st.header("Settings")
    default_api_key = st.secrets.get("OPENAI_API_KEY", "")
    if default_api_key:
        openai_api_key = default_api_key
        badge("OpenAI key loaded from secrets", kind="verified")
    else:
        openai_api_key = st.text_input(
            "OpenAI API Key",
            value="",
            type="password",
            help="Not found in secrets — enter one for this session only.",
    )

    st.divider()
    st.subheader("Load Details")
    st.caption("Used only if no exact historical lane match is found.")
    pickup_date = st.date_input("Pickup Date", value=date.today())
    equipment = st.selectbox("Equipment", ["Dry Van", "Reefer", "Flatbed", "Other"])
    trailer_length = st.text_input("Trailer Length", value="53ft")
    weight = st.text_input("Weight", value="")
    commodity = st.text_input("Commodity", value="")
    stops = st.number_input("Number of Stops", min_value=1, value=1, step=1)
    special_requirements = st.text_input("Special Requirements (optional)", value="")


render_header()
st.markdown('<div class="hazard-rule"></div>', unsafe_allow_html=True)
st.write("")
st.write("Press the microphone button and say a lane like **'Sayreville to Boston'**.")

st.markdown(
    """
    <div class="record-panel">
        <div class="rec-label">● Awaiting Voice Input</div>
        <div class="rec-ring"></div>
    """,
    unsafe_allow_html=True,
)
audio_bytes = audio_recorder(text="Click to record", icon_size="2x")
st.markdown("</div>", unsafe_allow_html=True)


def get_connection():
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        port=st.secrets.get("DB_PORT", "5432"),
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        sslmode="require"
    )


def get_openai_client(api_key):
    return OpenAI(api_key=api_key)


def to_number(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s.upper() == "EMPTY":
        return None
    s = s.replace("$", "").replace(",", "").replace("%", "")
    try:
        return float(s)
    except ValueError:
        return None


def safe_get(row_tuple, index):
    if isinstance(row_tuple, (tuple, list)) and len(row_tuple) > index:
        return row_tuple[index]
    return None


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "LineHaulVoiceLookup/1.0 (contact: shauryashah00@gmail.com)"}
_last_nominatim_call = {"t": 0.0}


def _nominatim_get(params, max_retries=3):
    for attempt in range(max_retries):
        elapsed = time.time() - _last_nominatim_call["t"]
        wait = 1.1 - elapsed
        if wait > 0:
            time.sleep(wait)
        try:
            resp = requests.get(NOMINATIM_URL, params=params, headers=NOMINATIM_HEADERS, timeout=8)
        finally:
            _last_nominatim_call["t"] = time.time()

        if resp.status_code == 429:
            time.sleep(2 * (attempt + 1))
            continue
        return resp
    return resp


def get_geo_info(city_name, debug=False):
    cache = st.session_state.geocode_cache
    if city_name in cache:
        val = cache[city_name]
        if val:
            if isinstance(val, dict):
                return val
            return {"lon": val[0], "lat": val[1], "state": None}

    if city_name in st.session_state.geocode_failed_this_session:
        return None

    try:
        query_str = city_name if "USA" in city_name.upper() else f"{city_name}, USA"
        params = {"q": query_str, "format": "json", "limit": 1, "addressdetails": 1}
        resp = _nominatim_get(params)

        if resp.status_code != 200:
            if debug:
                st.caption(f"Geocoding '{city_name}' failed: HTTP {resp.status_code}")
            st.session_state.geocode_failed_this_session.add(city_name)
            return None

        data = resp.json()
        if data:
            lon = float(data[0]["lon"])
            lat = float(data[0]["lat"])
            state = data[0].get("address", {}).get("state")
            info = {"lon": lon, "lat": lat, "state": state}
            cache[city_name] = info
            save_json_cache(GEOCODE_CACHE_PATH, cache)
            return info
        else:
            if debug:
                st.caption(f"Geocoding '{city_name}': no results for \"{query_str}\".")
            st.session_state.geocode_failed_this_session.add(city_name)
            return None
    except Exception as e:
        if debug:
            st.caption(f"Geocoding '{city_name}' raised an exception: {e}")
        st.session_state.geocode_failed_this_session.add(city_name)
        return None


def get_route_info(origin, destination, origin_geo=None, dest_geo=None, debug=False):
    cache = st.session_state.distance_cache
    key = f"{origin}|||{destination}"
    if key in cache:
        cached = cache[key]
        if isinstance(cached, dict) and cached.get("km"):
            return cached

    orig_geo = origin_geo or get_geo_info(origin, debug=debug)
    dest_geo = dest_geo or get_geo_info(destination, debug=debug)
    if not orig_geo or not dest_geo:
        return None

    try:
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{orig_geo['lon']},{orig_geo['lat']};{dest_geo['lon']},{dest_geo['lat']}?overview=false"
        )
        resp = requests.get(url, timeout=8)
        time.sleep(0.3)

        if resp.status_code != 200:
            if debug:
                st.caption(f"Routing failed: HTTP {resp.status_code}")
            return None

        data = resp.json()
        if data and data.get("routes"):
            route = data["routes"][0]
            info = {
                "km": round(route["distance"] / 1000, 1),
                "hours": round(route["duration"] / 3600, 1),
            }
            cache[key] = info
            save_json_cache(DISTANCE_CACHE_PATH, cache)
            return info
        else:
            if debug:
                st.caption("Routing: OSRM returned no route.")
            return None
    except Exception as e:
        if debug:
            st.caption(f"Routing raised an exception: {e}")
        return None


def get_weather(lat, lon):
    try:
        api_key = st.secrets.get("OPENWEATHER_KEY", "")
        if not api_key:
            return {"description": "API Key Missing", "temp_c": "N/A", "windspeed_kmh": "N/A"}

        url = (
            f"https://api.openweathermap.org/data/2.5/weather?"
            f"lat={lat}&lon={lon}&appid={api_key}&units=metric"
        )
        resp = requests.get(url, timeout=5)

        if resp.status_code != 200:
            return None

        data = resp.json()
        temp = data.get("main", {}).get("temp")
        wind = data.get("wind", {}).get("speed")
        desc = data.get("weather", [{}])[0].get("description", "Unknown")
        wind_kmh = round(wind * 3.6, 1) if wind else "N/A"
        temp_rounded = round(temp, 1) if temp else "N/A"

        return {
            "temp_c": temp_rounded,
            "windspeed_kmh": wind_kmh,
            "description": str(desc).title()
        }
    except Exception:
        return None


def transcribe_audio(client, audio_bytes):
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.wav"
    transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
    return transcript.text


def parse_lane_text(client, lane_text):
    prompt = (
        f"The following text describes a shipment lane, in the format "
        f"'CityA to CityB': \"{lane_text}\". "
        "Treat the first city mentioned as the ORIGIN and the second city "
        "mentioned as the DESTINATION. Only extract the city names exactly as "
        "written — do NOT guess or add a state. Respond with ONLY raw JSON, no "
        "markdown, no code fences, in this exact shape: "
        '{"origin": "CityName", "destination": "CityName"}'
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content.strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def get_known_cities():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f'''
                SELECT "{COL_ORIGIN}" FROM "{TABLE_NAME}"
                UNION
                SELECT "{COL_DEST}" FROM "{TABLE_NAME}"
            ''')
            rows = cur.fetchall()
        cities = set()
        for r in rows:
            val = safe_get(r, 0)
            if val:
                city_part = str(val).split(",")[0].strip()
                if city_part:
                    cities.add(city_part)
        return cities
    finally:
        conn.close()


def correct_city(heard_name, known_cities):
    if not heard_name:
        return None
    for c in known_cities:
        if c.lower() == heard_name.lower():
            return c
    matches = difflib.get_close_matches(heard_name, list(known_cities), n=1, cutoff=0.4)
    return matches[0] if matches else None


def rows_to_records(rows):
    results = []
    for r in rows:
        results.append({
            "Origin": safe_get(r, 0),
            "Destination": safe_get(r, 1),
            "Ship Date": safe_get(r, 2),
            "Line Haul": to_number(safe_get(r, 3)),
            "Additional Charges": to_number(safe_get(r, 4)),
            "Carrier Pay": to_number(safe_get(r, 5)),
            "Net Profit": to_number(safe_get(r, 6)),
            "%": to_number(safe_get(r, 7)),
        })
    return results


def query_shipment_details(origin_city, destination_city):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            safe_pct_col = COL_PCT.replace("%", "%%")
            query = f'''
                SELECT "{COL_ORIGIN}", "{COL_DEST}", "{COL_SHIP_DATE}",
                       "{COL_LINE_HAUL}", "{COL_ADDL_CHARGES}",
                       "{COL_CARRIER_PAY}", "{COL_NET_PROFIT}", "{safe_pct_col}"
                FROM "{TABLE_NAME}"
                WHERE "{COL_ORIGIN}" ILIKE %s
                  AND "{COL_DEST}" ILIKE %s
                ORDER BY "{COL_SHIP_DATE}" DESC
            '''
            cur.execute(query, (f"{origin_city}%", f"{destination_city}%"))
            rows = cur.fetchall()
    finally:
        conn.close()
    return rows_to_records(rows)


def query_state_to_state_details(origin_state_abbr, dest_state_abbr, limit=25):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            safe_pct_col = COL_PCT.replace("%", "%%")
            query = f'''
                SELECT "{COL_ORIGIN}", "{COL_DEST}", "{COL_SHIP_DATE}",
                       "{COL_LINE_HAUL}", "{COL_ADDL_CHARGES}",
                       "{COL_CARRIER_PAY}", "{COL_NET_PROFIT}", "{safe_pct_col}"
                FROM "{TABLE_NAME}"
                WHERE "{COL_ORIGIN}" ILIKE %s
                  AND "{COL_DEST}" ILIKE %s
                ORDER BY "{COL_SHIP_DATE}" DESC
                LIMIT %s
            '''
            cur.execute(query, (f"%, {origin_state_abbr}", f"%, {dest_state_abbr}", limit))
            rows = cur.fetchall()
    finally:
        conn.close()
    return rows_to_records(rows)


def get_comparable_loads(origin_city, destination_city, limit=5):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            query = f'''
                SELECT "{COL_ORIGIN}", "{COL_DEST}", "{COL_SHIP_DATE}", "{COL_LINE_HAUL}"
                FROM "{TABLE_NAME}"
                WHERE "{COL_ORIGIN}" ILIKE %s OR "{COL_DEST}" ILIKE %s
                ORDER BY "{COL_SHIP_DATE}" DESC
                LIMIT %s
            '''
            cur.execute(query, (f"{origin_city}%", f"{destination_city}%", limit))
            rows = cur.fetchall()
        results = []
        for r in rows:
            results.append({
                "Origin": safe_get(r, 0),
                "Destination": safe_get(r, 1),
                "Ship Date": safe_get(r, 2),
                "Line Haul": to_number(safe_get(r, 3)),
            })
        return results
    finally:
        conn.close()


def render_shipment_table(details, heading, badge_text="Verified — Your Database", badge_kind="verified"):
    panel_topbar("teal" if badge_kind == "verified" else "amber")
    badge(badge_text, kind=badge_kind)
    st.subheader(heading)

    valid_rates = [d["Line Haul"] for d in details if d["Line Haul"] is not None]
    avg_rate = statistics.mean(valid_rates) if valid_rates else None

    if avg_rate is not None:
        st.markdown(
            f"""
            <div class="readout-panel" style="justify-content:flex-start;">
                <div class="readout-item">
                    <div class="readout-value avg">${avg_rate:,.0f}</div>
                    <div class="readout-label">Avg Line Haul · {len(details)} shipment(s)</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    df = pd.DataFrame(details)
    display_df = df[[
        "Origin", "Destination", "Ship Date", "Line Haul", "Additional Charges",
        "Carrier Pay", "Net Profit", "%",
    ]].copy()

    for col in ["Line Haul", "Additional Charges", "Carrier Pay", "Net Profit"]:
        display_df[col] = display_df[col].apply(
            lambda v: f"${v:,.0f}" if pd.notnull(v) else "—"
        )
    display_df["%"] = display_df["%"].apply(
        lambda v: f"{v:.1f}%" if pd.notnull(v) else "—"
    )

    st.dataframe(display_df, use_container_width=True, hide_index=True)


def build_expert_prompt(origin, destination, load_details, route_info,
                         origin_weather, dest_weather, comparable_loads):
    real_data_lines = []

    if route_info:
        miles = route_info["km"] * 0.621371
        real_data_lines.append(
            f"- Exact driving distance: {route_info['km']:,.1f} km ({miles:,.1f} miles)"
        )
        real_data_lines.append(f"- Estimated driving time: {route_info['hours']:.1f} hours")
    else:
        real_data_lines.append("- Driving distance: NOT AVAILABLE (could not route this lane)")

    if origin_weather:
        real_data_lines.append(
            f"- Current weather at origin ({origin}): {origin_weather['description']}, "
            f"{origin_weather['temp_c']}\u00b0C, wind {origin_weather['windspeed_kmh']} km/h"
        )
    else:
        real_data_lines.append(f"- Current weather at origin ({origin}): NOT AVAILABLE")

    if dest_weather:
        real_data_lines.append(
            f"- Current weather at destination ({destination}): {dest_weather['description']}, "
            f"{dest_weather['temp_c']}\u00b0C, wind {dest_weather['windspeed_kmh']} km/h"
        )
    else:
        real_data_lines.append(f"- Current weather at destination ({destination}): NOT AVAILABLE")

    if comparable_loads:
        real_data_lines.append(
            "- Comparable loads from YOUR OWN historical database (real data, "
            "sharing this origin or destination):"
        )
        for cl in comparable_loads:
            rate_str = f"${cl['Line Haul']:,.0f}" if cl["Line Haul"] is not None else "unknown rate"
            real_data_lines.append(
                f"    * {cl['Ship Date']}: {cl['Origin']} -> {cl['Destination']}, "
                f"Line Haul {rate_str} (source: your shipmentsdb)"
            )
    else:
        real_data_lines.append("- Comparable loads from your historical database: NONE FOUND")

    real_data_block = "\n".join(real_data_lines)

    return f"""You are an expert freight pricing analyst.

==========================
DATA HONESTY RULES (CRITICAL)
==========================
You do NOT have live internet access, and you are NOT connected to DAT, Truckstop.com,
SONAR, EIA, or any other live market data service. The only real, verified data you have
is in the "REAL DATA PROVIDED" section below.

For ANY factor in the research list that is not covered by REAL DATA PROVIDED, you MUST NOT
invent a specific statistic, number, or source. Instead write "Not available — no live data
source connected for this factor," or clearly label a qualitative judgment as "General
industry expectation (not live-verified)." Do not cite DAT, Truckstop, SONAR, or any other
source unless it was explicitly given to you below — you cannot actually access them.

==========================
REAL DATA PROVIDED
==========================
{real_data_block}

==========================
LOAD INFORMATION
==========================
Origin: {origin}
Destination: {destination}
Pickup Date: {load_details['pickup_date']}
Equipment: {load_details['equipment']}
Trailer Length: {load_details['trailer_length']}
Weight: {load_details['weight'] or 'Not specified'}
Commodity: {load_details['commodity'] or 'Not specified'}
Number of Stops: {load_details['stops']}
Special Requirements: {load_details['special_requirements'] or 'None specified'}

==========================
RESEARCH
==========================
Using ONLY the REAL DATA PROVIDED for anything factual, and clearly flagging everything
else as unavailable or a general estimate (per the Data Honesty Rules), address each of:

1. Distance — exact driving distance and estimated driving hours
2. Lane Analysis — volume, historical average rate, seasonal rate, volatility
3. Supply and Demand — load-to-truck ratio, truck availability, freight demand
4. Deadhead — estimated deadhead to pickup, ease of finding a reload after delivery
5. Fuel — national diesel price, origin-state diesel price, estimated fuel cost
6. Market Conditions — spot vs contract trend, recession/boom indicators
7. Weather — conditions along the route, severe weather risk, road closures
8. Terrain — mountain driving, elevation change, traffic corridors, tolls
9. Seasonal Factors — produce season, holiday demand, construction, retail season
10. Commodity Analysis — typical rates for this commodity, theft risk, insurance, handling
11. Equipment Availability — dry van/reefer/flatbed availability, specialized demand
12. Pickup and Delivery — appointment freight, live load, drop trailer, detention risk
13. Economic Indicators — manufacturing, import/export activity, port congestion
14. Carrier Operating Costs — fuel, wages, insurance, maintenance, tires, depreciation,
    permits, tolls, and expected profit margin
15. Comparable Loads — use ONLY the comparable loads listed above; do not invent more

==========================
ANALYSIS
==========================
Score every pricing factor from -5 (significantly decreases price) to +5 (significantly
increases price), with a brief reason, then rank all factors from most to least influential.

==========================
PREDICTION
==========================
Estimate the fair TOTAL LINE HAUL RATE for this load — the flat total dollar amount a
broker would actually quote/pay a carrier for this specific lane.

==========================
OUTPUT FORMAT
==========================
1. Executive Summary
2. Lane Overview
3. Market Conditions
4. Weather & Fuel
5. Supply vs Demand
6. Comparable Loads
7. Carrier Cost Breakdown
8. Pricing Factors Ranked
9. Final Rate Prediction
10. Confidence Score

==========================
REQUIRED FIRST LINE
==========================
Before anything else, output ONE line containing ONLY raw JSON:
{{"low_rate": <number>, "avg_rate": <number>, "high_rate": <number>, "confidence_pct": <number>}}

Then on the next line write exactly: ---
Then continue with the full report in the OUTPUT FORMAT above."""


def get_ai_expert_rate_prediction(client, origin, destination, load_details):
    panel_topbar("amber")
    badge("AI Estimate", kind="estimate")
    st.subheader("Expert Freight Pricing Analysis")

    with st.spinner("Calculating real route distance..."):
        origin_geo = get_geo_info(origin, debug=True)
        dest_geo = get_geo_info(destination, debug=True)
        route_info = get_route_info(origin, destination, origin_geo=origin_geo, dest_geo=dest_geo, debug=True)

    if route_info:
        miles = route_info["km"] * 0.621371
        badge("Verified route", kind="verified")
        d1, d2 = st.columns(2)
        d1.metric("Distance", f"{route_info['km']:,.1f} km", f"{miles:,.1f} mi")
        d2.metric("Est. Driving Time", f"{route_info['hours']:.1f} hrs")
    else:
        badge("Route unavailable", kind="unavailable")
        st.warning("Could not calculate driving distance for this lane (geocoding failed).")

    with st.spinner("Checking live weather..."):
        origin_weather = get_weather(origin_geo["lat"], origin_geo["lon"]) if origin_geo else None
        dest_weather = get_weather(dest_geo["lat"], dest_geo["lon"]) if dest_geo else None

    wcol1, wcol2 = st.columns(2)
    with wcol1:
        if origin_weather:
            badge("Live weather", kind="verified")
            st.caption(
                f"**{origin}** — {origin_weather['description']}, "
                f"{origin_weather['temp_c']}°C, wind {origin_weather['windspeed_kmh']} km/h"
            )
        else:
            badge("Unavailable", kind="unavailable")
            st.caption(f"**{origin}** — no live weather data")
    with wcol2:
        if dest_weather:
            badge("Live weather", kind="verified")
            st.caption(
                f"**{destination}** — {dest_weather['description']}, "
                f"{dest_weather['temp_c']}°C, wind {dest_weather['windspeed_kmh']} km/h"
            )
        else:
            badge("Unavailable", kind="unavailable")
            st.caption(f"**{destination}** — no live weather data")

    with st.spinner("Pulling comparable loads from your database..."):
        try:
            comparable_loads = get_comparable_loads(origin, destination)
        except Exception:
            comparable_loads = []

    prompt = build_expert_prompt(
        origin, destination, load_details, route_info,
        origin_weather, dest_weather, comparable_loads,
    )

    with st.spinner("Running expert pricing analysis..."):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2500,
            )
            full_text = response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"Expert analysis failed: {e}")
            return

    summary = None
    report_text = full_text
    lines = full_text.split("\n", 1)
    if lines:
        first_line = lines[0].strip()
        first_line = re.sub(r"^```(json)?|```$", "", first_line).strip()
        try:
            summary = json.loads(first_line)
            rest = lines[1] if len(lines) > 1 else ""
            rest = rest.lstrip()
            if rest.startswith("---"):
                rest = rest[3:].lstrip("\n")
            report_text = rest
        except Exception:
            summary = None

    if summary:
        st.markdown("#### Quick Estimate")
        low = summary.get("low_rate", 0) or 0
        avg = summary.get("avg_rate", 0) or 0
        high = summary.get("high_rate", 0) or 0
        conf = summary.get("confidence_pct", 0) or 0
        st.markdown(
            f"""
            <div class="readout-panel">
                <div class="readout-item">
                    <div class="readout-value">${low:,.0f}</div>
                    <div class="readout-label">Low</div>
                </div>
                <div class="readout-item">
                    <div class="readout-value avg">${avg:,.0f}</div>
                    <div class="readout-label">Average</div>
                </div>
                <div class="readout-item">
                    <div class="readout-value">${high:,.0f}</div>
                    <div class="readout-label">High</div>
                </div>
                <div class="readout-item">
                    <div class="readout-value" style="color:var(--ok);">{conf:.0f}%</div>
                    <div class="readout-label">Confidence</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

    st.markdown(report_text)


def try_state_level_fallback(origin_text, destination_text):
    origin_geo = get_geo_info(origin_text, debug=False)
    dest_geo = get_geo_info(destination_text, debug=False)

    origin_state = origin_geo.get("state") if origin_geo else None
    dest_state = dest_geo.get("state") if dest_geo else None

    origin_abbr = US_STATE_ABBR.get(origin_state.strip().lower()) if origin_state else None
    dest_abbr = US_STATE_ABBR.get(dest_state.strip().lower()) if dest_state else None

    if not origin_abbr or not dest_abbr:
        return None, None, None

    try:
        state_details = query_state_to_state_details(origin_abbr, dest_abbr)
    except Exception:
        state_details = []

    return state_details, origin_abbr, dest_abbr


def run_pipeline(client, lane_text, load_details):
    try:
        parsed = parse_lane_text(client, lane_text)
    except Exception as e:
        st.error(f"Parsing failed: {e}")
        return

    with st.spinner("Checking cities against database..."):
        try:
            known_cities = get_known_cities()
        except Exception as e:
            st.error(f"Database connection error: {e}\n\nTraceback: {traceback.format_exc()}")
            return

    origin_corrected = correct_city(parsed["origin"], known_cities)
    destination_corrected = correct_city(parsed["destination"], known_cities)

    problems = []
    if not origin_corrected:
        problems.append(f"Origin city \"{parsed['origin']}\"")
    if not destination_corrected:
        problems.append(f"Destination city \"{parsed['destination']}\"")

    if problems:
        st.warning(
            f"Couldn't find past shipments containing {', '.join(problems)} "
            "in your database. Looking for state-to-state comparable loads..."
        )
        with st.spinner("Searching for comparable state-to-state shipments..."):
            state_details, origin_abbr, dest_abbr = try_state_level_fallback(
                parsed["origin"], parsed["destination"]
            )

        col_hist, col_ai = st.columns([2, 1], gap="large")
        with col_hist:
            with st.container(border=True):
                if state_details:
                    render_shipment_table(
                        state_details,
                        f"Comparable Shipments: {origin_abbr} → {dest_abbr}",
                        badge_text="Verified — Same State-to-State",
                        badge_kind="verified",
                    )
                else:
                    panel_topbar("teal")
                    badge("No comparable data", kind="unavailable")
                    st.write("No comparable state-to-state shipments were found in your database.")

        with col_ai:
            with st.container(border=True):
                get_ai_expert_rate_prediction(client, parsed["origin"], parsed["destination"], load_details)
        return

    with st.spinner("Searching shipmentsdb..."):
        try:
            details = query_shipment_details(origin_corrected, destination_corrected)
        except Exception as e:
            st.error(f"Database query error: {e}\n\nTraceback: {traceback.format_exc()}")
            return

    if not details:
        st.warning("No historical records found for this specific lane. Looking for state-to-state comparable loads...")
        with st.spinner("Searching for comparable state-to-state shipments..."):
            state_details, origin_abbr, dest_abbr = try_state_level_fallback(
                origin_corrected, destination_corrected
            )

        col_hist, col_ai = st.columns([2, 1], gap="large")
        with col_hist:
            with st.container(border=True):
                if state_details:
                    render_shipment_table(
                        state_details,
                        f"Comparable Shipments: {origin_abbr} → {dest_abbr}",
                        badge_text="Verified — Same State-to-State",
                        badge_kind="verified",
                    )
                else:
                    panel_topbar("teal")
                    badge("No comparable data", kind="unavailable")
                    st.write("No comparable state-to-state shipments were found in your database.")

        with col_ai:
            with st.container(border=True):
                get_ai_expert_rate_prediction(client, origin_corrected, destination_corrected, load_details)
        return

    col_hist, col_ai = st.columns([2, 1], gap="large")

    distinct_origins = sorted({d["Origin"] for d in details if d["Origin"]})
    distinct_destinations = sorted({d["Destination"] for d in details if d["Destination"]})

    geo_origin = distinct_origins[0] if distinct_origins else parsed["origin"]
    geo_destination = distinct_destinations[0] if distinct_destinations else parsed["destination"]

    with col_hist:
        with st.container(border=True):
            render_shipment_table(
                details,
                "Historical Matched Lane",
                badge_text="Verified — Your Database",
                badge_kind="verified",
            )

    with col_ai:
        with st.container(border=True):
            get_ai_expert_rate_prediction(client, geo_origin, geo_destination, load_details)


if audio_bytes:
    st.audio(audio_bytes, format="audio/wav")

    if not openai_api_key:
        st.warning("Enter your OpenAI API key in the sidebar first.")
    else:
        client = get_openai_client(openai_api_key)
        audio_hash = hashlib.md5(audio_bytes).hexdigest()

        if st.session_state.audio_hash != audio_hash:
            with st.spinner("Transcribing..."):
                try:
                    st.session_state["lane_text_box"] = transcribe_audio(client, audio_bytes)
                except Exception as e:
                    st.error(f"Transcription failed: {e}")
                    st.session_state["lane_text_box"] = ""
            st.session_state.audio_hash = audio_hash
            st.session_state.trigger += 1

        st.subheader("What I heard")
        st.caption("If this is wrong, edit it below and click Reprocess.")
        edited_text = st.text_input(
            "Transcribed lane",
            key="lane_text_box",
            label_visibility="collapsed",
        )

        if st.button("Reprocess"):
            st.session_state.trigger += 1

        if st.session_state.trigger != st.session_state.last_run_trigger:
            st.session_state.last_run_trigger = st.session_state.trigger
            if edited_text.strip():
                load_details = {
                    "pickup_date": pickup_date,
                    "equipment": equipment,
                    "trailer_length": trailer_length,
                    "weight": weight,
                    "commodity": commodity,
                    "stops": stops,
                    "special_requirements": special_requirements,
                }
                run_pipeline(client, edited_text, load_details)
            else:
                st.warning("No text to process.")