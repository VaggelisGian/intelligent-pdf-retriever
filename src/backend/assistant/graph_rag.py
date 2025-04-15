from langchain_openai import OpenAI
from langchain.chains import GraphQAChain
from langchain_community.graphs import Neo4jGraph
from langchain.chains.graph_qa.base import GraphQAChain
from dotenv import load_dotenv
import os

load_dotenv()

class GraphRAGAssistant:
    def __init__(self):
        github_token = os.getenv('GITHUB_TOKEN')
        neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        neo4j_user = os.getenv('NEO4J_USERNAME', 'neo4j')
        neo4j_password = os.getenv('NEO4J_PASSWORD', 'vaggpinel')
        
        # Initialize Neo4j graph
        self.graph = Neo4jGraph(
            url=neo4j_uri,
            username=neo4j_user,
            password=neo4j_password
        )
        
        # Initialize LLM with GitHub Models API
        self.llm = OpenAI(
            openai_api_key=github_token,
            openai_api_base="https://models.inference.ai.azure.com",
            model_name="gpt-4o-mini",
            temperature=0
        )
        
        # Initialize graph QA chain
        self.qa_chain = GraphQAChain.from_llm(
            llm=self.llm,
            graph=self.graph,
            verbose=True
        )
    
    def query(self, question):
        """Query the Graph RAG assistant with a question"""
        result = self.qa_chain.invoke({"query": question})
        return result