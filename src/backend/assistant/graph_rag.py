from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
from langchain.vectorstores import Neo4jVectorStore
from langchain.embeddings import OpenAIEmbeddings
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

# Initialize the FastAPI router
router = APIRouter()

# Define the request model for querying the assistant
class QueryRequest(BaseModel):
    query: str

# Define the response model for the assistant's answer
class QueryResponse(BaseModel):
    answer: str

# Initialize the LLM and the vector store
embeddings = OpenAIEmbeddings()
vector_store = Neo4jVectorStore(embeddings=embeddings, uri="neo4j://localhost:7687", username="neo4j", password="password")
llm = OpenAI(model="gpt-4o-mini")

# Create the Graph RAG assistant
graph_rag_assistant = RetrievalQA(llm=llm, retriever=vector_store.as_retriever())

@router.post("/graph_rag/query", response_model=QueryResponse)
async def query_graph_rag(request: QueryRequest):
    try:
        answer = graph_rag_assistant.run(request.query)
        return QueryResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))