import os
import sys
import time
import threading
from pathlib import Path

# Add the project root directory to Python's module search path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

# Import modules
from src.backend.assistant.rag import RAGAssistant
from src.backend.assistant.graph_rag import GraphRAGAssistant

class TimeoutError(Exception):
    pass

# Test RAG with timeouts
def test_with_timeout(rag_type, timeout_seconds=60):
    result = {"success": False, "response": None, "error": None}
    
    def target_function():
        try:
            start_time = time.time()
            print(f"Testing {rag_type}...")
            
            if rag_type == "Standard RAG":
                assistant = RAGAssistant()
            else:
                assistant = GraphRAGAssistant()
                
            print(f"Assistant initialized in {time.time() - start_time:.1f} seconds")
            
            query_start = time.time()
            print(f"Sending query to {rag_type}...")
            response = assistant.query("What are the main topics discussed in these documents?")
            print(f"Query completed in {time.time() - query_start:.1f} seconds")
            
            result["success"] = True
            result["response"] = response
        except Exception as e:
            result["error"] = str(e)
    
    # Create and start the thread
    thread = threading.Thread(target=target_function)
    thread.daemon = True
    thread.start()
    
    # Wait for the specified timeout
    thread.join(timeout_seconds)
    
    # Check if thread is still alive (meaning it timed out)
    if thread.is_alive():
        print(f"❌ {rag_type} timed out after {timeout_seconds} seconds!")
        return False
    
    # Check if there was an error
    if result["error"]:
        print(f"❌ Error with {rag_type}: {result['error']}")
        return False
    
    # If successful, print the result
    if result["success"]:
        print(f"{rag_type} Response: {result['response']['result']}")
        return True
    
    return False

# Run tests
print("Starting tests...")
test_with_timeout("Standard RAG", 120)  # 2 minute timeout
print("\n" + "="*50 + "\n")
test_with_timeout("Graph RAG", 180)     # 3 minute timeout