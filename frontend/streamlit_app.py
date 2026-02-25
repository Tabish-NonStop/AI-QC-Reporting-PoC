import os
import time
import requests
import streamlit as st
import streamlit.components.v1 as components

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="QC Upload PoC", layout="wide")

st.title("FASTQ Upload → Nextflow → MultiQC")

if "run_id" not in st.session_state:
    st.session_state.run_id = None


def api_post(path, **kwargs):
    r = requests.post(f"{BACKEND}{path}", timeout=300, **kwargs)
    if not r.ok:
        raise RuntimeError(f"{r.status_code}: {r.text}")
    return r.json()


def api_get(path, **kwargs):
    r = requests.get(f"{BACKEND}{path}", timeout=300, **kwargs)
    if not r.ok:
        raise RuntimeError(f"{r.status_code}: {r.text}")
    return r.json()


col1, col2 = st.columns([1, 2], vertical_alignment="top")

with col1:
    st.subheader("1) Create run")
    if st.button("Create new run", type="primary"):
        meta = api_post("/api/runs")
        st.session_state.run_id = meta["run_id"]
        st.success(f"Run created: {st.session_state.run_id}")

    run_id = st.text_input("Run ID", value=st.session_state.run_id or "", placeholder="create a run first")
    if run_id:
        st.session_state.run_id = run_id.strip()

    st.divider()
    st.subheader("2) Upload FASTQ")
    up = st.file_uploader("Choose .fastq/.fq or .gz", type=["fastq", "fq", "gz"])
    if st.session_state.run_id and up and st.button("Upload"):
        files = {"file": (up.name, up.getvalue())}
        meta = api_post(f"/api/runs/{st.session_state.run_id}/upload", files=files)
        st.success(f"Uploaded: {meta['fastq_filename']}")

    st.divider()
    st.subheader("3) Start pipeline")
    if st.session_state.run_id and st.button("Start Nextflow"):
        meta = api_post(f"/api/runs/{st.session_state.run_id}/start")
        st.info(f"Started, pid={meta.get('nextflow_pid')}")

    if st.session_state.run_id and st.button("Refresh status"):
        meta = api_get(f"/api/runs/{st.session_state.run_id}")
        st.write(meta)

    if st.session_state.run_id and st.button("Delete run"):
        api_delete = requests.delete(f"{BACKEND}/api/runs/{st.session_state.run_id}", timeout=300)
        if api_delete.ok:
            st.session_state.run_id = None
            st.success("Deleted run folder")
        else:
            st.error(api_delete.text)


with col2:
    st.subheader("Run status and MultiQC")
    if not st.session_state.run_id:
        st.info("Create a run, upload FASTQ, then start.")
        st.stop()

    try:
        meta = api_get(f"/api/runs/{st.session_state.run_id}")
    except Exception as e:
        st.error(f"Backend error: {e}")
        st.stop()

    status = meta.get("status")
    st.markdown(f"**Status:** `{status}`")

    if meta.get("error"):
        st.error(meta["error"])

    st.markdown("**Nextflow log tail:**")
    st.code(meta.get("log_tail", ""), language="text")

    # MultiQC iframe (served by backend)
    if status == "done":
        # Use the backend route that returns HTML
        multiqc_url = f"{BACKEND}/runs/{run_id}/results/multiqc_final/multiqc_report.html"

        st.markdown("**MultiQC report:**")
        components.iframe(multiqc_url, height=900, scrolling=True)
    elif status in ["running", "stopping", "uploaded", "created"]:
        st.info("MultiQC will appear here when the run is done.")
        if st.button("Auto-refresh every 5s (toggle on)"):
            for _ in range(200):  # ~1000s max
                time.sleep(5)
                st.rerun()

    st.markdown(f"[Download MultiQC HTML]({BACKEND}/api/runs/{run_id}/download/multiqc_html)")
    st.markdown(f"[Download MultiQC ZIP]({BACKEND}/api/runs/{run_id}/download/multiqc_zip)")