# app/services/outreach_service.py
from typing import List, Dict
from datetime import datetime, timezone
from app.services.firestore_service import FirestoreService
from app.services.email_service import EmailService
from app.services.candidate_service import CandidateService
from app.services.logger import AppLogger

logger = AppLogger.get_logger(__name__)

class OutreachService:
    def __init__(self, fs: FirestoreService, user_email: str):
        logger.info(f"Initializing OutreachService for user: {user_email}")
        self.fs = fs
        self.user_email = user_email
        self.campaigns = self.fs.db.collection("users").document(user_email).collection("campaigns")
        self.email_service = EmailService()

    def create_campaign(self, campaign_data: dict) -> dict:
        """Create new outreach campaign with detailed logging"""
        try:
            logger.info(f"Starting campaign creation for user {self.user_email}")
            logger.debug(f"Incoming campaign data: {campaign_data}")
            logger.debug(f"Campaign data type: {type(campaign_data)}")
            
            # Check each field individually
            for key, value in campaign_data.items():
                logger.debug(f"Field '{key}': {value} (type: {type(value)})")
            
            doc_ref = self.campaigns.document()
            logger.debug(f"Created document reference with ID: {doc_ref.id}")
            
            # Create datetime object
            created_at = datetime.now(timezone.utc)
            logger.debug(f"Created timestamp: {created_at} (type: {type(created_at)})")
            
            # Prepare update data
            update_data = {
                "id": doc_ref.id,
                "created_at": created_at,
                "created_by": self.user_email,
                "status": "draft",
                "emails_sent": 0
            }
            logger.debug(f"Update data: {update_data}")
            
            # Update campaign data
            campaign_data.update(update_data)
            logger.debug(f"Campaign data after update: {campaign_data}")
            
            # Validate target_candidate_ids
            if campaign_data.get("target_candidate_ids") is None:
                campaign_data["target_candidate_ids"] = []
                logger.debug("target_candidate_ids was None, set to empty list")
            
            # Final validation of all fields
            required_fields = ["id", "campaign_name", "message_template", "job_title", "target_candidate_ids", "created_at", "status", "emails_sent", "created_by"]
            for field in required_fields:
                value = campaign_data.get(field)
                logger.debug(f"Final check - {field}: {value} (type: {type(value)})")
                if value is None:
                    logger.warning(f"Field {field} is None!")
            
            # Save to Firestore
            logger.debug("Attempting to save to Firestore...")
            doc_ref.set(campaign_data)
            logger.info(f"Campaign saved to Firestore with ID {doc_ref.id}")
            
            # Prepare return data
            return_data = {
                "message": "Campaign created successfully",
                "campaign": campaign_data
            }
            logger.debug(f"Return data: {return_data}")
            
            return return_data
            
        except Exception as e:
            logger.error(f"Failed to create campaign: {e}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def get_campaigns(self) -> List[Dict]:
        """Get all campaigns for user"""
        try:
            docs = self.campaigns.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Failed to fetch campaigns: {e}")
            return []
    
    def send_campaign_emails(self, campaign_id: str, message_template: str) -> Dict:
        """Send emails for a campaign with specified message template"""
        try:
            # Get campaign data
            campaign_doc = self.campaigns.document(campaign_id).get()
            if not campaign_doc.exists:
                return {"success": False, "message": "Campaign not found"}
            
            campaign = campaign_doc.to_dict()
            
            # Get user data for recruiter info
            user_doc = self.fs.db.collection("users").document(self.user_email).get()
            user_data = user_doc.to_dict()
            recruiter_name = user_data.get("name", "Recruiter")
            company_name = campaign.get("company_name", "Our Company")  # Use from campaign
            
            # Get candidate service
            candidate_service = CandidateService(self.fs, self.user_email)
            
            # Get message template (passed as parameter now)
            template = self.email_service.get_message_template(message_template)
            
            emails_sent = 0
            failed_emails = []
            
            # Send emails to each target candidate
            for candidate_id in campaign["target_candidate_ids"]:
                try:
                    candidate = candidate_service.get_candidate(candidate_id)
                    if not candidate or not candidate.get("email"):
                        failed_emails.append(f"Candidate {candidate_id}: No email found")
                        continue
                    
                    # Format message
                    formatted_message = self.email_service.format_message(
                        template, candidate, recruiter_name, company_name, campaign["job_title"]
                    )
                    
                    # Create subject
                    subject = f"Exciting {campaign['job_title']} Opportunity at {company_name}"
                    
                    # Send email
                    if self.email_service.send_email(
                        candidate["email"], subject, formatted_message, recruiter_name
                    ):
                        emails_sent += 1
                    else:
                        failed_emails.append(f"Failed to send to {candidate['email']}")
                        
                except Exception as e:
                    failed_emails.append(f"Error with candidate {candidate_id}: {str(e)}")
            
            # Update campaign status with template used
            self.campaigns.document(campaign_id).update({
                "status": "sent",
                "emails_sent": emails_sent,
                "sent_at": datetime.now(timezone.utc),
                "last_template_used": message_template  # Track which template was used
            })
            
            return {
                "success": True,
                "emails_sent": emails_sent,
                "failed_emails": failed_emails,
                "message": f"Campaign sent using {message_template} template! {emails_sent} emails delivered.",
                "template_used": message_template
            }
            
        except Exception as e:
            logger.error(f"Failed to send campaign emails: {e}")
            return {"success": False, "message": str(e)}

