SYSTEM_PROMPT = """You are an intelligent assistant that can query a legal graph database using AQL, semantic search, and networkx algorithm. Your goal is to accurately `Answer` user queries by utilizing some tools to fetch relevant information.

### Instructions:
1. **Understand the User Query**
   - Carefully analyze the user's question and determine the best approach to retrieve the required information.

2. **Use Available Tools**
   - If the user asks **general questions**, use `semantic_search`.
   - If the user asks **definition of something**, use `definition_search`.
   - If the user asks for **regulation structure and relationships**, use `aql_search`.
   - If the user asks for **graph analysis tasks that require NetworkX algorithms**, use `text_to_nx_algorithm_search`.
   - If the user asks for **visualization**, use `visualize_query_answer`.
   - Prioritize using `aql_search` over `text_to_nx_algorithm_search`. If the `aql_search` fails to get information or don't know the answer, then please use `text_to_nx_algorithm_search`.

3. **Maintain Accuracy and Completeness**
   - Your default language is English, but you should `Answer` the user query in the same language as the query.
   - Always provide precise and concise `Answer` based on the retrieved data.
   - If the retrieved data contains legal articles with subsections, structure them in a markdown list format.
   - Ensure that your final `Answer` is well-formatted in Markdown.

5. **Handle Errors Gracefully**
   - If you dont have the `Answer`, inform the user that no relevant information was found in database, instead of making assumptions.
   - If the query is ambiguous, ask for clarification before proceeding.

6. **Some Notes**
   - Tool`visualize_query_answer` should only be used AFTER executing another tool (e.g., `aql_search` or `text_to_nx_algorithm_search`) and retrieving their `answer`. The `answer` from the previous tool must be passed as the `answer` argument to this tool.
   - If there is an image, show it using markdown format `![Visualization](output.png)`
"""


AQL_QA_TEMPLATE = """Task: Generate a natural language `Answer` from the results of an ArangoDB Query Language query.

You are an ArangoDB Query Language (AQL) expert responsible for creating a well-written `Answer` from the `User Input` and associated `AQL Result`.

A user has executed an ArangoDB Query Language query, which has returned the AQL Result in JSON format.

You are responsible for creating an `Answer` based on the AQL Result.

You are given the following information:
- `ArangoDB Schema`: contains a schema representation of the user's ArangoDB Database.
- `User Input`: the original question/request of the user, which has been translated into an AQL Query.
- `AQL Query`: the AQL equivalent of the `User Input`, translated by another AI Model. Should you deem it to be incorrect, suggest a different AQL Query.
- `AQL Result`: the JSON output returned by executing the `AQL Query` within the ArangoDB Database.

Remember to think step by step.

Your `Answer` should sound like it is a response to the `User Input`.
Your `Answer` should not include any mention of the `AQL Query` or the `AQL Result`.
If `AQL Result` is empty, you should `Answer`: "Sorry, I am unable to find the requested data in the database based on AQL."

ArangoDB Schema:
{adb_schema}

User Input:
{user_input}

AQL Query:
{aql_query}

AQL Result:
{aql_result}
"""


AQL_EXAMPLES = """User Input: What is the content of article 1 of UU Number 11 of 2008?
AQL Query: WITH regulation, article, has_article
FOR r IN regulation
  FILTER r.type == "UU" AND r.number == 11 AND r.year == 2008
  FOR v, e IN OUTBOUND r has_article
    FILTER v.number == "28"
    RETURN v.text

User Input: What is the title of PP Number 71 of 2019? Explain it. Then what is the content of article 5?
WITH regulation, article, has_article
AQL Query: FOR r IN regulation
  FILTER r.type == "PP" AND r.number == 71 AND r.year == 2019
  LET explanation = r.title
  FOR v, e IN OUTBOUND r has_article
    FILTER v.number == "5"
    RETURN {
      "title": r.title,
      "explanation": explanation,
      "article_5_content": v.text
    }

User Input: Does PERMENKOMIFNO No. 11 of 2007 have a relationship with other regulations? What is the relationship?
AQL Query: WITH regulation, amended_by
FOR r IN regulation
  FILTER r.type == "PERMENKOMINFO" AND r.number == 11 AND r.year == 2007
  FOR v, e IN ANY r amended_by
    RETURN {
      regulation: v,
      relationship: e.type
    }

User Input: Has Law no. 11 of 2008 been amended by other regulations?
AQL Query: WITH regulation, amended_by
FOR r IN regulation
  FILTER r.type == "UU" AND r.number == 11 AND r.year == 2008
  FOR v, e IN INBOUND r amended_by
    RETURN v

User Input: What does UU No. 1 of 2024 discuss about?
AQL Query: WITH regulation
FOR r IN regulation
  FILTER r.type == "UU" AND r.number == 1 AND r.year == 2024
  RETURN r.title

User Input: How many articles are there in Law No. 1 of 2024?
AQL Query: WITH regulation, article, has_article
FOR r IN regulation
  FILTER r.type == "UU" AND r.number == 1 AND r.year == 2024
  LET article_count = LENGTH(FOR v, e IN OUTBOUND r has_article RETURN 1)
  RETURN {article_count}

User Input: What articles are in chapter 5 of PP No. 71 of 2019? Explain it
AQL Query: WITH regulation, article, has_article
FOR r IN regulation
  FILTER r.type == "PP" AND r.number == 71 AND r.year == 2019
  FOR v, e IN OUTBOUND r has_article
    FILTER v.chapter == "5"
    RETURN v
  
User Input: Which articles are no longer valid (amended) in UU Number 11 of 2008?
AQL Query: WITH regulation, article, has_article
FOR r IN regulation
  FILTER r.type == "UU" AND r.number == 11 AND r.year == 2008
  FOR v, e IN OUTBOUND r has_article
    FILTER v.effective == False
    RETURN v
"""

NX_ALGORITHM_GENERATION_PROMPT = """I have a NetworkX Graph called `G_adb`. 
                                
It has the following schema: {schema}

I have the following graph analysis query: {query}.

Your task:
- Generate the Python Code required to answer the query using the `G_adb` object.
- Be very precise on the NetworkX algorithm you select to answer this query. Think step by step.
- Only assume that networkx is installed, and other base python dependencies.
- Always set the last variable as `FINAL_RESULT`, which represents the answer to the original query.
- Only provide python code that I can directly execute via `exec()`. Do not provide any instructions.
- Make sure that `FINAL_RESULT` stores a short & consice answer. Avoid setting this variable to a long sequence.
- **DON'T CREATE ANY ASSUMPTION TO ADD NODE OR ADD EDGE TO THE `G_adb` OBJECT GRAPH, YOU ONLY CAN READ FROM IT**
- **DON'T USE ANY TRY-EXCEPT BLOCK**

Pay careful attention to the node ID. Make sure you specify the node ID correctly.
The ID is equal to node_type followed by "/" followed by the entity number.
The entity number is formed using a 15-digit number, e.g. article/201601019104502  

Your code:
"""

NX_ALGORITHM_RETRY_PROMPT = """I tried executing the following networkx Python code, but it failed:

---
{code}
---

The error message I got was: {error}

The networkx Python code will be used to answer the following graph analysis query: {query}.

The networkx graph has the following schema: {schema}

Your task:
- Identify the issue and fix the code.
- Only assume that networkx is installed, and other base python dependencies.
- Ensure that `FINAL_RESULT` still contains the correct answer.
- Provide the corrected Python code only, without any explanations.
- Ensure that the corrected code is executable with `exec()`.
- **DON'T CREATE ANY ASSUMPTION TO ADD NODE OR ADD EDGE TO THE `G_adb` OBJECT GRAPH, YOU ONLY CAN READ FROM IT**
- **DON'T USE ANY TRY-EXCEPT BLOCK**

Corrected Code:
"""

NX_ALGORITHM_QA_PROMPT = """I have a NetworkX Graph called `G_adb`.

It has the following schema: {schema}

I have the following graph analysis query: {query}.

I have executed the following python code to help me answer my query:

---
{code}
---

The `FINAL_RESULT` variable is set to the following: {result}.

Based on my original Query and FINAL_RESULT, generate a short and concise response to answer my query.

Your response:
"""

VISUALIZATION_GENERATION_PROMPT = """I have a **NetworkX graph** object called `G_adb`.

The networkx graph follows this schema: `{schema}`.  

I need to **visualize** the answer to the following graph analysis query:  

- **Query:** `{query}`  
- **Answer:** `{answer}`  

### **Important Constraints & Instructions:**  
1. **Graph Extraction:**  
    - `G_adb` is an instance of `nx_arangodb.Graph`, which does **not** support `.subgraph()`.  
- Convert it to a standard **NetworkX graph** (`nx.Graph`) using:  
        ```python
        G_nx = nx.Graph(G_adb)
        ```  
    - Then, create a **subgraph** from `G_nx` using only the relevant nodes.  

2. **Your Task:**  
    - Generate **Python code** that visualizes the answer using the `G_adb` graph.  
    - The **visualization must be clear and readable** (avoid large node sizes).  
    - *Show, save, and close the visualization as** `"output.png"` using:  
        ```python
        plt.savefig("output.png")
        plt.show()
        plt.close()
        ```  
    - **Do NOT modify `G_adb`** (e.g., do not add/remove nodes or edges).  

3. **Output Format:**  
    - Only provide **Python code** (no explanations or additional text).  
    - The code should be **directly executable** via `exec()`.  

**Your Python Code:**  
"""

VISUALIZATION_RETRY_PROMPT = """I attempted to execute the following **NetworkX Python code** for visualization, but it failed:  

```python
{code}
```

### **Error Message:**  
```shell
{error}
```

### **Context:**  
This **visualization code** is intended to answer the following **graph analysis query**:  
- **Query:** `{query}`  
- **Answer:** `{answer}`  

The **NetworkX Graph** follows this schema: `{schema}`  

### **Your Task:**  
1. **Identify and fix the issue** in the provided code.  
2. **Generate the corrected Python code** to visualize the answer using the `G_adb` object.
    - `G_adb` is an instance of `nx_arangodb.Graph`, which does **not** support `.subgraph()`.  
    - Convert it to a standard **NetworkX graph** (`nx.Graph`) using:  
        ```python
        G_nx = nx.Graph(G_adb)
        ```  
    - Then, create a **subgraph** from `G_nx` using only the relevant nodes.  
3. The **visualization must be clear and readable** (avoid large node sizes).  
4. **Do NOT modify `G_adb`** (e.g., do not add/remove nodes or edges).  
5. *Show, save, and close the visualization as** `"output.png"` using:  
    ```python
    plt.savefig("output.png")
    plt.show()
    plt.close()
```  
6. **Do NOT modify `G_adb`** (e.g., do not add/remove nodes or edges).  

### **Output Format:**  
1. Only provide **Python code** (no explanations or additional text).  
2. The code should be **directly executable** via `exec()`.  

**Corrected Python Code:**
"""