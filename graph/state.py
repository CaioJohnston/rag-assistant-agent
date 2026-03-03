from typing import TypedDict, List, Dict, Optional


class AgentState(TypedDict):
    input: str
    tool: Optional[str]
    tool_result: Optional[List[Dict]]
    output: Optional[str]