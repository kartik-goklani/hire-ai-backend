# app/routers/test_enhanced_pii.py
from fastapi import APIRouter, HTTPException
from app.services.enhanced_pii_extractor_service import EnhancedPIIExtractorService
from app.services.logger import AppLogger

router = APIRouter()
logger = AppLogger.get_logger(__name__)

@router.post("/test-enhanced-pii")
async def test_enhanced_pii_extraction(text: str):
    """Test enhanced PII extraction"""
    try:
        logger.info("=== Enhanced PII Extraction Test Started ===")
        
        pii_extractor = EnhancedPIIExtractorService()
        
        # Extract PII with confidence
        pii_data = pii_extractor.extract_pii_with_confidence(text)
        voting_result = pii_extractor.extract_with_voting(text)
        
        # Sanitize text
        sanitized_text = pii_extractor.sanitize_text_for_llm(text, pii_data)
        
        
        logger.info("=== Enhanced PII Extraction Test Completed ===")
        
        return {
            "status": "success",
            "original_text": text,
            "extracted_pii": pii_data,
            "voted_pii": voting_result,
            "sanitized_text": sanitized_text,
            "pii_found": len([v for v in pii_data.values() if v is not None]),
            "accuracy_improvement": "Enhanced multi-method extraction with confidence scoring",
            "message": "Enhanced PII extraction test completed successfully"
        }
        
    except Exception as e:
        logger.error(f"Enhanced PII extraction test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")
