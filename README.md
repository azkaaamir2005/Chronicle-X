# ChronicleX 📰✨

> **An Autonomous, Personalization-Driven Morning Broadsheet & Audio Briefing Platform**

ChronicleX is an end-to-end multi-modal news aggregation, synthesis, and publishing platform engineered to bridge the gap between overloaded digital news streams and structured, high-density journalism. By combining real-time multi-source web ingestion, LLM-driven dialectic perspective generation, adaptive learning mechanics, and programmatic PDF broadsheet layout compilation, ChronicleX delivers a personalized daily news experience in both print and audio formats.

---

## 📋 Table of Contents
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Project Directory Structure](#-project-directory-structure)
- [Environment Configuration (`.env`)](#-environment-configuration-env)
- [Installation & Setup](#-installation--setup)
- [Detailed Component Overview](#-detailed-component-overview)
  - [1. Multi-Source Ingestion Pipeline](#1-multi-source-ingestion-pipeline)
  - [2. AI Synthesis & Dialectic Engine](#2-ai-synthesis--dialectic-engine)
  - [3. Adaptive Personalization & Weighting Engine](#3-adaptive-personalization--weighting-engine)
  - [4. Programmatic Broadsheet PDF Builder](#4-programmatic-broadsheet-pdf-builder)
  - [5. Offline Speech & Narration Engine](#5-offline-speech--narration-engine)
- [Execution & Workflow](#-execution--workflow)
- [License & Acknowledgments](#-license--acknowledgments)

---

## 📐 System Architecture

ChronicleX processes news through a sequential, modular pipeline:

1. **Ingestion Layer:** Asynchronously pulls live content from configured RSS feeds and web endpoints, removing redundant or duplicate coverage.
2. **Personalization Layer:** Evaluates historical reader engagement telemetry (`👍 Read more` / `Skip`) to re-weight story selection dynamically.
3. **Synthesis Engine:** Interfaces with Groq LLMs (`Llama-3.3-70b`) to craft executive summaries and opposing multi-angle perspectives (*Dialectic Viewpoints*).
4. **Multi-Modal Generation Engine:** 
   - Compiles a publication-ready broadsheet PDF using ReportLab layout geometries.
   - Generates a local, offline audio briefing via Windows SAPI5 (`pyttsx3`) for rapid playback.

---

## ✨ Key Features

* **Real-Time News Gathering:** Aggregates live stories across diverse categories including Technology, Business, Science, World News, and Culture.
* **Dialectic Perspective Analysis:** Automatically pairs primary story summaries with contrasting counter-analyses to mitigate media bias and foster balanced understanding.
* **Adaptive Bandit Learning Loop:** Tracks implicit and explicit reader feedback to continuously tailor category preferences over time without manual reconfiguration.
* **Publication-Grade Broadsheet PDF:** Programmatically generates multi-column, beautifully typeset digital broadsheets designed for printing or e-ink tablet reading.
* **Snappy Audio Headlines Briefing:** Uses thread-safe offline Text-to-Speech synthesis to build audio briefings optimized for sub-second rendering during live demonstrations.
* **Resilient Background Execution:** Utilizes Streamlit fragments and multi-threaded audio worker pools to ensure zero interface lockup while processing back-end workloads.

---

## 📂 Project Directory Structure

```text
ChronicleX/
├── assets/
│   └── styles.css                 # Custom CSS typography and layout overrides
├── outputs/                       # Generated output directory for PDFs and WAV files
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   └── synthesizer.py         # Groq LLM integration for editorial summary & dialectic generation
│   ├── audio/
│   │   ├── __init__.py
│   │   └── tts_engine.py          # Offline pyttsx3 speech narration engine
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── scraper.py             # Live RSS and web article scraping & deduplication pipeline
│   ├── learning/
│   │   ├── __init__.py
│   │   └── adaptive_weights.py    # Contextual telemetry and category weighting engine
│   └── pdf_engine/
│       ├── __init__.py
│       └── broadsheet_builder.py  # ReportLab PDF layout generator and typesetter
├── .env                           # Local environment configuration file (API Keys)
├── .env.example                   # Template for environment configuration
├── app.py                         # Streamlit user interface and workflow manager
├── config.py                      # Global application parameters and default configurations
├── README.md                      # Comprehensive project documentation
└── requirements.txt               # Required Python libraries and dependencies

## Environment Configuration (.env)
ChronicleX requires valid API keys for its synthesis layer. Create a .env file in the project root
Example .env File Format:
# =====================================================================
# CHRONICLEX SYSTEM ENVIRONMENT CONFIGURATION
# =====================================================================

# Groq API Key for high-speed Llama-3.3-70b synthesis
GROQ_API_KEY=gsk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0

# Optional System Overrides
OUTPUT_DIR=outputs
LOG_LEVEL=INFO

🚀 Installation & Setup
Prerequisites
Python 3.10+ installed on your system.
Active Groq API Key

Clone the Repository:
git clone [https://github.com/YOUR_USERNAME/Chronicle-X.git](https://github.com/YOUR_USERNAME/Chronicle-X.git)
cd Chronicle-X

Set Up a Virtual Environment
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate

Install Required Dependencies
pip install --upgrade pip
pip install -r requirements.txt

Launch the Application
streamlit run app.py


**Detailed Component Overview**
1. Multi-Source Ingestion Pipeline (src/ingestion/scraper.py)
Fetches stories from predefined RSS feeds and news APIs across user-selected categories. Sanitizes raw text, removes HTML tags, extracts publication metadata, and filters out duplicate news entries across feeds.

2. AI Synthesis & Dialectic Engine (src/agents/synthesizer.py)
Utilizes Groq's low-latency inference endpoints running Llama-3.3-70b to process gathered articles. For each story, it produces:

A concise executive summary tailored to the chosen reading depth.

A Dialectic Perspective highlighting counter-arguments, missing context, or opposing economic/political interpretations.

3. Adaptive Personalization & Weighting Engine (src/learning/adaptive_weights.py)
Implements an adaptive bandit learning framework. When users interact with stories using the 👍 Read more or Skip buttons, telemetry feedback updates topic preference weights stored locally in user_weights.json. Subsequent paper generations use weighted sampling to surface more content from favored categories.

4. Programmatic Broadsheet PDF Builder (src/pdf_engine/broadsheet_builder.py)
Utilizes Python's reportlab engine to dynamically generate a two-column newspaper broadsheet layout. Handles page geometry, masthead styling, category headings, horizontal rule dividers, and balanced column overflow automatically.

5. Offline Speech & Narration Engine (src/audio/tts_engine.py)
A thread-safe speech synthesis module using pyttsx3 and Windows SAPI5/COM. Converts synthesized headlines into a unified .wav audio briefing offline without depending on third-party cloud TTS APIs.

🛠️ Execution & Workflow
Configure Reader Profile: Select target categories, analysis depth, and story volume in the Streamlit sidebar.

Generate Paper: Click 🚀 Generate Today's Paper to execute scraper ingestion, LLM synthesis, PDF layout building, and background audio compilation.

Read & Listen: View the generated edition on-screen, download the broadsheet PDF, or play the headline audio brief directly in the browser.

Provide Feedback: Click 👍 Read more or Skip on articles to continuously train the personalization engine for tomorrow's edition.
