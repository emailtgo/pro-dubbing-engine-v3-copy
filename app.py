import streamlit as st
import asyncio
import os
from dotenv import load_dotenv

from engine.pro_dubbing_engine import ProDubbingEngine

# Load environment variables
load_dotenv()

# --- Streamlit UI --- 
st.set_page_config(layout="wide", page_title="Pro Dubbing Engine V3")

st.title("🎙️ Pro Dubbing Engine Pro V3")

if "engine" not in st.session_state:
    st.session_state.engine = None
if "step" not in st.session_state:
    st.session_state.step = 1
if "script_content" not in st.session_state:
    st.session_state.script_content = ""
if "translated_srt" not in st.session_state:
    st.session_state.translated_srt = ""
if "final_audio_path" not in st.session_state:
    st.session_state.final_audio_path = None
if "final_srt_content" not in st.session_state:
    st.session_state.final_srt_content = ""

# --- Configuration Sidebar ---
with st.sidebar:
    st.header("Configuration")
    gemini_api_keys_str = st.text_input("Gemini API Keys (comma-separated)", type="password", value=os.getenv("GEMINI_API_KEYS", ""))
    output_language = st.selectbox("Output Language", ["my", "en", "ja", "ko", "th", "vi"], index=0)
    voice_gender = st.selectbox("Voice Gender", ["Male", "Female"], index=0)
    num_workers = st.slider("Number of Parallel Workers", 1, 10, 5)
    tolerance = st.slider("TTS Duration Tolerance (seconds)", 0.1, 1.0, 0.3, 0.1)
    max_ai_retries = st.slider("Max AI Rewriting Retries", 1, 50, 50) # User requested 50
    max_rpm = st.slider("Gemini API RPM (Requests Per Minute)", 1, 60, 9) # User requested 9
    bitrate = st.selectbox("Audio Bitrate", ["96k", "128k", "192k", "256k"], index=2)

    if st.button("Initialize Engine"):
        if not gemini_api_keys_str:
            st.error("Please provide at least one Gemini API Key.")
        else:
            api_keys = [key.strip() for key in gemini_api_keys_str.split(",") if key.strip()]
            if not api_keys:
                st.error("Please provide valid Gemini API Keys.")
            else:
                st.session_state.engine = ProDubbingEngine(
                    api_keys=api_keys,
                    output_language=output_language,
                    voice_gender=voice_gender,
                    tolerance=tolerance,
                    max_ai_retries=max_ai_retries,
                    max_rpm=max_rpm,
                    bitrate=bitrate
                )
                st.success("Pro Dubbing Engine Initialized!")

# --- Main Content Area ---
if st.session_state.engine is None:
    st.warning("Please initialize the engine in the sidebar first.")
else:
    if st.session_state.step == 1:
        st.header("Step 1: Input Script & Translate")
        script_input_method = st.radio("Choose input method:", ("Text Input", "Upload .srt/.txt File"))

        if script_input_method == "Text Input":
            st.session_state.script_content = st.text_area("Paste your script here (SRT or plain text)", height=300, value=st.session_state.script_content)
        else:
            uploaded_file = st.file_uploader("Upload .srt or .txt file", type=["srt", "txt"])
            if uploaded_file is not None:
                st.session_state.script_content = uploaded_file.read().decode("utf-8")
                st.text_area("Uploaded Script Content", value=st.session_state.script_content, height=300, disabled=True)

        if st.button("Translate Script"):
            if st.session_state.script_content:
                with st.spinner("Translating script with Gemini AI..."):
                    try:
                        # Run the async translation in a synchronous context
                        result = st.session_state.engine.run_translation_and_processing_sync(
                            st.session_state.script_content, num_workers
                        )
                        st.session_state.translated_srt = result["final_srt_content"]
                        st.session_state.final_audio_path = result["final_audio_path"]
                        st.session_state.final_srt_content = result["final_srt_content"]
                        st.session_state.step = 2
                        st.success("Translation Complete!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error during translation: {e}")
                        st.exception(e)
            else:
                st.warning("Please provide script content to translate.")

    elif st.session_state.step == 2:
        st.header("Step 2: Review & Download")
        st.subheader("Translated SRT Content")
        st.text_area("", value=st.session_state.final_srt_content, height=400)

        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.final_srt_content:
                st.download_button(
                    label="Download Translated SRT",
                    data=st.session_state.final_srt_content.encode("utf-8"),
                    file_name="translated_dubbed.srt",
                    mime="text/plain"
                )
        with col2:
            if st.session_state.final_audio_path and os.path.exists(st.session_state.final_audio_path):
                with open(st.session_state.final_audio_path, "rb") as file:
                    st.download_button(
                        label="Download Dubbed Audio (MP3)",
                        data=file.read(),
                        file_name="final_dubbed_audio.mp3",
                        mime="audio/mpeg"
                    )
        
        if st.button("Start Over"):
            st.session_state.step = 1
            st.session_state.script_content = ""
            st.session_state.translated_srt = ""
            st.session_state.final_audio_path = None
            st.session_state.final_srt_content = ""
            st.rerun()

# Clean up temporary audio files if any
# This part might need more robust handling in a real deployment
# For now, we assume temp_audio directory is cleared on next run or manually
