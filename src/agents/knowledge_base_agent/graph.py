from langgraph.graph import END, StateGraph
from agents.knowledge_base_agent.state import AgentState
from agents.knowledge_base_agent.router import route_query

from agents.knowledge_base_agent.nodes_doc import retrieve_documents, prepare_augmented_prompt, acall_model
from agents.knowledge_base_agent.nodes_text2sql import (
    resolve_target_db,
    retrieve_sql_schema,
    retrieve_sql_examples,
    prepare_sql_context,
    generate_sql
)
from agents.knowledge_base_agent.nodes_sql_runtime import (
    repair_sql,
    validate_sql,
    execute_sql, 
    format_sql_result,
    should_repair_after_exec,
    should_repair_after_validate,
    mark_exec_max,
    mark_not_select,
    mark_validate_max
)


def build_graph():
    g = StateGraph(AgentState)

    # router
    g.add_node("route_query", route_query)

    # doc branch
    g.add_node("retrieve_documents", retrieve_documents)
    g.add_node("prepare_augmented_prompt", prepare_augmented_prompt)
    g.add_node("doc_model", acall_model)

    # text2sql branch
    g.add_node("resolve_target_db", resolve_target_db)
    g.add_node("retrieve_sql_schema", retrieve_sql_schema)
    g.add_node("retrieve_sql_examples", retrieve_sql_examples)
    g.add_node("prepare_sql_context", prepare_sql_context)
    g.add_node("text2sql_model", generate_sql)

    # sql executor branch
    g.add_node("validate_sql", validate_sql)
    g.add_node("execute_sql", execute_sql)
    g.add_node("repair_sql", repair_sql)
    g.add_node("format_sql_result", format_sql_result)
    g.add_node("mark_not_select", mark_not_select)
    g.add_node("mark_validate_max", mark_validate_max)
    g.add_node("mark_exec_max", mark_exec_max)

    # entry
    g.set_entry_point("route_query")

    # conditional routing
    g.add_conditional_edges(
        "route_query",
        lambda s: s.get("route", "doc"),
        {
            "doc": "retrieve_documents",
            "text2sql": "resolve_target_db",
        },
    )

    g.add_conditional_edges(
        "validate_sql",
        should_repair_after_validate,
        {
            "ok": "execute_sql",
            "repair": "repair_sql",
            "not_select": "mark_not_select",
            "maxed": "mark_validate_max",
        }
    )

    g.add_conditional_edges(
        "execute_sql",
        should_repair_after_exec,
        {
            "ok": "format_sql_result",
            "repair": "repair_sql",
            "maxed": "mark_exec_max",
        }
    )

    # doc flow
    g.add_edge("retrieve_documents", "prepare_augmented_prompt")
    g.add_edge("prepare_augmented_prompt", "doc_model")
    g.add_edge("doc_model", END)

    # text2sql flow
    g.add_edge("resolve_target_db", "retrieve_sql_schema")
    g.add_edge("retrieve_sql_schema", "retrieve_sql_examples")
    g.add_edge("retrieve_sql_examples", "prepare_sql_context")
    g.add_edge("prepare_sql_context", "text2sql_model")

    # sql executor flow
    g.add_edge("text2sql_model", "validate_sql")
    g.add_edge("repair_sql", "validate_sql")
    g.add_edge("mark_not_select", "format_sql_result")
    g.add_edge("mark_validate_max", "format_sql_result")
    g.add_edge("mark_exec_max", "format_sql_result")
    g.add_edge("format_sql_result", END)

    agent = g.compile()

    g = agent.get_graph()
    png_bytes = g.draw_mermaid_png()
    with open("docs/kb_agent.png", "wb") as f:
        f.write(png_bytes)

    return agent

kb_agent = build_graph()
