from langchain_openai import ChatOpenAI # Changed from OpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings # Use local embeddings
from langchain_community.vectorstores import Neo4jVector
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Neo4jVector
from dotenv import load_dotenv
from langchain.chains import RetrievalQA
from langchain_core.language_models.chat_models import BaseChatModel # Import base class
import os
from typing import Optional

load_dotenv()

class RAGAssistant:
    def __init__(self, llm: Optional[BaseChatModel] = None):
        # --- Configuration for Local LM Studio ---
        lm_studio_api_base = "http://localhost:1234/v1" # Default LM Studio endpoint
        lm_studio_api_key = "lm-studio" # Dummy key, LM Studio doesn't usually need one

        # --- Configuration for Local Embeddings ---
        # Choose a model from Hugging Face suitable for embeddings
        # Make sure you have sentence-transformers installed: pip install sentence-transformers
        embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"

        # --- Neo4j Configuration ---
        neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        neo4j_user = os.getenv('NEO4J_USERNAME', 'neo4j')
        neo4j_password = os.getenv('NEO4J_PASSWORD', 'vaggpinel')

        # Initialize embeddings using HuggingFaceEmbeddings
        print(f"Initializing local embeddings model: {embedding_model_name}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model_name,
            model_kwargs={'device': 'cpu'} # Or 'cuda' if you have GPU support and PyTorch installed
        )
        print("Embeddings model initialized.")

        # Initialize vector store (remains the same)
        print("Connecting to Neo4j vector store (using Chunk nodes)...")
        self.vector_store = Neo4jVector.from_existing_graph(
            embedding=self.embeddings,
            url=neo4j_uri,
            username=neo4j_user,
            password=neo4j_password,
            index_name="chunk_embeddings", # CHANGE index name
            node_label="Chunk",            # CHANGE node label
            text_node_properties=["content"],
            embedding_node_property="embedding"
        )
        print("Neo4j vector store connected.")

        # Initialize LLM using ChatOpenAI pointed to LM Studio
        print(f"Initializing LLM via LM Studio at: {lm_studio_api_base}")
        self.llm = ChatOpenAI(
            openai_api_key=lm_studio_api_key,
            openai_api_base=lm_studio_api_base,
            # model_name is often ignored by LM Studio but can be kept
            # model_name="PrunaAI/mistralai-Mistral-7B-Instruct-v0.2-GGUF-smashed",
            temperature=0
        )
        print("LLM initialized.")

        if llm:
            self.llm = llm
            print("RAG Assistant initialized with provided LLM.")
        else:
            # Initialize default LLM using ChatOpenAI pointed to LM Studio
            print(f"Initializing default LLM via LM Studio at: {lm_studio_api_base}")
            self.llm = ChatOpenAI(
                openai_api_key=lm_studio_api_key,
                openai_api_base=lm_studio_api_base,
                temperature=0 # Default temperature
            )
            print("Default LLM initialized.")

        # Initialize retrieval chain using self.llm
        self._create_qa_chain()
        print("RAG Assistant ready.")

    def _create_qa_chain(self):
        """Helper to create/recreate the QA chain."""
        self.qa = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff", # Or "map_reduce", etc.
            retriever=self.vector_store.as_retriever(),
            return_source_documents=True # Ensure sources are returned
        )
        print("RetrievalQA chain created/updated.")

    def update_llm(self, llm: BaseChatModel):
        """Updates the LLM instance and recreates the chain."""
        self.llm = llm
        self._create_qa_chain()
        print("RAG Assistant LLM updated.")

    def query(self, question):
        """Query the RAG assistant with a question"""
        print(f"RAG Query: {question}")
        # The chain now uses the potentially updated self.llm
        result = self.qa.invoke({"query": question})
        print(f"RAG Result: {result}")
        return result