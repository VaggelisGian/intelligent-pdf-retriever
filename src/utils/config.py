# Configuration settings for the application

import os

class Config:
    # API settings
    API_KEY = os.getenv("API_KEY", "your_api_key_here")
    API_URL = os.getenv("API_URL", "http://localhost:8000")

    # Neo4J settings
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

    # Redis settings
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = os.getenv("REDIS_PORT", 6379)
    REDIS_DB = os.getenv("REDIS_DB", 0)

    # Other settings
    PDF_DIRECTORY = os.getenv("PDF_DIRECTORY", "data/pdf_files")
    PROCESSED_DIRECTORY = os.getenv("PROCESSED_DIRECTORY", "data/processed")