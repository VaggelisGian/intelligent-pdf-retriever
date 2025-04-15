from langchain_openai import OpenAI, OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Neo4jVector
from dotenv import load_dotenv
import os

load_dotenv()

class RAGAssistant:
    def __init__(self):
        github_token = os.getenv('GITHUB_TOKEN')
        neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        neo4j_user = os.getenv('NEO4J_USERNAME', 'neo4j')
        neo4j_password = os.getenv('NEO4J_PASSWORD', 'vaggpinel')
        
        # Initialize embeddings with GitHub API
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=github_token,
            openai_api_base="https://models.inference.ai.azure.com",
            model="text-embedding-3-small"  # Add this line to specify the model
        )
        
        # Initialize vector store
        self.vector_store = Neo4jVector.from_existing_graph(
            embedding=self.embeddings,
            url=neo4j_uri,
            username=neo4j_user,
            password=neo4j_password,
            index_name="sentence_embeddings",
            node_label="Sentence",
            text_node_properties=["content"],
            embedding_node_property="embedding"
        )
        
        # Initialize LLM with GitHub API
        self.llm = OpenAI(
            openai_api_key=github_token, 
            openai_api_base="https://models.inference.ai.azure.com",
            model_name="gpt-4o-mini",
            temperature=0
        )
        
        # Initialize retrieval chain
        self.qa = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vector_store.as_retriever()
        )
    
    def query(self, question):
        """Query the RAG assistant with a question"""
        result = self.qa.invoke({"query": question})
        return result