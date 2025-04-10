from PyPDF2 import PdfReader
import os

class PDFLoader:
    def __init__(self, pdf_directory):
        self.pdf_directory = pdf_directory

    def load_pdfs(self):
        pdf_texts = {}
        for filename in os.listdir(self.pdf_directory):
            if filename.endswith('.pdf'):
                file_path = os.path.join(self.pdf_directory, filename)
                pdf_texts[filename] = self.extract_text_from_pdf(file_path)
        return pdf_texts

    def extract_text_from_pdf(self, file_path):
        text = ""
        with open(file_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()