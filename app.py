import os
import json
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import streamlit as st

from dotenv import load_dotenv
load_dotenv()

from config import DEFAULT_CATEGORIES, NEWSPAPER_NAME, NEWSPAPER_TAGLINE, OUTPUTS_DIR
from src.ingestion.scraper import NewsIngestionPipeline
from src.agents.synthesizer import NewsSynthesizer
from src.pdf_engine.broadsheet_builder import BroadsheetPDFBuilder
from src.learning.adaptive_weights import AdaptiveWeightEngine
from src.audio.tts_engine import PaperNarrator, AUDIO_MODES, MODE_SUMMARIES

# Page Configuration (must be the first Streamlit command)
st.set_page_config(
    page_title=NEWSPAPER_NAME,
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

engine = AdaptiveWeightEngine(user_id="default_user")

# Inject styles.css into Streamlit (won't crash if the file is missing)
css_path = Path(__file__).parent / "assets" / "styles.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
else:
    st.warning(f"styles.css not found at {css_path}. Using default styling.")

# Custom Styling for Newspaper Aesthetic & Word Highlighting
st.markdown("""
    <style>
    .masthead-title {
        font-family: 'Playfair Display', 'Georgia', serif;
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        letter-spacing: 1px;
        margin-bottom: 0px;
    }
    .masthead-subtitle {
        font-family: 'Helvetica', sans-serif;
        font-size: 1rem;
        font-style: italic;
        text-align: center;
        color: #555;
        margin-bottom: 15px;
    }
    .dialectic-box {
        background-color: #f8f9fa;
        border-left: 3px solid #333;
        padding: 10px 15px;
        font-size: 0.92rem;
        border-radius: 2px;
    }
    </style>
""", unsafe_allow_html=True)

# Session State Initialization
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {
        "categories": DEFAULT_CATEGORIES[:3],
        "reading_depth": "High-Density Brief",
        "perspective": "Dialectic & Multi-Angle"
    }

if "today_edition" not in st.session_state:
    st.session_state.today_edition = []

if "latest_pdf_path" not in st.session_state:
    st.session_state.latest_pdf_path = None


# --- Helpers ---
def pick_weighted(raw_articles, categories, weights, limit=6):
    """
    Choose up to `limit` articles across the selected categories.
    - Every selected category that has articles gets one slot first (if there's room),
      so no topic is ignored.
    - Remaining slots go to categories in proportion to their learned weight
      (higher weight = more stories), using a highest-averages split.
    """
    buckets = defaultdict(list)
    for a in raw_articles:
        cat = a.get("category")
        if cat in categories:
            buckets[cat].append(a)

    if not buckets:
        return []

    picked = []
    taken = {cat: 0 for cat in buckets}

    def weight_of(cat):
        return max(weights.get(cat, 1.0), 0.01)

    # Pass 1: one story from each category, highest weight first
    for cat in sorted(buckets, key=weight_of, reverse=True):
        if len(picked) >= limit:
            return picked
        picked.append(buckets[cat][0])
        taken[cat] = 1

    # Pass 2: hand out remaining slots proportionally to weight
    while len(picked) < limit:
        candidates = [c for c in buckets if taken[c] < len(buckets[c])]
        if not candidates:
            break
        best = max(candidates, key=lambda c: weight_of(c) / (taken[c] + 1))
        picked.append(buckets[best][taken[best]])
        taken[best] += 1

    return picked


def record_feedback(category: str, action: str):
    """Send a read/skip signal to the adaptive weight engine."""
    updated = engine.update_weights_from_telemetry(
        [{"category": category, "action": action}]
    )
    new_weight = updated.get(category)
    if new_weight is not None:
        verb = "more" if action in ("read", "bookmark") else "fewer"
        st.toast(f"Got it. You'll see {verb} '{category}' stories (weight {new_weight}).", icon="✅")
    else:
        st.toast("Could not save your preference.", icon="⚠️")


@st.cache_data(show_spinner=False)
def get_installed_voices():
    """Voices installed on this computer (cached so the sidebar stays fast)."""
    return PaperNarrator.list_voices()


@st.cache_resource
def get_audio_jobs():
    """Shared dict that holds the state of the background audio recording."""
    return {}


def start_audio_job(articles, voice_id, rate, mode):
    """
    Records the audio briefing in a background thread so the page stays usable.
    Only plain data is passed in: Streamlit session state can't be used from threads.
    """
    job = {"status": "running", "done": 0, "total": 1, "path": None, "json_path": None, "error": None}
    get_audio_jobs()["current"] = job
    articles_copy = [dict(a) for a in articles]

    def run():
        try:
            narrator = PaperNarrator(voice_id=voice_id, rate=rate)
            wav_path, json_path = narrator.generate_audio(
                articles_copy,
                mode=mode,
                progress_callback=lambda done, total: job.update(done=done, total=total),
            )
            job["path"] = wav_path
            job["json_path"] = json_path
            job["status"] = "done"
        except Exception as e:
            print(f"AUDIO ERROR: {type(e).__name__}: {e}")
            job["error"] = f"{type(e).__name__}: {e}"
            job["status"] = "error"

    threading.Thread(target=run, daemon=True).start()


# --- SIDEBAR: Onboarding & Navigation ---
with st.sidebar:
    st.title("⚙️ Personalization Engine")
    st.subheader("1. Reader Profile")

    selected_categories = st.multiselect(
        "Topics of Interest",
        options=DEFAULT_CATEGORIES,
        default=st.session_state.user_profile["categories"],
        help="Select key topics to prioritize in your morning broadsheet."
    )
    st.session_state.user_profile["categories"] = selected_categories

    reading_depth = st.select_slider(
        "Analysis Depth",
        options=["Executive Summary", "High-Density Brief", "Deep Academic Dive"],
        value=st.session_state.user_profile["reading_depth"]
    )
    st.session_state.user_profile["reading_depth"] = reading_depth

    story_count = st.slider(
        "Stories per edition",
        min_value=4,
        max_value=12,
        value=6,
        help="More stories means more Groq calls, so generation takes longer."
    )

    # Audio options (offline voices installed in Windows)
    st.subheader("🎧 Audio Briefing")
    audio_mode = st.selectbox(
        "Audio length & Scope",
        options=AUDIO_MODES,
        index=AUDIO_MODES.index(MODE_SUMMARIES),
        help="Choose whether to listen to headlines, summaries, or full counter-perspectives."
    )
    audio_auto = st.checkbox(
        "Record audio in the background after each paper",
        value=True,
        help="Audio is prepared while you read, so it's ready when you want it."
    )

    installed_voices = get_installed_voices()
    voice_lookup = {name: vid for vid, name in installed_voices}
    if voice_lookup:
        audio_voice_name = st.selectbox("Voice", options=list(voice_lookup.keys()))
    else:
        audio_voice_name = None
        st.caption("No offline voices detected. The system default voice will be used.")

    audio_rate = st.slider(
        "Speech speed (words per minute)",
        min_value=120,
        max_value=240,
        value=175,
        step=5
    )
    selected_voice_id = voice_lookup.get(audio_voice_name) if audio_voice_name else None

    # Show what the engine has learned so far
    with st.expander("📈 Learned interests"):
        learned = engine.get_weights()
        if learned:
            for cat, w in sorted(learned.items(), key=lambda kv: kv[1], reverse=True):
                st.write(f"{cat}: **{w}**")
        else:
            st.caption("No feedback yet. Use 👍 Read more / Skip on stories to teach the paper.")

    st.divider()

    st.subheader("2. Action Center")
    generate_btn = st.button("🚀 Generate Today's Paper", use_container_width=True, type="primary")

    st.divider()

    # Previous Editions Archive Access
    st.subheader("📁 Paper Archives")
    archive_files = sorted([f for f in os.listdir(OUTPUTS_DIR) if f.endswith(".pdf")], reverse=True)
    if archive_files:
        selected_archive = st.selectbox("Select Past Edition", options=archive_files)
        archive_path = os.path.join(OUTPUTS_DIR, selected_archive)
        with open(archive_path, "rb") as pdf_file:
            st.download_button(
                label=f"📥 Download {selected_archive}",
                data=pdf_file,
                file_name=selected_archive,
                mime="application/pdf",
                use_container_width=True
            )
    else:
        st.info("No archived editions found yet.")


# --- MAIN UI: Newspaper View ---
st.markdown(f"<div class='masthead-title'>{NEWSPAPER_NAME}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='masthead-subtitle'>{NEWSPAPER_TAGLINE} &bull; {datetime.now().strftime('%A, %B %d, %Y')}</div>", unsafe_allow_html=True)
st.divider()

# Handle News Generation Pipeline
if generate_btn:
    user_categories = st.session_state.user_profile["categories"]

    if not user_categories:
        st.warning("Please select at least one topic in the sidebar.")
    else:
        with st.status("Assembling your personalized morning paper...", expanded=True) as status:
            st.write("🔍 Scraping live RSS feeds and web articles across selected categories...")
            scraper = NewsIngestionPipeline()
            raw_articles = scraper.gather_all_news(categories=user_categories)

            st.write("⚡ Synthesizing editorial briefs & dialectic viewpoints via Groq...")
            synthesizer = NewsSynthesizer()
            processed_articles = []

            # Pick stories across topics, favouring the ones this reader engages with
            selected_articles = pick_weighted(
                raw_articles,
                user_categories,
                engine.get_weights(),
                limit=story_count
            )
            if not selected_articles:  # fallback if nothing matched
                selected_articles = raw_articles[:story_count]

            for i, article in enumerate(selected_articles):
                if i > 0:
                    time.sleep(1)  # small pause to stay under Groq rate limits

                synthesis = synthesizer.synthesize_article(
                    article_text=f"Title: {article['title']}\nContent: {article['raw_content']}",
                    user_profile=st.session_state.user_profile
                )
                # Keep the scraper's category instead of letting the LLM guess one
                synthesis["category"] = article.get("category", synthesis.get("category", "General"))
                processed_articles.append(synthesis)

            st.session_state.today_edition = processed_articles
            get_audio_jobs()["current"] = None  # old audio no longer matches this edition

            st.write("📄 Programmatically compiling Broadsheet PDF layout...")
            pdf_builder = BroadsheetPDFBuilder()
            pdf_path = pdf_builder.generate_pdf(processed_articles)
            st.session_state.latest_pdf_path = pdf_path

            if audio_auto and processed_articles:
                st.write("🎧 Recording audio briefing in the background...")
                start_audio_job(processed_articles, selected_voice_id, audio_rate, audio_mode)

            status.update(label="Morning Paper Ready!", state="complete", expanded=False)


# Display Active Morning Paper
if st.session_state.today_edition:
    # PDF download + audio generation side by side
    pdf_col, audio_col, _ = st.columns([1, 1, 2])

    with pdf_col:
        if st.session_state.latest_pdf_path and os.path.exists(st.session_state.latest_pdf_path):
            with open(st.session_state.latest_pdf_path, "rb") as pdf_file:
                st.download_button(
                    label="📥 Download Morning Paper PDF",
                    data=pdf_file,
                    file_name=os.path.basename(st.session_state.latest_pdf_path),
                    mime="application/pdf",
                    type="primary"
                )

    with audio_col:
        audio_btn = st.button("🎧 Re-record Audio Briefing")

    # Manual (re)recording with the current sidebar settings
    if audio_btn:
        start_audio_job(st.session_state.today_edition, selected_voice_id, audio_rate, audio_mode)

    # Audio panel: polls every 2 seconds while recording, then shows the player + live word highlighter
    current_job = get_audio_jobs().get("current")
    audio_running = bool(current_job and current_job["status"] == "running")

    @st.fragment(run_every=2 if audio_running else None)
    def audio_panel():
        job = get_audio_jobs().get("current")
        if not job:
            return

        # Recording just finished: refresh the whole page so polling stops
        if audio_running and job["status"] != "running":
            st.rerun()

        if job["status"] == "running":
            total = max(job["total"], 1)
            st.progress(
                min(job["done"] / total, 1.0),
                text=f"🎧 Recording audio in the background ({job['done']}/{total}). You can keep reading."
            )
        elif job["status"] == "error":
            st.error(
                "Could not generate audio. Make sure pyttsx3 is installed and a Windows "
                f"voice is available. ({job['error']})"
            )
        elif job["status"] == "done" and job["path"] and os.path.exists(job["path"]):
            st.markdown("---")
            st.subheader("📻 ChronicleX Live Audio Briefing & Synchronized Word Highlighter")
            
            with open(job["path"], "rb") as audio_file:
                audio_bytes = audio_file.read()
            st.audio(audio_bytes, format="audio/wav")

            # Load word timing metadata for word-level highlighting
            json_meta_path = job.get("json_path")
            if json_meta_path and os.path.exists(json_meta_path):
                with open(json_meta_path, "r", encoding="utf-8") as jf:
                    timing_data = json.load(jf)

                # Render synchronized HTML/JS text box for live word highlighting
                highlight_html = f"""
                <div style="background-color: #12151c; padding: 18px; border-radius: 8px; border: 1px solid #374151; max-height: 220px; overflow-y: auto; margin-top: 10px;">
                    <p id="transcript-box" style="font-size: 1.05em; line-height: 1.7; color: #d1d5db; font-family: monospace;">
                        {' '.join([f'<span id="w-{i}" style="transition: color 0.1s ease;">{item["word"]}</span>' for i, item in enumerate(timing_data)])}
                    </p>
                </div>
                <script>
                    const audioEle = window.parent.document.querySelector('audio');
                    const timings = {json.dumps(timing_data)};
                    
                    if (audioEle) {{
                        audioEle.ontimeupdate = function() {{
                            const currentTime = audioEle.currentTime;
                            timings.forEach((t, idx) => {{
                                const span = window.parent.document.getElementById('w-' + idx);
                                if (span) {{
                                    if (currentTime >= t.start && currentTime <= t.end) {{
                                        span.style.color = '#38bdf8'; // Highlight cyan color
                                        span.style.fontWeight = 'bold';
                                    }} else {{
                                        span.style.color = '#d1d5db';
                                        span.style.fontWeight = 'normal';
                                    }}
                                }}
                            }});
                        }};
                    }}
                </script>
                """
                st.markdown(highlight_html, unsafe_allow_html=True)

            st.download_button(
                label="📥 Download audio brief (WAV)",
                data=audio_bytes,
                file_name=os.path.basename(job["path"]),
                mime="audio/wav"
            )

    audio_panel()

    st.divider()

    # Article Layout Grid
    for idx, article in enumerate(st.session_state.today_edition):
        col1, col2 = st.columns([1.6, 1])
        category = article.get("category", "General")

        with col1:
            st.caption(f"CATEGORY: {category.upper()}")
            st.subheader(article.get("headline", "Untitled"))
            st.write(article.get("summary", ""))

            # Feedback buttons -> adaptive weight engine
            btn_col1, btn_col2, _ = st.columns([1, 1, 3])
            with btn_col1:
                if st.button("👍 Read more", key=f"read_{idx}"):
                    record_feedback(category, "read")
            with btn_col2:
                if st.button("Skip", key=f"skip_{idx}"):
                    record_feedback(category, "skip")

        with col2:
            st.markdown("<div class='dialectic-box'>", unsafe_allow_html=True)
            st.markdown("**💡 Dialectic Perspective / Counter-Analysis:**")
            st.write(article.get("dialectic_perspective", "N/A"))
            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
else:
    st.info("👈 Configure your reader profile in the sidebar and click **'Generate Today's Paper'** to start reading.")