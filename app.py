import html as _html
import json
import os
import re
import streamlit as st
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env file FIRST — must happen before any os.getenv() calls
load_dotenv()

st.set_page_config(
    page_title="NewsVerified AI — Tamil & English Fact Checker",
    page_icon="🛡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================================
# DESIGN SYSTEM
# ==========================================================

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&family=Noto+Sans+Tamil:wght@400;500;600;700&display=swap');

:root{
    --ink:#080C12;
    --panel:#0F1318;
    --panel-2:#141920;
    --panel-3:#1A2030;
    --border:#232B3A;
    --border-2:#2E3A50;
    --text:#E8ECF4;
    --muted:#7A88A0;
    --gold:#D4A843;
    --gold-glow:rgba(212,168,67,0.18);
    --verified:#2FD494;
    --verified-glow:rgba(47,212,148,0.14);
    --false:#F06060;
    --false-glow:rgba(240,96,96,0.14);
    --misleading:#F0B429;
    --misleading-glow:rgba(240,180,41,0.14);
    --unknown:#566070;
    --tamil:#A78BFA;
    --serif:'Fraunces',serif;
    --sans:'Inter',sans-serif;
    --mono:'JetBrains Mono',monospace;
    --ta:'Noto Sans Tamil','Inter',sans-serif;
}

html,body,[class*="css"]{
    background:var(--ink) !important;
    color:var(--text);
    font-family:var(--sans);
}

.block-container{
    padding-top:1.8rem;
    padding-left:2.8rem;
    padding-right:2.8rem;
    max-width:1340px;
}

hr{ border-color:var(--border) !important; }

/* ── MASTHEAD ── */
.masthead{
    border-top:3px double var(--gold);
    border-bottom:1px solid var(--border);
    padding:32px 4px 20px;
    margin-bottom:16px;
}
.masthead .eyebrow{
    font-family:var(--mono);
    font-size:10px;
    letter-spacing:3px;
    color:var(--gold);
    text-transform:uppercase;
    margin-bottom:10px;
}
.masthead h1{
    font-family:var(--serif);
    font-weight:700;
    font-size:52px;
    margin:0 0 6px;
    color:var(--text);
    line-height:1.1;
}
.masthead h1 .icon{ color:var(--gold); }
.masthead .sub{
    font-family:var(--sans);
    font-size:15px;
    color:var(--muted);
    max-width:700px;
    line-height:1.6;
    margin-bottom:14px;
}
.pill-row{ display:flex; flex-wrap:wrap; gap:8px; }
.pill{
    font-family:var(--mono);
    font-size:11px;
    color:var(--text);
    background:var(--panel-2);
    border:1px solid var(--border);
    border-radius:20px;
    padding:5px 14px;
}
.pill.on{ border-color:var(--verified); color:var(--verified); }
.pill.lang{ border-color:var(--tamil); color:var(--tamil); }

/* ── STAT CARDS ── */
.stat-card{
    background:var(--panel);
    border:1px solid var(--border);
    border-radius:14px;
    padding:18px 16px;
    transition:border-color .2s;
}
.stat-card:hover{ border-color:var(--gold); }
.stat-card .lbl{
    font-family:var(--mono);
    font-size:10px;
    letter-spacing:1.5px;
    text-transform:uppercase;
    color:var(--muted);
    margin-bottom:6px;
}
.stat-card .val{
    font-family:var(--serif);
    font-size:34px;
    font-weight:700;
    color:var(--text);
}
.stat-card.real .val{ color:var(--verified); }
.stat-card.fake .val{ color:var(--false); }
.stat-card.mis .val{ color:var(--misleading); }
.stat-card.ta .val{ color:var(--tamil); }

/* ── SECTION LABELS ── */
.sec-lbl{
    font-family:var(--mono);
    font-size:10px;
    letter-spacing:2.5px;
    text-transform:uppercase;
    color:var(--gold);
    margin:28px 0 4px;
    display:flex;
    align-items:center;
    gap:10px;
}
.sec-lbl::after{ content:''; flex:1; height:1px; background:var(--border); }
.sec-title{
    font-family:var(--serif);
    font-size:22px;
    font-weight:600;
    margin:2px 0 12px;
    color:var(--text);
}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"]{
    gap:4px;
    border-bottom:1px solid var(--border);
}
.stTabs [data-baseweb="tab"]{
    font-family:var(--mono);
    font-size:12px;
    letter-spacing:1px;
    text-transform:uppercase;
    color:var(--muted);
    background:transparent;
    border-radius:8px 8px 0 0;
    padding:10px 20px;
}
.stTabs [aria-selected="true"]{
    color:var(--gold) !important;
    background:var(--panel) !important;
    border-bottom:2px solid var(--gold) !important;
}

/* ── INPUTS ── */
.stTextArea textarea,.stTextInput input{
    background:var(--panel) !important;
    color:var(--text) !important;
    border:1px solid var(--border) !important;
    border-radius:10px !important;
    font-family:var(--ta) !important;
    font-size:15px !important;
    line-height:1.8 !important;
}
.stTextArea textarea:focus,.stTextInput input:focus{
    border-color:var(--gold) !important;
    box-shadow:0 0 0 1px var(--gold) !important;
}
[data-testid="stFileUploaderDropzone"]{
    background:var(--panel) !important;
    border:1.5px dashed var(--border-2) !important;
    border-radius:12px !important;
    transition:border-color .2s;
}
[data-testid="stFileUploaderDropzone"]:hover{
    border-color:var(--gold) !important;
}

/* ── BUTTONS ── */
.stButton>button{
    width:100%;
    border:1.5px solid var(--gold);
    border-radius:10px;
    background:transparent;
    color:var(--gold);
    padding:12px 8px;
    font-family:var(--mono);
    font-size:13px;
    letter-spacing:1.5px;
    text-transform:uppercase;
    transition:all .15s ease;
}
.stButton>button:hover{
    background:var(--gold);
    color:var(--ink);
    transform:translateY(-1px);
    box-shadow:0 6px 16px var(--gold-glow);
}

/* ── VERDICT STAMP ── */
.stamp-wrap{
    display:flex;
    flex-direction:column;
    align-items:center;
    padding:24px 8px 12px;
}
.stamp{
    font-family:var(--serif);
    font-weight:700;
    font-size:18px;
    letter-spacing:2px;
    text-transform:uppercase;
    border:3px double currentColor;
    border-radius:12px;
    padding:14px 24px;
    transform:rotate(-4deg);
    text-align:center;
    animation:stamp-in .4s ease;
    transition:transform .3s;
}
.stamp:hover{ transform:rotate(0) scale(1.06); }
@keyframes stamp-in{
    from{ transform:rotate(-4deg) scale(1.4); opacity:0; }
    to{ transform:rotate(-4deg) scale(1); opacity:1; }
}
.stamp-true{ color:var(--verified); box-shadow:0 0 24px var(--verified-glow); }
.stamp-false{ color:var(--false); box-shadow:0 0 24px var(--false-glow); }
.stamp-misleading{ color:var(--misleading); box-shadow:0 0 24px var(--misleading-glow); }
.stamp-unknown{ color:var(--unknown); }
.conf-val{
    font-family:var(--mono);
    font-size:36px;
    font-weight:600;
    color:var(--text);
    margin-top:16px;
}
.conf-cap{
    font-family:var(--mono);
    font-size:10px;
    letter-spacing:1.5px;
    text-transform:uppercase;
    color:var(--muted);
    margin-top:2px;
}
.stProgress>div>div{
    border-radius:4px !important;
    transition:width .5s ease;
}

/* ── TEXT BOXES ── */
.claim-box{
    background:var(--panel);
    border-left:3px solid var(--gold);
    border-radius:0 10px 10px 0;
    padding:16px 18px;
    font-family:var(--ta);
    font-size:15px;
    line-height:1.85;
    color:var(--text);
    margin-bottom:14px;
}
.field-lbl{
    font-family:var(--mono);
    font-size:10px;
    letter-spacing:1.5px;
    text-transform:uppercase;
    color:var(--muted);
    margin:14px 0 6px;
}
.explanation-box{
    background:var(--panel-2);
    border:1px solid var(--border);
    border-radius:10px;
    padding:16px 18px;
    font-size:15px;
    line-height:1.7;
    color:var(--text);
    margin-bottom:10px;
}
.recommend-box{
    background:rgba(167,139,250,0.07);
    border:1px solid rgba(167,139,250,0.22);
    border-radius:10px;
    padding:14px 18px;
    font-size:15px;
    line-height:1.7;
    color:var(--text);
}
.ocr-box{
    background:var(--panel);
    border:1px solid var(--border);
    border-left:3px solid var(--tamil);
    border-radius:0 10px 10px 0;
    padding:14px 16px;
    font-family:var(--ta);
    font-size:14px;
    line-height:1.85;
    color:var(--muted);
    margin:8px 0 14px;
    max-height:180px;
    overflow-y:auto;
}

/* ── NEWS CARDS ── */
.news-card{
    background:var(--panel);
    border:1px solid var(--border);
    border-radius:14px;
    overflow:hidden;
    margin-bottom:14px;
    transition:border-color .2s, transform .2s, box-shadow .2s;
}
.news-card:hover{
    border-color:var(--gold);
    transform:translateY(-3px);
    box-shadow:0 8px 24px rgba(0,0,0,0.4);
}
.news-card-img{
    width:100%;
    max-height:200px;
    object-fit:cover;
    display:block;
}
.news-card-body{ padding:14px 16px; }
.news-card-source{
    font-family:var(--mono);
    font-size:10px;
    letter-spacing:1.5px;
    text-transform:uppercase;
    color:var(--gold);
    margin-bottom:6px;
}
.news-card h4{
    font-family:var(--serif);
    font-size:16px;
    font-weight:600;
    margin:0 0 6px;
    color:var(--text);
    line-height:1.4;
}
.news-card-snippet{
    font-family:var(--ta);
    font-size:13px;
    color:var(--muted);
    line-height:1.65;
}

/* ── VIDEO EMBED ── */
.video-frame{
    position:relative;
    padding-bottom:56.25%;
    height:0;
    overflow:hidden;
    border-radius:12px;
    border:1px solid var(--border);
    background:var(--panel-2);
    margin-bottom:14px;
}
.video-frame iframe{
    position:absolute;
    top:0; left:0;
    width:100%; height:100%;
    border:none;
    border-radius:12px;
}

/* ── FOOTER ── */
.site-footer{
    text-align:center;
    padding:28px 0 6px;
    border-top:1px solid var(--border);
    margin-top:8px;
}
.site-footer .ft{
    font-family:var(--mono);
    font-size:11px;
    color:var(--muted);
    letter-spacing:1px;
    margin:3px 0;
}

[data-testid="stMetricValue"]{ font-family:var(--serif) !important; }
[data-testid="stMetricLabel"]{ font-family:var(--mono) !important; font-size:10px !important; letter-spacing:1px !important; text-transform:uppercase !important; color:var(--muted) !important; }
.streamlit-expanderHeader{
    background:var(--panel) !important;
    border:1px solid var(--border) !important;
    border-radius:10px !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# HELPERS
# ==========================================================

def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        d = urlparse(url).netloc
        return d.lstrip("www.") or url[:40]
    except Exception:
        return url[:40]


def _is_real_article_image(img_url: str) -> bool:
    """Return True only if this URL looks like a real article photo, not a logo/favicon."""
    if not img_url:
        return False
    lower = img_url.lower()

    # ── ALWAYS ALLOW: trusted real-image CDNs ─────────────────────────
    always_allow = [
        "img.youtube.com",           # YouTube video thumbnails (hqdefault.jpg)
        "i.ytimg.com",               # YouTube CDN thumbnails
        "upload.wikimedia.org",      # Wikipedia images
        "ichef.bbci.co.uk",          # BBC images
        "images.hindustantimes",
        "static.toiimg.com",         # Times of India
        "ndtvimg.com",               # NDTV
        "akm-img-a-in.tosshub.com",  # India Today CDN
        "images.indianexpress.com",
        "s3.ap-southeast-1",         # Common AWS S3 news CDN
        "res.cloudinary.com",        # Cloudinary CDN
    ]
    for pat in always_allow:
        if pat in lower:
            return True

    # ── BLOCK: Google branding, icons, logos ─────────────────────────
    skip_patterns = [
        "google.com/s2/favicons",
        "googleg_standard_color",
        "branding/googleg",
        "google.com/images/branding",
        "news.google.com",           # Google News GE icon
        "lh3.googleusercontent.com", # Google-hosted app icons
        "play-lh.googleusercontent.com",
        "ssl.gstatic.com",
        "gstatic.com/images",
        "/logo",
        "logo.png",
        "logo.jpg",
        "-logo.",
        "favicon",
        "thehindu-logo",
        "logo_india_today",
        ".ico",
        "app-icon",
        "app_icon",
    ]
    for pat in skip_patterns:
        if pat in lower:
            return False

    # ── REQUIRE: URL must resemble a real image resource ──────────────
    image_signals = [
        ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif",
        "/image", "/photo", "/media", "/thumb", "/picture",
        "cdn", "upload", "static", "assets", "content",
        "img", "images",
    ]
    if not any(sig in lower for sig in image_signals):
        return False

    return True


def _youtube_embed(url: str):
    patterns = [
        r"youtube\.com/watch\?v=([A-Za-z0-9_\-]+)",
        r"youtu\.be/([A-Za-z0-9_\-]+)",
        r"youtube\.com/shorts/([A-Za-z0-9_\-]+)",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return f"https://www.youtube.com/embed/{m.group(1)}"
    return None


def _verdict_label(label: str) -> str:
    return {
        "True":                "Verified True",
        "False":               "Verified False",
        "Misleading":          "Misleading",
        "Needs Verification":  "Needs Verification",
    }.get(label, "Unknown")


def _stamp_class(label: str) -> str:
    return {
        "True":       "stamp-true",
        "False":      "stamp-false",
        "Misleading": "stamp-misleading",
    }.get(label, "stamp-unknown")


def _progress_color(label: str) -> str:
    return {
        "True":       "#2FD494",
        "False":      "#F06060",
        "Misleading": "#F0B429",
    }.get(label, "#566070")


def _save_result(data: dict):
    st.session_state["result"] = data
    hist = st.session_state.get("history", [])
    if data not in hist:
        hist.append(data)
        st.session_state["history"] = hist

# ==========================================================
# LOAD PERSISTENT HISTORY
# ==========================================================

HISTORY_PATH = Path(os.getenv("HISTORY_PATH", "history.json"))

if "history" not in st.session_state:
    if HISTORY_PATH.exists():
        try:
            with HISTORY_PATH.open("r", encoding="utf-8") as f:
                st.session_state["history"] = json.load(f)
        except Exception:
            st.session_state["history"] = []
    else:
        st.session_state["history"] = []

# ==========================================================
# SIDEBAR — API STATUS DIAGNOSTICS
# ==========================================================

with st.sidebar:
    st.markdown("## 🛡 NewsVerified AI")
    st.markdown("---")
    st.markdown("### ⚙️ System Status")

    _groq_key     = os.getenv("GROQ_API_KEY", "")
    _news_key     = os.getenv("NEWS_API_KEY", "")
    _gnews_key    = os.getenv("GNEWS_API_KEY", "")
    _newsdata_key = os.getenv("NEWSDATA_API_KEY", "")
    _PLACEHOLDERS = {
        "your_groq_api_key_here", "your_newsapi_key_here",
        "your_gnews_api_key_here", "your_newsdata_api_key_here", "", None,
    }

    def _key_badge(key, name, url, required=False):
        is_set = bool(key) and key not in _PLACEHOLDERS
        icon  = "🟢" if is_set else ("🔴" if required else "🟡")
        label = "Active" if is_set else ("MISSING — Required" if required else "Not set (optional)")
        st.markdown(f"{icon} **{name}** — {label}")
        if not is_set:
            st.caption(f"↑ Get free key: [{url}]({url})")

    _key_badge(_groq_key,     "Groq API (LLM)",        "https://console.groq.com/",  required=True)
    _key_badge(_news_key,     "NewsAPI (English news)", "https://newsapi.org/",        required=False)
    _key_badge(_gnews_key,    "GNews (Tamil/English)",  "https://gnews.io/",           required=False)
    _key_badge(_newsdata_key, "NewsData.io (Tamil)",    "https://newsdata.io/",        required=False)

    st.markdown("---")
    _groq_active = bool(_groq_key) and _groq_key not in _PLACEHOLDERS
    if not _groq_active:
        st.error(
            "🚨 **No API keys found!**\n\n"
            "Your `.env` file has placeholder values.\n\n"
            "**To fix:**\n"
            "1. Open `.env` in your project folder\n"
            "2. Replace `your_groq_api_key_here` with your real key\n"
            "   from [console.groq.com](https://console.groq.com/)\n"
            "3. Save the file and **restart** the Streamlit app\n\n"
            "Without Groq, only basic rule-based analysis runs."
        )
    else:
        st.success("✅ Groq LLM is active. AI-powered verification enabled.")

    st.markdown("### 📰 Active News Sources")
    _active_sources = [
        "Google News RSS ✅ (always on)",
        "Wikipedia ✅ (always on)",
        "YouTube Tamil Channels ✅ (always on)",
    ]
    if _news_key     and _news_key     not in _PLACEHOLDERS: _active_sources.append("NewsAPI ✅")
    if _gnews_key    and _gnews_key    not in _PLACEHOLDERS: _active_sources.append("GNews ✅")
    if _newsdata_key and _newsdata_key not in _PLACEHOLDERS: _active_sources.append("NewsData.io ✅")

    for src in _active_sources:
        st.markdown(f"- {src}")

    if len(_active_sources) <= 3:
        st.warning(
            "⚠️ Only free sources active. Add NewsAPI / GNews / NewsData.io keys "
            "in your `.env` for much better accuracy."
        )

    st.markdown("---")
    st.caption("📁 Edit `.env` in your project folder and restart the app to apply changes.")


# ==========================================================
# MASTHEAD
# ==========================================================

st.markdown("""
<div class="masthead">
    <div class="eyebrow">Multilingual AI Verification Desk &mdash; Tamil &amp; English</div>
    <h1><span class="icon">&#128737;</span> NewsVerified AI</h1>
    <div class="sub">
        A professional fact-checking bench for Tamil and English news &mdash;
        verify text, images, video, and URLs with AI-powered analysis,
        cross-referenced with live news sources, related images, and videos.
    </div>
    <div class="pill-row">
        <span class="pill on">&#10003; Text</span>
        <span class="pill on">&#10003; Image</span>
        <span class="pill on">&#10003; Video</span>
        <span class="pill on">&#10003; URL</span>
        <span class="pill lang">Tamil</span>
        <span class="pill lang">English</span>
        <span class="pill">AI + OCR + RAG + Groq</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================================
# DASHBOARD STATS
# ==========================================================

history_all = st.session_state.get("history", [])
_total = len(history_all)
_real  = sum(1 for i in history_all if i.get("result", {}).get("label") == "True")
_fake  = sum(1 for i in history_all if i.get("result", {}).get("label") == "False")
_mis   = sum(1 for i in history_all if i.get("result", {}).get("label") == "Misleading")
_tamil = sum(1 for i in history_all if i.get("detected_language") == "ta")

c1, c2, c3, c4, c5 = st.columns(5)
for col, css, lbl, val in [
    (c1, "",     "Total Verified",    _total),
    (c2, "real", "Verified True",     _real),
    (c3, "fake", "Verified False",    _fake),
    (c4, "mis",  "Misleading",        _mis),
    (c5, "ta",   "Tamil Checks",      _tamil),
]:
    with col:
        st.markdown(f"""
        <div class='stat-card {css}'>
            <div class='lbl'>{lbl}</div>
            <div class='val'>{val}</div>
        </div>""", unsafe_allow_html=True)

st.write("")

# ==========================================================
# VERIFICATION TABS
# ==========================================================

st.markdown("<div class='sec-lbl'>Submit for Review</div>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📝 Text", "🖼 Image", "🎬 Video", "🔗 URL"])

BACKEND = "http://127.0.0.1:8000"
ERR_MSG = (
    "❌ Cannot connect to the backend. "
    "Make sure it is running: `uvicorn main:app --reload`"
)

# ── TAB 1: TEXT ──────────────────────────────────────────
with tab1:
    st.markdown("<div class='sec-title'>Verify News Text</div>", unsafe_allow_html=True)
    st.caption("Paste Tamil or English news content below to verify it.")

    news_text = st.text_area(
        "News content",
        height=190,
        placeholder="Paste a news article, headline, or claim here (Tamil or English)...",
        key="text_input",
        label_visibility="collapsed",
    )

    if st.button("🛡 Verify Text", key="verify_text"):
        if not news_text.strip():
            st.warning("Please enter some news text.")
        else:
            with st.spinner("Analyzing..."):
                try:
                    r = requests.post(
                        f"{BACKEND}/verify/text",
                        json={"content": news_text},
                        timeout=180,
                    )
                    if r.status_code == 200:
                        _save_result(r.json())
                        st.success("✅ Verification complete!")
                        st.rerun()
                    else:
                        st.error(r.text)
                except requests.exceptions.ConnectionError:
                    st.error(ERR_MSG)
                except Exception as e:
                    st.error(str(e))

# ── TAB 2: IMAGE ─────────────────────────────────────────
with tab2:
    st.markdown("<div class='sec-title'>Verify News Image</div>", unsafe_allow_html=True)
    st.caption(
        "Upload a Tamil newspaper screenshot, WhatsApp forward, or any news image. "
        "AI will OCR both Tamil and English text automatically."
    )

    uploaded_img = st.file_uploader(
        "Upload image",
        type=["png", "jpg", "jpeg", "webp"],
        key="image",
        label_visibility="collapsed",
    )

    if uploaded_img:
        col_img, col_btn = st.columns([3, 1])
        with col_img:
            st.image(uploaded_img, width=600)
        with col_btn:
            if st.button("🛡 Verify Image", key="verify_image"):
                with st.spinner("Reading image text..."):
                    try:
                        r = requests.post(
                            f"{BACKEND}/verify/image",
                            files={
                                "file": (
                                    uploaded_img.name,
                                    uploaded_img.getvalue(),
                                    uploaded_img.type,
                                )
                            },
                            timeout=150,
                        )
                        if r.status_code == 200:
                            _save_result(r.json())
                            st.success("✅ Done!")
                            st.rerun()
                        else:
                            st.error(r.text)
                    except requests.exceptions.ConnectionError:
                        st.error(ERR_MSG)
                    except Exception as e:
                        st.error(str(e))

        # OCR text preview
        res = st.session_state.get("result", {})
        if res.get("source_type") == "image" and res.get("ocr_text"):
            st.markdown(
                "<div class='field-lbl'>Text Extracted from Image (OCR)</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='ocr-box'>{res['ocr_text']}</div>",
                unsafe_allow_html=True,
            )

# ── TAB 3: VIDEO ─────────────────────────────────────────
with tab3:
    st.markdown("<div class='sec-title'>Verify News Video</div>", unsafe_allow_html=True)
    st.caption(
        "Upload a Tamil news channel clip. "
        "AI samples frames every second and reads the full frame "
        "and the lower-third chyron/ticker region for text."
    )

    uploaded_vid = st.file_uploader(
        "Upload video",
        type=["mp4", "avi", "mov", "mkv"],
        key="video",
        label_visibility="collapsed",
    )

    if uploaded_vid:
        st.video(uploaded_vid)
        if st.button("🛡 Verify Video", key="verify_video"):
            with st.spinner("Analyzing video frames..."):
                try:
                    r = requests.post(
                        f"{BACKEND}/verify/video",
                        files={
                            "file": (
                                uploaded_vid.name,
                                uploaded_vid.getvalue(),
                                uploaded_vid.type,
                            )
                        },
                        timeout=210,
                    )
                    if r.status_code == 200:
                        _save_result(r.json())
                        st.success("✅ Video verification complete!")
                        st.rerun()
                    else:
                        st.error(r.text)
                except requests.exceptions.ConnectionError:
                    st.error(ERR_MSG)
                except Exception as e:
                    st.error(str(e))

        res = st.session_state.get("result", {})
        if res.get("source_type") == "video" and res.get("ocr_text"):
            st.markdown(
                "<div class='field-lbl'>Text Extracted from Video (OCR)</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='ocr-box'>{res['ocr_text']}</div>",
                unsafe_allow_html=True,
            )

# ── TAB 4: URL ───────────────────────────────────────────
with tab4:
    st.markdown("<div class='sec-title'>Verify News URL</div>", unsafe_allow_html=True)
    st.caption(
        "Paste a Tamil or English news article URL. "
        "Supports Dinamalar, BBC Tamil, The Hindu Tamil, and most Indian news sites."
    )

    news_url = st.text_input(
        "News URL",
        placeholder="https://www.dinamalar.com/...  or  https://tamil.bbc.com/...",
        key="url_input",
        label_visibility="collapsed",
    )

    if st.button("🛡 Verify URL", key="verify_url"):
        if not news_url.strip():
            st.warning("Please enter a URL.")
        else:
            with st.spinner("Fetching and analyzing article..."):
                try:
                    r = requests.post(
                        f"{BACKEND}/verify/url",
                        json={"url": news_url},
                        timeout=120,
                    )
                    if r.status_code == 200:
                        _save_result(r.json())
                        st.success("✅ URL verification complete!")
                        st.rerun()
                    else:
                        st.error(r.text)
                except requests.exceptions.ConnectionError:
                    st.error(ERR_MSG)
                except Exception as e:
                    st.error(str(e))

# ==========================================================
# VERIFICATION RESULT
# ==========================================================

if "result" in st.session_state:
    data   = st.session_state["result"]
    result = data.get("result", {})
    lang   = data.get("detected_language", "en")
    is_ta  = lang == "ta"
    label  = result.get("label", "Unknown")
    score  = result.get("confidence_score", 0)

    st.markdown("<div class='sec-lbl'>Findings</div>", unsafe_allow_html=True)
    st.markdown("<div class='sec-title'>AI Verification Result</div>", unsafe_allow_html=True)

    # ── VERDICT + CONFIDENCE ─────────────────────────────
    v_label   = _verdict_label(label)
    s_class   = _stamp_class(label)
    p_color   = _progress_color(label)

    col_main, col_verdict = st.columns([3, 1])

    with col_verdict:
        st.markdown(f"""
        <div class='stamp-wrap'>
            <div class='stamp {s_class}'>{v_label}</div>
            <div class='conf-val'>{score}%</div>
            <div class='conf-cap'>Confidence Score</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(
            f"<style>.stProgress>div>div{{background:{p_color}!important}}</style>",
            unsafe_allow_html=True,
        )
        st.progress(score / 100)

        # Language badge
        lang_display = "Tamil" if is_ta else "English"
        lang_color   = "var(--tamil)" if is_ta else "var(--gold)"
        st.markdown(
            f"<div style='text-align:center;margin-top:10px;font-family:var(--mono);"
            f"font-size:10px;letter-spacing:1px;text-transform:uppercase;"
            f"color:{lang_color}'>Detected Language · {lang_display}</div>",
            unsafe_allow_html=True,
        )

    with col_main:

        # Claim
        st.markdown("<div class='field-lbl'>Claim</div>", unsafe_allow_html=True)
        claim_display = data.get("original_text") or data.get("claim", "No Claim")
        st.markdown(
            f"<div class='claim-box'>{claim_display}</div>",
            unsafe_allow_html=True,
        )

        # Show English translation if input was Tamil
        if is_ta and data.get("claim") and data.get("claim") != claim_display:
            st.markdown(
                "<div class='field-lbl'>English Translation</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='claim-box' style='border-color:var(--tamil);'>"
                f"{data.get('claim', '')}</div>",
                unsafe_allow_html=True,
            )

        # AI Explanation (English)
        st.markdown("<div class='field-lbl'>AI Explanation</div>", unsafe_allow_html=True)
        explanation = result.get("explanation", "No explanation available.")
        st.markdown(
            f"<div class='explanation-box'>{explanation}</div>",
            unsafe_allow_html=True,
        )

        # Recommendation
        st.markdown("<div class='field-lbl'>Recommendation</div>", unsafe_allow_html=True)
        recommendation = result.get("recommendation", "No recommendation.")
        st.markdown(
            f"<div class='recommend-box'>{recommendation}</div>",
            unsafe_allow_html=True,
        )

        # Misinformation analysis
        if result.get("misinformation_analysis"):
            with st.expander("⚠ Misinformation Analysis"):
                st.write(result["misinformation_analysis"])

    st.divider()

    # ── RELATED ARTICLES ─────────────────────────────────
    related = data.get("related_articles", [])

    # Separate images, YouTube videos, and website articles
    all_images = [
        (a.get("image", ""), a.get("source", ""), a.get("title", ""), a.get("url", ""))
        for a in related if _is_real_article_image(a.get("image", ""))
    ]
    yt_videos = [
        (a.get("url", ""), a.get("title", ""), a.get("source", ""), a.get("image", ""))
        for a in related if _youtube_embed(a.get("url", ""))
    ]
    website_articles = [
        a for a in related
        if a.get("url", "") and not _youtube_embed(a.get("url", ""))
    ]

    # ── IMAGE GALLERY ─────────────────────────────────────
    st.markdown("<div class='sec-lbl'>Related Media</div>", unsafe_allow_html=True)
    st.markdown("<div class='sec-title'>News Images</div>", unsafe_allow_html=True)

    if all_images:
        img_cols = st.columns(min(3, len(all_images)))
        for idx, (img_url, src, title, art_url) in enumerate(all_images[:9]):
            with img_cols[idx % 3]:
                try:
                    st.image(img_url, width="stretch")
                    clean_title = re.sub(r"<[^>]+>", "", title)[:65]
                    st.caption(f"📰 {src}\n{clean_title}")
                    if art_url:
                        st.link_button("🔗 View Article", art_url, use_container_width=True)
                except Exception:
                    pass
    else:
        st.info("No article images found. Images appear when news sources provide thumbnails.")

    # ── YOUTUBE VIDEO EMBEDS ──────────────────────────────
    if yt_videos:
        st.markdown("<div class='sec-lbl'>Related Videos</div>", unsafe_allow_html=True)
        st.markdown("<div class='sec-title'>News Videos</div>", unsafe_allow_html=True)

        vid_cols = st.columns(min(2, len(yt_videos)))
        for idx, (url, title, src, thumb) in enumerate(yt_videos[:6]):
            embed = _youtube_embed(url)
            with vid_cols[idx % 2]:
                st.markdown(
                    f'<div class="video-frame"><iframe src="{embed}" '
                    f'allowfullscreen style="width:100%;height:220px;border:none;">'
                    f'</iframe></div>',
                    unsafe_allow_html=True,
                )
                clean_title = re.sub(r"<[^>]+>", "", title)[:75]
                st.caption(f"▶ {src} — {clean_title}")
                st.link_button("🎬 Watch on YouTube", url, use_container_width=True)

    # ── NEWS WEBSITE CARDS ────────────────────────────────
    st.markdown("<div class='sec-lbl'>Related News Sources</div>", unsafe_allow_html=True)
    st.markdown("<div class='sec-title'>News Websites & Articles</div>", unsafe_allow_html=True)

    if not website_articles:
        st.info("No related news articles found. Try a different claim or add more context.")
    else:
        for art in website_articles[:10]:
            img   = art.get("image", "")
            url   = art.get("url", "")
            title_raw = re.sub(r"<[^>]+>", "", art.get("title", "") or "(No Title)")
            src_raw   = re.sub(r"<[^>]+>", "", art.get("source", "Unknown Source"))
            snip_raw  = re.sub(r"<[^>]+>", "", art.get("content", ""))
            date_raw  = art.get("date", "")[:10]
            dom       = _domain(url) if url else src_raw
            score     = art.get("score", 0)
            lang      = art.get("language", "en")
            lang_tag  = "🇮🇳 Tamil" if lang == "ta" else "🇬🇧 English"
            score_pct = int(score * 100)

            with st.container():
                col_img, col_text, col_btn = st.columns([1, 4, 1])

                with col_img:
                    if img and _is_real_article_image(img):
                        try:
                            st.image(img, width="stretch")
                        except Exception:
                            st.markdown("🌐")
                    else:
                        st.markdown("🌐")

                with col_text:
                    st.markdown(f"**{title_raw[:120]}**")
                    meta_parts = [f"📰 {src_raw}", f"🌐 {dom}", lang_tag]
                    if date_raw:
                        meta_parts.append(f"📅 {date_raw}")
                    meta_parts.append(f"● Relevance: {score_pct}%")
                    st.caption(" · ".join(meta_parts))
                    if snip_raw:
                        st.caption(snip_raw[:180] + ("..." if len(snip_raw) > 180 else ""))

                with col_btn:
                    if url:
                        st.link_button("Visit Website →", url, use_container_width=True)

                st.divider()


    # ── EVIDENCE TABLE ────────────────────────────────────

    evidence = data.get("evidence", [])
    if evidence:
        with st.expander("📊 Evidence Table"):
            import pandas as pd
            ev_df = pd.DataFrame([{
                "Title":    e.get("title", "")[:60],
                "Source":   e.get("source", ""),
                "Language": "Tamil" if e.get("language") == "ta" else "English",
                "Score":    round(float(e.get("score", 0)), 3),
                "Date":     e.get("date", "")[:10],
            } for e in evidence])
            st.dataframe(ev_df, width="stretch")

# ==========================================================
# HISTORY TABLE
# ==========================================================

history = st.session_state.get("history", [])

if history:
    st.markdown("<div class='sec-lbl'>Desk Analytics</div>", unsafe_allow_html=True)
    st.markdown("<div class='sec-title'>Verification History</div>", unsafe_allow_html=True)

    total = len(history)
    real = fake = mis = unk = 0
    for item in history:
        lbl = item.get("result", {}).get("label", "")
        if lbl == "True":         real += 1
        elif lbl == "False":      fake += 1
        elif lbl == "Misleading": mis += 1
        else:                     unk += 1

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total",      total)
    m2.metric("True",       real)
    m3.metric("False",      fake)
    m4.metric("Misleading", mis)

    import pandas as pd
    rows = []
    for item in reversed(history[-25:]):
        lbl = item.get("result", {}).get("label", "")
        rows.append({
            "Time":       item.get("timestamp", "")[:16],
            "Type":       item.get("source_type", "text").upper(),
            "Language":   "Tamil" if item.get("detected_language") == "ta" else "English",
            "Claim":      (item.get("original_text") or item.get("claim", ""))[:65],
            "Verdict":    _verdict_label(lbl),
            "Confidence": f"{item.get('result', {}).get('confidence_score', 0)}%",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch")

# ==========================================================
# FOOTER
# ==========================================================

st.markdown("""
<div class="site-footer">
    <div class="ft">&#128737; NewsVerified AI &mdash; Tamil &amp; English Fact Checking Desk</div>
    <div class="ft" style="color:#444;margin-top:4px">
        Powered by Groq &middot; EasyOCR &middot; Google News RSS &middot; RAG &middot; Sentence Transformers
    </div>
</div>
""", unsafe_allow_html=True)