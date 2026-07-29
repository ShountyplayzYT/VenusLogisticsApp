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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap');

        :root{
            --bg-page:#0f1115;
            --bg-panel:#161920;
            --bg-panel-2:#1d212a;
            --border:#2a2f3a;
            --text-primary:#e8eaed;
            --text-secondary:#8b93a1;
            --accent:#4f7cff;
            --accent-dark:#3d63d1;
            --ok:#3fb27f;
            --warn:#d99a3d;
            --err:#e05a5a;
            --font-body:'Inter', sans-serif;
            --font-mono:'JetBrains Mono', monospace;
        }

        html, body, .stApp{
            background: var(--bg-page) !important;
            color: var(--text-primary) !important;
            font-family: var(--font-body) !important;
        }
        [data-testid="stHeader"]{ background: transparent !important; }
        .block-container{ padding-top: 2rem; max-width: 1200px; }

        h1,h2,h3,h4{ font-family: var(--font-body) !important; font-weight: 600 !important; color: var(--text-primary) !important; }
        p, span, label, .stMarkdown, .stCaption{ color: var(--text-primary); }
        [data-testid="stCaptionContainer"]{ color: var(--text-secondary) !important; }

        [data-testid="stSidebar"]{
            background: var(--bg-panel) !important;
            border-right: 1px solid var(--border);
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3{
            color: var(--text-secondary) !important;
            text-transform: uppercase;
            font-size: .85rem;
            letter-spacing: .06em;
        }

        input, textarea, [data-baseweb="select"] > div{
            background: var(--bg-panel-2) !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border) !important;
            border-radius: 6px !important;
        }
        input:focus{
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 2px rgba(79,124,255,.15) !important;
        }

        .stButton>button, .stFormSubmitButton>button{
            background: var(--accent) !important;
            color: #ffffff !important;
            font-weight: 500 !important;
            border: none !important;
            border-radius: 6px !important;
            padding: .5rem 1.1rem !important;
            transition: background .15s ease;
        }
        .stButton>button:hover, .stFormSubmitButton>button:hover{
            background: var(--accent-dark) !important;
        }

        [data-testid="stMetric"]{
            background: var(--bg-panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: .75rem .9rem;
        }
        [data-testid="stMetricValue"]{ font-family: var(--font-mono) !important; color: var(--text-primary) !important; font-size: 1.25rem !important; }
        [data-testid="stMetricLabel"]{ color: var(--text-secondary) !important; text-transform: uppercase; font-size: .68rem; letter-spacing: .06em; }

        [data-testid="stAlert"]{ background: var(--bg-panel) !important; border-left: 3px solid var(--accent) !important; border-radius: 6px !important; }
        [data-testid="stSpinner"] p{ color: var(--text-secondary) !important; font-family: var(--font-mono); font-size: .85rem; }

        [data-testid="stVerticalBlockBorderWrapper"]{
            background: var(--bg-panel) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
        }

        [data-testid="stDataFrame"]{
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }

        hr{ border-color: var(--border) !important; }

        .app-header{
            border-bottom: 1px solid var(--border);
            padding-bottom: 1rem;
            margin-bottom: 1.5rem;
        }
        .app-header h1{
            margin: 0;
            font-size: 1.5rem;
        }
        .app-header .sub{
            color: var(--text-secondary);
            font-size: .9rem;
            margin-top: .2rem;
        }

        .record-panel{
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1rem;
            text-align: center;
            margin-bottom: 1rem;
        }

        .badge{
            display: inline-block;
            font-family: var(--font-mono);
            font-size: .68rem;
            font-weight: 600;
            padding: .18rem .55rem;
            border-radius: 5px;
            letter-spacing: .02em;
            text-transform: uppercase;
            margin: .1rem .3rem .5rem 0;
        }
        .badge-verified{ background: rgba(63,178,127,.12); color: var(--ok); border: 1px solid rgba(63,178,127,.3); }
        .badge-estimate{ background: rgba(217,154,61,.12); color: var(--warn); border: 1px solid rgba(217,154,61,.3); }
        .badge-unavailable{ background: rgba(224,90,90,.1); color: var(--err); border: 1px solid rgba(224,90,90,.3); }

        .readout-panel{
            background: var(--bg-panel-2);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1rem 1.2rem;
            display: flex;
            flex-wrap: wrap;
            gap: 1.6rem;
            margin-bottom: .8rem;
        }
        .readout-item{ text-align: center; }
        .readout-value{
            font-family: var(--font-mono);
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        .readout-value.avg{
            font-size: 2rem;
            color: var(--accent);
        }
        .readout-label{
            color: var(--text-secondary);
            font-size: .65rem;
            text-transform: uppercase;
            letter-spacing: .08em;
            margin-top: .15rem;
        }

        .login-card [data-baseweb="tab-list"]{ gap: .4rem; border-bottom: 1px solid var(--border); }
        .login-card [data-baseweb="tab"]{
            text-transform: uppercase;
            font-size: .75rem;
            letter-spacing: .04em;
            color: var(--text-secondary);
        }
        .login-card [aria-selected="true"]{ color: var(--accent) !important; }
        .login-card [data-baseweb="tab-highlight"]{ background-color: var(--accent) !important; }

        .login-card{
            background: var(--bg-panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.6rem 1.6rem .4rem 1.6rem;
            margin-top: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(subtitle="Say a lane, get a rate."):
    st.markdown(
        f"""
        <div class="app-header">
            <h1>Line Haul Voice Lookup</h1>
            <div class="sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text, kind="estimate"):
    st.markdown(f'<span class="badge badge-{kind}">{text}</span>', unsafe_allow_html=True)


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
    render_header(subtitle="Sign in to continue.")
    st.write("")

    left, mid, right = st.columns([1, 1.3, 1])
    with mid:
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
            with mid:
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
            with mid:
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
st.write("Press the microphone button and say a lane like **'Sayreville to Boston'**.")

st.markdown('<div class="record-panel">', unsafe_allow_html=True)
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