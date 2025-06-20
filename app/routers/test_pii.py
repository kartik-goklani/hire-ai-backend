# app/routers/test_pii.py
from fastapi import APIRouter, HTTPException
from app.services.pii_extractor_service import PIIExtractorService
from app.services.logger import AppLogger

router = APIRouter()
logger = AppLogger.get_logger(__name__)

@router.post("/test-pii-extraction")
async def test_pii_extraction(text: str):
    """Test endpoint to verify PII extraction is working"""
    try:
        logger.info("=== PII Extraction Test Started ===")
        
        pii_extractor = PIIExtractorService()
        
        # Extract PII
        pii_data = pii_extractor.extract_pii_from_text(text)
        
        # Sanitize text
        sanitized_text = pii_extractor.sanitize_text_for_llm(text, pii_data)
        
        logger.info("=== PII Extraction Test Completed ===")
        
        return {
            "status": "success",
            "original_text": text,
            "extracted_pii": pii_data,
            "sanitized_text": sanitized_text,
            "pii_found": len([v for v in pii_data.values() if v is not None]),
            "message": "PII extraction test completed successfully"
        }
        
    except Exception as e:
        logger.error(f"PII extraction test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")
