from streamlit import st
import requests

# Set the title of the chat interface
st.title("Graph RAG Assistant Chat")

# Input field for user messages
user_input = st.text_input("You:", "")

# Button to send the message
if st.button("Send"):
    if user_input:
        # Call the backend API to get the assistant's response
        response = requests.post("http://localhost:8000/api/chat", json={"message": user_input})
        
        if response.status_code == 200:
            assistant_response = response.json().get("response", "No response from assistant.")
            st.text_area("Assistant:", assistant_response, height=300)
        else:
            st.error("Error: Unable to get response from the assistant.")
    else:
        st.warning("Please enter a message.")