import os
import re
import torch
import typing
import numpy as np
import networkx as nx
import deep_translator
import nx_arangodb as nxadb
import sentence_transformers

from src.graph_rag import prompt
from src.graph_rag import models
from sentence_transformers import util
from langchain import prompts
from langchain_core import tools
from langchain_core.language_models import chat_models
from langchain_community import graphs
from langchain_community.chains.graph_qa import arangodb



def create_semantic_search(
    nxadb_graph: nxadb.MultiDiGraph,
    embedding_model: sentence_transformers.SentenceTransformer
) -> typing.Callable[[str, str], str]:
    
    @tools.tool(args_schema=models.UserQuery)
    def semantic_search(query: str, lang: str = "id"):
        """This tool is used to retrieve relevant articles based on semantic similarity 
        using text embeddings stored in the database. 
    
        Use this tool when the user query:
        - Asks about general topics that cannot be structured into an AQL query.
        - Requests conceptual explanations, summaries, or discussions.
        """

        if lang != "id":
            query = deep_translator.GoogleTranslator(source=lang, target="id").translate(query)

        # Embed the query
        query_embedding = embedding_model.encode(query)
        
        # Retrieve all embeddings data from nodes article
        nodes = nxadb_graph.query("""
            FOR node IN article
                RETURN { id: node._id, embedding: node.embedding }
        """)
        
        nodes_id = []
        nodes_text_embedding = []

        for item in nodes:
            nodes_id.append(item["id"])
            nodes_text_embedding.append(np.array(item["embedding"], dtype=np.float32))

        nodes_id = np.array(nodes_id)
        nodes_text_embedding = np.array(nodes_text_embedding)

        # Compute dot product scores on embeddings
        # Not cosine similarity since all-MiniLM-L6-v2 normalizes the data
        dot_scores = util.dot_score(query_embedding, nodes_text_embedding)[0]

        # Get the top-k most similar article to the user query
        scores, indices = torch.topk(input=dot_scores, k=5)
        initial_nodes_id = nodes_id[indices].tolist()
        initial_nodes = nxadb_graph.query("""
            FOR node IN article
                FILTER node._id IN @initial_nodes_id
                RETURN {id: node._id, text: node.text}
            """,
            bind_vars={"initial_nodes_id": initial_nodes_id}
        )

        text_result = ""

        # Process each retrieved article
        for number, initial_node in enumerate(initial_nodes):
            if number == 0:
                text_result = text_result + f"RELEVANT TEXT FROM DATABASE ({number + 1})"
            else:
                text_result = text_result + "\n" + f"RELEVANT TEXT FROM DATABASE ({number + 1})"
            text_result = text_result + "\n" * 2 + initial_node["text"]
            
            # Retrieve other articles connected via the 'refer_to' edge
            refer_to_other_nodes = nxadb_graph.query("""
                FOR edge IN refer_to
                FILTER edge._from == @initial_node_id OR edge._to == @initial_node_id
                FOR target IN article
                    FILTER ( target._id == edge._from OR target._id == edge._to ) AND target._id != @initial_node_id
                    SORT target._id ASC
                    RETURN { id: target._id, text: target.text }
                """,
                bind_vars={"initial_node_id": initial_node["id"]}
            )

            for other_node in refer_to_other_nodes:
                text_result = text_result + "\n" * 2 + other_node["text"]
            
            text_result = text_result + "\n" * 2 + "-" * 50

        return text_result
    
    return semantic_search


def create_definition_search(
    nxadb_graph: nxadb.MultiDiGraph,
    embedding_model: sentence_transformers.SentenceTransformer
) -> typing.Callable[[str, str], str]:

    @tools.tool(args_schema=models.UserQuery)
    def definition_search(query: str, lang: str = "id"):
        """This tool is used to retrieve relevant definition statement based on semantic
        similarity  using text embeddings stored in the database. 
    
        Use this tool only when the user query:
        - Asks about definition of something.
        """

        if lang != "id":
            query = deep_translator.GoogleTranslator(source=lang, target="id").translate(query)

        # Embed the query
        query_embedding = embedding_model.encode(query)
        
        # Retrieve all embeddings data from nodes definition
        nodes = nxadb_graph.query("""
            FOR node IN definition
                RETURN { id: node._id, embedding: node.embedding }
        """)
        
        nodes_id = []
        nodes_text_embedding = []

        for item in nodes:
            nodes_id.append(item["id"])
            nodes_text_embedding.append(np.array(item["embedding"], dtype=np.float32))

        nodes_id = np.array(nodes_id)
        nodes_text_embedding = np.array(nodes_text_embedding)

        # Compute dot product scores on embeddings
        # Not cosine similarity since all-MiniLM-L6-v2 normalizes the data
        dot_scores = util.dot_score(query_embedding, nodes_text_embedding)[0]

        # Get the top-k most similar definition to the user query
        scores, indices = torch.topk(input=dot_scores, k=10)
        initial_nodes_id = nodes_id[indices].tolist()
        initial_nodes = nxadb_graph.query("""
            FOR node IN definition
                FILTER node._id IN @initial_nodes_id
                RETURN {id: node._id, text: node.text}
            """,
            bind_vars={"initial_nodes_id": initial_nodes_id}
        )

        text_result = ""

        # Process each retrieved article
        for number, initial_node in enumerate(initial_nodes):
            if number == 0:
                text_result = text_result + f"RELEVANT DEFINITION FROM DATABASE ({number + 1})"
            else:
                text_result = text_result + "\n" + f"RELEVANT DEFINITION FROM DATABASE ({number + 1})"
            text_result = text_result + "\n" * 2 + initial_node["text"] + "\n" * 2 + "-" * 50

        return text_result
    
    return definition_search


def create_aql_search(
    llm: chat_models.BaseChatModel,
    arango_graph: graphs.ArangoGraph,
    verbose: bool = False
) -> typing.Callable[[str, str], str]:
    
    @tools.tool(args_schema=models.UserQuery)
    def aql_search(query: str, lang: str = "en") -> str:
        """This tool is used to translate a Natural Language Query into an AQL query
        (Arango Query Language), execute the query, and return the results in Natural Language. 
    
        Use this tool when the user asks about:
        - Regulation structures, relationships such as `next_article`, or regulation content.
        - Specific data that can be directly retrieved from ArangoDB using AQL.

        DO NOT use this tool to answer definition-based questions, use `definition_search` instead.
        DO NOT use this tool if the query cannot be structured into AQL, use `semantic_search` instead. 
        """
        
        if lang != "en":
            query = deep_translator.GoogleTranslator(source=lang, target="en").translate(query)

        # Create the prompt template
        AQL_QA_PROMPT = prompts.PromptTemplate(
            input_variables=["adb_schema", "user_input", "aql_query", "aql_result"],
            template=prompt.AQL_QA_TEMPLATE
        )
        
        # Initialize the ArangoDB Graph QA Chain
        qa_chain = arangodb.ArangoGraphQAChain.from_llm(
            llm=llm,
            qa_prompt=AQL_QA_PROMPT,
            graph=arango_graph,
            aql_examples=prompt.AQL_EXAMPLES,
            allow_dangerous_requests=True,
            verbose=verbose
        )

        result = qa_chain.invoke(query)

        return str(result["result"])
    
    return aql_search


def create_text_to_nx_algorithm_search(
    llm: chat_models.BaseChatModel,
    nxadb_graph: nxadb.MultiDiGraph,
    arango_graph: graphs.ArangoGraph,
    verbose: bool = False
) -> typing.Callable[[str, str], str]:
    
    @tools.tool(args_schema=models.UserQuery)
    def text_to_nx_algorithm_search(query: str, lang: str = "en") -> str:
        """This tool is used to analyze and retrieve insights from a NetworkX graph representation 
        of the ArangoDB dataset by generating and executing Python code.

        Use this tool when the user query:
        - Asks about graph analysis tasks that require NetworkX algorithms.
        - Requests shortest paths, centrality measures, community detection, or other graph-based metrics.
        - Involves complex graph operations that cannot be directly handled by an AQL query.

        DO NOT use this tool for simple data retrieval; use `aql_search` instead.
        DO NOT use this tool if the query is about general topics or definitions; use `semantic_search`
        or `definition_search` instead.
        """

        if lang != "en":
            query = deep_translator.GoogleTranslator(source=lang, target="en").translate(query)

        if verbose: print("\n### 1. Generating NetworkX code")

        text_to_nx = llm.invoke(
            prompt.NX_ALGORITHM_GENERATION_PROMPT.format(
                schema=arango_graph.schema,
                query=query
            )
        ).content

        text_to_nx_cleaned = re.sub(r"^```python\n|```$", "", text_to_nx, flags=re.MULTILINE).strip()

        if verbose:
            print("-" * 50)
            print(text_to_nx_cleaned)
            print("-" * 50)
        
        ######################

        if verbose: print("\n### 2. Executing NetworkX code")
        global_vars = {"G_adb": nxadb_graph, "nx": nx}
        local_vars = {}

        MAX_ATTEMPTS = 3

        for attempt in range(MAX_ATTEMPTS + 1):
            try:
                exec(text_to_nx_cleaned, global_vars, global_vars)
                FINAL_RESULT = global_vars["FINAL_RESULT"]
                break
            except Exception as e:
                if verbose:
                    print("-" * 50)
                    print(f"EXEC ERROR (Attempt {attempt}): {e}")
                    print("-" * 50)

                if attempt == MAX_ATTEMPTS:
                    return f"Execution failed after {MAX_ATTEMPTS} attempts: {e}"
                
                if verbose: print(f"\n### 2.{attempt + 1}. Correcting Code")

                # Minta LLM memperbaiki kode berdasarkan error
                text_to_nx = llm.invoke(
                    prompt.NX_ALGORITHM_RETRY_PROMPT.format(
                        code=text_to_nx_cleaned,
                        error=e,
                        query=query,
                        schema=arango_graph.schema
                    )
                ).content

                text_to_nx_cleaned = re.sub(r"^```python\n|```$", "", text_to_nx, flags=re.MULTILINE).strip()

                if verbose:
                    print("-" * 50)
                    print(text_to_nx_cleaned)
        
        if verbose:
            print("-" * 50)
            print(f"FINAL_RESULT: {FINAL_RESULT}")
            print("-" * 50)

        ######################
        
        if verbose: print("\n### 3. Formulating final answer")

        nx_to_text = llm.invoke(
            prompt.NX_ALGORITHM_QA_PROMPT.format(
                schema=arango_graph.schema,
                query=query,
                code=text_to_nx_cleaned,
                result=FINAL_RESULT
            )
        ).content

        return nx_to_text

    return text_to_nx_algorithm_search


def create_visualize_query_answer(
    llm: chat_models.BaseChatModel,
    nxadb_graph: nxadb.MultiDiGraph,
    arango_graph: graphs.ArangoGraph,
    verbose: bool = False
) -> typing.Callable[[str, str, str], str]:

    @tools.tool(args_schema=models.VisualizeQuery)
    def visualize_query_answer(query: str, answer: str, lang: str):
        """This tool is used to generate and execute Python code for visualizing the result  
        of a graph analysis query on a NetworkX representation of the ArangoDB dataset.  

        IMPORTANT: This tool should only be used AFTER executing another tool (e.g., `aql_search`,  
        `text_to_nx_algorithm_search`) and retrieving their `answer`. The `answer` from the  
        previous tool must be passed as the `answer` argument to this tool.

        Use this tool when:
        - A visual representation of the retrieved graph data is needed.  
        - The query involves NetworkX graph structures and relationships.  
        - A graphical depiction of paths, connections, or centrality measures is required.  

        DO NOT use this tool for general data retrieval or text-based explanations.  
        **Use `aql_search`, `semantic_search`, `definition_search`, or `text_to_nx_algorithm_search` first,  
        then pass their output as the `answer` to this tool for visualization.
        """

        if lang != "en":
            translator = deep_translator.GoogleTranslator(source=lang, target="en")
            query = translator.translate(query)
            answer = translator.translate(answer)

        if verbose: print("\n### 1. Generating visualization code")

        text_to_visual = llm.invoke(
            prompt.VISUALIZATION_GENERATION_PROMPT.format(
                schema=arango_graph.schema,
                query=query,
                answer=answer
            )
        ).content
        
        text_to_visual_cleaned = re.sub(r"^```python\n|```$", "", text_to_visual, flags=re.MULTILINE).strip()

        if verbose:
            print("-" * 50)
            print(text_to_visual_cleaned)
            print("-" * 50)

        ######################

        if verbose: print("\n### 2. Executing the visualization code")
        global_vars = {"G_adb": nxadb_graph, "nx": nx}
        local_vars = {}

        MAX_ATTEMPTS = 3

        for attempt in range(MAX_ATTEMPTS + 1):
            try:
                exec(text_to_visual_cleaned, global_vars, global_vars)
                break
            except Exception as e:
                if verbose:
                    print("-" * 50)
                    print(f"EXEC ERROR (Attempt {attempt}): {e}")
                    print("-" * 50)

                if attempt == MAX_ATTEMPTS:
                    return f"Execution failed after {MAX_ATTEMPTS} attempts: {e}"
                
                if verbose: print(f"\n### 2.{attempt + 1}. Correcting Code")

                # Minta LLM memperbaiki kode berdasarkan error
                text_to_visual = llm.invoke(
                    prompt.VISUALIZATION_RETRY_PROMPT.format(
                        code=text_to_visual_cleaned,
                        error=e,
                        query=query,
                        answer=answer,
                        schema=arango_graph.schema
                    )
                )

                text_to_visual_cleaned = re.sub(r"^```python\n|```$", "", text_to_visual, flags=re.MULTILINE).strip()

                if verbose:
                    print("-" * 50)
                    print(text_to_visual_cleaned)
        
        if os.path.exists("assets/output.png"):
            return "Visualization has been saved to 'assets/output.png', print it using markdown!"
        else:
            return "Unable to generate the visualization"
    
    return visualize_query_answer
