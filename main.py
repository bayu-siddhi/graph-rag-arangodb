import os
import src
import dotenv
import functools
import gradio as gr

from src import helper
from torch import cuda
from langchain_community import graphs
from langchain_openai import chat_models as openai_chat_models
from langchain_google_genai import chat_models as google_chat_models


if __name__=="__main__":

    dotenv.load_dotenv(".env")

    # Determine device
    device = "cuda" if cuda.is_available() else "cpu"

    # Instantiate the dataset object
    dataset_obj = src.Dataset("data")

    # Instantiate the database object
    database_obj = src.Database(
        host=os.environ["DATABASE_HOST"],
        db_name=os.environ["DATABASE_NAME"],
        graph_name=os.environ["GRAPH_NAME"],
        username=os.environ["DATABASE_USERNAME"],
        password=os.environ["DATABASE_PASSWORD"]
    )

    # Get NetworkX ArangoDB graph representation
    G_adb = database_obj.get_nxadb_graph()

    # Instantiate the ArangoGraph LangChain wrapper
    arango_graph = graphs.ArangoGraph(database_obj.db_obj)

    # Instatiate the LLM object
    if os.environ.get("OPENAI_API_KEY"):
        llm = openai_chat_models.ChatOpenAI(
            model="gpt-4o",
            temperature=0.0,
            api_key=os.environ["OPENAI_API_KEY"]
        )
    elif os.environ.get("GOOGLE_API_KEY"):
        llm = google_chat_models.ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.0,
            api_key=os.environ["GOOGLE_API_KEY"]
        )

    # Create agent
    ask_agent = src.create_ask_agent(
        llm=llm,
        nxadb_graph=database_obj.get_nxadb_graph(),
        arango_graph=arango_graph,
        embedding_model=os.environ["EMBEDDING_MODEL"],
        device=device
    )

    # Running ask_agent on Gradio Chat Interface
    with gr.Blocks() as demo:
        # Check if dataset/database exist
        is_dataset_empty, is_graph_empty = helper.check_database_status(
            dataset_obj=dataset_obj, database_obj=database_obj
        )

        page1 = gr.Column(visible=(is_dataset_empty or is_graph_empty))
        page2 = gr.Column(visible=(not is_dataset_empty and not is_graph_empty))

        if not is_dataset_empty and not is_graph_empty:
            helper.refresh_database_schema(arango_graph=arango_graph)

        # Preparation Page
        with page1:
            with gr.Row():
                with gr.Column(scale=3):
                    gr.Markdown()

                with gr.Column(scale=4):
                    image = gr.Image(
                        helper.load_image("assets/ITS-logo.png"),
                        width=300,
                        show_label=False,
                        show_download_button=False,
                        show_fullscreen_button=False
                    )
                    status_text = gr.Markdown("<center><h2>Database is empty</h2></center>")
                    prepare_button = gr.Button("Prepare and Load Database", variant="primary")
                    refresh_button = gr.Button("Refresh Database Status")

                    prepare_button.click(
                        fn=functools.partial(
                            helper.prepare_and_load_database_with_status,
                            dataset_obj,
                            database_obj,
                            arango_graph,
                            device
                        ),
                        outputs=[status_text, page1, page2]
                    )

                    refresh_button.click(
                        fn=functools.partial(helper.refresh_status, dataset_obj, database_obj),
                        outputs=[page1, page2]
                    )

                with gr.Column(scale=3):
                    gr.Markdown()

        # Chat page
        with page2:
            image = gr.Image(helper.load_image("assets/ITS-logo.png"), label="Image Output", render=False)
            with gr.Row():
                with gr.Column(scale=7):
                    gr.Markdown("<center><h1>Chatbot Interface</h1></center>")
                    gr.ChatInterface(
                        ask_agent,
                        examples=[
                            "What is the definition of private data?", 
                            "Explain, what are the obligations of electronic system organizers?",
                            "What is the content of article 33 of UU Number 11 of 2008?",
                            "Which regulation article has the most influence?",
                            "What is the shortest path between article/200801011600100 to article/202401001604000? Visualize it",
                            "Which regulation node id is the center of a particular legal community based on the number of references it has? What it's title? Then check whether the regulation has ever been amended?"
                        ],
                        additional_outputs=[image],
                        type="messages"
                    )

                with gr.Column(scale=3):
                    gr.Markdown("<center><h1>Image Output</h1></center>")
                    image.render()

    demo.launch()
