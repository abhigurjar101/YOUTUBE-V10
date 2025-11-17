import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from googleapiclient.discovery import build
from textblob import TextBlob
from wordcloud import WordCloud
from collections import Counter
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
import isodate 
import requests
from PIL import Image
from io import BytesIO

# ==========================================
# 1. CONFIG & THEME (PROFESSIONAL BRIGHT)
# ==========================================
st.set_page_config(
    page_title="YouTube GEN AXE", 
    page_icon="https://www.gstatic.com/youtube/img/branding/favicon/favicon_192x192.png", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a professional light/bright theme
st.markdown("""
    <style>
    /* Main Theme */
    .stApp { 
        background-color: #F0F2F6; /* Light grey background */
    }
    [data-testid="stSidebar"] { 
        background-color: #FFFFFF; /* White sidebar */
        border-right: 1px solid #E0E0E0;
    }
    
    /* Cards (HUD & Content) */
    .metric-card { 
        background-color: #FFFFFF; 
        border: 1px solid #E0E0E0;
        border-radius: 12px; 
        padding: 25px;
        margin-bottom: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    
    /* BIGGER, BOLDER TITLES */
    h1 { font-size: 38px !important; font-weight: 800; color: #111; }
    h2 { font-size: 28px !important; font-weight: 700; color: #111; }
    h3 { font-size: 22px !important; font-weight: 700; color: #111; }
    
    /* Eye-Catching Stats (BIGGER & COLORED) */
    .stat-value-red { 
        font-size: 36px; 
        font-weight: 900; 
        color: #D90000; /* YouTube Red */
    }
    .stat-value-orange { 
        font-size: 36px; 
        font-weight: 900; 
        color: #E65100; /* Deep Orange */
    }
    .stat-label { 
        font-size: 14px; 
        color: #555555; 
        text-transform: uppercase; 
        letter-spacing: 1px; 
        font-weight: 600;
    }
    
    /* Branding */
    .brand-text { 
        color: #FF0000; 
        font-weight: bold; 
        letter-spacing: 0.5px; 
        font-size: 14px; 
    }
    
    /* Button */
    div.stButton > button {
        background-color: #FF0000;
        color: white;
        border: none;
        font-weight: bold;
        width: 100%;
        height: 42px;
        margin-top: 28px; /* Aligns with search box */
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SESSION STATE
# ==========================================
if 'search_done' not in st.session_state: st.session_state.search_done = False
if 'df' not in st.session_state: st.session_state.df = pd.DataFrame()
if 'all_tags' not in st.session_state: st.session_state.all_tags = []
if 'selected_video_id' not in st.session_state: st.session_state.selected_video_id = None

# ==========================================
# 3. SIDEBAR (BRANDED & KEY INPUTS)
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg", width=150)
    st.markdown("<div class='brand-text'>Version A.X.G -Abhi1 Edition</div>", unsafe_allow_html=True)
    st.divider()
    
    # Secure Key Handling
    # Use st.secrets for deployed app, fallback to text_input for local
    if "YOUTUBE_API_KEY" in st.secrets:
        api_key = st.secrets["YOUTUBE_API_KEY"]
        st.success("YouTube Key: ONLINE")
    else:
        api_key = st.text_input("🔑 YouTube API Key", type="password")

    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        ai_enabled = True
        st.success("AI Agent: ONLINE")
    else:
        gemini_key = st.text_input("✨ Gemini API Key", type="password")
        if gemini_key:
            genai.configure(api_key=gemini_key)
            ai_enabled = True
        else:
            ai_enabled = False
            st.warning("AI Agent: OFFLINE")
    
    st.divider()
    country_code = st.selectbox("Target Region", ["US", "IN", "GB", "CA", "AU"], index=0)
    rpm = st.slider("RPM Calculator ($)", 0.5, 20.0, 3.0)

# ==========================================
# 4. CORE FUNCTIONS
# ==========================================
@st.cache_data(show_spinner=False)
def get_market_data(api_key, query, max_results=50):
    youtube = build('youtube', 'v3', developerKey=api_key)
    search_req = youtube.search().list(part="snippet", q=query, type="video", regionCode=country_code, maxResults=max_results, order="viewCount").execute()
    video_ids = [item['id']['videoId'] for item in search_req.get('items', [])]
    
    stats_req = youtube.videos().list(part="snippet,statistics,contentDetails", id=",".join(video_ids)).execute()
    
    data, all_tags = [], []
    for item in stats_req.get('items', []):
        stats, snippet, content = item['statistics'], item['snippet'], item['contentDetails']
        
        views = int(stats.get('viewCount', 0))
        likes = int(stats.get('likeCount', 0))
        comments = int(stats.get('commentCount', 0))
        tags = snippet.get('tags', [])
        if tags: all_tags.extend(tags)
        
        try:
            duration_mins = round(isodate.parse_duration(content['duration']).total_seconds() / 60, 2)
        except:
            duration_mins = 0
        
        thumb_url = snippet['thumbnails'].get('maxres', snippet['thumbnails']['high'])['url']
        
        data.append({
            'Video ID': item['id'],
            'Thumbnail': thumb_url,
            'Title': snippet['title'],
            'Views': views,
            'Likes': likes,
            'Comments': comments,
            'Engagement': round(((likes + comments) / views * 100) if views > 0 else 0, 2),
            'Earnings': round((views / 1000) * rpm, 2),
            'Virality Raw': (views * 0.5) + (likes * 50) + (comments * 100),
            'Link': f"https://www.youtube.com/watch?v={item['id']}",
            'Published': snippet['publishedAt'][:10],
            'Duration': duration_mins,
            'Tags': tags
        })
    
    df = pd.DataFrame(data)
    if not df.empty:
        df['Virality Score'] = (df['Virality Raw'] / df['Virality Raw'].max()) * 10
    return df, all_tags

def get_transcript_text(video_id):
    try:
        return " ".join([t['text'] for t in YouTubeTranscriptApi.get_transcript(video_id)])
    except:
        return None

# --- AI FUNCTIONS (FIXED MODEL NAMES) ---
def ai_forensic_audit(transcript, title, duration, tags):
    # Fixed to stable gemini-1.0-pro
    model = genai.GenerativeModel('gemini-1.0-pro') 
    
    if transcript:
        context_source = "Full Transcript"
        context_data = transcript[:8000]
    else:
        context_source = "Title & Metadata (Transcript Unavailable)"
        context_data = f"Title: {title}. Tags: {tags}"

    prompt = f"Act as a Pro Video Editor. Analyze this content (Source: {context_source}): {context_data}. Output a Markdown report with: 1. Pacing Analysis (Fast/Slow, Est. Cuts/Min). 2. Recommended Tech Stack (Software, Effects). 3. A 3-point Timeline Blueprint (Hook, Middle, End)."
    return model.generate_content(prompt).text

def ai_title_generator(transcript, title):
    # Fixed to stable gemini-1.0-pro
    model = genai.GenerativeModel('gemini-1.0-pro')
    prompt = f"Act as MrBeast's Title writer. Here is a video transcript: {transcript[:4000]}. The original title was '{title}'. Give me 5 NEW, high-CTR (Click-Through Rate) title alternatives. Be bold and create curiosity."
    return model.generate_content(prompt).text

def ai_thumbnail_auditor(image_url):
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    
    # Fixed to stable gemini-pro-vision
    model = genai.GenerativeModel('gemini-pro-vision') 
    prompt = "You are a YouTube Thumbnail Expert. Audit this image. Provide: 1. A CTR Score (out of 10). 2. Analysis of its colors, text, and emotion. 3. One actionable tip for improvement."
    return model.generate_content([prompt, img]).text

# ==========================================
# 5. POPUP MODAL
# ==========================================
@st.dialog("Forensic Editing Lab", width="large")
def open_forensic_lab(vid, title, duration, tags):
    st.markdown(f"### Target: {title}")
    transcript = get_transcript_text(vid)
    
    if not transcript:
        st.warning("No transcript found. Running metadata-only estimation...")

    with st.spinner("⚙️ Reverse Engineering Timeline..."):
        analysis = ai_forensic_audit(transcript, title, duration, tags)
    
    st.success("✅ Analysis Complete")
    st.markdown(analysis)

# ==========================================
# 6. DASHBOARD UI
# ==========================================
st.title("YouTube GEN AXE")

# 1. Search Bar (NameError Fix)
c1, c2 = st.columns([4, 1])
with c1:
    query = st.text_input("Enter Topic, Niche, or Channel", placeholder="e.g. 'MrBeast', 'AI News'", label_visibility="collapsed")
with c2:
    if st.button("Analyze Market", type="primary", use_container_width=True):
        if api_key and query:
            with st.spinner('🛰️ Analyzing market data...'):
                try:
                    st.session_state.df, st.session_state.all_tags = get_market_data(api_key, query, 50)
                    st.session_state.search_done = True
                    st.session_state.selected_video_id = None
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        else:
            st.error("❌ Keys or Query Missing")

# 4. RESULTS AREA
if st.session_state.search_done:
    df = st.session_state.df
    st.write("") 
    
    # --- HUD METRICS (with Red/Orange CSS) ---
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(f"<div class='metric-card'><div class='stat-label'>Total Views</div><div class='stat-value-red'>{df['Views'].sum():,}</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-card'><div class='stat-label'>Est. Market Value</div><div class='stat-value-orange'>${df['Earnings'].sum():,.0f}</div></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='metric-card'><div class='stat-label'>Avg Duration</div><div class='stat-value-red'>{df['Duration'].mean():.1f}m</div></div>", unsafe_allow_html=True)
    with m4: st.markdown(f"<div class='metric-card'><div class='stat-label'>Top Virality</div><div class='stat-value-orange'>{df['Virality Score'].max():.1f} / 10</div></div>", unsafe_allow_html=True)

    st.write("")
    
    # --- MAIN TABLE (Click-to-Select) ---
    st.markdown("### Market Database")
    st.caption("Click any video row to select it for analysis.")
    
    event = st.dataframe(
        df[['Thumbnail', 'Title', 'Views', 'Duration', 'Virality Score', 'Link', 'Video ID']], 
        column_config={
            "Thumbnail": st.column_config.ImageColumn("Preview"), 
            "Virality Score": st.column_config.ProgressColumn("Score ( / 10)", min_value=0, max_value=10),
            "Link": st.column_config.LinkColumn("▶️ WATCH"), 
            "Video ID": None
        }, 
        use_container_width=True, 
        height=500,
        hide_index=True,
        on_select="rerun", 
        selection_mode="single-row"
    )
    
    if event.selection.rows:
        selected_index = event.selection.rows[0]
        st.session_state.selected_video_id = df.iloc[selected_index]['Video ID']

    st.divider()

    # --- ADVANCED TOOLS (Show if a video is selected) ---
    if st.session_state.selected_video_id:
        video_id = st.session_state.selected_video_id
        try:
            row = df[df['Video ID'] == video_id].iloc[0]
        except IndexError:
             st.session_state.selected_video_id = None
             st.stop()
        
        st.markdown(f"### Creator Studio: *{row['Title']}*")
        
        # --- FEATURE TABS ---
        tabs = st.tabs(["✂️ AI Editing Lab", "🎨 AI Thumbnail Auditor", "✍️ AI Title Generator", "🎬 Video Player"])

        # TAB 1: EDITING LAB
        with tabs[0]:
            if st.button("Run Forensic Editing Autopsy", key="edit_btn", type="primary", use_container_width=True):
                if ai_enabled:
                    open_forensic_lab(row['Video ID'], row['Title'], row['Duration'], row['Tags'])
                else:
                    st.warning("AI Module Offline")
            st.info("Analyzes script pacing, estimates cut density, and recommends editing software.")

        # TAB 2: THUMBNAIL AUDITOR (NEW!)
        with tabs[1]:
            c1, c2 = st.columns([1, 1])
            with c1:
                st.image(row['Thumbnail'], use_container_width=True, caption="Target Thumbnail")
            with c2:
                if st.button("Run Thumbnail Vision Audit", key="thumb_btn", type="primary", use_container_width=True):
                    if ai_enabled:
                        with st.spinner("👁️ AI is analyzing image..."):
                            try:
                                audit = ai_thumbnail_auditor(row['Thumbnail'])
                                st.markdown(audit)
                            except Exception as e:
                                st.error(f"Vision API Error: {e}")
                    else:
                        st.warning("AI Module Offline")
                st.info("Uses Gemini Vision to score the thumbnail on color, emotion, and text readability.")
        
        # TAB 3: TITLE GENERATOR (NEW!)
        with tabs[2]:
            if st.button("Generate 5 Viral Titles", key="title_btn", type="primary", use_container_width=True):
                if ai_enabled:
                    transcript = get_transcript_text(row['Video ID']) or f"Title: {row['Title']}"
                    with st.spinner("✍️ AI is writing titles..."):
                        titles = ai_title_generator(transcript, row['Title'])
                        st.markdown(titles)
                else:
                    st.warning("AI Module Offline")
            st.info("Generates 5 new, high-CTR titles based on the video's content.")

        # TAB 4: VIDEO PLAYER
        with tabs[3]:
            st.video(row['Link'])
    else:
        st.info("Select a video from the database to load advanced tools.")
