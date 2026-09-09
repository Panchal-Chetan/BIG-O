import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # must run before groq_client/hf_client read env vars

from prompts import (
    ANALYZE_SYSTEM_PROMPT,
    TRANSFORM_SYSTEM_PROMPT,
    CHAT_SYSTEM_PROMPT,
    build_transform_user_prompt,
    build_chat_context_block,
)
from groq_client import chat_completion, chat_completion_json, GroqError
from hf_client import zero_shot_complexity
from complexity import COMPLEXITY_CLASSES, CLASS_BY_KEY, plot_scope, normalize_complexity

LANGUAGES = ["python", "javascript", "java", "c++", "typescript", "go"]

st.set_page_config(page_title="BigO Scope", page_icon="⧉", layout="wide")

# ---------------------------------------------------------------- styling --

st.markdown("""
<style>
:root {
  --bg: #090C0A; --panel: #101512; --panel-alt: #141B17;
  --border: #232B26; --text-dim: #8AA394; --accent: #5EEAD4;
}
.stApp { background-color: var(--bg); }
[data-testid="stSidebar"] { background-color: var(--panel); border-right: 1px solid var(--border); }
h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; }
.badge {
  display: inline-block; font-family: monospace; font-weight: 700; font-size: 15px;
  padding: 6px 12px; border-radius: 8px; margin-bottom: 6px;
}
.hotline { color: #FF6B6B; font-family: monospace; font-size: 12px; }
.dim { color: var(--text-dim); font-size: 13px; }
.small-mono { color: #5B6E63; font-family: monospace; font-size: 11.5px; }
.exact-line { color: #FFC145; font-family: monospace; font-size: 12px; margin-top: 4px; }
.channel-tag {
  font-size: 10px; font-family: monospace; padding: 1px 6px; border-radius: 4px;
  font-weight: 700; margin-left: 6px;
}
hr { border-color: var(--border); }

/* Floating chat bubble - pins the popover trigger to the bottom-right of the
   viewport regardless of scroll position, so it behaves like a normal chat widget. */
div[data-testid="stPopover"] {
  position: fixed;
  bottom: 22px;
  right: 22px;
  z-index: 9999;
}
div[data-testid="stPopover"] button {
  border-radius: 999px !important;
  padding: 10px 20px !important;
  background: linear-gradient(135deg, #14B8A6, #34D399) !important;
  color: #04120E !important;
  font-weight: 700 !important;
  border: none !important;
  box-shadow: 0 6px 18px rgba(0,0,0,0.45);
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------ session state --

defaults = {
    "code": "",
    "original_code": "",
    "analysis": None,
    "target": None,
    "transform_result": None,
    "chat_history": [],
    "language": "python",
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

detected = st.session_state.analysis["complexity"] if st.session_state.analysis else None

# ------------------------------------------------------------------ sidebar --

with st.sidebar:
    st.markdown("### ⧉ BigO Scope")
    st.caption("paste code → read its growth curve → retune it")
    st.session_state.language = st.selectbox("Language", LANGUAGES, index=LANGUAGES.index(st.session_state.language))
    st.divider()
    st.caption("API keys (optional here if set in .env)")
    groq_key_input = st.text_input("GROQ_API_KEY", type="password", value="")
    hf_key_input = st.text_input("HF_API_KEY (optional)", type="password", value="")
    if groq_key_input:
        os.environ["GROQ_API_KEY"] = groq_key_input
    if hf_key_input:
        os.environ["HF_API_KEY"] = hf_key_input

    default_model = os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
    groq_model_input = st.text_input(
        "GROQ_MODEL",
        value=default_model,
        help="GROQ periodically deprecates model ids. If Analyze/rewrite/chat suddenly "
             "404s with 'model does not exist', check https://console.groq.com/docs/models "
             "for a current id and paste it here.",
    )
    if groq_model_input:
        os.environ["GROQ_MODEL"] = groq_model_input
    st.divider()
    st.caption("GROQ does the reasoning (complexity detection + rewrite + chat). "
               "Hugging Face's zero-shot classifier gives an independent NLP cross-check.")

st.title("BigO Scope")

col_left, col_right = st.columns([1.1, 0.9], gap="large")

# ------------------------------------------------------------------- left --

with col_left:
    st.markdown("**SOURCE**")

    try:
        from streamlit_ace import st_ace
        edited = st_ace(
            value=st.session_state.code,
            language=st.session_state.language if st.session_state.language != "c++" else "c_cpp",
            theme="terminal",
            font_size=14,
            tab_size=2,
            show_gutter=True,
            wrap=False,
            auto_update=True,
            height=320,
            placeholder="// paste your function here",
            key="ace_editor",
        )
    except ImportError:
        edited = st.text_area(
            "code", value=st.session_state.code, height=320,
            label_visibility="collapsed",
            placeholder="# paste your function here",
        )

    st.session_state.code = edited

    analyze_clicked = st.button("▶ Analyze", type="primary", use_container_width=True,
                                  disabled=not st.session_state.code.strip())

    if analyze_clicked:
        with st.spinner("Scanning code…"):
            try:
                messages = [
                    {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Language: {st.session_state.language}\n\nCode:\n```{st.session_state.language}\n{st.session_state.code}\n```"},
                ]
                result = chat_completion_json(messages, temperature=0.1)

                # Safety net: guarantee 'complexity' is always one of the 8 fixed
                # classes, even if the model slips up (e.g. returns "O(n^4)").
                # The exact form is preserved separately for display.
                bucketed, exact = normalize_complexity(result.get("complexity", ""))
                result["complexity"] = bucketed
                result["exact_complexity"] = result.get("exact_complexity") or exact

                result["hf_cross_check"] = zero_shot_complexity(st.session_state.code)
                result["agrees_with_hf"] = (
                    result["hf_cross_check"] is not None
                    and result["hf_cross_check"]["top_label"] == result["complexity"]
                )
                st.session_state.analysis = result
                st.session_state.original_code = st.session_state.code
                st.session_state.target = None
                st.session_state.transform_result = None
                st.rerun()
            except GroqError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Failed to parse model output: {e}")

    if st.session_state.analysis:
        a = st.session_state.analysis
        color = CLASS_BY_KEY.get(a["complexity"], {}).get("color", "#5EEAD4")
        st.markdown(
            f'<div class="badge" style="color:{color};border:1px solid {color};'
            f'background:{color}22">{a["complexity"]}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{a.get('dominant_operation', '')}**")
        st.markdown(f'<div class="dim">{a.get("reasoning", "")}</div>', unsafe_allow_html=True)
        if a.get("exact_complexity") and a["exact_complexity"] != a["complexity"]:
            st.markdown(
                f'<div class="exact-line">⚠ exact complexity is {a["exact_complexity"]} — '
                f'rounded up to the nearest offered class, {a["complexity"]}, for the chart</div>',
                unsafe_allow_html=True,
            )
        if a.get("hotspot_lines"):
            st.markdown(
                f'<div class="hotline">⚠ hotspot lines: {", ".join(str(x) for x in a["hotspot_lines"])}</div>',
                unsafe_allow_html=True,
            )
        cross = a.get("hf_cross_check")
        conf_line = f"confidence {round((a.get('confidence') or 0) * 100)}%"
        if cross:
            agree = "✓ agrees" if a.get("agrees_with_hf") else "— differs"
            conf_line += f" · NLP cross-check: {cross['top_label']} ({round(cross['top_score']*100)}%) {agree}"
        st.markdown(f'<div class="small-mono">{conf_line}</div>', unsafe_allow_html=True)

    # Rewritten code always renders as its own separate block - the original
    # source above is never overwritten automatically.
    if st.session_state.transform_result:
        t = st.session_state.transform_result
        st.markdown("---")
        st.markdown(f"**🔧 REWRITTEN CODE** — target `{st.session_state.target}` → achieved `{t['achieved_complexity']}`")
        st.code(t["modified_code"], language=st.session_state.language if st.session_state.language != "c++" else "cpp")
        st.info(t["explanation"])
        if t.get("warnings"):
            st.warning(t["warnings"])
        if st.button("✕ Clear rewrite", use_container_width=True):
            st.session_state.transform_result = None
            st.session_state.target = None
            st.rerun()

# ------------------------------------------------------------------ right --

with col_right:
    st.markdown("**COMPLEXITY SCOPE**")
    fig = plot_scope(detected, st.session_state.target)
    st.pyplot(fig, use_container_width=True)

    grid_cols = st.columns(2)
    for i, cls in enumerate(COMPLEXITY_CLASSES):
        col = grid_cols[i % 2]
        key = cls["key"]
        is_detected = key == detected
        is_target = key == st.session_state.target
        tag = ""
        if is_detected:
            tag = f'<span class="channel-tag" style="background:{cls["color"]};color:#04120E">DETECTED</span>'
        elif is_target:
            tag = f'<span class="channel-tag" style="background:{cls["color"]}33;color:{cls["color"]};border:1px solid {cls["color"]}">TARGET</span>'
        with col:
            st.markdown(
                f'<span style="color:{cls["color"]}">●</span> **{cls["label"]}**{tag}',
                unsafe_allow_html=True,
            )
            if st.button("Set as target", key=f"target_{key}", disabled=not detected, use_container_width=True):
                st.session_state.target = key
                if key == detected:
                    st.session_state.transform_result = None
                    st.rerun()
                else:
                    with st.spinner(f"Rewriting toward {key}…"):
                        try:
                            messages = [
                                {"role": "system", "content": TRANSFORM_SYSTEM_PROMPT},
                                {"role": "user", "content": build_transform_user_prompt(
                                    st.session_state.original_code, st.session_state.language,
                                    detected, key,
                                )},
                            ]
                            result = chat_completion_json(messages, temperature=0.2)
                            result.setdefault("warnings", "")
                            st.session_state.transform_result = result
                            st.rerun()
                        except GroqError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"Failed to parse model output: {e}")

# ------------------------------------------------------- floating chat --

with st.popover("💬 Ask Assistant", use_container_width=False):
    st.markdown("**BigO Scope Assistant**")
    st.caption("Grounded in your current code, analysis, and rewrite.")

    chat_box = st.container(height=320)
    with chat_box:
        if not st.session_state.chat_history:
            st.markdown(
                '<div class="dim">Analyze some code first, then ask me anything about '
                "the complexity or the rewrite.</div>",
                unsafe_allow_html=True,
            )
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    with st.form("chat_form", clear_on_submit=True):
        user_msg = st.text_input(
            "message", label_visibility="collapsed",
            placeholder="Ask about the complexity, the rewrite, or the code…",
        )
        submitted = st.form_submit_button("Send", use_container_width=True)

    if submitted and user_msg.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_msg})

        context_block = build_chat_context_block(
            st.session_state.original_code,
            st.session_state.transform_result["modified_code"] if st.session_state.transform_result else "",
            detected or "",
            st.session_state.target or "",
            st.session_state.transform_result["achieved_complexity"] if st.session_state.transform_result else "",
            st.session_state.transform_result["explanation"] if st.session_state.transform_result else "",
        )
        messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT + "\n\n" + context_block}]
        messages += st.session_state.chat_history[-12:]

        try:
            reply = chat_completion(messages, temperature=0.4)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
        except GroqError as e:
            st.session_state.chat_history.append({"role": "assistant", "content": f"⚠ {e}"})
        st.rerun()
