from fastapi import FastAPI
import streamlit as st
import requests

# Initialize the FastAPI app
app = FastAPI()

# Streamlit UI setup
def main():
    st.title("Graph RAG Assistant")
    
    # File upload section
    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    if uploaded_file is not None:
        # Process the uploaded PDF file
        response = requests.post("http://localhost:8000/api/upload", files={"file": uploaded_file})
        if response.status_code == 200:
            st.success("File uploaded successfully!")
        else:
            st.error("Error uploading file.")
    
    # Chat interface
    user_input = st.text_input("Ask a question:")
    if st.button("Submit"):
        if user_input:
            response = requests.post("http://localhost:8000/api/chat", json={"question": user_input})
            if response.status_code == 200:
                answer = response.json().get("answer")
                st.write("Assistant:", answer)
            else:
                st.error("Error getting response from assistant.")

if __name__ == "__main__":
    main()