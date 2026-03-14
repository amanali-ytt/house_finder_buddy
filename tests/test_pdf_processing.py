"""
Pytest coverage for PDF extraction and optional LLM normalization.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.file_processor import FileProcessingError, file_processor


def extract_pdf_text() -> str:
    """Extract text from the bundled sample PDF."""
    pdf_path = "Chennai_Properties.pdf"

    if not os.path.exists(pdf_path):
        pytest.skip(f"PDF not found: {pdf_path}")

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    is_valid, message = file_processor.validate_file(file_bytes, pdf_path)
    assert is_valid, message

    try:
        return file_processor.extract_from_pdf(file_bytes)
    except FileProcessingError as exc:
        pytest.fail(f"Extraction failed: {exc}")


@pytest.fixture
def extracted_text() -> str:
    return extract_pdf_text()


def test_pdf_extraction(extracted_text: str):
    assert extracted_text
    assert len(extracted_text) > 100
    assert "Chennai" in extracted_text


@pytest.mark.asyncio
async def test_normalization(extracted_text: str):
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("No LLM API key configured for normalization test")

    from app.agents.normalizer_agent import normalizer_agent

    result = await normalizer_agent.normalize(extracted_text[:3000], source="pdf")

    assert result.city
    assert 0.0 <= result.confidence_score <= 1.0


def main():
    text = extract_pdf_text()
    print(f"Extracted {len(text)} characters from the sample PDF.")
    if os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY"):
        asyncio.run(test_normalization(text))


if __name__ == "__main__":
    main()
