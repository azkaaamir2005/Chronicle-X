import os
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

# Custom Styling for Newspaper Aesthetic
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

            st.write("📄 Programmatically compiling Broadsheet PDF layout...")
            pdf_builder = BroadsheetPDFBuilder()
            pdf_path = pdf_builder.generate_pdf(processed_articles)
            st.session_state.latest_pdf_path = pdf_path

            status.update(label="Morning Paper Ready!", state="complete", expanded=False)


# Display Active Morning Paper
if st.session_state.today_edition:
    # PDF Download Option
    if st.session_state.latest_pdf_path and os.path.exists(st.session_state.latest_pdf_path):
        with open(st.session_state.latest_pdf_path, "rb") as pdf_file:
            st.download_button(
                label="📥 Download Morning Paper PDF",
                data=pdf_file,
                file_name=os.path.basename(st.session_state.latest_pdf_path),
                mime="application/pdf",
                type="primary"
            )
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