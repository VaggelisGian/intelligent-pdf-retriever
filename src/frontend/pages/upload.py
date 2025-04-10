import streamlit as st
import requests

def upload_pdf():
    st.title("Upload PDF Document")
    st.write("Please upload your PDF file for processing.")

    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file is not None:
        # Display the file details
        st.write("File Name:", uploaded_file.name)
        st.write("File Size:", uploaded_file.size, "bytes")

        # Send the file to the backend for processing
        if st.button("Upload"):
            files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
            response = requests.post("http://localhost:8000/api/upload", files=files)

            if response.status_code == 200:
                st.success("File uploaded successfully!")
            else:
                st.error("Error uploading file. Please try again.")

if __name__ == "__main__":
    upload_pdf()