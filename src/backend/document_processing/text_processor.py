from typing import List
import re
import time
from tqdm import tqdm

class TextProcessor:
    def __init__(self):
        pass

    def clean_text(self, text: str) -> str:
        """Cleans the input text by removing unwanted characters and normalizing whitespace."""
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
        text = text.strip()  # Remove leading and trailing whitespace
        return text

    def extract_sentences(self, text: str, verbose: bool = False) -> List[str]:
        """Extracts sentences from the cleaned text."""
        if verbose:
            print(f"Starting sentence extraction for text of length: {len(text)} characters")
            
        start_time = time.time()
        
        # More robust sentence splitting pattern
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        if verbose:
            print(f"Split into {len(sentences)} raw sentences in {time.time() - start_time:.2f} seconds")
        
        cleaned_sentences = []
        
        # Use tqdm for progress bar
        sentence_iter = tqdm(sentences, desc="Processing sentences", disable=not verbose) if verbose else sentences
        
        for sentence in sentence_iter:
            if sentence.strip():
                cleaned_sentences.append(self.clean_text(sentence))
                
        if verbose:
            print(f"Finished extracting {len(cleaned_sentences)} sentences in {time.time() - start_time:.2f} seconds")
            
        return cleaned_sentences

    def process_text(self, text: str, verbose: bool = False) -> List[str]:
        """Processes the input text and returns a list of cleaned sentences."""
        if verbose:
            print(f"Starting text processing for {len(text)} characters...")
            
        start_time = time.time()
        cleaned_text = self.clean_text(text)
        
        if verbose:
            print(f"Text cleaned in {time.time() - start_time:.2f} seconds")
        
        sentences = self.extract_sentences(cleaned_text, verbose)
        
        if verbose:
            print(f"Text processing completed in {time.time() - start_time:.2f} seconds total")
            
        return sentences