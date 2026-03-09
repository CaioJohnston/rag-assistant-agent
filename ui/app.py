import streamlit as st
from agents.router_agent import run_agent_realtime_stream

st.set_page_config(page_title="Multi-Agent Assistant", layout="wide")
st.title("Multi-Agent Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown("""
<style>
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stHorizontalBlock"]:first-child) {
    position: sticky;
    top: 0;
    z-index: 999;
    background: #0e1117;
    padding-bottom: 6px;
    border-bottom: 1px solid #222;
}
</style>
""", unsafe_allow_html=True)

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

def render_log_entry(entry: dict):
    step    = entry.get("step", "")
    detail  = entry.get("detail", "")
    elapsed = entry.get("elapsed", "")
    text_color, bg_color = get_style(step)
    
    is_tool_result = step.startswith("TOOL RESULT")

    if is_tool_result:
        st.markdown(
            f"""
            <div style='background: {bg_color}; border-left: 3px solid {text_color}; margin: 1px 0 1px 20px; padding: 6px 12px; border-radius: 3px; font-family: monospace; font-size: 0.78rem;'>
                <div style='display:flex; justify-content:space-between; margin-bottom:4px;'>
                    <span style='color:{text_color}; font-weight:600;'>{step}</span>
                    <span style='color:#555;'>{elapsed}</span>
                </div>
                <pre style='margin: 0; white-space: pre-wrap; word-break: break-word; color: #dddddd; font-size: 0.76rem; max-height: 180px; overflow-y: auto; background: transparent;'>{detail}</pre>
            </div>
            """, unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <div style='background: {bg_color}; border-left: 4px solid {text_color}; margin: 1px 0; padding: 6px 12px; border-radius: 3px; font-family: monospace; font-size: 0.80rem; display: flex; justify-content: space-between; align-items: baseline;'>
                <span>
                    <span style='color:{text_color}; font-weight:700;'>{step}</span>
                    <span style='color:#cccccc; margin-left:10px;'>{detail}</span>
                </span>
                <span style='color:#555; font-size:0.72rem; white-space:nowrap; margin-left:12px;'>{elapsed}</span>
            </div>
            """, unsafe_allow_html=True
        )

def stream_text(text: str):
    """Gerador sem delay para alimentar o write_stream nativo do Streamlit"""
    for word in text.split(" "):
        yield word + " "

# 1. Área de Sugestões (fixada no topo)
sugestoes = [
    "Compare a temperatura atual de Belém com a média histórica de outubro.",
    "Qual a definição de clima presente no documento PDF e qual a definição da internet?",
    "Qual a previsão do tempo para esta semana em Belém?",
    "O que é GCM (Modelos de Circulação Global)?"
]
suggestion_clicked = None

with st.container():
    st.markdown("<p style='color:#888; font-size:0.8rem; margin-bottom:5px;'> <b>Sugestões:</b></p>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    if col1.button(sugestoes[0], use_container_width=True): suggestion_clicked = sugestoes[0]
    if col2.button(sugestoes[1], use_container_width=True): suggestion_clicked = sugestoes[1]
    if col1.button(sugestoes[2], use_container_width=True): suggestion_clicked = sugestoes[2]
    if col2.button(sugestoes[3], use_container_width=True): suggestion_clicked = sugestoes[3]

# 2. Renderiza o histórico de chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant" and "debug" in msg:
            with st.expander("Logs de execucao do pipeline", expanded=False):
                for log_item in msg.get("debug", {}).get("logs", []):
                    render_log_entry(log_item)

# 3. Input do usuário
user_input = st.chat_input("Digite sua pergunta")
prompt = user_input or suggestion_clicked

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        
        # Criação dos blocos visuais na ordem correta
        response_placeholder = st.empty()
        log_expander = st.expander("Logs de execucao do pipeline", expanded=True)
        
        final_debug = {"logs": []}
        full_response_text = ""

        # O Spinner agora roda DENTRO do espaço que será da resposta final
        with response_placeholder:
            with st.spinner("Pensando", show_time=True):
                # Roda o backend gerando os logs nativamente
                for event in run_agent_realtime_stream(prompt):
                    
                    if event["type"] == "log":
                        final_debug["logs"].append(event["data"])
                        with log_expander:
                            render_log_entry(event["data"])
                    
                    elif event["type"] == "final_response":
                        full_response_text = event["data"]
        
        # Limpa o placeholder (destruindo o spinner) para escrever o texto definitivo
        response_placeholder.empty()
        
        with response_placeholder:
            if full_response_text:
                # O Streamlit trata essa exibição nativamente com st.write_stream
                st.write_stream(stream_text(full_response_text))
            else:
                st.markdown("Não foi possível gerar uma resposta.")

    # Salva no histórico
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response_text,
        "debug": final_debug,
    })