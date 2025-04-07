import typing
import gradio as gr
import nx_arangodb as nxadb
import sentence_transformers

from src import helper
from src.graph_rag import prompt
from src.graph_rag import tools as custom_tools
from langgraph import prebuilt
from langgraph.checkpoint import memory
from langchain_core import messages
from langchain_community import graphs
from langchain_core.language_models import chat_models


def create_ask_agent(
    llm: chat_models.BaseChatModel,
    nxadb_graph: nxadb.MultiDiGraph,
    arango_graph: graphs.ArangoGraph,
    embedding_model: str,
    device: str,
) -> typing.Callable[[str], str]:
    
    # Instantiate embedding model
    embedding_model = sentence_transformers.SentenceTransformer(
        model_name_or_path=embedding_model, device=device
    )
    
    # Instantiate all tools for retrieving information
    aql_search = custom_tools.create_aql_search(
        llm=llm, arango_graph=arango_graph, verbose=False
    )
    semantic_search  = custom_tools.create_semantic_search(
        nxadb_graph=nxadb_graph, embedding_model=embedding_model
    )
    definition_search = custom_tools.create_definition_search(
        nxadb_graph=nxadb_graph, embedding_model=embedding_model
    )
    text_to_nx_algorithm_search = custom_tools.create_text_to_nx_algorithm_search(
        llm=llm, nxadb_graph=nxadb_graph, arango_graph=arango_graph, verbose=False
    )
    visualize_query_answer = custom_tools.create_visualize_query_answer(
        llm=llm, nxadb_graph=nxadb_graph, arango_graph=arango_graph, verbose=False
    )
    
    tools = [
        semantic_search,
        definition_search,
        aql_search,
        text_to_nx_algorithm_search,
        visualize_query_answer
    ]
    
    # Instantiate the ReAct agent with the LLM, tools, and memory
    state_memory = memory.MemorySaver()
    config = {"configurable": {"thread_id": "hackathon"}}
    agent = prebuilt.create_react_agent(
        llm, tools, prompt=messages.SystemMessage(content=prompt.SYSTEM_PROMPT), checkpointer=state_memory
    )
        
    def ask_agent(query: str, history: list):
        # Process the query with the agent
        response = agent.invoke({"messages": [messages.HumanMessage(query)]}, config)
        response = response["messages"][-1].content
        if "output.png" in response:
            return response, gr.Image(helper.load_image("assets/output.png"), label="Visualization Output")
        else:
            return response, gr.Image(helper.load_image("assets/ITS-logo.png"), label="Visualization Output")

    return ask_agent
