import time
import streamlit as st
from agents.router_agent import run_agent_with_debug

st.set_page_config(page_title="Multi-Agent Assistant", layout="wide")
st.title("Multi-Agent Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

STEP_STYLES = {
    "PIPELINE START":     ("#00ff88", "#0a0a0a"),
    "PIPELINE END":       ("#aaaaaa", "#0a0a0a"),
    "LOOP":               ("#ff9900", "#0a0a0a"),
    "AGENTE":             ("#66b3ff", "#0a0a0a"),
    "TOOL CALL":          ("#ffdd57", "#0a0a0a"),
    "TOOL RESULT":        ("#ffffff", "#111111"),
    "user-agent BLOCKED": ("#ff4444", "#0a0a0a"),
    "user-agent INSUFFICIENT": ("#ff7700", "#0a0a0a"),
    "user-agent":         ("#88ddaa", "#0a0a0a"),
    "orchestrator-agent": ("#cc99ff", "#0a0a0a"),
}

def get_style(step: str):
    for key, (text_color, bg_color) in STEP_STYLES.items():
        if step.startswith(key):
            return text_color, bg_color
    return "#cccccc", "#0a0a0a"


def render_debug(debug: dict):
    logs = debug.get("logs", [])
    if not logs:
        st.warning("Nenhum log capturado.")
        return

    for entry in logs:
        step    = entry["step"]
        detail  = entry["detail"]
        elapsed = entry.get("elapsed", "")
        text_color, bg_color = get_style(step)

        is_tool_result = step.startswith("TOOL RESULT")

        with st.container():
            if is_tool_result:
                st.markdown(
                    f"""
                    <div style='
                        background: {bg_color};
                        border-left: 3px solid {text_color};
                        margin: 1px 0 1px 20px;
                        padding: 6px 12px;
                        border-radius: 3px;
                        font-family: monospace;
                        font-size: 0.78rem;
                    '>
                        <div style='display:flex; justify-content:space-between; margin-bottom:4px;'>
                            <span style='color:{text_color}; font-weight:600;'>{step}</span>
                            <span style='color:#555;'>{elapsed}</span>
                        </div>
                        <pre style='
                            margin: 0;
                            white-space: pre-wrap;
                            word-break: break-word;
                            color: #dddddd;
                            font-size: 0.76rem;
                            max-height: 180px;
                            overflow-y: auto;
                            background: transparent;
                        '>{detail}</pre>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style='
                        background: {bg_color};
                        border-left: 4px solid {text_color};
                        margin: 1px 0;
                        padding: 6px 12px;
                        border-radius: 3px;
                        font-family: monospace;
                        font-size: 0.80rem;
                        display: flex;
                        justify-content: space-between;
                        align-items: baseline;
                    '>
                        <span>
                            <span style='color:{text_color}; font-weight:700;'>{step}</span>
                            <span style='color:#cccccc; margin-left:10px;'>{detail}</span>
                        </span>
                        <span style='color:#555; font-size:0.72rem; white-space:nowrap; margin-left:12px;'>{elapsed}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def stream_text(text: str):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.025)


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
    if msg["role"] == "assistant" and "debug" in msg:
        with st.expander("Log de execucao do pipeline"):
            render_debug(msg["debug"])


user_input = st.chat_input("Digite sua pergunta")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Processando..."):
            response, debug = run_agent_with_debug(user_input)
        full_response = st.write_stream(stream_text(response))

    with st.expander("Log de execucao do pipeline"):
        render_debug(debug)

    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "debug": debug,
    })