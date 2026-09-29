from langgraph.graph import END, StateGraph

from src.agents.nodes.rag_nodes import classify_node, generate_node, retrieve_node, validate_node
from src.agents.state import AgentState


def after_classification(state: AgentState) -> str:
    return "end" if state.get("short_circuit") else "retrieve"


def after_retrieval(state: AgentState) -> str:
    return "end" if state.get("short_circuit") else "generate"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("validate", validate_node)

    graph.set_entry_point("classify")
    graph.add_conditional_edges("classify", after_classification, {"end": END, "retrieve": "retrieve"})
    graph.add_conditional_edges("retrieve", after_retrieval, {"end": END, "generate": "generate"})
    graph.add_edge("generate", "validate")
    graph.add_edge("validate", END)
    return graph.compile()


agent = build_graph()
