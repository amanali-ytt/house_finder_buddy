"""
File processing service for PDF and Excel uploads.
Extracts text content for normalization by the AI agent.
"""

import io
from typing import Optional, Tuple, List
from pathlib import Path

import pandas as pd
import pdfplumber


class FileProcessingError(Exception):
    """Raised when file processing fails."""
    pass


class FileProcessor:
    """Handles extraction of property data from uploaded files."""
    
    SUPPORTED_EXTENSIONS = {
        ".pdf": "pdf",
        ".xlsx": "excel",
        ".xls": "excel",
        ".csv": "csv",
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    def __init__(self):
        pass
    
    def validate_file(self, file_bytes: bytes, filename: str) -> Tuple[bool, str]:
        """Validate file type and size."""
        # Check size
        if len(file_bytes) > self.MAX_FILE_SIZE:
            return False, f"File too large. Maximum size: {self.MAX_FILE_SIZE // (1024*1024)}MB"
        
        # Check extension
        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            return False, f"Unsupported file type: {ext}. Supported: {', '.join(self.SUPPORTED_EXTENSIONS.keys())}"
        
        return True, "OK"
    
    def extract_from_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF file."""
        try:
            text_parts = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages[:20]:  # Limit to first 20 pages
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                    
                    # Also extract tables
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row:
                                text_parts.append(" | ".join(str(cell) for cell in row if cell))
            
            return "\n\n".join(text_parts)
        except Exception as e:
            raise FileProcessingError(f"Failed to extract PDF content: {str(e)}")
    
    def extract_from_excel(self, file_bytes: bytes, filename: str) -> str:
        """Extract data from Excel/CSV file and convert to text."""
        try:
            ext = Path(filename).suffix.lower()
            
            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(file_bytes))
            else:
                df = pd.read_excel(io.BytesIO(file_bytes))
            
            # Handle multiple properties (one per row)
            text_parts = []
            
            # If dataset has many columns, likely one property per row
            if len(df.columns) > 3:
                for idx, row in df.iterrows():
                    if idx >= 100:  # Limit to 100 properties
                        break
                    property_text = self._row_to_text(row)
                    text_parts.append(f"Property {idx + 1}:\n{property_text}")
            else:
                # Simple key-value format
                text_parts.append(df.to_string())
            
            return "\n\n---\n\n".join(text_parts)
        except Exception as e:
            raise FileProcessingError(f"Failed to extract Excel content: {str(e)}")
    
    def _row_to_text(self, row: pd.Series) -> str:
        """Convert a DataFrame row to readable text."""
        parts = []
        for col, value in row.items():
            if pd.notna(value):
                parts.append(f"{col}: {value}")
        return "\n".join(parts)
    
    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        """Extract text from any supported file type."""
        is_valid, message = self.validate_file(file_bytes, filename)
        if not is_valid:
            raise FileProcessingError(message)
        
        ext = Path(filename).suffix.lower()
        file_type = self.SUPPORTED_EXTENSIONS[ext]
        
        if file_type == "pdf":
            return self.extract_from_pdf(file_bytes)
        elif file_type in ("excel", "csv"):
            return self.extract_from_excel(file_bytes, filename)
        else:
            raise FileProcessingError(f"Unsupported file type: {file_type}")
    
    def parse_multiple_properties(self, text: str) -> List[str]:
        """
        Split extracted text into multiple property descriptions.
        Returns list of text chunks, each representing one property.
        """
        # Common separators
        separators = ["---", "Property ", "===", "###"]
        
        # Try to split by common patterns
        for sep in separators:
            if sep in text:
                parts = text.split(sep)
                # Filter out empty parts
                parts = [p.strip() for p in parts if p.strip() and len(p.strip()) > 50]
                if len(parts) > 1:
                    return parts
        
        # If no separators found, return as single property
        return [text]


# Singleton instance
file_processor = FileProcessor()
