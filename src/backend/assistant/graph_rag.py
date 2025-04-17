from langchain_openai import ChatOpenAI
from langchain.chains import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from typing import Optional
import os

load_dotenv()

class GraphRAGAssistant:
    def __init__(self, llm: Optional[BaseChatModel] = None):
        # --- Configuration for Local LM Studio ---
        # IMPORTANT: Use host.docker.internal for backend running in Docker to reach host
        lm_studio_api_base = "http://host.docker.internal:1234/v1" # <-- CORRECTED for Docker
        lm_studio_api_key = "lm-studio" # Dummy key

        # --- Neo4j Configuration ---
        # IMPORTANT: Use 'neo4j' as hostname for backend running in Docker
        neo4j_uri = os.getenv('NEO4J_URI', 'bolt://neo4j:7687') # <-- CORRECTED for Docker
        neo4j_user = os.getenv('NEO4J_USERNAME', 'neo4j')
        neo4j_password = os.getenv('NEO4J_PASSWORD', 'vaggpinel')

        # Initialize Neo4j graph
        print("Connecting to Neo4j graph...")
        try:
            self.graph = Neo4jGraph(
                url=neo4j_uri,
                username=neo4j_user,
                password=neo4j_password
            )
            # Refresh schema to make it available for the chain
            self.graph.refresh_schema()
            print("Neo4j graph connected and schema refreshed.")
        except Exception as e:
            print(f"FATAL: Failed to connect to Neo4j or refresh schema: {e}")
            # Depending on your error handling strategy, you might want to raise here
            raise e # Or handle appropriately

        # Initialize LLM using ChatOpenAI pointed to LM Studio
        print(f"Initializing LLM via LM Studio at: {lm_studio_api_base}")
        # Use the provided LLM if available, otherwise create default
        if llm:
            self.llm = llm
            print("GraphRAG Assistant initialized with provided LLM.")
        else:
            print(f"Initializing default LLM via LM Studio at: {lm_studio_api_base}")
            self.llm = ChatOpenAI(
                openai_api_key=lm_studio_api_key,
                openai_api_base=lm_studio_api_base,
                temperature=0 # Default temperature
            )
            print("Default LLM initialized.")

        # Initialize graph QA chain using self.llm
        self._create_qa_chain()
        print("Graph RAG Assistant ready.")

    def _create_qa_chain(self):
        """Helper to create/recreate the QA chain."""
        print("Creating GraphCypherQAChain...")
        try:
            # Use GraphCypherQAChain instead
            self.qa_chain = GraphCypherQAChain.from_llm(
                cypher_llm=self.llm, # LLM to generate Cypher
                qa_llm=self.llm,     # LLM to answer based on Cypher results
                graph=self.graph,
                verbose=True,
                allow_dangerous_requests=True, # <-- ADD THIS LINE
                # You might need to adjust prompts depending on your LLM/data
                # validate_cypher=True, # Optional: adds a validation step
            )
            print("GraphCypherQAChain created/updated.")
        except Exception as e:
            print(f"FATAL: Failed to create GraphCypherQAChain: {e}")
            # Depending on your error handling strategy, you might want to raise here
            raise e # Or handle appropriately


    def update_llm(self, llm: BaseChatModel):
        """Updates the LLM instance and recreates the chain."""
        print("Updating GraphRAG Assistant LLM...")
        self.llm = llm
        self._create_qa_chain() # Recreate the chain with the new LLM
        print("GraphRAG Assistant LLM updated.")


    def query(self, question):
        """Query the Graph RAG assistant with a question"""
        if not hasattr(self, 'qa_chain') or self.qa_chain is None:
             error_msg = "GraphCypherQAChain is not initialized."
             print(f"ERROR: {error_msg}")
             return {"error": error_msg} # Or raise an exception

        print(f"GraphRAG Query: {question}")
        try:
            # The chain now uses the potentially updated self.llm
            result = self.qa_chain.invoke({"query": question})
            print(f"GraphRAG Result: {result}")
            return result
        except Exception as e:
             error_msg = f"Error during GraphRAG query: {type(e).__name__}: {e}"
             print(f"ERROR: {error_msg}")
             traceback.print_exc() # Print full traceback for debugging
             # Return a dictionary indicating error, or raise exception
             return {"error": error_msg, "details": traceback.format_exc()}