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
# 1. CONFIG & PROFESSIONAL BRIGHT THEME
# ==========================================
st.set_page_config(
    page_title="YouTube GEN AXE", 
    page_icon="https://www.gstatic.com/youtube/img/branding/favicon/favicon_192x192.png", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a professional light/bright "UpGrad-Style" UI
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
# 3. SIDEBAR (BRANDED & FIXED KEY INPUT)
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg", width=150)
    st.markdown("<div class='brand-text'>Version A.X.G -Abhi1 Edition</div>", unsafe_allow_html=True)
    st.divider()
    
    # Secure Key Handling
    if "YOUTUBE_API_KEY" in st.secrets:
        api_key = st.secrets["YOUTUBE_API_KEY"]
        st.success("YouTube Key: ONLINE")
    else:
        api_key = st.text_input("🔑 YouTube API Key", type="password")

    # GEMINI KEY (FIXED: Added manual input)
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
    # FIXED: Using stable gemini-1.0-pro
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
    # FIXED: Using stable gemini-1.0-pro
    model = genai.GenerativeModel('gemini-1.0-pro')
    prompt = f"Act as MrBeast's Title writer. Here is a video transcript: {transcript[:4000]}. The original title was '{title}'. Give me 5 NEW, high-CTR (Click-Through Rate) title alternatives. Be bold and create curiosity."
    return model.generate_content(prompt).text

def ai_thumbnail_auditor(image_url):
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    
    # FIXED: Using stable gemini-pro-vision
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
        analysis = ai_forensic_audit(transcript, title
                                     
