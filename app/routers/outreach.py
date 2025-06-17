# app/routers/outreach.py
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.dependencies import get_firestore, get_user_email
from app.schemas.outreach import OutreachCampaignCreate, OutreachCampaignResponse, SendCampaignRequest
from app.services.outreach_service import OutreachService
from app.services.firestore_service import FirestoreService

router = APIRouter()

from app.services.logger import AppLogger

logger = AppLogger.get_logger(__name__)

@router.post("/campaigns", response_model=OutreachCampaignResponse)
async def create_campaign(
    campaign: OutreachCampaignCreate,
    user_email: str = Depends(get_user_email),
    fs: FirestoreService = Depends(get_firestore)
):
    """Create new outreach campaign"""
    try:
        logger.info(f"Campaign creation request from user: {user_email}")
        logger.debug(f"Request data: {campaign.dict()}")
        
        outreach_service = OutreachService(fs, user_email)
        logger.debug("OutreachService initialized")
        
        result = outreach_service.create_campaign(campaign.dict())
        logger.debug(f"Service returned: {result}")
        
        campaign_data = result["campaign"]
        logger.debug(f"Extracted campaign data: {campaign_data}")
        
        # Validate response data before returning
        for key, value in campaign_data.items():
            logger.debug(f"Response field '{key}': {value} (type: {type(value)})")
        
        logger.info("About to return campaign data to client")
        return campaign_data
        
    except Exception as e:
        logger.error(f"Campaign creation failed in router: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Campaign creation failed: {str(e)}")


@router.get("/campaigns", response_model=List[OutreachCampaignResponse])
async def get_campaigns(
    user_email: str = Depends(get_user_email),
    fs: FirestoreService = Depends(get_firestore)
):
    """Get all campaigns for user"""
    try:
        outreach_service = OutreachService(fs, user_email)
        return outreach_service.get_campaigns()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch campaigns: {str(e)}")

@router.post("/campaigns/{campaign_id}/send")
async def send_campaign(
    campaign_id: str,
    send_request: SendCampaignRequest,  # Accept message template in request body
    user_email: str = Depends(get_user_email),
    fs: FirestoreService = Depends(get_firestore)
):
    """Send emails for a campaign with specified message template"""
    try:
        outreach_service = OutreachService(fs, user_email)
        result = outreach_service.send_campaign_emails(campaign_id, send_request.message_template)
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result["message"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send campaign: {str(e)}")

@router.get("/templates")
async def get_message_templates():
    """Get available message templates"""
    return {
        "templates": [
            {"id": "initial_connection", "name": "Initial Connection Request"},
            {"id": "linkedin_inmail", "name": "LinkedIn InMail"},
            {"id": "follow_up", "name": "Follow-up After No Response"}
        ]
    }
    
@router.post("/test-email")
async def test_email_config(
    user_email: str = Depends(get_user_email),
    fs: FirestoreService = Depends(get_firestore)
):
    """Test email configuration"""
    try:
        from app.services.email_service import EmailService
        email_service = EmailService()
        
        # Test email sending
        success = email_service.send_email(
            to_email=user_email,
            subject="Test Email from HireAI",
            message="This is a test email to verify SMTP configuration.",
            from_name="HireAI Test"
        )
        
        return {
            "success": success,
            "message": "Test email sent successfully" if success else "Failed to send test email",
            "smtp_config": {
                "server": email_service.smtp_server,
                "port": email_service.smtp_port,
                "username_configured": bool(email_service.smtp_username),
                "password_configured": bool(email_service.smtp_password)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Email test failed: {str(e)}"
        }
