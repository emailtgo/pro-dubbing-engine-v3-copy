import streamlit as st
import asyncio
import os
from dotenv import load_dotenv
import pandas as pd

from engine.pro_dubbing_engine import ProDubbingEngine
from engine.models import DubbingSentence

# Load environment variables
load_dotenv()

def get_api_keys():
    """Get API keys from Streamlit Secrets or Environment Variables."""
    if "GEMINI_API_KEYS" in st.secrets:
        return st.secrets["GEMINI_API_KEYS"]
    env_keys = os.getenv("GEMINI_API_KEYS", "")
    return env_keys

# --- Streamlit UI --- 
st.set_page_config(layout="wide", page_title="Pro Dubbing Engine V3")

st.title("🎙️ Pro Dubbing Engine Pro V3")

# Initialize session state variables
if "engine" not in st.session_state:
    st.session_state.engine = None
if "step" not in st.session_state:
    st.session_state.step = 1
if "script_content" not in st.session_state:
    st.session_state.script_content = ""
if "translated_srt_content" not in st.session_state:
    st.session_state.translated_srt_content = ""
if "dubbing_sentences" not in st.session_state:
    st.session_state.dubbing_sentences = []
if "final_audio_path" not in st.session_state:
    st.session_state.final_audio_path = None
if "final_srt_content" not in st.session_state:
    st.session_state.final_srt_content = ""

# --- Configuration Area (Main UI) ---
st.header("⚙️ Configuration")
col1, col2, col3 = st.columns(3)

with col1:
    output_language = st.selectbox("Output Language", ["my", "en", "ja", "ko", "th", "vi"], index=0)
with col2:
    voice_gender = st.selectbox("Voice Gender", ["Male", "Female"], index=0)
with col3:
    num_workers = st.slider("Parallel Workers", 1, 10, 5)

# Process API Keys
raw_keys = get_api_keys()
if isinstance(raw_keys, list):
    api_keys = [str(key).strip() for key in raw_keys if str(key).strip()]
elif isinstance(raw_keys, str):
    api_keys = [key.strip() for key in raw_keys.split(",") if key.strip()]
else:
    api_keys = []

if api_keys:
    st.success(f"✅ {len(api_keys)} Gemini API Keys Loaded")
else:
    st.error("❌ No Gemini API Keys found. Please add them to Streamlit Secrets.")

# Hardcoded values
bitrate = "192k"
tolerance = 0.3 
max_ai_retries = 50
max_rpm = 9 

# Auto-initialize or Re-initialize Engine if settings change
# We'll use a simple button for now to ensure user is ready
if st.button("🚀 Start / Initialize Engine"):
    if not api_keys:
        st.error("Cannot initialize without API Keys.")
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
        st.success("Engine Ready! Follow the steps below.")
        st.session_state.step = 1

st.divider()

# --- Main Workflow Area ---
if st.session_state.engine is None:
    st.info("Please click the 'Start / Initialize Engine' button above to begin.")
else:
    # Step 1: Script Input & Translation
    if st.session_state.step == 1:
        st.header("Step 1: Script Input & Translate")
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
                        result = st.session_state.engine.run_sync(
                            st.session_state.engine.translate_script(st.session_state.script_content, num_workers)
                        )
                        st.session_state.translated_srt_content = result["reconstructed_srt_content"]
                        st.success("Translation Complete!")
                        st.session_state.step = 2
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error during translation: {e}")
            else:
                st.warning("Please provide script content to translate.")

    # Step 2: Sentence Grouping & Review
    elif st.session_state.step == 2:
        st.header("Step 2: Sentence Grouping & Review")
        st.subheader("Translated SRT Content (Editable)")
        st.session_state.translated_srt_content = st.text_area("", value=st.session_state.translated_srt_content, height=400, key="editable_translated_srt")

        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("⬅️ Back to Step 1"):
                st.session_state.step = 1
                st.rerun()
        with col_next:
            if st.button("Group Sentences & Next ➡️"):
                if st.session_state.translated_srt_content:
                    with st.spinner("Grouping sentences..."):
                        try:
                            st.session_state.dubbing_sentences = st.session_state.engine.run_sync(
                                st.session_state.engine.group_sentences(st.session_state.translated_srt_content)
                            )
                            st.success(f"Grouped {len(st.session_state.dubbing_sentences)} sentences.")
                            st.session_state.step = 3
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error during sentence grouping: {e}")
                else:
                    st.warning("Please translate script first.")

    # Step 3: TTS Generation & AI Adjustment
    elif st.session_state.step == 3:
        st.header("Step 3: TTS Generation & AI Adjustment")
        if not st.session_state.dubbing_sentences:
            st.warning("Please group sentences in Step 2 first.")
            if st.button("Back to Step 2"):
                st.session_state.step = 2
                st.rerun()
        else:
            st.info(f"Ready to generate audio for {len(st.session_state.dubbing_sentences)} sentences.")
            
            # Placeholder for real-time status updates
            status_placeholders = {sentence.sentence_id: st.empty() for sentence in st.session_state.dubbing_sentences}

            def update_status_callback(sentence_id, message):
                if sentence_id in status_placeholders:
                    status_placeholders[sentence_id].text(f"Sentence {sentence_id}: {message}")

            col_back, col_gen = st.columns(2)
            with col_back:
                if st.button("⬅️ Back to Step 2"):
                    st.session_state.step = 2
                    st.rerun()
            with col_gen:
                if st.button("🎙️ Generate Audio & AI Adjust"):
                    with st.spinner("Generating TTS and adjusting with AI..."):
                        try:
                            st.session_state.dubbing_sentences = st.session_state.engine.run_sync(
                                st.session_state.engine.generate_tts_and_adjust(
                                    st.session_state.dubbing_sentences, num_workers, update_status_callback
                                )
                            )
                            st.success("Audio Generation and AI Adjustment Complete!")
                            st.session_state.step = 4
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error during audio generation: {e}")

    # Step 4: Final Merging & Download
    elif st.session_state.step == 4:
        st.header("Step 4: Final Merging & Download")
        if not st.session_state.dubbing_sentences:
            st.warning("Please generate audio in Step 3 first.")
            if st.button("Back to Step 3"):
                st.session_state.step = 3
                st.rerun()
        else:
            if st.button("🔄 Merge & Finalize"):
                with st.spinner("Merging audio and generating final SRT..."):
                    try:
                        result = st.session_state.engine.run_sync(
                            st.session_state.engine.merge_and_finalize(st.session_state.dubbing_sentences)
                        )
                        st.session_state.final_audio_path = result["final_audio_path"]
                        st.session_state.final_srt_content = result["final_srt_content"]
                        st.success("Finalization Complete!")
                    except Exception as e:
                        st.error(f"Error during finalization: {e}")
            
            if st.session_state.final_srt_content:
                st.subheader("Final SRT Content")
                st.text_area("", value=st.session_state.final_srt_content, height=400, disabled=True)
                st.download_button(
                    label="📥 Download Final SRT",
                    data=st.session_state.final_srt_content.encode("utf-8"),
                    file_name="final_dubbed.srt",
                    mime="text/plain"
                )
            
            if st.session_state.final_audio_path and os.path.exists(st.session_state.final_audio_path):
                st.subheader("Final Dubbed Audio")
                st.audio(st.session_state.final_audio_path, format="audio/mp3")
                with open(st.session_state.final_audio_path, "rb") as file:
                    st.download_button(
                        label="📥 Download Final Audio (MP3)",
                        data=file.read(),
                        file_name="final_dubbed_audio.mp3",
                        mime="audio/mpeg"
                    )
            
            st.divider()
            col_back, col_reset = st.columns(2)
            with col_back:
                if st.button("⬅️ Back to Step 3"):
                    st.session_state.step = 3
                    st.rerun()
            with col_reset:
                if st.button("♻️ Start Over"):
                    st.session_state.step = 1
                    st.session_state.script_content = ""
                    st.session_state.translated_srt_content = ""
                    st.session_state.dubbing_sentences = []
                    st.session_state.final_audio_path = None
                    st.session_state.final_srt_content = ""
                    st.rerun()
