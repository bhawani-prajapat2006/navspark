"""
The Compliance Clerk — Streamlit Web UI

Production-ready web interface for document extraction.
API key is loaded from .env file (never exposed in UI).

Run with: streamlit run app.py
"""

import os
import shutil
import tempfile
import logging
from pathlib import Path

import streamlit as st
import pandas as pd

from compliance_clerk.pipeline.extractor import ExtractionPipeline
from compliance_clerk.llm.client import LLMClient, LLMClientError
from compliance_clerk.llm.demo_responses import DemoLLMClient
from compliance_clerk.audit.logger import AuditLogger
from compliance_clerk.output.report_generator import generate_excel
from compliance_clerk.config import GEMINI_API_KEY

# ─────────────────── Page Config ───────────────────
st.set_page_config(
    page_title="The Compliance Clerk",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────── Premium CSS ───────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ── Global ── */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .stApp {
        background: #0c0c1d;
    }
    .block-container {
        padding: 2rem 2rem 4rem;
        max-width: 1060px;
    }

    /* Hide Streamlit chrome */
    #MainMenu, footer, header { visibility: hidden; }
    div[data-testid="stDecoration"] { display: none; }

    /* ── Navbar ── */
    .navbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 0 28px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        margin-bottom: 32px;
    }
    .navbar-brand {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .navbar-logo {
        width: 32px; height: 32px;
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-weight: 700;
        font-size: 14px;
    }
    .navbar-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f1f5f9;
        letter-spacing: -0.3px;
    }
    .navbar-badge {
        padding: 5px 12px;
        border-radius: 100px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        text-transform: uppercase;
    }
    .badge-ready {
        background: rgba(34,197,94,0.12);
        color: #4ade80;
        border: 1px solid rgba(34,197,94,0.2);
    }
    .badge-demo {
        background: rgba(168,85,247,0.12);
        color: #c084fc;
        border: 1px solid rgba(168,85,247,0.2);
    }
    .badge-missing {
        background: rgba(251,191,36,0.12);
        color: #fbbf24;
        border: 1px solid rgba(251,191,36,0.2);
    }

    /* ── Section Headers ── */
    .section-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 14px;
    }

    /* ── Cards ── */
    .card {
        background: rgba(255,255,255,0.025);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 20px 22px;
        margin-bottom: 16px;
    }

    /* ── Metrics Row ── */
    .metrics {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin: 20px 0 24px;
    }
    .metric {
        background: rgba(255,255,255,0.025);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 18px 16px;
        text-align: center;
    }
    .metric-val {
        font-size: 1.6rem;
        font-weight: 700;
        color: #f8fafc;
        line-height: 1;
    }
    .metric-lbl {
        font-size: 0.68rem;
        color: #64748b;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        margin-top: 6px;
    }
    .m-blue .metric-val { color: #60a5fa; }
    .m-purple .metric-val { color: #a78bfa; }
    .m-green .metric-val { color: #34d399; }
    .m-amber .metric-val { color: #fbbf24; }

    /* ── File List ── */
    .flist {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .fitem {
        display: flex;
        align-items: center;
        padding: 9px 14px;
        border-radius: 8px;
        background: rgba(255,255,255,0.02);
    }
    .fitem:hover { background: rgba(255,255,255,0.04); }
    .fdot {
        width: 7px; height: 7px;
        border-radius: 50%;
        margin-right: 12px;
        flex-shrink: 0;
    }
    .fdot-na { background: #60a5fa; }
    .fdot-ld { background: #a78bfa; }
    .fname {
        flex: 1;
        font-size: 0.82rem;
        color: #cbd5e1;
        font-weight: 500;
    }
    .fsize {
        font-size: 0.72rem;
        color: #475569;
        font-weight: 500;
    }

    /* ── Results ── */
    .results-header {
        font-size: 0.95rem;
        font-weight: 600;
        color: #e2e8f0;
        margin-bottom: 16px;
    }

    /* ── Override Streamlit widgets ── */
    .stRadio > div { flex-direction: row; gap: 16px; }
    .stRadio label span { color: #94a3b8 !important; font-weight: 500 !important; }
    .stCheckbox label span { color: #94a3b8 !important; font-weight: 500 !important; }
    div[data-testid="stFileUploader"] label p { color: #64748b !important; }
    .stAlert { border-radius: 10px; }
    .stDataFrame { border-radius: 10px; overflow: hidden; }

    /* ── Divider ── */
    .divider {
        height: 1px;
        background: rgba(255,255,255,0.06);
        margin: 28px 0;
    }

    /* ── Footer ── */
    .app-footer {
        text-align: center;
        padding: 28px 0 0;
        border-top: 1px solid rgba(255,255,255,0.05);
        margin-top: 40px;
    }
    .app-footer p {
        color: #334155;
        font-size: 0.75rem;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────── Navbar ───────────────────
has_api_key = bool(GEMINI_API_KEY)

mode = st.radio(
    "Mode",
    ["API Mode", "Demo Mode"],
    index=0 if has_api_key else 1,
    horizontal=True,
    label_visibility="collapsed",
)
is_demo = mode == "Demo Mode"

if is_demo:
    badge = '<span class="navbar-badge badge-demo">Demo Mode</span>'
elif has_api_key:
    badge = '<span class="navbar-badge badge-ready">Connected</span>'
else:
    badge = '<span class="navbar-badge badge-missing">API Key Missing</span>'

st.markdown(f"""
<div class="navbar">
    <div class="navbar-brand">
        <div class="navbar-logo">CC</div>
        <span class="navbar-title">The Compliance Clerk</span>
    </div>
    {badge}
</div>
""", unsafe_allow_html=True)

incremental = st.checkbox("Incremental mode — skip previously processed documents", value=False)


# ─────────────────── Upload ───────────────────
st.markdown('<div class="section-label">Upload Documents</div>', unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    "Drop NA Order and Lease Deed PDFs here",
    type=["pdf"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if uploaded_files:
    na_count = sum(1 for f in uploaded_files if "ORDER" in f.name.upper())
    ld_count = sum(1 for f in uploaded_files if "LEASE" in f.name.upper() or "DEED" in f.name.upper())
    total_mb = sum(f.size for f in uploaded_files) / (1024 * 1024)

    st.markdown(f"""
    <div class="metrics">
        <div class="metric m-blue"><div class="metric-val">{len(uploaded_files)}</div><div class="metric-lbl">Documents</div></div>
        <div class="metric m-purple"><div class="metric-val">{na_count}</div><div class="metric-lbl">NA Orders</div></div>
        <div class="metric m-green"><div class="metric-val">{ld_count}</div><div class="metric-lbl">Lease Deeds</div></div>
        <div class="metric m-amber"><div class="metric-val">{total_mb:.1f}</div><div class="metric-lbl">Total MB</div></div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("View uploaded files"):
        files_html = '<div class="flist">'
        for f in uploaded_files:
            is_na = "ORDER" in f.name.upper()
            dot = "fdot-na" if is_na else "fdot-ld"
            size = f"{f.size/(1024*1024):.1f} MB" if f.size > 1024*1024 else f"{f.size/1024:.0f} KB"
            files_html += f'<div class="fitem"><div class="fdot {dot}"></div><span class="fname">{f.name}</span><span class="fsize">{size}</span></div>'
        files_html += '</div>'
        st.markdown(files_html, unsafe_allow_html=True)


# ─────────────────── Extract ───────────────────
if uploaded_files and st.button("Extract Data", type="primary", use_container_width=True):

    if not is_demo and not has_api_key:
        st.error("No API key configured. Add GEMINI_API_KEY to your .env file and restart.")
        st.stop()

    temp_dir = tempfile.mkdtemp(prefix="compliance_clerk_")
    input_dir = Path(temp_dir) / "input"
    input_dir.mkdir()
    output_dir = Path(temp_dir) / "output"
    output_dir.mkdir()

    for f in uploaded_files:
        (input_dir / f.name).write_bytes(f.read())

    output_path = output_dir / "output.xlsx"
    progress = st.progress(0, text="Initializing...")
    status = st.empty()

    try:
        logging.basicConfig(level=logging.INFO)
        llm_client = DemoLLMClient() if is_demo else LLMClient()

        pipeline = ExtractionPipeline(
            input_dir=str(input_dir),
            llm_client=llm_client,
            incremental=incremental,
        )

        from compliance_clerk.parsers.pdf_extractor import get_paired_documents
        pairs = get_paired_documents(input_dir)
        total_pairs = len(pairs)

        if total_pairs == 0:
            st.warning("No matching document pairs found. Ensure NA Orders and Lease Deeds share survey numbers.")
            st.stop()

        status.info(f"Processing {total_pairs} document pair(s)...")
        rows = pipeline.run()

        progress.progress(100, text="Complete")
        status.empty()

        # ─────── Results ───────
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

        if rows:
            stats = pipeline.audit_logger.get_stats()

            st.markdown(f"""
            <div class="metrics">
                <div class="metric m-green"><div class="metric-val">{len(rows)}</div><div class="metric-lbl">Rows Extracted</div></div>
                <div class="metric m-blue"><div class="metric-val">{total_pairs}</div><div class="metric-lbl">Pairs</div></div>
                <div class="metric m-purple"><div class="metric-val">{stats['successful']}</div><div class="metric-lbl">Successful</div></div>
                <div class="metric m-amber"><div class="metric-val">{stats['failed']}</div><div class="metric-lbl">Failed</div></div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="section-label">Extracted Data</div>', unsafe_allow_html=True)

            data = [row.to_excel_dict() for row in rows]
            df = pd.DataFrame(data)
            st.dataframe(df, width='stretch', hide_index=True)

            # Area discrepancies
            mismatches = []
            for row in rows:
                if row.lease_area > 0 and row.area_in_na_order > 0:
                    diff = abs(row.area_in_na_order - row.lease_area)
                    if diff > 100:
                        mismatches.append(
                            f"Survey {row.survey_number}: "
                            f"NA Area = {row.area_in_na_order:.0f}, "
                            f"Lease Area = {row.lease_area:.0f} "
                            f"(difference: {diff:.0f} sq.m)"
                        )
            if mismatches:
                with st.expander("Area discrepancies detected", expanded=True):
                    for m in mismatches:
                        st.warning(m)

            # Download
            generate_excel(rows, str(output_path))
            with open(output_path, "rb") as f:
                st.download_button(
                    label="Download Report (.xlsx)",
                    data=f.read(),
                    file_name="compliance_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        else:
            st.error("No data could be extracted. Check your PDF files.")

    except LLMClientError as e:
        st.error(f"Extraction failed: {e}")
    except Exception as e:
        st.error(f"Error: {e}")
        st.exception(e)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ─────────────────── Footer ───────────────────
st.markdown("""
<div class="app-footer">
    <p>The Compliance Clerk &middot; Powered by Google Gemini &middot; All data processed locally</p>
</div>
""", unsafe_allow_html=True)
