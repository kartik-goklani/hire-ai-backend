# app/services/email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict
import os
from app.services.logger import AppLogger

logger = AppLogger.get_logger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        
    def get_message_template(self, template_type: str) -> str:
        """Get predefined message templates"""
        templates = {
            "initial_connection": """Hi {{candidate_name}},\n\n I hope this message finds you well.\n I'm {{recruiter_name}} from {{company_name}}, and I came across your profile which shows your impressive experience with {{skill_highlights}}. We're currently looking for a {{job_title}} role that aligns well with your background. Would you be interested in learning more?\n\n Best regards,\n {{recruiter_name}}""",
            
            "linkedin_inmail": """Hello {{candidate_name}},\n\n I'm impressed by your background in {{skill_highlights}}. We have an exciting {{job_title}} role at {{company_name}} that could be a great next step for you. Are you open to new opportunities at the moment?\n\n Regards,\n {{recruiter_name}}""",
            
            "follow_up": """Hi {{candidate_name}},\n\n I reached out last week about a {{job_title}} role at {{company_name}} that aligns with your expertise in {{skill_highlights}}. I'm following up to see if you'd be interested in a quick chat about this opportunity. We offer good benefits and a competitive compensation package. Looking forward to hearing from you!\n\n Best,\n {{recruiter_name}}"""
        }
        return templates.get(template_type, "")
    
    def format_message(self, template: str, candidate: Dict, recruiter_name: str, company_name: str, job_title: str) -> str:
        """Format message template with candidate and recruiter data"""
        try:
            # Extract skill highlights (first 3 skills)
            skills = candidate.get("skills", [])
            if isinstance(skills, list) and skills:
                skill_highlights = ", ".join(skills[:3])
            else:
                skill_highlights = "your technical expertise"
            
            # Replace template variables
            formatted_message = template.replace("{{candidate_name}}", candidate.get("name", "there"))
            formatted_message = formatted_message.replace("{{recruiter_name}}", recruiter_name)
            formatted_message = formatted_message.replace("{{company_name}}", company_name)
            formatted_message = formatted_message.replace("{{skill_highlights}}", skill_highlights)
            formatted_message = formatted_message.replace("{{job_title}}", job_title)
            
            return formatted_message
            
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
            return template
    
    def send_email(self, to_email: str, subject: str, message: str, from_name: str) -> bool:
        """Send email using SMTP"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{from_name} <{self.smtp_username}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body to email
            msg.attach(MIMEText(message, 'plain'))
            
            # Create SMTP session
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()  # Enable security
            server.login(self.smtp_username, self.smtp_password)
            
            # Send email
            text = msg.as_string()
            server.sendmail(self.smtp_username, to_email, text)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
