from typing import TypedDict, List, Dict, Optional, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Estado compartilhado entre todos os nós do grafo.

    - messages : histórico completo da conversa (append-only via add_messages)
    - tool     : nome da tool escolhida pelo router ("web_search" | "rag" | "sql" | "weather" | None)
    - tool_result : resultado bruto retornado pela tool
    - output   : resposta final formatada para o usuário
    """
    messages: Annotated[List[Dict], add_messages]
    tool: Optional[str]
    tool_result: Optional[object]
    output: Optional[str]
