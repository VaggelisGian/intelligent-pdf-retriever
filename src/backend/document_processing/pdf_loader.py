from PyPDF2 import PdfReader
import os
import time
import uuid
from tqdm import tqdm
import json
import redis
import asyncio

# Import the progress tracking module
from src.backend.api.progress import create_job, update_job_progress, complete_job, complete_job_sync

class PDFLoader:
    def __init__(self, pdf_directory, max_pages=None):
        self.pdf_directory = pdf_directory
        self.max_pages = max_pages
        
    async def extract_text_from_pdf(self, file_path, job_id=None): # <-- Make method async
        text = ""
        start_time = time.time()
        try:
            with open(file_path, 'rb') as file:
                reader = PdfReader(file)
                total_pages = len(reader.pages)
                pages_to_process = min(total_pages, self.max_pages) if self.max_pages else total_pages

                # Create a progress tracking job
                if job_id:
                    file_name = os.path.basename(file_path)
                    create_job(job_id, file_name, pages_to_process)
                    print(f"Progress tracking initialized for job: {job_id} with {pages_to_process} pages")

                print(f"Starting PDF extraction of {pages_to_process} pages...")
                # Use non-blocking tqdm if available, or remove if causing issues
                # For simplicity, let's remove tqdm for now in the async context
                # for i in tqdm(range(pages_to_process), desc="Extracting pages"):
                for i in range(pages_to_process):
                    # Extract text from page
                    page = reader.pages[i]
                    page_text = page.extract_text()
                    if page_text: # Append only if text was extracted
                        text += page_text + "\n"

                    # Update progress after each page
                    if job_id:
                        current_page = i + 1
                        # Properly await the async function
                        await update_job_progress(job_id, current_page)

                        # Log progress less frequently
                        if current_page % max(1, pages_to_process // 20) == 0 or current_page == pages_to_process:
                            percent = int((current_page / pages_to_process) * 100)
                            print(f"  PDF Extract Progress: {current_page}/{pages_to_process} ({percent}%)")

                    # Yield control to the event loop
                    await asyncio.sleep(0) # <-- Add this line

                print(f"PDF extraction completed in {time.time() - start_time:.2f} seconds")

        except Exception as e:
            print(f"ERROR extracting text from PDF: {type(e).__name__}: {str(e)}")
            if job_id:
                # Use the sync version in exception handlers
                complete_job_sync(job_id, f"Error during PDF extraction: {str(e)}", final_status="failed") 

        return text.strip()