#!/bin/bash
# entrypoint.sh — Setup automatico e start do Multi-Agent Assistant.
#
# Executado pelo Docker no boot do container.
# Etapas:
#   1. Cria agentes no Azure AI Foundry (idempotente — skip se ja existem)
# 2. inicializa a interface do usuario
#
# Erros nas etapas 1-2 sao capturados e logados como WARN.
# Apenas a etapa 3 (Streamlit) e obrigatoria.

echo "=============================="
echo " Multi-Agent Assistant — setup"
echo "=============================="

# 1. Inicializa agentes no Foundry (skip se ja existem)
echo ""
echo "[setup] Verificando agentes no Azure AI Foundry..."
python agents/init_agents.py 2>&1 \
    && echo "[setup] Agentes OK" \
    || echo "[setup] WARN: init_agents falhou (agentes podem ja existir ou credenciais ausentes)"


# 2. inicializa a interface do usuario
echo "" && echo "[setup] Inicializando interface do usuario..."
streamlit run "ui/app.py" --server.port=8501 --server.address=0.0.0.0 --server.headless=true