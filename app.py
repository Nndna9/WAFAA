"""
Project Wafa — Retention Intelligence Dashboard (M5).

The full journey on one screen: message in -> understanding -> risk + why ->
action -> drafted outreach -> human approval -> audit log. Light & dark mode,
presenter notes explaining every stage, fully offline by default.

Run:  streamlit run app.py
Deploy note: app.py must live at the project root, next to src/, data/ and
fixtures/. models/ is optional — the trainers rerun automatically (seconds).
"""
from __future__ import annotations

import datetime
import html
import json
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Offline-safe defaults: deterministic drafter + template gloss (no downloads).
# Unset these env vars on a machine with torch/transformers for Qwen + NLLB.
os.environ.setdefault("WAFA_LLM", "template")
os.environ.setdefault("WAFA_GLOSS", "template")

_IMPORT_ERR = None
try:
    from src.contracts import validate_c6  # noqa: E402
    from src.integration_stubs.journey_stub import run_journey  # noqa: E402
    from src.utils.io import load_messages, load_profiles_by_id  # noqa: E402
except Exception as _exc:  # surfaced after set_page_config (Streamlit rule)
    _IMPORT_ERR = _exc

AUDIT_LOG = ROOT / "audit_log.jsonl"
DEMO_CASES = ROOT / "fixtures" / "demo_cases.json"

LANG_NAMES = {"en": "English", "ar": "Arabic", "hi": "Hindi (romanized)",
              "tl": "Tagalog"}

# ---------------------------------------------------------------------------
# Page + theme
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Wafa — Retention Intelligence",
                   page_icon="🏦", layout="wide",
                   initial_sidebar_state="expanded")

if _IMPORT_ERR is not None:
    here = sorted(q.name + ("/" if q.is_dir() else "") for q in ROOT.iterdir())
    st.error(
        f"**Wafa cannot start — the platform code was not found next to app.py.**\n\n"
        f"`{type(_IMPORT_ERR).__name__}: {_IMPORT_ERR}`\n\n"
        f"app.py needs the WHOLE project folder deployed with it — at minimum "
        f"`src/`, `data/`, `fixtures/` and `requirements.txt` in the same "
        f"directory. If deploying to Streamlit Cloud, push the entire `wafa/` "
        f"folder contents to the repo root (models are optional — they retrain "
        f"automatically on first run).\n\n"
        f"Files currently next to app.py: `{', '.join(here)}`")
    st.stop()

PALETTES = {
    "light": dict(bg="#f4f6fa", card="#ffffff", text="#0f172a", sub="#46556b",
                  border="#dde4ee", accent="#0e7490", accent_soft="#e0f2f7",
                  sidebar="#eaeef5", input="#ffffff", code="#f1f5f9",
                  high="#b91c1c", high_bg="#fde8e8", med="#b45309",
                  med_bg="#fdf0dd", low="#15803d", low_bg="#e3f4e9",
                  flag_bg="#fde8e8", flag_tx="#b91c1c", shadow="0 1px 3px rgba(15,23,42,.08)"),
    "dark": dict(bg="#0d1117", card="#161c26", text="#e9eef6", sub="#9db0c8",
                 border="#2b3648", accent="#34d3c0", accent_soft="#12313a",
                 sidebar="#10151d", input="#1b2330", code="#10151d",
                 high="#f87171", high_bg="#3a1520", med="#fbbf24",
                 med_bg="#37280e", low="#4ade80", low_bg="#12301d",
                 flag_bg="#3a1520", flag_tx="#f87171", shadow="0 1px 3px rgba(0,0,0,.45)"),
}


def inject_css(p: dict) -> None:
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stApp, p, li, label, span, div {{
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }}
    .stApp {{ background: {p['bg']}; }}
    [data-testid="stSidebar"] {{ background: {p['sidebar']}; border-right: 1px solid {p['border']}; }}
    [data-testid="stSidebar"] * {{ color: {p['text']}; }}
    h1, h2, h3, h4, h5 {{ color: {p['text']} !important; letter-spacing: -0.01em; }}
    p, li, label, .stMarkdown, [data-testid="stWidgetLabel"] p {{ color: {p['text']}; font-size: 1.0rem; }}
    small, .stCaption, [data-testid="stCaptionContainer"] * {{ color: {p['sub']} !important; }}

    /* inputs */
    .stTextArea textarea, .stTextInput input {{
        background: {p['input']} !important; color: {p['text']} !important;
        border: 1.5px solid {p['border']} !important; border-radius: 10px !important;
        font-size: 1.0rem !important; line-height: 1.55 !important;
    }}
    [data-baseweb="select"] > div {{
        background: {p['input']} !important; color: {p['text']} !important;
        border: 1.5px solid {p['border']} !important; border-radius: 10px !important;
    }}
    [data-baseweb="select"] * {{ color: {p['text']} !important; }}
    [data-baseweb="popover"] ul, [data-baseweb="menu"] {{ background: {p['card']} !important; }}
    [data-baseweb="popover"] li, [data-baseweb="menu"] li {{ color: {p['text']} !important; }}

    /* buttons */
    .stButton > button {{
        border-radius: 10px; border: 1.5px solid {p['border']};
        background: {p['card']}; color: {p['text']};
        font-weight: 600; font-size: .97rem; padding: .5rem 1.1rem;
    }}
    .stButton > button:hover {{ border-color: {p['accent']}; color: {p['accent']}; }}
    .stButton > button[kind="primary"] {{
        background: {p['accent']}; border-color: {p['accent']};
        color: {'#062a2a' if p is PALETTES['dark'] else '#ffffff'};
    }}

    /* expanders */
    [data-testid="stExpander"] {{
        background: {p['card']}; border: 1px solid {p['border']};
        border-radius: 12px;
    }}
    [data-testid="stExpander"] summary, [data-testid="stExpander"] p {{ color: {p['text']}; }}

    /* wafa components */
    .wafa-hero {{
        background: linear-gradient(135deg, {p['accent_soft']}, {p['card']});
        border: 1px solid {p['border']}; border-radius: 16px;
        padding: 22px 28px; margin-bottom: 6px; box-shadow: {p['shadow']};
    }}
    .wafa-card {{
        background: {p['card']}; border: 1px solid {p['border']};
        border-radius: 14px; padding: 20px 24px; margin-bottom: 14px;
        box-shadow: {p['shadow']};
    }}
    .wafa-stage {{
        display:inline-flex; align-items:center; justify-content:center;
        width: 30px; height: 30px; border-radius: 9px; margin-right: 10px;
        background: {p['accent']}; color: {'#062a2a' if p is PALETTES['dark'] else '#fff'};
        font-weight: 800; font-size: .95rem;
    }}
    .wafa-h {{ font-size: 1.18rem; font-weight: 700; color: {p['text']};
               display:flex; align-items:center; margin-bottom: 4px; }}
    .wafa-sub {{ color: {p['sub']}; font-size: .92rem; margin-bottom: 14px; }}
    .wafa-kv {{ color: {p['sub']}; font-size: .85rem; font-weight:600;
                text-transform: uppercase; letter-spacing:.06em; margin-bottom:2px; }}
    .wafa-v {{ color: {p['text']}; font-size: 1.12rem; font-weight: 700; }}
    .wafa-chip {{
        display:inline-block; padding: 4px 12px; border-radius: 999px;
        font-size: .9rem; font-weight: 600; margin: 2px 6px 2px 0;
        background: {p['accent_soft']}; color: {p['accent']};
        border: 1px solid {p['border']};
    }}
    .wafa-flag {{
        display:inline-block; padding: 4px 12px; border-radius: 999px;
        font-size: .88rem; font-weight: 700; margin: 2px 6px 2px 0;
        background: {p['flag_bg']}; color: {p['flag_tx']};
        border: 1px solid {p['flag_tx']}55;
    }}
    .wafa-msg {{
        background: {p['code']}; border: 1px solid {p['border']};
        border-radius: 10px; padding: 14px 16px; font-size: 1.08rem;
        line-height: 1.6; color: {p['text']};
    }}
    .wafa-trace {{
        background: {p['code']}; border: 1px solid {p['border']};
        border-radius: 10px; padding: 12px 16px;
        font-family: 'SFMono-Regular', Consolas, monospace;
        font-size: .92rem; line-height: 1.7; color: {p['text']};
        white-space: pre-wrap;
    }}
    .wafa-bar {{ background: {p['border']}; border-radius: 999px; height: 12px;
                 overflow: hidden; margin: 6px 0 2px; }}
    .wafa-bar > div {{ height: 100%; border-radius: 999px; }}
    .wafa-banner {{
        border-radius: 12px; padding: 14px 18px; font-weight: 700;
        font-size: 1.02rem; margin: 10px 0;
    }}
    table.wafa-table {{ width:100%; border-collapse: collapse; font-size:.97rem; }}
    table.wafa-table th {{ text-align:left; color:{p['sub']}; font-size:.82rem;
        text-transform:uppercase; letter-spacing:.05em; padding:8px 10px;
        border-bottom: 1.5px solid {p['border']}; }}
    table.wafa-table td {{ color:{p['text']}; padding:9px 10px;
        border-bottom: 1px solid {p['border']}; }}
    </style>
    """, unsafe_allow_html=True)


def tier_colors(p: dict, tier: str):
    return {"High": (p["high"], p["high_bg"]),
            "Medium": (p["med"], p["med_bg"]),
            "Low": (p["low"], p["low_bg"])}.get(tier, (p["sub"], p["code"]))


# ---------------------------------------------------------------------------
# Cached data + model bootstrap
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="First run — training the M2/M3 models (a few seconds)…")
def _ensure_models():
    """Cloud-friendly: models/ may not be deployed; both trainers run in seconds."""
    from src import config
    if not (config.M2_MODELS_DIR / config.M2_TFIDF_ISSUE).exists():
        from src.m2_text_intel import train_baseline
        train_baseline.main()
    if not (config.M3_MODELS_DIR / config.M3_MODEL_FILE).exists():
        from src.m3_churn_fusion import train_churn
        train_churn.main()
    return True


@st.cache_resource(show_spinner=False)
def _profiles():
    return load_profiles_by_id()


@st.cache_resource(show_spinner=False)
def _messages():
    return load_messages()


_FALLBACK_DEMOS = [
    {"name": "A_high_churn_non_english",
     "description": "High-risk customer, romanized-Hindi fees complaint signalling churn.",
     "input_text": "yeh charges bilkul galat hain, itni zyada fees kaat li, main bahut pareshan hoon",
     "language": "hi", "c1": {"customer_id": "FB1138", "message_id": "DEMO_A"}},
    {"name": "B_confirmed_leaver_dignified_goodbye",
     "description": "Explicit departure + confirming behaviour -> dignified goodbye.",
     "input_text": "I have resigned and I am leaving the UAE for good, please close my account.",
     "language": "en", "c1": {"customer_id": "FB1102", "message_id": "DEMO_B"}},
    {"name": "C_routine_low_risk",
     "description": "Routine query, low-risk customer -> standard service.",
     "input_text": "hello, what are the branch timings this week? thank you",
     "language": "en", "c1": {"customer_id": "FB1003", "message_id": "DEMO_C"}},
]


@st.cache_resource(show_spinner=False)
def _demo_cases():
    if DEMO_CASES.exists():
        return json.loads(DEMO_CASES.read_text(encoding="utf-8"))
    return _FALLBACK_DEMOS


def _append_audit(c5: dict, decision: str, final_text: str,
                  override: str | None = None) -> dict:
    rec = {
        "message_id": c5["message_id"], "action": c5["action"],
        "reviewer_decision": decision, "final_text": final_text,
        "override_action": override, "reviewer": "demo_agent",
        "timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    validate_c6(rec)
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _read_audit(n: int = 10) -> list:
    if not AUDIT_LOG.exists():
        return []
    lines = AUDIT_LOG.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(l) for l in lines[-n:]][::-1]


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


# ---------------------------------------------------------------------------
# Sidebar — controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏦 Wafa")
    st.caption("Customer Retention Intelligence — Falcon Bank UAE")

    dark = st.toggle("🌙 Dark mode", value=True)
    notes = st.toggle("🎓 Presenter notes", value=True,
                      help="Show the 'How this works' explainer under each stage.")
    P = PALETTES["dark" if dark else "light"]
    inject_css(P)

    st.divider()
    st.markdown("#### Incoming message")
    source = st.radio("Source", ["Demo scenario", "Dataset message", "Paste custom"],
                      label_visibility="collapsed")

    text, customer_id, message_id, language = "", None, "M_LIVE", None
    profiles = _profiles()
    msgs = _messages()

    if source == "Demo scenario":
        cases = _demo_cases()
        labels = {f"{c['name'].split('_', 1)[0]} — {c['description']}": c for c in cases}
        pick = st.selectbox("Demo case", list(labels))
        case = labels[pick]
        text = case["input_text"]
        customer_id = case["c1"]["customer_id"]
        message_id = case["c1"]["message_id"]
        language = case.get("language")
    elif source == "Dataset message":
        mrow = st.selectbox(
            "Message", msgs.to_dict("records"),
            format_func=lambda r: f"{r['message_id']} · {r['language']} · {str(r['text'])[:48]}…")
        text, customer_id = str(mrow["text"]), str(mrow["customer_id"])
        message_id, language = str(mrow["message_id"]), str(mrow["language"])
    else:
        text = st.text_area("Customer message", height=140,
                            placeholder="Paste a customer message (en / ar / hi / tl)…")
        customer_id = st.selectbox(
            "Customer", sorted(profiles),
            format_func=lambda c: f"{c} · {profiles[c]['segment']} · CLV {profiles[c]['clv_estimate_aed']:,} AED")
        lang_pick = st.selectbox("Language", ["Auto-detect", "en", "ar", "hi", "tl"],
                                 help="Manual override wins over detection (the agent is authoritative).")
        language = None if lang_pick == "Auto-detect" else lang_pick

    run_clicked = st.button("▶  Run the platform", type="primary",
                            use_container_width=True, disabled=not str(text).strip())

    st.divider()
    st.caption(f"Drafter: **{os.environ.get('WAFA_LLM', 'auto')}** · "
               f"Gloss: **{os.environ.get('WAFA_GLOSS', 'auto')}**  \n"
               "Unset `WAFA_LLM`/`WAFA_GLOSS` for Qwen 2.5 + NLLB.")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="wafa-hero">
  <div style="font-size:1.65rem; font-weight:800; color:{P['text']}">
    Wafa <span style="color:{P['accent']}">وفاء</span> — Retention Intelligence
  </div>
  <div style="color:{P['sub']}; font-size:1.02rem; margin-top:4px">
    One screen, the full journey — <b>LISTEN</b> (M1·M2) → <b>UNDERSTAND</b> (M3) →
    <b>ACT</b> (M4) → <b>human approval</b> (M5). Nothing reaches a customer without review.
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Run pipeline
# ---------------------------------------------------------------------------
if run_clicked:
    _ensure_models()
    with st.spinner("Running M1 → M2 → M3 → M4 …"):
        try:
            st.session_state["journey"] = run_journey(
                str(text), customer_id=customer_id, message_id=message_id,
                language=language, profiles=profiles)
            st.session_state["journey_meta"] = {"customer_id": customer_id}
        except Exception as exc:  # surface, don't crash the app
            st.session_state.pop("journey", None)
            st.error(f"Pipeline error: {exc}")

out = st.session_state.get("journey")

if not out:
    st.markdown(f"""
    <div class="wafa-card" style="text-align:center; padding:44px">
      <div style="font-size:1.25rem; font-weight:700; color:{P['text']}">
        Select a message in the sidebar and press <span style="color:{P['accent']}">Run the platform</span>
      </div>
      <div style="color:{P['sub']}; margin-top:8px">
        Try the three demo scenarios: a high-churn non-English complaint, a confirmed
        leaver (dignified goodbye), and a routine low-risk query.
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

c1, c2, c4, c5 = out["c1"], out["c2"], out["c4"], out["c5"]
tcol, tbg = tier_colors(P, c4["risk_tier"])

# ---------------------------------------------------------------------------
# ① UNDERSTOOD (M1 + M2)
# ---------------------------------------------------------------------------
lang_label = LANG_NAMES.get(c1["language"], c1["language"])
lowconf = float(c1["lang_confidence"]) < 0.80

def _same_text(a, b):
    import re as _re
    _norm = lambda x: _re.sub(r"[\s\.,!?\u060c\u061f]+", "", str(x)).lower()
    return _norm(a) == _norm(b)


gloss_html = ""
if c1["language"] != "en":
    if _same_text(c1["display_en"], c1["text_raw"]):
        gloss_html = ('<div style="height:10px"></div>'
                      '<div class="wafa-kv">English gloss</div>'
                      f'<div class="wafa-msg" style="font-size:.98rem; color:{P["sub"]}">'
                      'No offline translation available for this free text — showing the original. '
                      'Install the heavy tier (NLLB) for free-text glosses. Classification is '
                      'unaffected: it always runs on the original text, never the gloss.</div>')
    else:
        gloss_html = ('<div style="height:10px"></div>'
                      '<div class="wafa-kv">English gloss — machine translation, display only</div>'
                      f'<div class="wafa-msg" style="font-size:.98rem">{esc(c1["display_en"])}</div>')

ents = c2["entities"]
ent_chips = "".join(f'<span class="wafa-chip">{esc(k.replace("_", " "))}: {esc(v)}</span>'
                    for k, vals in ents.items() for v in vals) or \
            f'<span style="color:{P["sub"]}">none detected</span>'
flags12 = "".join(f'<span class="wafa-flag">⚑ {esc(f)}</span>' for f in c2["guard_flags"])

st.markdown(f"""
<div class="wafa-card">
  <div class="wafa-h"><span class="wafa-stage">1</span> Understood — what the customer said</div>
  <div class="wafa-sub">M1 Intake &amp; Language → M2 Text Intelligence (contracts C1 → C2)</div>
  <div class="wafa-kv">Original message ({esc(c1['message_id'])} · customer {esc(c1['customer_id'])})</div>
  <div class="wafa-msg" dir="auto">{esc(c1['text_raw'])}</div>
  <div style="height:12px"></div>
  <div style="display:flex; flex-wrap:wrap; gap:26px">
    <div><div class="wafa-kv">Language</div>
      <div class="wafa-v">{esc(lang_label)} <span style="color:{P['sub']}; font-weight:500">({float(c1['lang_confidence']):.0%} conf)</span></div></div>
    <div><div class="wafa-kv">Issue type</div>
      <div class="wafa-v">{esc(c2['issue_type'].replace('_', ' '))} <span style="color:{P['sub']}; font-weight:500">({float(c2['issue_confidence']):.0%})</span></div></div>
    <div><div class="wafa-kv">Churn signal (from text)</div>
      <div class="wafa-v" style="color:{tier_colors(P, c2['churn_signal'])[0]}">{esc(c2['churn_signal'])} <span style="color:{P['sub']}; font-weight:500">({float(c2['signal_confidence']):.0%})</span></div></div>
    <div><div class="wafa-kv">Explicit departure</div>
      <div class="wafa-v">{"⚠️ Yes — states leaving the UAE" if c2['explicit_departure'] else "No"}</div></div>
  </div>
  <div style="height:12px"></div>
  <div class="wafa-kv">Entities</div>
  <div>{ent_chips}</div>
  {gloss_html}
  {'<div style="height:10px"></div>' + flags12 if flags12 else ''}
</div>
""", unsafe_allow_html=True)

if lowconf:
    st.warning("Language confidence is below 0.80 — the platform asks the agent to "
               "confirm the language (use the sidebar override).")

if notes:
    with st.expander("🎓 How stage 1 works (M1 + M2)"):
        st.markdown(f"""
- **M1 — language ID:** an Arabic-script rule + cue-word lexicons (fastText when installed).
  Confidence **< 0.80** prompts the agent to confirm; a manual override always wins.
- **M1 — English gloss:** translation is **display-only** (`display_en`). Classification always
  runs on the original `text_raw`, so translation errors can never propagate into decisions.
- **M2 — trained classifier** (`{esc(c2['model_version'])}`): predicts the 7-class issue type and the
  High/Medium/Low churn signal with confidences the next stage actually uses.
  Backend ladder: XLM-R → DistilmBERT → MiniLM+LR → TF-IDF+LR (guaranteed floor).
- **M2 — transparent rules:** entities via regex + curated lexicons; the **explicit-departure**
  trigger is deliberately high-precision — it prefers missing a leaver over trapping a stayer.
""")

# ---------------------------------------------------------------------------
# ② RISK (M3)
# ---------------------------------------------------------------------------
drivers_rows = "".join(
    f"<tr><td><b>{esc(d['feature'])}</b></td><td>{esc(d['value'])}</td>"
    f"<td style='color:{P['high'] if str(d['impact']).startswith('+') else P['low']}; font-weight:700'>{esc(d['impact'])}</td>"
    f"<td>{esc(d['direction'])}</td></tr>"
    for d in c4["drivers"])
trace_html = esc("\n".join(c4["fusion_trace"]))
banner = ""
if c4["confirmed_leaver"]:
    banner = (f'<div class="wafa-banner" style="background:{P["high_bg"]}; color:{P["high"]}; '
              f'border:1.5px solid {P["high"]}55">🕊️ Confirmed leaver — explicit departure '
              f'confirmed by behaviour (salary stopped / transfer spike). Routing to the '
              f'<u>dignified-goodbye</u> pathway: no retention pressure, by policy.</div>')

st.markdown(f"""
<div class="wafa-card">
  <div class="wafa-h"><span class="wafa-stage">2</span> Risk — who is leaving and why</div>
  <div class="wafa-sub">M3 Churn Model &amp; Fusion — behaviour (customer profile) + text signal (contract C4)</div>
  {banner}
  <div style="display:flex; flex-wrap:wrap; gap:26px; align-items:flex-end">
    <div style="flex:2; min-width:260px">
      <div class="wafa-kv">Fused churn risk</div>
      <div style="font-size:2.0rem; font-weight:800; color:{tcol}">{float(c4['fused_risk']):.0%}
        <span style="font-size:1.0rem; background:{tbg}; color:{tcol}; padding:4px 14px;
              border-radius:999px; vertical-align:middle; margin-left:8px">{esc(c4['risk_tier'])} tier</span></div>
      <div class="wafa-bar"><div style="width:{float(c4['fused_risk'])*100:.1f}%; background:{tcol}"></div></div>
      <div style="color:{P['sub']}; font-size:.85rem">thresholds — High ≥ 70% · Medium ≥ 40%</div>
    </div>
    <div><div class="wafa-kv">Behaviour score (trained model)</div>
      <div class="wafa-v">{float(c4['behaviour_score']):.0%}</div></div>
    <div><div class="wafa-kv">Text signal</div>
      <div class="wafa-v" style="color:{tier_colors(P, c4['text_signal'])[0]}">{esc(c4['text_signal'])}</div></div>
    <div><div class="wafa-kv">Segment · CLV</div>
      <div class="wafa-v">{esc(c4['segment'])} · {int(c4['clv_estimate_aed']):,} AED</div></div>
  </div>
  <div style="height:16px"></div>
  <div class="wafa-kv">Top drivers — why this score (exact linear contributions)</div>
  <table class="wafa-table">
    <tr><th>feature</th><th>value</th><th>impact</th><th>direction</th></tr>
    {drivers_rows}
  </table>
  <div style="height:14px"></div>
  <div class="wafa-kv">Fusion trace — every line auditable</div>
  <div class="wafa-trace">{trace_html}</div>
</div>
""", unsafe_allow_html=True)

if notes:
    with st.expander("🎓 How stage 2 works (M3)"):
        st.markdown("""
- **Behaviour score:** a team-trained, calibrated **logistic regression** over the customer
  profile (tenure, balance trend, salary credits, remittances, complaints…).
  `nationality_region` is **structurally excluded** from the features (fairness by
  construction) and used only to audit outcomes — see `eval/m3/fairness_region.md`.
- **Fusion is a readable rule, not a model:** `fused = 0.55·behaviour + 0.45·map(text signal)`,
  and the text weight drops to **0.25** when M2's confidence is low. The full arithmetic is
  printed in the trace above — defensible line by line in front of a board.
- **Confirmed leaver requires text AND behaviour** (explicit departure + salary stopped or
  transfer spike) — a noisy sentence alone can never trigger the goodbye pathway.
- **Drivers are exact,** not approximations: coefficient × standardised value per feature.
""")

# ---------------------------------------------------------------------------
# ③ ACTION (M4 decision)
# ---------------------------------------------------------------------------
cap = 0.02 * float(c4["clv_estimate_aed"])
rules_html = esc("\n".join(c5["rule_trace"]))
action_label = c5["action"].replace("_", " ").title()
acol, abg = (P["accent"], P["accent_soft"]) if c5["action"] != "dignified_goodbye" \
    else (P["high"], P["high_bg"])

st.markdown(f"""
<div class="wafa-card">
  <div class="wafa-h"><span class="wafa-stage">3</span> Action — what the bank should do</div>
  <div class="wafa-sub">M4 Decision layer — explicit rules table, first match wins (contract C5)</div>
  <div style="display:flex; flex-wrap:wrap; gap:26px">
    <div><div class="wafa-kv">Decided action</div>
      <div class="wafa-v"><span style="background:{abg}; color:{acol}; padding:6px 16px;
           border-radius:10px">{esc(action_label)}</span></div></div>
    <div><div class="wafa-kv">Offer budget</div>
      <div class="wafa-v">{float(c5['offer_budget_aed']):,.0f} AED
        <span style="color:{P['sub']}; font-weight:500; font-size:.9rem">(cap: 2% of CLV = {cap:,.0f} AED)</span></div></div>
    <div><div class="wafa-kv">Outreach language</div>
      <div class="wafa-v">{esc(LANG_NAMES.get(c5['outreach_language'], c5['outreach_language']))}</div></div>
  </div>
  <div style="height:14px"></div>
  <div class="wafa-kv">Fired rule — the audit trail of the decision</div>
  <div class="wafa-trace">{rules_html}</div>
</div>
""", unsafe_allow_html=True)

if notes:
    with st.expander("🎓 How stage 3 works (M4 rules + offer economics)"):
        st.markdown("""
- **Where money and trust are decided, we use readable rules — not a model.** Seven ordered
  rules (R1–R7), first match wins, and the fired rule is shown verbatim above.
- **R1 is unconditional and first:** a confirmed leaver gets the **dignified goodbye** —
  thank-you, smooth closure, transfer help, budget **forced to 0**. The contract validator
  itself rejects any goodbye packet carrying an offer.
- **Offer economics:** no retention offer may exceed **2% of the customer's CLV** —
  the bank never spends more retaining a customer than the relationship is worth.
""")

# ---------------------------------------------------------------------------
# ④ OUTREACH + human review (M5)
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="wafa-card" style="margin-bottom:4px">
  <div class="wafa-h"><span class="wafa-stage">4</span> Outreach — drafted, guarded, awaiting a human</div>
  <div class="wafa-sub">Drafted by {esc(c5['llm_meta'].get('model', 'LLM'))} under a tone-constrained prompt ·
  hallucination guard active · nothing is sent without approval</div>
</div>
""", unsafe_allow_html=True)

guard_html = "".join(f'<span class="wafa-flag">⚑ {esc(f)}</span>' for f in c5["guard_flags"])
if guard_html:
    st.markdown(f'<div style="margin:2px 0 8px">{guard_html}</div>', unsafe_allow_html=True)
    if any("not_in_source" in f for f in c5["guard_flags"]):
        st.error("Hallucination guard: the draft contains a figure or date that does not "
                 "trace to a source fact — review carefully before approving.")

draft = st.text_area("Draft outreach (editable before approval)",
                     value=c5["draft_text"], height=170)

b1, b2, b3, b4, b5 = st.columns([1, 1, 1, 1.4, 1])
with b1:
    if st.button("✅ Approve", type="primary", use_container_width=True):
        _append_audit(c5, "approved", draft)
        st.success("Approved — C6 record written to the audit log.")
with b2:
    if st.button("✏️ Save edit", use_container_width=True):
        _append_audit(c5, "edited", draft)
        st.success("Edited draft saved — C6 record written to the audit log.")
with b3:
    if st.button("❌ Reject", use_container_width=True):
        _append_audit(c5, "rejected", draft)
        st.warning("Rejected — C6 record written. Nothing will be sent.")
with b4:
    override_to = st.selectbox("Override action", ["fee_waiver", "rate_offer", "rm_call",
                                                   "service_fix", "dignified_goodbye",
                                                   "standard_service"],
                               label_visibility="collapsed")
with b5:
    if st.button("↪ Override", use_container_width=True):
        _append_audit(c5, "overridden", draft, override=override_to)
        st.info(f"Overridden to **{override_to}** — C6 record written.")

if notes:
    with st.expander("🎓 How stage 4 works (drafting, guardrails, human-in-the-loop)"):
        st.markdown("""
- **Tone-constrained prompt (the ethics artefact):** honest and warm, **no false urgency,
  no hidden conditions, no exploiting anxiety**; only provided facts may be used; the
  goodbye draft must never attempt retention. The prompt ships in
  `src/m4_decision_outreach/prompts.py` and is quoted in the Ethics Statement.
- **Hallucination guard:** every number, percentage and date in the draft is checked
  against the source facts; anything unexplained raises a red `⚑ *_not_in_source` badge.
- **Human in the loop:** every decision here — approve / edit / reject / override — is
  appended as a **C6 record** to `audit_log.jsonl`. No message is ever sent automatically.
- Offline the deterministic template drafter runs; with torch installed the same code
  drafts with **Qwen2.5-1.5B-Instruct** (fallback ladder: Qwen-0.5B → FLAN-T5).
""")

# ---------------------------------------------------------------------------
# ⑤ Audit trail
# ---------------------------------------------------------------------------
audit = _read_audit(10)
rows = "".join(
    f"<tr><td>{esc(r['timestamp'][:19].replace('T', ' '))}</td><td>{esc(r['message_id'])}</td>"
    f"<td>{esc(r['action'])}</td><td><b>{esc(r['reviewer_decision'])}</b></td>"
    f"<td>{esc(r.get('override_action') or '—')}</td><td>{esc(r['reviewer'])}</td></tr>"
    for r in audit) or f"<tr><td colspan='6' style='color:{P['sub']}'>No reviews yet — approve or reject a draft above.</td></tr>"

st.markdown(f"""
<div class="wafa-card">
  <div class="wafa-h"><span class="wafa-stage">5</span> Audit trail — last 10 review records (C6)</div>
  <div class="wafa-sub">Append-only <code>audit_log.jsonl</code> — the accountability layer</div>
  <table class="wafa-table">
    <tr><th>timestamp</th><th>message</th><th>action</th><th>decision</th><th>override</th><th>reviewer</th></tr>
    {rows}
  </table>
</div>
""", unsafe_allow_html=True)

st.caption("Wafa (وفاء) means loyalty — engineered in both directions. Learned models for fuzzy "
           "language · transparent rules for money and trust · a human before anything reaches "
           "a customer.")
