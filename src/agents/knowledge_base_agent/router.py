from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from core import get_model, settings
from agents.knowledge_base_agent.state import AgentState
from agents.knowledge_base_agent.prompts import ROUTER_SYSTEM

KEYWORDS = ["sql", "select", "join", "group by", "where", "查询", "统计", "取数", "表结构", "字段", "DDL"]

async def route_query(state: AgentState, config: RunnableConfig) -> AgentState:
    # 获取到最后一条HumanMessage
    human = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    text = (human.content if human else "") or ""

    # 1. 使用关键词进行启发式判断
    low = text.lower()
    if any(k in low for k in KEYWORDS):
        return {"route": "text2sql"}

    # 2. 使用llm进行意图识别
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    resp = await m.ainvoke([
        {"role": "system", "content": ROUTER_SYSTEM},
        {"role": "user", "content": text}
    ])
    decision = (resp.content or "").strip().lower()
    if decision not in ("doc", "text2sql"):
        decision = "doc"
    return {"route": decision}
