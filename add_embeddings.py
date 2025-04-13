from src.backend.database.neo4j_client import Neo4jClient
from dotenv import load_dotenv
import os
import time
from tqdm import tqdm
import numpy as np
import requests
import json
from datetime import datetime

# Load environment variables
load_dotenv()

def chunks(lst, n):
    """Split a list into chunks of size n"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def estimate_tokens(text):
    """Estimate token count in a text (rough approximation)"""
    # Average of ~4 characters per token in English
    return len(text) // 4 + 1

def create_token_aware_batches(sentences, max_tokens=7500):
    """Create batches that respect token limits"""
    batches = []
    current_batch = []
    current_token_count = 0
    
    for sentence_id, sentence_text in sentences:
        # Estimate tokens in this sentence
        tokens = estimate_tokens(sentence_text)
        
        # If adding this sentence would exceed the token limit, start a new batch
        if current_token_count + tokens > max_tokens and current_batch:
            batches.append(current_batch)
            current_batch = [(sentence_id, sentence_text)]
            current_token_count = tokens
        else:
            current_batch.append((sentence_id, sentence_text))
            current_token_count += tokens
    
    # Add the last batch if it's not empty
    if current_batch:
        batches.append(current_batch)
    
    return batches

def main():
    # Initialize with token
    api_key = os.getenv('GITHUB_TOKEN')
    if not api_key:
        print("Error: GITHUB_TOKEN not found in .env file")
        return
    
    # Initialize Neo4j client
    neo4j_client = Neo4jClient(
        os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        os.getenv('NEO4J_USERNAME', 'neo4j'),
        os.getenv('NEO4J_PASSWORD', 'vaggpinel')
    )
    
    # Get sentences without embeddings
    print("Fetching sentences without embeddings...")
    results = neo4j_client.run_query("""
        MATCH (s:Sentence) 
        WHERE s.embedding IS NULL
        RETURN s.id AS id, s.content AS content
        LIMIT 500
    """)
    
    sentences = [(record["id"], record["content"]) for record in results]
    total_sentences = len(sentences)
    print(f"Found {total_sentences} sentences without embeddings")
    
    if total_sentences == 0:
        print("No sentences need embeddings. Exiting.")
        neo4j_client.close()
        return
    
    # Create token-aware batches
    batches = create_token_aware_batches(sentences, max_tokens=7500)  # Using 7500 as buffer
    print(f"Created {len(batches)} batches respecting the 8000 token input limit")
    
    successful = 0
    
    # Keep track of request times to manage rate limits
    request_times = []
    
    # Process token-aware batches
    for i, batch in enumerate(batches):
        batch_ids = [s[0] for s in batch]
        batch_texts = [s[1] for s in batch]
        
        # Check rate limits
        current_time = time.time()
        request_times = [t for t in request_times if current_time - t < 60]
        
        # If we've made 10+ requests in the last minute, wait until we're under the limit
        while len(request_times) >= 10:
            sleep_time = max(0, 61 - (current_time - request_times[0]))
            if sleep_time > 0:
                print(f"Rate limit approaching, waiting {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
            
            # Update our tracking after waiting
            current_time = time.time()
            request_times = [t for t in request_times if current_time - t < 60]
        
        try:
            # Add a small delay between batches
            if i > 0:
                time.sleep(5)
                
            # Record this request time
            request_times.append(time.time())
            
            print(f"Processing batch {i+1}/{len(batches)} with {len(batch_texts)} sentences...")
            
            # Make the API call with batch input
            response = requests.post(
                "https://models.inference.ai.azure.com/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "text-embedding-3-small",
                    "input": batch_texts
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                embeddings = [item["embedding"] for item in result["data"]]
                
                # Update Neo4j with these embeddings
                for j, embedding in enumerate(embeddings):
                    neo4j_client.run_query(
                        "MATCH (s:Sentence {id: $id}) SET s.embedding = $embedding",
                        {"id": batch_ids[j], "embedding": embedding}
                    )
                
                successful += len(embeddings)
                print(f"Progress: {successful}/{total_sentences} sentences processed")
                
            elif response.status_code == 429:
                # Rate limit hit - parse wait time but cap it
                error_data = response.json()
                wait_time = 60  # Default wait time
                
                # Try to extract the wait time but cap it at 5 minutes
                error_msg = error_data.get('error', {}).get('message', '')
                print(f"Rate limit error: {error_msg}")
                
                import re
                wait_match = re.search(r'Please wait (\d+) seconds', error_msg)
                if wait_match:
                    parsed_wait = int(wait_match.group(1))
                    wait_time = min(parsed_wait, 300)  # Cap at 5 minutes (300 seconds)
                
                print(f"Rate limit exceeded, waiting {wait_time} seconds...")
                time.sleep(wait_time)
                
                # Try this batch again
                i -= 1
                
            else:
                print(f"Error: {response.status_code} - {response.text}")
                time.sleep(30)  # Wait before retrying
                
        except Exception as e:
            print(f"Error processing batch: {e}")
            time.sleep(30)  # Wait before continuing
    
    print(f"Finished adding embeddings to {successful}/{total_sentences} sentences")
    neo4j_client.close()

if __name__ == "__main__":
    main()