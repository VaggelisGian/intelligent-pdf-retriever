# Graph RAG Assistant

## Overview
The Graph RAG Assistant is an AI-powered system designed to facilitate access to data, particularly from PDF files, using graph structures. This project leverages various technologies to create a seamless experience for users looking to interact with and retrieve information from documents.

## Features
- **Retrieval-Augmented Generation (RAG)**: Integrates with large language models (LLMs) to enhance the assistant's capabilities in retrieving and generating relevant information.
- **Graph RAG**: Utilizes Neo4J to implement graph-based data retrieval, improving the efficiency and accuracy of information access.
- **Document Processing**: Capable of loading and processing PDF files to extract useful data for the assistant.
- **REST API**: Built with FastAPI to handle requests related to the assistant and document processing.
- **Frontend Interface**: Developed using Streamlit, providing an intuitive user interface for interaction with the assistant.

## Technologies Used
- **Langchain**: For developing the assistant and implementing RAG and Graph RAG functionalities.
- **OpenAI LLMs**: Such as GPT-4o-mini for natural language processing tasks.
- **Neo4J**: An open-source graph database for managing and querying graph data.
- **FastAPI**: A modern web framework for building APIs with Python.
- **Redis**: Used for memory management in dialogues.
- **Streamlit**: A Python library for creating web applications quickly.

## Project Structure
```
graph-rag-assistant
├── src
│   ├── backend
│   │   ├── api
│   │   ├── assistant
│   │   ├── database
│   │   ├── document_processing
│   │   └── main.py
│   ├── frontend
│   │   ├── app.py
│   │   └── pages
│   └── utils
├── data
│   ├── pdf_files
│   └── processed
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

## Setup Instructions
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/graph-rag-assistant.git
   cd graph-rag-assistant
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Configure environment variables by copying `.env.example` to `.env` and updating the values as necessary.

4. Start the application:
   ```
   uvicorn src/backend/main:app --reload
   ```

5. Access the frontend interface by navigating to `http://localhost:8501` in your web browser.

## Usage
- Upload PDF files through the upload interface.
- Interact with the assistant via the chat interface to retrieve information from the uploaded documents.

## Contributing
Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.