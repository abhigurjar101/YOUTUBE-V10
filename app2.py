import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from googleapiclient.discovery import build
from wordcloud import WordCloud
from collections import Counter
from youtube_transcript_api import YouTubeTranscriptApi
import isodate 
import requests
from PIL import Image
from io import BytesIO

# NEW LIBRARIES FOR GCP/VERTEX AI
from google.cloud import aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# ==========================================
# 1. CONFIG & PRO "BRIGHT" THEME
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
if 'selected_video_id' not in st.session_state: st.session_state.selected_video_id = None

# ==========================================
# 3. SIDEBAR (BRANDED & AUTO-LOGIN)
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
        api_key = None
        st.error("YouTube Key: OFFLINE")

    # NEW: GCP Account Check
    if "GCP_PROJECT_ID" in st.secrets and "GCP_LOCATION" in st.secrets:
        try:
            PROJECT_ID = st.secrets["GCP_PROJECT_ID"]
            LOCATION = st.secrets["GCP_LOCATION"]
            vertexai.init(project=PROJECT_ID, location=LOCATION)
            ai_enabled = True
            st.success(f"AI Account: {PROJECT_ID}")
        except Exception as e:
            st.error(f"AI Login Failed. Run `gcloud auth application-default login` in your terminal.")
            ai_enabled = False
    else:
        ai_enabled = False
        st.warning("AI OFFLINE (Add GCP Secrets)")
    
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
            'Tags': tags,
            'Engagement': round(((likes + comments) / views * 100) if views > 0 else 0, 2),
            'Earnings': round((views / 1000) * rpm, 2),
            'Virality Raw': (views * 0.5) + (likes * 50) + (comments * 100),
            'Link': f"https://www.youtube.com/watch?v={item['id']}",
            'Published': snippet['publishedAt'][:10],
            'Duration': duration_mins,
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

# --- AI FUNCTIONS (REBUILT FOR GCP/VERTEX AI) ---
def ai_text_generator(prompt_text):
    # This uses your GCP key and the model you requested
    model = GenerativeModel("gemini-2.5-pro") 
    response = model.generate_content(prompt_text)
    return response.text

def ai_vision_auditor(image_url, prompt_text):
    response = requests.get(image_url)
    image_bytes = response.content
    
    # This is the correct model name for GCP Vision
    model = GenerativeModel("gemini-1.5-flash-001") 
    
    image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")
    
    response = model.generate_content([prompt_text, image_part])
    return response.text

# ==========================================
# 5. POPUP MODALS
# ==========================================
@st.dialog("AI Tool Result", width="large")
def show_ai_popup(title, analysis_type, content):
    st.markdown(f"### {analysis_type}")
    st.caption(f"Target: {title}")
    st.divider()
    st.markdown(content)

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
        if api_key and query and ai_enabled:
            with st.spinner('🛰️ Analyzing market data...'):
                try:
                    st.session_state.df, st.session_state.all_tags = get_market_data(api_key, query, 50)
                    st.session_state.search_done = True
                    st.session_state.selected_video_id = None
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        elif not api_key:
            st.error("❌ YouTube Key Missing in Secrets")
        elif not ai_enabled:
            st.error("❌ AI Account Offline")
        else:
            st.error("❌ Enter a search query")

# 4. RESULTS AREA
if st.session_state.search_done:
    df = st.session_state.df
    st.write("") 
    
    # --- HUD METRICS ---
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
            transcript = get_transcript_text(row['Video ID']) or f"Title: {row['Title']}"
        except IndexError:
             st.session_state.selected_video_id = None
             st.stop()
        
        st.markdown(f"### Creator Studio: *{row['Title']}*")
        
        # --- FEATURE TABS ---
        tabs = st.tabs(["🤖 AI Marketing Suite", "✂️ AI Editing Lab", "🎨 AI Thumbnail Auditor", "🎬 Video Player"])

        # TAB 1: AI MARKETING (NEW!)
        with tabs[0]:
            st.subheader("SEO & Marketing Strategy")
            if st.button("Run SEO & Marketing Analysis", key="seo_btn", type="primary", use_container_width=True):
                if ai_enabled:
                    with st.spinner("✍️ AI is writing your marketing plan..."):
                        prompt = f"""
                        Act as a YouTube Marketing Expert.
                        Analyze this video:
                        - Title: "{row['Title']}"
                        - Transcript/Context: "{transcript[:6000]}"
                        
                        Generate a complete marketing plan in Markdown:
                        1. **SEO Optimized Description:** Write a full, professional YouTube description.
                        2. **Timestamp Chapters:** Create a list of 5-10 key timestamps and titles.
                        3. **Shorts/Reels Ideas:** Give 3 specific ideas for 60-second shorts from this content.
                        """
                        analysis = ai_text_generator(prompt)
                        show_ai_popup(row['Title'], "AI Marketing Plan", analysis)
                else:
                    st.warning("AI Module Offline")
            st.info("Generates a full SEO description, timestamps, and 3 viral Shorts ideas from the video.")

        # TAB 2: EDITING LAB
        with tabs[1]:
            if st.button("Run Forensic Editing Autopsy", key="edit_btn", type="primary", use_container_width=True):
                if ai_enabled:
                    with st.spinner("⚙️ Reverse Engineering Timeline..."):
                        prompt = f"""
                        Act as a Senior Video Editor. Analyze this content:
                        - Title: "{row['Title']}"
                        - Duration: {row['Duration']} Mins
                        - Transcript: "{transcript[:6000]}"
                        
                        Output a Markdown report with:
                        1. Pacing Analysis (Fast/Slow, Est. Cuts/Min)
                        2. Recommended Tech Stack (Software, Effects)
                        3. A 3-point Timeline Blueprint (Hook, Middle, End)
                        """
                        analysis = ai_text_generator(prompt)
                        show_ai_popup(row['Title'], "AI Editing Autopsy", analysis)
                else:
                    st.warning("AI Module Offline")
            st.info("Analyzes script pacing, estimates cut density, and recommends editing software.")

        # TAB 3: THUMBNAIL AUDITOR
        with tabs[2]:
            c1, c2 = st.columns([1, 1])
            with c1:
                st.image(row['Thumbnail'], use_container_width=True, caption="Target Thumbnail")
            with c2:
                if st.button("Run Thumbnail Vision Audit", key="thumb_btn", type="primary", use_container_width=True):
                    if ai_enabled:
                        with st.spinner("👁️ AI is analyzing image..."):
                            try:
                                prompt = "You are a YouTube Thumbnail Expert. Audit this image. Provide: 1. A CTR Score (out of 10). 2. Analysis of its colors, text, and emotion. 3. One actionable tip for improvement."
                                audit = ai_vision_auditor(row['Thumbnail'], prompt)
                                show_ai_popup(row['Title'], "AI Thumbnail Audit", audit)
                            except Exception as e:
                                st.error(f"Vision API Error: {e}")
                    else:
                        st.warning("AI Module Offline")
                st.info("Uses Gemini Vision to score the thumbnail on color, emotion, and text readability.")
        
        # TAB 4: VIDEO PLAYER
        with tabs[3]:
            st.video(row['Link'])
    else:
        st.info("Select a video from the database to load advanced tools.")
