from typing import List
import re

class TextProcessor:
    def __init__(self):
        pass

    def clean_text(self, text: str) -> str:
        """Cleans the input text by removing unwanted characters and normalizing whitespace."""
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
        text = text.strip()  # Remove leading and trailing whitespace
        return text

    def extract_sentences(self, text: str) -> List[str]:
        """Extracts sentences from the cleaned text."""
        sentences = re.split(r'(?<=[.!?]) +', text)  # Split text into sentences
        return [self.clean_text(sentence) for sentence in sentences if sentence]

    def process_text(self, text: str) -> List[str]:
        """Processes the input text and returns a list of cleaned sentences."""
        cleaned_text = self.clean_text(text)
        return self.extract_sentences(cleaned_text)