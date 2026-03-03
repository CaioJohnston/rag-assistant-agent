import streamlit as st

from agents.router_agent import run_agent

st.set_page_config(page_title="Multi-Agent App")

st.title("Multi-Agent Assistant")

# ---------- session state ----------

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------- render histórico ----------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------- input do usuário ----------

user_input = st.chat_input("Digite sua pergunta")

if user_input:
    # salva user
    st.session_state.messages.append(
        {"role": "user", "content": user_input}
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    # chama agente
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            response = run_agent(user_input)
            st.write(response)

            # pega última mensagem (tool ou resposta futura)
            last_msg = response

            st.markdown(last_msg)

    # salva assistant
    st.session_state.messages.append(
        {"role": "assistant", "content": last_msg}
    )