import streamlit as st
import asyncio
import os
from dotenv import load_dotenv
from engine.pro_dubbing_engine import ProDubbingEngine

load_dotenv()

def get_api_keys():
    if "GEMINI_API_KEYS" in st.secrets:
        keys = st.secrets["GEMINI_API_KEYS"]
        return keys if isinstance(keys, list) else [k.strip() for k in keys.split(",") if k.strip()]
    return []

st.set_page_config(layout="wide", page_title="Pro Dubbing Engine V3")
st.title("🎙️ Pro Dubbing Engine V3 (Parallel Mode)")

# Sidebar for basic settings
with st.sidebar:
    st.header("Settings")
    output_language = st.selectbox("Output Language", ["my", "en", "ja", "ko", "th", "vi"], index=0)
    voice_gender = st.selectbox("Voice Gender", ["Male", "Female"], index=0)
    num_chunks = st.slider("Chunks to Split (Parallel Engines)", 1, 10, 5)
    
    api_keys = get_api_keys()
    if api_keys:
        st.success(f"✅ {len(api_keys)} API Keys Loaded")
    else:
        st.error("❌ No API Keys found in Secrets")

# Initialize Engine
if "engine" not in st.session_state:
    if api_keys:
        st.session_state.engine = ProDubbingEngine(
            api_keys=api_keys,
            output_language=output_language,
            voice_gender=voice_gender
        )
    else:
        st.session_state.engine = None

# Workflow State
if "step" not in st.session_state: st.session_state.step = "input"
if "srt_content" not in st.session_state: st.session_state.srt_content = ""
if "chunks" not in st.session_state: st.session_state.chunks = []
if "final_result" not in st.session_state: st.session_state.final_result = None

if st.session_state.engine is None:
    st.warning("Please add GEMINI_API_KEYS to your Streamlit Secrets to begin.")
else:
    # --- STEP 1: INPUT ---
    if st.session_state.step == "input":
        st.header("Step 1: Input Script")
        
        input_method = st.radio("Choose input method:", ("Text Input", "Upload .srt/.txt File"))
        
        input_text = ""
        if input_method == "Text Input":
            input_text = st.text_area("Paste Text or SRT content here", height=300)
        else:
            uploaded_file = st.file_uploader("Upload .srt or .txt file", type=["srt", "txt"])
            if uploaded_file is not None:
                input_text = uploaded_file.read().decode("utf-8")
                st.text_area("Uploaded Content Preview", value=input_text, height=200, disabled=True)
        
        if st.button("🚀 Process & Translate"):
            if input_text:
                with st.spinner("Generating precise SRT with AI..."):
                    translated_srt = st.session_state.engine.run_sync(
                        st.session_state.engine.prepare_srt(input_text)
                    )
                    if translated_srt.startswith("ERROR:"):
                        st.error(f"AI Error: {translated_srt}")
                    elif translated_srt and len(translated_srt) > 10:
                        st.session_state.srt_content = translated_srt
                        st.session_state.step = "review"
                        st.rerun()
                    else:
                        st.error("AI failed to generate a valid SRT. The output was too short or empty.")
            else:
                st.warning("Please provide input content.")

    # --- STEP 2: REVIEW & CHUNK ---
    elif st.session_state.step == "review":
        st.header("Step 2: Review Translated SRT")
        st.session_state.srt_content = st.text_area("Edit SRT if needed", value=st.session_state.srt_content, height=400)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Back"): st.session_state.step = "input"; st.rerun()
        with col2:
            if st.button("🎙️ Start Parallel Dubbing ➡️"):
                with st.spinner("Dividing into chunks..."):
                    st.session_state.chunks = st.session_state.engine.run_sync(
                        st.session_state.engine.create_chunks(st.session_state.srt_content, num_chunks)
                    )
                    st.session_state.step = "processing"
                    st.rerun()

    # --- STEP 3: PARALLEL PROCESSING ---
    elif st.session_state.step == "processing":
        st.header(f"Step 3: Parallel Processing ({len(st.session_state.chunks)} Chunks)")
        
        # Display progress for each chunk
        progress_bars = [st.progress(0, text=f"Chunk {c.chunk_id}: Pending") for c in st.session_state.chunks]
        status_text = st.empty()

        def update_ui(sentence_id, message):
            # Find which chunk this sentence belongs to and update UI
            # (In a real app, this needs more complex state management, 
            # for now we'll just show global logs)
            status_text.text(f"Processing Sentence {sentence_id}: {message}")

        if st.button("▶️ Run Engines"):
            with st.spinner("Engines are running in parallel..."):
                st.session_state.chunks = st.session_state.engine.run_sync(
                    st.session_state.engine.process_parallel(st.session_state.chunks, update_ui)
                )
                st.session_state.step = "finalizing"
                st.rerun()

    # --- STEP 4: FINALIZE ---
    elif st.session_state.step == "finalizing":
        st.header("Step 4: Finalizing")
        with st.spinner("Merging audio and finalizing..."):
            st.session_state.final_result = st.session_state.engine.run_sync(
                st.session_state.engine.finalize(st.session_state.chunks)
            )
            st.session_state.step = "result"
            st.rerun()

    # --- STEP 5: RESULT ---
    elif st.session_state.step == "result":
        st.header("✅ Dubbing Complete!")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Final Audio")
            st.audio(st.session_state.final_result["final_audio_path"])
            with open(st.session_state.final_result["final_audio_path"], "rb") as f:
                st.download_button("📥 Download Audio", f, file_name="dubbed_audio.mp3")
        
        with col2:
            st.subheader("Final SRT")
            st.text_area("SRT Content", st.session_state.final_result["final_srt_content"], height=200)
            st.download_button("📥 Download SRT", st.session_state.final_result["final_srt_content"], file_name="final.srt")

        if st.button("♻️ Start New Project"):
            st.session_state.step = "input"
            st.session_state.final_result = None
            st.rerun()
