from typing import List
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter

class TextProcessor:
    def __init__(self, chunk_size=1000, chunk_overlap=150):
        """
        Initializes the TextProcessor with chunking parameters.

        Args:
            chunk_size (int): The target size for each text chunk (in characters).
            chunk_overlap (int): The number of characters to overlap between chunks.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            add_start_index=False, # We'll generate IDs based on chunk index
        )

    def clean_text(self, text: str) -> str:
        """Cleans the input text by removing unwanted characters and normalizing whitespace."""
        # Remove multiple newlines, keeping single ones
        text = re.sub(r'\n\s*\n', '\n', text)
        # Replace multiple spaces with a single space, but not newlines
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()
        return text

    def process_text(self, text: str, verbose: bool = False) -> List[str]:
        """Processes the input text and returns a list of text chunks."""
        if verbose:
            print(f"Starting text processing for {len(text)} characters...")

        cleaned_text = self.clean_text(text)

        if verbose:
            print(f"Text cleaned. Splitting into chunks (size={self.chunk_size}, overlap={self.chunk_overlap})...")

        chunks = self.splitter.split_text(cleaned_text)

        if verbose:
            print(f"Generated {len(chunks)} chunks.")

        # Further clean each chunk (optional, e.g., remove leading/trailing spaces again)
        cleaned_chunks = [chunk.strip() for chunk in chunks if chunk.strip()]

        if verbose:
            print(f"Returning {len(cleaned_chunks)} non-empty chunks.")

        return cleaned_chunks