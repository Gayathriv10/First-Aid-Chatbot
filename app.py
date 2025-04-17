import streamlit as st
import json
import os
import nltk
import speech_recognition as sr
from fuzzywuzzy import process
import google.generativeai as genai
from dotenv import load_dotenv
from langdetect import detect
from deep_translator import GoogleTranslator

# Initialize session state keys
if "language" not in st.session_state:
    st.session_state.language = None

# (Add more if needed)
if "user_input" not in st.session_state:
    st.session_state.user_input = ""

# Avoid repeated NLTK download messages
import nltk.data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Load dataset
with open("intents.json", "r", encoding="utf-8") as file:
    data = json.load(file)

# Initialize Gemini API
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 1000,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
)

# Convert JSON into a dictionary for quick search
conditions_dict = {
    pattern.lower(): intent["responses"][0] for intent in data["intents"] for pattern in intent["patterns"]
}

# Function to find the best match from local dataset
def get_first_aid_response(user_query, language):
    user_query = user_query.lower()
    closest_match = process.extractOne(user_query, conditions_dict.keys())

    if closest_match and closest_match[1] > 60:
        return conditions_dict[closest_match[0]]

    return "மன்னிக்கவும்! எனக்கு இந்த தகவல் இல்லை, மருத்துவரை தொடர்பு கொள்ளவும்." if language == "Tamil" else "Sorry! I don't have the answer, consult with a doctor pls."

# ✅ Updated Function to recognize Tamil & English speech input
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
        except sr.UnknownValueError:
            return "மன்னிக்கவும், உங்கள் குரலை புரிந்துகொள்ள முடியவில்லை." if st.session_state.language == "Tamil" else "Sorry, I couldn't understand your voice."
        except sr.RequestError:
            return "மன்னிக்கவும், சேவை கிடைக்கவில்லை." if st.session_state.language == "Tamil" else "Speech recognition service is unavailable."
        except Exception as e:
            return f"பிழை: {str(e)}" if st.session_state.language == "Tamil" else f"Error: {str(e)}"

# Streamlit UI
st.set_page_config(page_title="Dr.Aidy", layout="centered")

# Header with image
col1, col2 = st.columns([1, 4])
with col1:
    st.image("first_aid.jpeg", width=75)
with col2:
    st.markdown("<h2 style='margin-bottom: 0px;'>Dr.Aidy - First Aid Chatbot</h2>", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.language = None
    st.session_state.awaiting_response = False
    st.session_state.show_buttons = False
    st.session_state.stop_convo = False
    st.session_state.voice_input = None

# Language selection
if st.session_state.language is None:
    st.write("Please choose your language:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("English", use_container_width=True):
            st.session_state.language = "English"
            st.session_state.messages.append({"role": "assistant", "content": "Hello! How can I assist you?"})
    with col2:
        if st.button("தமிழ்", use_container_width=True):
            st.session_state.language = "Tamil"
            st.session_state.messages.append({"role": "assistant", "content": "வணக்கம்! நான் எப்படி உதவலாம்?"})
    st.rerun()

# Chatbox styling
st.markdown("""
<style>
.bot-message {border: 1px solid #ddd; padding: 10px; border-radius: 10px; height: 75px; overflow-y: auto; background-color: #f9f9f9; color: #0645AD; font-weight: bold;}
.user-message {border: 1px solid #ddd; padding: 10px; border-radius: 10px; height: 40px; overflow-y: auto; background-color: #f9f9f9; color: #4CAF50; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# Display chat messages
st.markdown('<div class="chat-box">', unsafe_allow_html=True)
for message in st.session_state.messages:
    role_class = "bot-message" if message["role"] == "assistant" else "user-message"
    sender_name = "Dr.Aidy 🤖" if message["role"] == "assistant" else "You 👤"
    st.markdown(f'<p class="{role_class}"><strong>{sender_name}: </strong>{message["content"]}</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Stop conversation
if st.session_state.stop_convo:
    st.stop()

# Accept user input
if st.session_state.language and not st.session_state.awaiting_response and not st.session_state.show_buttons:
    prompt_placeholder = "உங்கள் கேள்வியை இங்கே உள்ளிடவும்..." if st.session_state.language == "Tamil" else "Type your message here..."
    col1, col2 = st.columns([4, 1])

    with col1:
        prompt = st.chat_input(prompt_placeholder)

    mic_label = "🎙️ Speak" if st.session_state.language == "English" else "🎙️ பேசவும்"
    with col2:
        if st.button(mic_label, use_container_width=True):
            spoken_text = recognize_speech()

            # Language detection fallback for translation
            try:
                detected_lang = detect(spoken_text)
            except:
                detected_lang = "en"

            # If selected Tamil but voice detected non-Tamil
            if st.session_state.language == "Tamil" and detected_lang != "ta":
                try:
                    translated_text = GoogleTranslator(source='auto', target='ta').translate(spoken_text)
                    spoken_text = translated_text
                except Exception:
                    spoken_text = "மன்னிக்கவும், மொழிபெயர்ப்பு தோல்வியடைந்தது."

            st.session_state.voice_input = spoken_text
            st.rerun()

    # Process voice input
    if st.session_state.voice_input:
        prompt = st.session_state.voice_input
        st.session_state.voice_input = None

    if prompt:
        st.session_state.awaiting_response = True
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

# Process user query
if st.session_state.awaiting_response:
    user_prompt = st.session_state.messages[-1]["content"]

    if st.session_state.language == "Tamil":
        gemini_prompt = f"குறைந்தது 2-3 வரிகளில் {user_prompt} க்கு முதல் உதவி அறிவுரை வழங்கவும்."
    else:
        gemini_prompt = f"Provide a **2-3 line** first-aid measure for: {user_prompt}."

    response = model.generate_content(gemini_prompt).text if model else ""

    if len(response.split()) < 5:
        response = get_first_aid_response(user_prompt, st.session_state.language)

    st.session_state.messages.append({"role": "assistant", "content": response})

    follow_up_q = "உங்களுக்குத் துணை செய்ய ஏதேனும் கூடுதல் கேள்விகள் உள்ளதா?" if st.session_state.language == "Tamil" else "Do you have any other questions?"
    st.session_state.messages.append({"role": "assistant", "content": follow_up_q})

    st.session_state.show_buttons = True
    st.session_state.awaiting_response = False
    st.rerun()

# Display Yes/No buttons
if st.session_state.show_buttons:
    col1, col2 = st.columns(2)
    with col1:
        yes_label = "✅ Yes" if st.session_state.language == "English" else "✅ ஆம்"
        if st.button(yes_label, use_container_width=True):
            st.session_state.show_buttons = False
            st.rerun()

    with col2:
        no_label = "❌ No" if st.session_state.language == "English" else "❌ இல்லை"
        if st.button(no_label, use_container_width=True):
            final_message = "Okay! Stay safe and take care! 😊" if st.session_state.language == "English" else "சரி! பாதுகாப்பாக இருங்கள், நல்லபடியாக இருங்கள்! 😊"
            st.session_state.messages.append({"role": "assistant", "content": final_message})
            st.session_state.show_buttons = False
            st.rerun()
