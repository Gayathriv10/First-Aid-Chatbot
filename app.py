import streamlit as st
import json
import os
import nltk.data
import speech_recognition as sr
from fuzzywuzzy import process
import google.generativeai as genai
from dotenv import load_dotenv
from langdetect import detect
from deep_translator import GoogleTranslator
from pymongo import MongoClient
from datetime import datetime

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# MongoDB connection
client = MongoClient(os.getenv("MONGO_URL"))
db = client["dr_aidy"]
users_col = db["users"]
queries_col = db["queries"]

# Ensure NLTK tokenizer is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Load intents
with open("intents.json", "r", encoding="utf-8") as file:
    data = json.load(file)

conditions_dict = {
    pattern.lower(): intent["responses"][0]
    for intent in data["intents"]
    for pattern in intent["patterns"]
}

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 1000,
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
)

st.set_page_config(page_title="Dr.Aidy", layout="centered")
if "user" not in st.session_state:
    st.session_state.user = None
for key in ["language", "messages", "awaiting_response", "show_buttons", "stop_convo", "voice_input", "chat_started"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "messages" else False if isinstance(key, bool) else None

def signup():
    st.subheader("🔐 Signup")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Create Account"):
        if users_col.find_one({"username": username}):
            st.error("Username already taken!")
        else:
            users_col.insert_one({
                "username": username,
                "password": password,
                "created_at": datetime.now()
            })
            st.success("Account created! Please sign in.")
            st.session_state.signup = False

def signin():
    st.subheader("🔓 Sign In")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = users_col.find_one({"username": username, "password": password})
        if user:
            st.session_state.user = {"username": user["username"]}
            st.success(f"Welcome {user['username']}!")
        else:
            st.error("Invalid credentials.")

if st.session_state.user is None:
    if "signup" not in st.session_state:
        st.session_state.signup = False
    st.title("👨‍⚕️ Dr.Aidy - First Aid Companion")
    if st.session_state.signup:
        signup()
    else:
        signin()
        if st.button("Create new account"):
            st.session_state.signup = True
    st.stop()

with st.sidebar:
    st.write(f"Logged in as: **{st.session_state.user['username']}**")
    if st.button("🧹 Clear Chat"):
        for key in list(st.session_state.keys()):
            if key not in ["user", "signup"]:
                st.session_state[key] = [] if key == "messages" else False if isinstance(st.session_state[key], bool) else None
    if st.button("🔓 Logout"):
        st.session_state.user = None
        st.rerun()

def get_first_aid_response(user_query, language):
    user_query = user_query.lower()
    closest_match = process.extractOne(user_query, conditions_dict.keys())
    if closest_match and closest_match[1] > 60:
        return conditions_dict[closest_match[0]]
    return "மன்னிக்கவும்! எனக்கு இந்த தகவல் இல்லை, மருத்துவரை தொடர்பு கொள்ளவும்." if language == "Tamil" else "Sorry! I don't have the answer, consult with a doctor pls."

def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening... Speak now!")
        try:
            audio = recognizer.listen(source, timeout=5)
            st.success("Processing voice input...")
            lang_code = "ta-IN" if st.session_state.language == "Tamil" else "en-US"
            text = recognizer.recognize_google(audio, language=lang_code)
            return text
        except:
            return "Speech recognition failed."

st.image("first_aid.jpeg", width=75)
st.title("🩺 Dr.Aidy - First Aid Chatbot")

if not st.session_state.chat_started:
    st.markdown("## 👋 Welcome to Dr.Aidy - Your First Aid Companion")
    if st.button("🚀 Start Conversation"):
        st.session_state.chat_started = True
    st.stop()

if st.session_state.language is None:
    st.write("Please choose your language:")
    col1, col2 = st.columns(2)
    if col1.button("English"):
        st.session_state.language = "English"
        st.session_state.messages.append({"role": "assistant", "content": "Hello! How can I assist you?"})
    if col2.button("தமிழ்"):
        st.session_state.language = "Tamil"
        st.session_state.messages.append({"role": "assistant", "content": "வணக்கம்! நான் எப்படி உதவலாம்?"})
    st.stop()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if not st.session_state.awaiting_response and not st.session_state.show_buttons:
    prompt = st.chat_input("Type your message..." if st.session_state.language == "English" else "உங்கள் கேள்வியை இங்கே உள்ளிடவும்...")
    if st.button("🎙️ Speak", use_container_width=True):
        spoken = recognize_speech()
        try:
            if st.session_state.language == "Tamil" and detect(spoken) != "ta":
                spoken = GoogleTranslator(source='auto', target='ta').translate(spoken)
        except:
            pass
        st.session_state.voice_input = spoken
        st.rerun()
    if st.session_state.voice_input:
        prompt = st.session_state.voice_input
        st.session_state.voice_input = None
    if prompt:
        st.session_state.awaiting_response = True
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

if st.session_state.awaiting_response:
    user_prompt = st.session_state.messages[-1]["content"]
    gemini_prompt = (
        f"குறைந்தது 2-3 வரிகளில் {user_prompt} க்கு முதல் உதவி அறிவுரை வழங்கவும்." if st.session_state.language == "Tamil"
        else f"Provide a **2-3 line** first-aid measure for: {user_prompt}."
    )
    try:
        response = model.generate_content(gemini_prompt).text
    except:
        response = ""

    if len(response.split()) < 5:
        response = get_first_aid_response(user_prompt, st.session_state.language)

    st.session_state.messages.append({"role": "assistant", "content": response})

    queries_col.insert_one({
        "username": st.session_state.user["username"],
        "query": user_prompt,
        "response": response,
        "language": st.session_state.language,
        "timestamp": datetime.now()
    })

    follow_up = "Do you have any other questions?" if st.session_state.language == "English" else "உங்களுக்குத் துணை செய்ய ஏதேனும் கூடுதல் கேள்விகள் உள்ளதா?"
    st.session_state.messages.append({"role": "assistant", "content": follow_up})
    st.session_state.awaiting_response = False
    st.session_state.show_buttons = True
    st.rerun()

# Follow-up buttons
if st.session_state.show_buttons:
    col1, col2 = st.columns(2)
    if col1.button("✅ Yes" if st.session_state.language == "English" else "✅ ஆம்"):
        st.session_state.show_buttons = False
        st.rerun()
    if col2.button("❌ No" if st.session_state.language == "English" else "❌ இல்லை"):
        bye_msg = "Okay! Stay safe and take care! 😊" if st.session_state.language == "English" else "சரி! பாதுகாப்பாக இருங்கள், நல்லபடியாக இருங்கள்! 😊"
        st.session_state.messages.append({"role": "assistant", "content": bye_msg})
        st.session_state.show_buttons = False
        st.session_state.stop_convo = True
        st.rerun()
