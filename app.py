import streamlit as st
import requests
import json

st.set_page_config(
    page_title="NewsVerified AI",
    page_icon="🛡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================================
# DESIGN SYSTEM
# ==========================================================
# Concept: a press-credential / newsroom verification desk.
# Ink-black canvas, a single muted-gold "official seal" accent,
# a serif masthead paired with a clean data-grade sans, and a
# rotated stamp motif standing in for the verdict badge.
# ==========================================================

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root{
    --ink:#0A0E14;
    --panel:#12161C;
    --panel-2:#171C26;
    --border:#262C3A;
    --text:#ECEEF1;
    --muted:#8A93A6;
    --gold:#C9A24B;
    --verified:#34D399;
    --false:#F87171;
    --misleading:#FBBF24;
    --unknown:#64748B;
    --serif:'Fraunces', serif;
    --sans:'Inter', sans-serif;
    --mono:'JetBrains Mono', monospace;
}

html, body, [class*="css"]{
    background:var(--ink) !important;
    color:var(--text);
    font-family:var(--sans);
}

.block-container{
    padding-top:2.2rem;
    padding-left:3.2rem;
    padding-right:3.2rem;
    max-width:1280px;
}

hr{ border-color:var(--border) !important; }

/* ---------- MASTHEAD ---------- */

.masthead{
    border-top:3px double var(--gold);
    border-bottom:1px solid var(--border);
    padding:34px 6px 22px 6px;
    margin-bottom:8px;
}

.masthead .eyebrow{
    font-family:var(--mono);
    font-size:12px;
    letter-spacing:3px;
    color:var(--gold);
    text-transform:uppercase;
    margin-bottom:14px;
}

.masthead h1{
    font-family:var(--serif);
    font-weight:700;
    font-size:56px;
    letter-spacing:-1px;
    margin:0 0 10px 0;
    color:var(--text);
}

.masthead h1 .shield{
    color:var(--gold);
    -webkit-text-fill-color:var(--gold);
}

.masthead .dek{
    font-size:16px;
    color:var(--muted);
    max-width:640px;
    line-height:1.6;
    margin-bottom:18px;
}

.pill-row{
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin-top:6px;
}

.pill{
    font-family:var(--mono);
    font-size:12px;
    letter-spacing:0.5px;
    color:var(--text);
    background:var(--panel-2);
    border:1px solid var(--border);
    border-radius:20px;
    padding:6px 14px;
}

.pill.on{
    border-color:var(--verified);
    color:var(--verified);
}

.pill.lang{
    border-color:var(--gold);
    color:var(--gold);
}

/* ---------- STAT CARDS ---------- */

.stat-card{
    background:var(--panel);
    border:1px solid var(--border);
    border-radius:14px;
    padding:22px 20px;
    text-align:left;
    position:relative;
}

.stat-card .stat-label{
    font-family:var(--mono);
    font-size:11px;
    letter-spacing:1.5px;
    text-transform:uppercase;
    color:var(--muted);
    margin-bottom:10px;
}

.stat-card .stat-value{
    font-family:var(--serif);
    font-size:38px;
    font-weight:600;
    color:var(--text);
}

.stat-card .stat-accent{ border-top:2px solid var(--gold); }
.stat-card .stat-verified .stat-value{ color:var(--verified); }
.stat-card .stat-false .stat-value{ color:var(--false); }

/* ---------- SECTION LABELS ---------- */

.section-label{
    font-family:var(--mono);
    font-size:12px;
    letter-spacing:2.5px;
    text-transform:uppercase;
    color:var(--gold);
    margin:34px 0 4px 0;
    display:flex;
    align-items:center;
    gap:10px;
}

.section-label::after{
    content:"";
    flex:1;
    height:1px;
    background:var(--border);
}

.section-title{
    font-family:var(--serif);
    font-size:26px;
    font-weight:600;
    margin:2px 0 18px 0;
    color:var(--text);
}

/* ---------- TABS ---------- */

.stTabs [data-baseweb="tab-list"]{
    gap:6px;
    border-bottom:1px solid var(--border);
}

.stTabs [data-baseweb="tab"]{
    font-family:var(--mono);
    font-size:13px;
    letter-spacing:1px;
    text-transform:uppercase;
    color:var(--muted);
    background:transparent;
    border-radius:8px 8px 0 0;
    padding:10px 18px;
}

.stTabs [aria-selected="true"]{
    color:var(--gold) !important;
    background:var(--panel) !important;
    border-bottom:2px solid var(--gold) !important;
}

/* ---------- INPUTS ---------- */

.stTextArea textarea, .stTextInput input{
    background:var(--panel) !important;
    color:var(--text) !important;
    border:1px solid var(--border) !important;
    border-radius:10px !important;
    font-family:var(--sans) !important;
}

.stTextArea textarea:focus, .stTextInput input:focus{
    border-color:var(--gold) !important;
    box-shadow:0 0 0 1px var(--gold) !important;
}

[data-testid="stFileUploaderDropzone"]{
    background:var(--panel) !important;
    border:1px dashed var(--border) !important;
    border-radius:10px !important;
}

/* ---------- BUTTONS ---------- */

.stButton>button{
    width:100%;
    border:1px solid var(--gold);
    border-radius:8px;
    background:transparent;
    color:var(--gold);
    padding:11px;
    font-family:var(--mono);
    font-size:13px;
    letter-spacing:1.5px;
    text-transform:uppercase;
    transition:all .15s ease;
}

.stButton>button:hover{
    background:var(--gold);
    color:var(--ink);
}

.stDownloadButton>button{
    border:1px solid var(--border);
    border-radius:8px;
    background:var(--panel);
    color:var(--text);
    font-family:var(--mono);
    font-size:13px;
    letter-spacing:1px;
}

/* ---------- ALERTS (success/warning/error/info) ---------- */

[data-testid="stAlert"]{
    background:var(--panel) !important;
    border:1px solid var(--border) !important;
    border-radius:10px !important;
}

/* ---------- RESULT CARD ---------- */

.claim-box{
    background:var(--panel);
    border-left:3px solid var(--gold);
    border-radius:0 10px 10px 0;
    padding:18px 20px;
    font-size:15px;
    line-height:1.6;
    color:var(--text);
    margin-bottom:18px;
}

.field-label{
    font-family:var(--mono);
    font-size:11px;
    letter-spacing:1.5px;
    text-transform:uppercase;
    color:var(--muted);
    margin:16px 0 8px 0;
}

.body-text{
    font-size:15px;
    line-height:1.65;
    color:var(--text);
}

.recommend-box{
    background:var(--panel-2);
    border:1px solid var(--border);
    border-radius:10px;
    padding:16px 18px;
    font-size:14px;
    color:var(--text);
    line-height:1.6;
}

/* ---------- VERDICT STAMP ---------- */

.stamp-wrap{
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    padding:22px 10px 10px 10px;
}

.stamp{
    font-family:var(--serif);
    font-weight:700;
    font-size:18px;
    letter-spacing:2px;
    text-transform:uppercase;
    border:3px double currentColor;
    border-radius:10px;
    padding:14px 22px;
    transform:rotate(-4deg);
    text-align:center;
    display:inline-block;
}

.stamp-true{ color:var(--verified); }
.stamp-false{ color:var(--false); }
.stamp-misleading{ color:var(--misleading); }
.stamp-unknown{ color:var(--unknown); }

.confidence-value{
    font-family:var(--mono);
    font-size:34px;
    font-weight:600;
    color:var(--text);
    margin-top:18px;
}

.confidence-caption{
    font-family:var(--mono);
    font-size:11px;
    letter-spacing:1.5px;
    text-transform:uppercase;
    color:var(--muted);
}

.stProgress > div > div{
    background:var(--gold) !important;
}

/* ---------- ARTICLE ROW ---------- */

.article-card{
    background:var(--panel);
    border:1px solid var(--border);
    border-radius:12px;
    padding:18px 20px;
    margin-bottom:14px;
}

.article-card h4{
    font-family:var(--serif);
    font-size:19px;
    margin:0 0 4px 0;
    color:var(--text);
}

.article-source{
    font-family:var(--mono);
    font-size:11px;
    letter-spacing:1px;
    text-transform:uppercase;
    color:var(--gold);
    margin-bottom:10px;
}

/* ---------- FOOTER ---------- */

.site-footer{
    text-align:center;
    padding:36px 0 10px 0;
    border-top:1px solid var(--border);
    margin-top:10px;
}

.site-footer .foot-title{
    font-family:var(--serif);
    font-size:20px;
    color:var(--gold);
    margin-bottom:8px;
}

.site-footer .foot-line{
    font-family:var(--mono);
    font-size:12px;
    letter-spacing:1px;
    color:var(--muted);
    margin:4px 0;
}

[data-testid="stMetricValue"]{
    font-family:var(--serif) !important;
    color:var(--text) !important;
}

[data-testid="stMetricLabel"]{
    font-family:var(--mono) !important;
    letter-spacing:1px;
    text-transform:uppercase;
    color:var(--muted) !important;
}

.streamlit-expanderHeader{
    background:var(--panel) !important;
    border:1px solid var(--border) !important;
    border-radius:10px !important;
    font-family:var(--sans) !important;
}

</style>
""", unsafe_allow_html=True)

# ==========================================================
# MASTHEAD
# ==========================================================

st.markdown("""
<div class="masthead">
    <div class="eyebrow">Multilingual AI Verification Desk</div>
    <h1><span class="shield">&#128737;</span> NewsVerified AI</h1>
    <div class="dek">
        A professional fact-checking bench for text, images, video and URLs —
        cross-referenced with retrieval-augmented evidence and read aloud
        in Tamil and English.
    </div>
    <div class="pill-row">
        <span class="pill on">&#10003; Text</span>
        <span class="pill on">&#10003; Images</span>
        <span class="pill on">&#10003; Video</span>
        <span class="pill on">&#10003; URLs</span>
        <span class="pill lang">IN Tamil</span>
        <span class="pill lang">GB English</span>
        <span class="pill">AI + RAG + OCR + Groq</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")

# ==========================================================
# DASHBOARD STATS
# ==========================================================

history_preview = st.session_state.get("history", [])
_total = len(history_preview)
_real = sum(1 for i in history_preview if i.get("result", {}).get("label") == "True")
_fake = sum(1 for i in history_preview if i.get("result", {}).get("label") == "False")
_bi = sum(1 for i in history_preview if i.get("claim", "").isascii() is False) if history_preview else 0

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class='stat-card stat-accent'>
        <div class='stat-label'>Total Verifications</div>
        <div class='stat-value'>{_total}</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class='stat-card stat-verified'>
        <div class='stat-label'>Real News</div>
        <div class='stat-value'>{_real}</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class='stat-card stat-false'>
        <div class='stat-label'>Fake News</div>
        <div class='stat-value'>{_fake}</div>
    </div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class='stat-card'>
        <div class='stat-label'>Tamil + English</div>
        <div class='stat-value'>{_total}</div>
    </div>""", unsafe_allow_html=True)

st.write("")

# ==========================================================
# VERIFICATION DESK — TABS
# ==========================================================

st.markdown("<div class='section-label'>Submit for Review</div>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "Text",
    "Image",
    "Video",
    "URL"
])

# ------------------------------
# TEXT
# ------------------------------

with tab1:
    st.markdown("<div class='section-title'>Verify News Text</div>", unsafe_allow_html=True)

    news_text = st.text_area(
        "Paste News Content",
        height=180,
        placeholder="Paste any news article or claim..."
    )

    if st.button("Verify Text", key="verify_text"):

        if news_text.strip() == "":
            st.warning("Please enter some news text.")
        else:
            with st.spinner("Analyzing..."):
                try:
                    response = requests.post(
                        "http://127.0.0.1:8000/verify/text",
                        json={"content": news_text}
                    )

                    if response.status_code == 200:
                        data = response.json()
                        st.success("Verification Completed")
                        st.session_state["result"] = data
                    else:
                        st.error(response.text)

                except Exception as e:
                    st.error(str(e))

# ------------------------------
# IMAGE
# ------------------------------

with tab2:
    st.markdown("<div class='section-title'>Verify News Image</div>", unsafe_allow_html=True)

    uploaded_image = st.file_uploader(
        "Upload News Image",
        type=["png", "jpg", "jpeg"],
        key="image"
    )

    if uploaded_image:
        st.image(uploaded_image, use_container_width=True)

        if st.button("Verify Image", key="verify_image"):

            files = {
                "file": (
                    uploaded_image.name,
                    uploaded_image.getvalue(),
                    uploaded_image.type
                )
            }

            with st.spinner("Reading image..."):
                try:
                    response = requests.post(
                        "http://127.0.0.1:8000/verify/image",
                        files=files
                    )

                    if response.status_code == 200:
                        data = response.json()
                        st.success("Image Verification Completed")
                        st.session_state["result"] = data
                    else:
                        st.error(response.text)

                except Exception as e:
                    st.error(str(e))

# ------------------------------
# VIDEO
# ------------------------------

with tab3:
    st.markdown("<div class='section-title'>Verify News Video</div>", unsafe_allow_html=True)

    uploaded_video = st.file_uploader(
        "Upload Video",
        type=["mp4", "avi", "mov"],
        key="video"
    )

    if uploaded_video:
        st.video(uploaded_video)

        if st.button("Verify Video", key="verify_video"):

            files = {
                "file": (
                    uploaded_video.name,
                    uploaded_video.getvalue(),
                    uploaded_video.type
                )
            }

            with st.spinner("Analyzing video..."):
                try:
                    response = requests.post(
                        "http://127.0.0.1:8000/verify/video",
                        files=files
                    )

                    if response.status_code == 200:
                        data = response.json()
                        st.success("Video Verification Completed")
                        st.session_state["result"] = data
                    else:
                        st.error(response.text)

                except Exception as e:
                    st.error(str(e))

# ------------------------------
# URL
# ------------------------------

with tab4:
    st.markdown("<div class='section-title'>Verify News URL</div>", unsafe_allow_html=True)

    news_url = st.text_input("Enter News URL")

    if st.button("Verify URL", key="verify_url"):

        if news_url == "":
            st.warning("Enter a URL.")
        else:
            with st.spinner("Checking URL..."):
                try:
                    response = requests.post(
                        "http://127.0.0.1:8000/verify/url",
                        json={"url": news_url}
                    )

                    if response.status_code == 200:
                        data = response.json()
                        st.success("URL Verification Completed")
                        st.session_state["result"] = data
                    else:
                        st.error(response.text)

                except Exception as e:
                    st.error(str(e))

# ==========================================================
# AI VERIFICATION RESULT
# ==========================================================

if "result" in st.session_state:

    data = st.session_state["result"]
    result = data.get("result", {})

    st.markdown("<div class='section-label'>Findings</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>AI Verification Result</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("<div class='field-label'>Claim</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='claim-box'>{data.get('claim', 'No Claim')}</div>",
            unsafe_allow_html=True
        )

        st.markdown("<div class='field-label'>AI Explanation</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='body-text'>{result.get('explanation', 'No explanation available.')}</div>",
            unsafe_allow_html=True
        )

        st.markdown("<div class='field-label'>Recommendation</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='recommend-box'>{result.get('recommendation', 'No recommendation.')}</div>",
            unsafe_allow_html=True
        )

    with col2:
        label = result.get("label", "Unknown")
        score = result.get("confidence_score", 0)

        stamp_class = {
            "True": "stamp-true",
            "False": "stamp-false",
            "Misleading": "stamp-misleading"
        }.get(label, "stamp-unknown")

        stamp_text = {
            "True": "Verified True",
            "False": "Verified False",
            "Misleading": "Misleading"
        }.get(label, "Needs Verification")

        st.markdown(f"""
        <div class='stamp-wrap'>
            <div class='stamp {stamp_class}'>{stamp_text}</div>
            <div class='confidence-value'>{score}%</div>
            <div class='confidence-caption'>Confidence Score</div>
        </div>
        """, unsafe_allow_html=True)

        st.progress(score / 100)

    # ------------------------------
    # RELATED NEWS
    # ------------------------------

    st.markdown("<div class='section-label'>Cross References</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Related News</div>", unsafe_allow_html=True)

    related = data.get("related_articles", [])

    if len(related) == 0:
        st.info("No related articles found.")
    else:
        for article in related:
            with st.container():
                st.markdown(f"""
                <div class='article-card'>
                    <h4>{article.get('title', 'No Title')}</h4>
                    <div class='article-source'>{article.get('source', 'Unknown Source')}</div>
                </div>
                """, unsafe_allow_html=True)

                if article.get("image"):
                    st.image(article["image"], use_container_width=True)

                st.markdown(
                    f"<div class='body-text'>{article.get('content', 'No Content')}</div>",
                    unsafe_allow_html=True
                )

                if article.get("url"):
                    st.link_button("Read Full Article", article["url"])

    # ------------------------------
    # EVIDENCE
    # ------------------------------

    st.markdown("<div class='section-label'>Source Material</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Evidence</div>", unsafe_allow_html=True)

    evidence = data.get("evidence", [])

    if evidence:
        st.dataframe(evidence, use_container_width=True)
    else:
        st.info("No evidence available.")

# ==========================================================
# ANALYTICS DASHBOARD
# ==========================================================

st.markdown("<div class='section-label'>Desk Analytics</div>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>Analytics Dashboard</div>", unsafe_allow_html=True)

history = st.session_state.get("history", [])

if "result" in st.session_state:
    if st.session_state["result"] not in history:
        history.append(st.session_state["result"])
        st.session_state["history"] = history

total = len(history)
real = fake = misleading = unknown = 0

for item in history:
    label = item.get("result", {}).get("label", "")
    if label == "True":
        real += 1
    elif label == "False":
        fake += 1
    elif label == "Misleading":
        misleading += 1
    else:
        unknown += 1

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total", total)
c2.metric("True", real)
c3.metric("False", fake)
c4.metric("Misleading", misleading)

st.markdown("<div class='field-label'>Verification Summary</div>", unsafe_allow_html=True)

chart_data = {
    "True": real,
    "False": fake,
    "Misleading": misleading,
    "Unknown": unknown
}

st.bar_chart(chart_data)

# ==========================================================
# HISTORY
# ==========================================================

st.markdown("<div class='section-label'>Archive</div>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>Verification History</div>", unsafe_allow_html=True)

if len(history) == 0:
    st.info("No history available.")
else:
    for item in reversed(history):
        with st.expander(item.get("claim", "Unknown")):
            st.json(item)

# ==========================================================
# DOWNLOAD
# ==========================================================

if "result" in st.session_state:
    json_data = json.dumps(st.session_state["result"], indent=4)

    st.download_button(
        label="Download Verification Report",
        data=json_data,
        file_name="verification_report.json",
        mime="application/json"
    )

# ==========================================================
# FOOTER
# ==========================================================

st.markdown("""
<div class="site-footer">
    <div class="foot-title">&#128737; NewsVerified AI</div>
    <div class="foot-line">Python &bull; Streamlit &bull; FastAPI &bull; OCR &bull; RAG &bull; Groq AI</div>
    <div class="foot-line">IN Tamil &nbsp;|&nbsp; GB English</div>
</div>
""", unsafe_allow_html=True)