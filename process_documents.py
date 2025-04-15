from src.backend.document_processing.pdf_loader import PDFLoader
from src.backend.document_processing.text_processor import TextProcessor
from src.backend.database.neo4j_client import Neo4jClient
from dotenv import load_dotenv
import os
import time
import argparse
from tqdm import tqdm

# Load environment variables
load_dotenv()

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Process PDF documents and build a knowledge graph')
    parser.add_argument('--max-pages', type=int, default=None, help='Maximum pages to process per PDF (default: all)')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for Neo4j operations (default: 50)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    # Initialize components
    pdf_loader = PDFLoader('data/pdf_files', max_pages=args.max_pages)
    text_processor = TextProcessor()
    neo4j_client = Neo4jClient(
        os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        os.getenv('NEO4J_USERNAME', 'neo4j'),
        os.getenv('NEO4J_PASSWORD', 'vaggpinel')
    )
    
    print('Loading PDFs...')
    start_time = time.time()
    pdf_texts = pdf_loader.load_pdfs()
    
    if not pdf_texts:
        print('No PDF files found in data/pdf_files directory')
        return
    
    print(f'Processing {len(pdf_texts)} PDF files')
    
    for filename, text in pdf_texts.items():
        file_start = time.time()
        print(f'\nProcessing {filename}... (Length: {len(text)} characters)')
        
        # Create document node
        doc_id = filename.replace('.pdf', '')
        neo4j_client.create_node('Document', {'id': doc_id, 'title': filename, 'content': text[:500]})
        
        # Process text into sentences with progress reporting
        print("Extracting sentences...")
        sentences = text_processor.process_text(text, verbose=args.verbose)
        print(f'  Found {len(sentences)} sentences')
        
        # Create sentence nodes and relationships in batches
        batch_size = args.batch_size
        num_batches = (len(sentences) + batch_size - 1) // batch_size
        
        print(f'  Creating graph nodes and relationships in {num_batches} batches...')
        sentences_added = 0
        
        # Use tqdm for progress bar over batches
        for batch_idx in tqdm(range(0, len(sentences), batch_size), desc="  Processing batches"):
            batch_end = min(batch_idx + batch_size, len(sentences))
            for i in range(batch_idx, batch_end):
                sentence = sentences[i]
                if len(sentence) > 10:  # Skip very short sentences
                    sent_id = f'{doc_id}_s{i}'
                    neo4j_client.create_node('Sentence', {'id': sent_id, 'content': sentence})
                    neo4j_client.run_query(
                        'MATCH (d:Document), (s:Sentence) WHERE d.id = $doc_id AND s.id = $sent_id CREATE (d)-[:CONTAINS]->(s)',
                        {'doc_id': doc_id, 'sent_id': sent_id}
                    )
                    sentences_added += 1
        
        print(f'  Added {sentences_added} sentences from {filename} to the graph')
        print(f'  Completed in {time.time() - file_start:.2f} seconds')
    
    neo4j_client.close()
    total_time = time.time() - start_time
    print(f'\nAll documents processed and graph built in {total_time:.2f} seconds total!')

if __name__ == '__main__':
    main()