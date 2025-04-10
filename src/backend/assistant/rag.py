from langchain import OpenAI
from langchain.chains import RetrievalQA
from langchain.vectorstores import Neo4jVectorStore
from langchain.embeddings import OpenAIEmbeddings
from fastapi import HTTPException

class RAGAssistant:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str, openai_api_key: str):
        self.vector_store = Neo4jVectorStore(
            uri=neo4j_uri,
            username=neo4j_user,
            password=neo4j_password,
            embedding_function=OpenAIEmbeddings(openai_api_key=openai_api_key)
        )
        self.llm = OpenAI(api_key=openai_api_key)
        self.retrieval_qa = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vector_store.as_retriever()
        )

    def query(self, question: str):
        if not question:
            raise HTTPException(status_code=400, detail="Question cannot be empty.")
        answer = self.retrieval_qa.run(question)
        return answer