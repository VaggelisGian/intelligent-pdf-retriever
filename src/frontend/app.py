import streamlit as st
import requests
import time
import os
import json
import threading
import websocket  # Make sure to install: pip install websocket-client
from datetime import datetime

# Define backend URL at the module level
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
print(f"Using backend URL: {BACKEND_URL}")

# Define global variables for thread-safe polling
_last_poll_result = None
_should_continue_polling = False

# WebSocket client class to handle real-time progress updates
class ProgressWebSocketClient:
    def __init__(self, job_id):
        self.job_id = job_id
        self.ws = None
        self.thread = None
        self.running = False
        
        # Convert HTTP URL to WebSocket URL
        ws_url = BACKEND_URL.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_url}/ws/progress/{job_id}"
        
        print(f"DEBUG: Initializing WebSocket client for {job_id}")
        print(f"DEBUG: WebSocket URL: {self.ws_url}")
    
    def on_message(self, ws, message):
        """Handle incoming progress updates from server"""
        try:
            # Parse the progress update
            print(f"DEBUG: WebSocket received message: {message[:100]}...")
            data = json.loads(message)
            
            # Update the session state with the new progress
            st.session_state.progress_data = data
            
            # Print progress update for debugging
            current_page = data.get("current_page", 0)
            total_pages = data.get("total_pages", 0)
            percent = data.get("percent_complete", 0)
            status = data.get("status", "processing")
            
            print(f"WebSocket update: {percent}%, page {current_page}/{total_pages}, status: {status}")
            
            # Mark processing as complete if status is completed/failed/error
            if status in ["completed", "failed", "error"]:
                st.session_state.processing_active = False
                
            # Signal that UI needs to be updated
            st.session_state.needs_rerun = True
            
        except Exception as e:
            print(f"WebSocket message error: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"DEBUG: WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        print(f"DEBUG: WebSocket closed: {close_status_code} - {close_msg}")
        self.running = False
    
    def on_open(self, ws):
        """Handle WebSocket connection open"""
        print(f"DEBUG: WebSocket connection established for job: {self.job_id}")
        self.running = True
        
        # Send ping message every 30 seconds to keep connection alive
        def ping_thread():
            while self.running:
                try:
                    ws.send("ping")
                    print(f"DEBUG: Sent ping to keep WebSocket alive")
                    time.sleep(30)
                except Exception as e:
                    print(f"DEBUG: Error in ping thread: {e}")
                    break
        
        threading.Thread(target=ping_thread).start()
    
    def start(self):
        """Start WebSocket connection in background thread"""
        # Create WebSocket connection
        print(f"DEBUG: Creating WebSocketApp for {self.job_id}")
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        
        # Run WebSocket client in a thread
        def run_ws():
            print(f"DEBUG: Starting WebSocket run_forever() loop")
            self.ws.run_forever()
            print(f"DEBUG: WebSocket run_forever() loop ended")
        
        self.thread = threading.Thread(target=run_ws)
        self.thread.daemon = True
        self.thread.start()
        print(f"DEBUG: WebSocket thread started")
        
        return self
    
    def stop(self):
        """Stop WebSocket connection"""
        print(f"DEBUG: Stopping WebSocket connection")
        self.running = False
        if self.ws:
            self.ws.close()
            print(f"DEBUG: WebSocket closed")


# Replace your poll_progress function with this simpler version:

# Replace the poll_progress function with this:

def poll_progress(job_id):
    """Direct polling function that updates session state"""
    try:
        progress_url = f"{BACKEND_URL}/api/progress/{job_id}"
        print(f"DEBUG: Polling {progress_url}")
        response = requests.get(progress_url, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            
            # Update progress data directly in session state
            st.session_state.progress_data = data
            st.session_state.last_poll_time = time.time()
            
            # Debug output
            current_page = data.get("current_page", 0)
            total_pages = data.get("total_pages", 0)
            percent = data.get("percent_complete", 0)
            status = data.get("status", "processing")
            print(f"Poll update: {percent}%, page {current_page}/{total_pages}, status: {status}")
            
            # Stop polling on completion
            if status in ["completed", "failed", "error"]:
                print(f"DEBUG: Job {job_id} has status {status}, stopping polling")
                st.session_state.should_continue_polling = False
                return
        else:
            print(f"DEBUG: Poll failed with status {response.status_code}")
            print(f"DEBUG: Response text: {response.text[:200]}")

    except Exception as e:
        print(f"DEBUG: Error in polling: {e}")
    
    # Continue polling if needed
    if st.session_state.should_continue_polling:
        threading.Timer(1.0, lambda: poll_progress(job_id)).start()
    else:
        print(f"DEBUG: Polling stopped for job {job_id}")

def check_services_ready():
    """Check if backend services are ready"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=5)
        if response.status_code == 200:
            return True
        return False
    except Exception:
        return False

def update_debug_mode():
    st.session_state.debug_mode = st.session_state.debug_checkbox_key

def call_chat_api(question: str, use_graph: bool = False):
    """Sends question to backend and returns the response."""
    try:
        chat_url = f"{BACKEND_URL}/api/chat"
        payload = {"question": question, "use_graph": use_graph}
        response = requests.post(chat_url, json=payload, timeout=120) # Increased timeout for LLM calls
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Chat API error: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None
    
def main():
    # This needs to be the very first thing in main()
    global _should_continue_polling, _last_poll_result
    _should_continue_polling = False
    time.sleep(0.1)
    # Add debug print to see what's happening with polling results
    print(f"DEBUG: Main loop start. _last_poll_result exists: {_last_poll_result is not None}")
    
    if _last_poll_result and st.session_state.get("current_job_id") == _last_poll_result["job_id"]:
        print(f"DEBUG: Processing poll result: {_last_poll_result['job_id']}")
        print(f"DEBUG: Poll result data: {_last_poll_result['data'].get('percent_complete')}%, " +
              f"page {_last_poll_result['data'].get('current_page')}/{_last_poll_result['data'].get('total_pages')}")
        
        # Update session state with the polling result
        st.session_state.progress_data = _last_poll_result["data"]
        
        # Update processing status if needed
        if _last_poll_result["data"].get("status") in ["completed", "failed", "error"]:
            print(f"DEBUG: Job complete/failed. Stopping processing and polling.")
            st.session_state.processing_active = False
            _should_continue_polling = False  # Stop polling
        
        # Clear the result so we don't process it again
        _last_poll_result = None
        
        # Trigger UI refresh
        print("DEBUG: Triggering UI rerun from poll result")
        st.rerun()
    
    # FIRST: Session State Initialization 
    for key, default in [
        ("processing_active", False),
        ("current_job_id", None),
        ("uploaded_file_info", None),
        ("debug_mode", False),
        ("progress_data", None),    
        ("chat_history", []),
        ("user_question", ""),
        ("needs_rerun", False),
        ("ws_client", None),
        ("last_current_page", 0),
        ("last_update_time", time.time()),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # Now it is safe to use st.session_state.current_job_id, etc.
    job_id = st.session_state.current_job_id
    if (
        st.session_state.processing_active
        and job_id
        and (
            not st.session_state.progress_data
            or st.session_state.progress_data.get("status") not in ["completed", "failed", "error"]
        )
    ):
        progress_url = f"{BACKEND_URL}/api/progress/{job_id}"
        try:
            response = requests.get(progress_url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                st.session_state.progress_data = data
                st.session_state.last_poll_time = time.time()
                # If not complete, rerun after a short delay
                if data.get("status") not in ["completed", "failed", "error"]:
                    time.sleep(1)
                    st.rerun()
            else:
                print(f"Poll failed: {response.status_code} {response.text[:200]}")
        except Exception as e:
            print(f"Polling error: {e}")
                    
    # UI code
    st.title("Intelligent PDF Retriever!")

    # Main UI with sidebar
    st.sidebar.info(f"Connected to: {BACKEND_URL}")
    if st.sidebar.button("Refresh Connection"):
        if check_services_ready():
            st.sidebar.success("✅ Connection OK")
        else:
            st.sidebar.error("❌ Connection failed")

    st.header("Upload Document!!")
    
    # File Uploader
    uploaded_file = st.file_uploader(
        "Upload a PDF file",
        type=["pdf"],
        key="pdf_uploader",
        disabled=st.session_state.processing_active
    )
    
    if uploaded_file is not None and not st.session_state.processing_active:
        if st.session_state.uploaded_file_info is None or st.session_state.uploaded_file_info["name"] != uploaded_file.name:
            st.session_state.uploaded_file_info = {
                "name": uploaded_file.name,
                "bytes": uploaded_file.getvalue()
            }
            st.session_state.current_job_id = None
            st.session_state.progress_data = None
            st.session_state.processing_active = False

    # Display File Info and Controls
    if st.session_state.uploaded_file_info:
        st.write("File selected:", st.session_state.uploaded_file_info["name"])
        
        st.checkbox(
            "Debug mode",
            value=st.session_state.debug_mode,
            key="debug_checkbox_key",
            on_change=update_debug_mode,
            disabled=st.session_state.processing_active
        )
        
        # Process Button
        process_button_disabled = st.session_state.processing_active or st.session_state.uploaded_file_info is None
        if st.button("Process PDF", disabled=process_button_disabled):
            st.session_state.processing_active = True
            st.session_state.current_job_id = None
            st.session_state.progress_data = None
            st.rerun()

    # Upload Logic
    if st.session_state.processing_active and st.session_state.current_job_id is None and st.session_state.uploaded_file_info:
        files = {"file": (st.session_state.uploaded_file_info["name"], st.session_state.uploaded_file_info["bytes"], "application/pdf")}
        
        upload_container = st.empty()
        
        with upload_container, st.status("Uploading file...", expanded=True) as status:
            try:
                upload_url = f"{BACKEND_URL}/api/upload"
                response = requests.post(upload_url, files=files, timeout=60)
                
                # In the upload section (line ~310):
                if response.status_code == 200:
                    resp_json = response.json()
                    job_id = resp_json.get("job_id")
                    st.session_state.current_job_id = job_id
                    st.session_state.progress_data = {
                        "job_id": job_id,
                        "status": "starting",
                        "message": "Upload successful. Starting processing...",
                        "percent_complete": 0
                    }
                    # Close existing WebSocket client if any
                    if st.session_state.ws_client:
                        st.session_state.ws_client.stop()
                    print(f"DEBUG: Starting polling for job {job_id}")
                    status.update(label="✅ Upload successful", state="complete", expanded=False)
                    # DO NOT call st.rerun() or start any thread here!
                else:
                    fail_msg = f"Upload failed: {response.status_code} - {response.text}"
                    status.update(label=f"❌ {fail_msg}", state="error")
                    st.session_state.processing_active = False
                    st.session_state.current_job_id = None
                    
            except Exception as e:
                fail_msg = f"Error during upload: {str(e)}"
                status.update(label=f"❌ {fail_msg}", state="error")
                st.session_state.processing_active = False
                st.session_state.current_job_id = None

    # Display progress
    if st.session_state.current_job_id and st.session_state.progress_data:
        data = st.session_state.progress_data
        job_id = st.session_state.current_job_id

        # Get values from the latest progress_data in session state
        percent = data.get("percent_complete", 0)
        message = data.get("message", "Processing...")
        status_value = data.get("status", "processing")
        
        # Get page information 
        current_page = data.get("current_page", 0)
        total_pages = data.get("total_pages", 0)
        
        # Improved progress calculation for PDF extraction phase
        if status_value == "processing" and total_pages > 0 and current_page > 0:
            # Scale extraction phase to 0-55% as per backend logic
            calculated_pct = int((current_page / total_pages) * 55)
            # Ensure minimum progress visibility once started
            calculated_pct = max(1, calculated_pct)
            # Use the maximum of backend-reported or calculated percentage
            percent = max(percent, calculated_pct)
        
        # For neo4j processing phase, rely on backend percentage but ensure it's at least 55%
        elif status_value == "processing_neo4j":
            percent = max(percent, 55)  # Neo4j phase starts after 55% completion
        
        # Debug output for progress tracking
        print(f"PROGRESS DISPLAY: {percent}%, page {current_page}/{total_pages}, status: {status_value}")

        # Set appropriate label and state based on status
        if status_value == "completed":
            label = "✅ Complete"
            state = "complete"
        elif status_value in ["failed", "error"]:
            label = f"❌ {message}"
            state = "error"
        else:
            phase_info = ""
            if status_value == "processing": 
                phase_info = "Phase 1/2: PDF Extraction"
            elif status_value == "processing_neo4j": 
                phase_info = "Phase 2/2: Knowledge Graph Creation"
            display_message = f"{phase_info} - {message}" if phase_info else message
            label = f"⏳ {display_message}"
            state = "running"

        # Show the status widget
        status_widget = st.status(
            label, 
            state=state, 
            expanded=(status_value not in ["completed", "failed", "error"])
        )

        with status_widget:
            # Convert percent to float and ensure it's between 0-1
            progress_value = float(percent) / 100.0
            progress_value = max(0.0, min(1.0, progress_value))
            
            # Show the progress bar
            st.progress(progress_value)
            
            # Show detailed progress information
            if current_page > 0 and total_pages > 0:
                page_progress = f"{current_page}/{total_pages} pages"
                st.text(f"Progress: {percent}% ({page_progress})")
            else:
                st.text(f"Progress: {percent}%")
            
            # Only show debug info when debug mode is enabled
            if st.session_state.debug_mode:
                st.divider()
                st.text("Debug Information:")
                st.json(data)
                st.text(f"Raw percent value: {data.get('percent_complete')}")
                st.text(f"Calculated percent: {percent}")

    # Chat Interface (only shows after successful processing)
    st.header("2. Chat with Document")

    # Check if processing is complete before showing chat
    processing_complete = (st.session_state.progress_data and
                          st.session_state.progress_data.get("status") == "completed")
    
    if not processing_complete:
        st.info("Please upload and process a document successfully before chatting.")
    else:
        # Display chat history
        chat_container = st.container(height=400) # Use container for scrollable history
        with chat_container:
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    if message.get("sources"):
                        with st.expander("Sources"):
                            for source in message["sources"]:
                                st.code(source, language='text') # Display sources if available

        # Chat input area
        user_question = st.chat_input("Ask a question about the document...", key="chat_input_box")

        if user_question:
            st.session_state.user_question = user_question # Store user input

            # Add user message to history immediately
            st.session_state.chat_history.append({"role": "user", "content": st.session_state.user_question})

            # Display user message in chat container
            with chat_container:
                 with st.chat_message("user"):
                     st.markdown(st.session_state.user_question)

            # Call backend API and display response
            with st.spinner("Thinking..."):
                # TODO: Add toggle for use_graph if needed
                response_data = call_chat_api(st.session_state.user_question, use_graph=False)

            if response_data:
                answer = response_data.get("answer", "Sorry, I couldn't find an answer.")
                sources = response_data.get("sources", [])
                # Add assistant message to history
                st.session_state.chat_history.append({"role": "assistant", "content": answer, "sources": sources})
                # Display assistant message in chat container
                with chat_container:
                    with st.chat_message("assistant"):
                        st.markdown(answer)
                        if sources:
                             with st.expander("Sources"):
                                 for source in sources:
                                     st.code(source, language='text')
            else:
                 # Error message already shown by call_chat_api
                 st.session_state.chat_history.append({"role": "assistant", "content": "Error communicating with the backend."})
                 with chat_container:
                     with st.chat_message("assistant"):
                         st.error("Error communicating with the backend.")

            # Clear the input box state variable after processing
            st.session_state.user_question = ""
            # Rerun to clear the actual input box widget and show the new message
            st.rerun()


if __name__ == "__main__":
    main()

# Register cleanup function
import atexit

def cleanup():
    """Clean up resources when app exits"""
    if 'ws_client' in st.session_state and st.session_state.ws_client:
        print("Closing WebSocket connection during cleanup")
        st.session_state.ws_client.stop()

atexit.register(cleanup)