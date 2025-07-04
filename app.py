import streamlit as st
import os
import json
from datetime import datetime, timedelta
import mimetypes
import humanize
import hashlib
import random
import time

# --- Configuration ---
ROOMS_FILE = "secure_rooms/_room_passwords.json"
OTP_FILE = "secure_rooms/_otp_cache.json"
AUTO_DELETE_HOURS = 12
os.makedirs("secure_rooms", exist_ok=True)

# --- Helpers ---
def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(password, hashed):
    return hash_pw(password) == hashed

def load_room_passwords():
    if not os.path.exists(ROOMS_FILE):
        return {}
    with open(ROOMS_FILE, "r") as f:
        return json.load(f)

def save_room_passwords(data):
    with open(ROOMS_FILE, "w") as f:
        json.dump(data, f)

def load_otps():
    if not os.path.exists(OTP_FILE):
        return {}
    with open(OTP_FILE, "r") as f:
        return json.load(f)

def save_otps(data):
    with open(OTP_FILE, "w") as f:
        json.dump(data, f)

def generate_otp(username):
    otp = str(random.randint(100000, 999999))
    data = load_otps()
    data[username] = {"otp": otp, "timestamp": time.time()}
    save_otps(data)
    return otp

def validate_otp(username, input_otp):
    data = load_otps()
    if username in data:
        entry = data[username]
        if time.time() - entry["timestamp"] > 300:
            return False
        return entry["otp"] == input_otp
    return False

def cleanup_old_files(folder):
    now = datetime.now()
    for fname in os.listdir(folder):
        if fname == "chat.txt":
            continue
        fpath = os.path.join(folder, fname)
        if now - datetime.fromtimestamp(os.path.getmtime(fpath)) > timedelta(hours=AUTO_DELETE_HOURS):
            os.remove(fpath)

# --- Session Initialization ---
for key in ["authenticated", "username", "room", "otp_verified"]:
    if key not in st.session_state:
        st.session_state[key] = ""

# --- Login Portal ---
if not st.session_state.authenticated:
    st.title("🔐 Secure Login Portal (OTP)")
    username = st.text_input("Username")
    room = st.text_input("Room Name")
    password = st.text_input("Room Password", type="password")

    if username and room and password:
        if st.button("Request OTP"):
            otp = generate_otp(username)
            st.info(f"Simulated OTP sent to `{username}`: **{otp}** (valid 5 mins)")

    otp_input = st.text_input("Enter OTP")
    login_btn = st.button("Login / Create Room")

    if login_btn:
        if not username or not room or not password or not otp_input:
            st.warning("All fields are required.")
            st.stop()

        if not validate_otp(username, otp_input):
            st.error("❌ Invalid or expired OTP")
            st.stop()

        room_passwords = load_room_passwords()
        room_path = f"secure_rooms/{room}"
        os.makedirs(room_path, exist_ok=True)

        if room in room_passwords:
            if not check_password(password, room_passwords[room]):
                st.error("❌ Incorrect room password.")
                st.stop()
        else:
            room_passwords[room] = hash_pw(password)
            save_room_passwords(room_passwords)
            st.success(f"✅ New room `{room}` created.")

        st.session_state.authenticated = True
        st.session_state.username = username
        st.session_state.room = room

    else:
        st.stop()

# --- Room Setup ---
room = st.session_state.room
username = st.session_state.username
room_path = f"secure_rooms/{room}"
os.makedirs(room_path, exist_ok=True)

chat_file = os.path.join(room_path, "chat.txt")
if not os.path.exists(chat_file):
    with open(chat_file, "w"): pass

st.title(f"🔒 Private Room: `{room}`")
st.caption(f"Logged in as: `{username}`")

# --- Refresh Button ---
if st.button("🔄 Refresh"):
    pass

# --- Cleanup ---
cleanup_old_files(room_path)

# --- File Upload Section ---
st.header("📁 Upload File")
uploaded_file = st.file_uploader("Choose a file to share", type=None)
if uploaded_file:
    save_path = os.path.join(room_path, uploaded_file.name)
    with open(save_path, "wb") as f:
        f.write(uploaded_file.read())
    st.success(f"✅ File `{uploaded_file.name}` uploaded successfully")

# --- Shared Files Table ---
st.header("📂 Shared Files")
files = [f for f in os.listdir(room_path) if f != "chat.txt"]

if files:
    for fname in files:
        fpath = os.path.join(room_path, fname)
        size = humanize.naturalsize(os.path.getsize(fpath))
        mtype, _ = mimetypes.guess_type(fpath)
        mtype = mtype or "Unknown"
        mod_time = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
        icon = "📄"
        if fname.lower().endswith((".png", ".jpg", ".jpeg")):
            icon = "🖼️"
        elif fname.lower().endswith(".pdf"):
            icon = "📕"
        elif fname.lower().endswith((".zip", ".rar")):
            icon = "🗜️"
        elif fname.lower().endswith((".txt", ".md", ".log", ".py")):
            icon = "📜"

        col1, col2, col3, col4 = st.columns([3, 3, 2, 2])
        with col1:
            st.markdown(f"{icon} **{fname}**")
        with col2:
            st.caption(f"Size: {size}  \nType: {mtype}")
        with col3:
            st.caption(f"Uploaded: {mod_time}")
        with col4:
            with open(fpath, "rb") as f:
                st.download_button("⬇ Download", f, file_name=fname)
else:
    st.info("No files currently shared.")

# --- Chat Section ---
st.header("💬 Chat Room")
with open(chat_file, "r") as f:
    chat = f.read()
st.text_area("Chat Log", value=chat, height=250, disabled=True)

with st.form("chat_form", clear_on_submit=True):
    message = st.text_input("Type your message")
    send_btn = st.form_submit_button("Send")
    if send_btn and message.strip():
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(chat_file, "a") as f:
            f.write(f"[{timestamp}] {username}: {message.strip()}\n")
        with open(chat_file, "r") as f:
            chat = f.read()
        st.text_area("Chat Log", value=chat, height=250, disabled=True)

# --- Admin Tools ---
with st.expander("⚙️ Room Settings", expanded=False):
    if st.button("🧹 Clear all files in room"):
        for fname in files:
            os.remove(os.path.join(room_path, fname))
        st.success("All shared files deleted.")

    if st.button("🧼 Clear chat log"):
        with open(chat_file, "w"): pass
        st.success("Chat log cleared.")

# --- Logout Button ---
if st.button("🚪 Logout"):
    st.session_state.clear()
    st.success("🔓 Logged out. Please refresh.")
    st.stop()