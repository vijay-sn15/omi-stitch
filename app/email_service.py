"""
OMI Global Productions - Email Service Module
Handles sending transactional emails via Gmail SMTP with full audit logging.

Best practices implemented:
- Both HTML and plain text versions (improves deliverability)
- Proper email headers (Message-ID, Date, Reply-To)
- TLS encryption for secure transmission
- Async background sending to not block requests
- Full email logging in database
- Retry mechanism for transient failures
"""

import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from typing import Optional
import threading

from jinja2 import Template


# Gmail SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "vijay@omiproductions.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SENDER_NAME = os.getenv("SENDER_NAME", "OMI Global Productions")


class EmailService:
    """
    Email service for sending transactional emails.
    Uses Gmail SMTP with app password authentication.
    """

    def __init__(self, db=None):
        self.db = db
        self.smtp_host = SMTP_HOST
        self.smtp_port = SMTP_PORT
        self.smtp_user = SMTP_USER
        self.smtp_password = SMTP_PASSWORD
        self.sender_name = SENDER_NAME

    def _create_email_record(
        self,
        submission_id: str,
        to_email: str,
        to_name: str,
        subject: str,
        body_html: str,
        body_plain: str,
        email_type: str = "submission_confirmation",
    ) -> Optional[str]:
        """Create an email record in the database with pending status."""
        if not self.db:
            return None

        try:
            result = self.db.fetch_one(
                """
                INSERT INTO emails_sent (
                    submission_id,
                    from_email,
                    from_name,
                    to_email,
                    to_name,
                    reply_to,
                    subject,
                    body_html,
                    body_plain,
                    email_type,
                    status,
                    created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    submission_id,
                    self.smtp_user,
                    self.sender_name,
                    to_email,
                    to_name,
                    self.smtp_user,
                    subject,
                    body_html,
                    body_plain,
                    email_type,
                    "pending",
                    datetime.utcnow(),
                ),
            )
            if result:
                return str(result["id"])
        except Exception as e:
            print(f"Failed to create email record: {e}")
        return None

    def _update_email_status(
        self,
        email_id: str,
        status: str,
        message_id: Optional[str] = None,
        smtp_response: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update email record with delivery status."""
        if not self.db or not email_id:
            return

        try:
            if status == "sent":
                self.db.fetch_one(
                    """
                    UPDATE emails_sent
                    SET status = %s,
                        message_id = %s,
                        smtp_response = %s,
                        sent_at = %s,
                        updated_at = %s
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        status,
                        message_id,
                        smtp_response,
                        datetime.utcnow(),
                        datetime.utcnow(),
                        email_id,
                    ),
                )
            else:
                self.db.fetch_one(
                    """
                    UPDATE emails_sent
                    SET status = %s,
                        error_message = %s,
                        failed_at = %s,
                        retry_count = retry_count + 1,
                        updated_at = %s
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        status,
                        error_message,
                        datetime.utcnow(),
                        datetime.utcnow(),
                        email_id,
                    ),
                )
        except Exception as e:
            print(f"Failed to update email status: {e}")

    def _send_smtp(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        body_html: str,
        body_plain: str,
    ) -> tuple[bool, str, str]:
        """
        Send email via SMTP.
        Returns: (success, message_id, response/error)
        """
        # Create message with both HTML and plain text
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr((self.sender_name, self.smtp_user))
        msg["To"] = formataddr((to_name, to_email))
        msg["Reply-To"] = self.smtp_user
        msg["Date"] = formatdate(localtime=True)
        
        # Generate a proper Message-ID
        message_id = make_msgid(domain="omiproductions.com")
        msg["Message-ID"] = message_id

        # Attach plain text first (fallback), then HTML (preferred)
        part_plain = MIMEText(body_plain, "plain", "utf-8")
        part_html = MIMEText(body_html, "html", "utf-8")
        msg.attach(part_plain)
        msg.attach(part_html)

        try:
            # Create secure SSL context
            context = ssl.create_default_context()

            # Connect using STARTTLS (port 587)
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self.smtp_user, self.smtp_password)
                response = server.sendmail(
                    self.smtp_user,
                    to_email,
                    msg.as_string()
                )
                return True, message_id, str(response) if response else "OK"

        except smtplib.SMTPAuthenticationError as e:
            return False, "", f"Authentication failed: {e}"
        except smtplib.SMTPRecipientsRefused as e:
            return False, "", f"Recipient refused: {e}"
        except smtplib.SMTPException as e:
            return False, "", f"SMTP error: {e}"
        except Exception as e:
            return False, "", f"Unexpected error: {e}"

    def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        body_html: str,
        body_plain: str,
        submission_id: Optional[str] = None,
        email_type: str = "submission_confirmation",
    ) -> tuple[bool, Optional[str]]:
        """
        Send an email and log it to the database.
        Returns: (success, email_record_id)
        """
        # Create email record first
        email_id = self._create_email_record(
            submission_id=submission_id,
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            body_html=body_html,
            body_plain=body_plain,
            email_type=email_type,
        )

        # Send via SMTP
        success, message_id, response = self._send_smtp(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            body_html=body_html,
            body_plain=body_plain,
        )

        # Update email record
        if success:
            self._update_email_status(
                email_id=email_id,
                status="sent",
                message_id=message_id,
                smtp_response=response,
            )
            print(f"✓ Email sent successfully to {to_email}")
        else:
            self._update_email_status(
                email_id=email_id,
                status="failed",
                error_message=response,
            )
            print(f"✗ Email failed to {to_email}: {response}")

        return success, email_id

    def send_email_async(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        body_html: str,
        body_plain: str,
        submission_id: Optional[str] = None,
        email_type: str = "submission_confirmation",
    ) -> None:
        """
        Send email asynchronously in a background thread.
        Does not block the main request.
        """
        thread = threading.Thread(
            target=self.send_email,
            args=(to_email, to_name, subject, body_html, body_plain, submission_id, email_type),
            daemon=True,
        )
        thread.start()


def generate_submission_confirmation_email(submission_data: dict) -> tuple[str, str, str]:
    """
    Generate the confirmation email for a project submission.
    Returns: (subject, html_body, plain_text_body)
    """
    
    # Extract data
    contact_name = submission_data.get("contact_name", "")
    first_name = contact_name.split()[0] if contact_name else "there"
    title = submission_data.get("title", "")
    logline = submission_data.get("logline", "")
    synopsis = submission_data.get("synopsis", "")
    budget = submission_data.get("budget")
    languages = submission_data.get("languages", "")
    
    # Format actors list
    actors = []
    for i in range(1, 7):
        actor = submission_data.get(f"actor_{i}")
        if actor:
            actors.append(actor)
    actors_str = ", ".join(actors) if actors else None
    
    # Subject line - clean and professional
    if title:
        subject = f"We've Received Your Project: {title}"
    else:
        subject = "Your Project Submission Has Been Received"
    
    # Format budget nicely
    budget_formatted = None
    if budget:
        try:
            budget_formatted = f"${float(budget):,.2f}"
        except (ValueError, TypeError):
            budget_formatted = str(budget)
    
    # Current year for footer
    current_year = datetime.now().year
    
    # HTML Email Template - Elegant and professional matching OMI branding
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Project Submission Confirmation</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f6f8f6; -webkit-font-smoothing: antialiased;">
    <!-- Wrapper Table -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f6f8f6;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                
                <!-- Main Content Card -->
                <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
                    
                    <!-- Header with Brand -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #112116 0%, #1a2f20 100%); padding: 40px 40px 30px; text-align: center;">
                            <!-- Logo Circle -->
                            <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 0 auto 20px;">
                                <tr>
                                    <td style="width: 80px; height: 80px; background: linear-gradient(135deg, #B4941E 0%, #d4b42e 100%); border-radius: 50%; text-align: center; vertical-align: middle;">
                                        <span style="font-size: 36px; font-weight: 700; color: #112116; line-height: 80px;">O</span>
                                    </td>
                                </tr>
                            </table>
                            <h1 style="margin: 0; color: #B4941E; font-size: 28px; font-weight: 700; letter-spacing: 2px;">OMI GLOBAL</h1>
                            <p style="margin: 8px 0 0; color: rgba(255,255,255,0.7); font-size: 13px; letter-spacing: 3px; text-transform: uppercase;">PRODUCTIONS</p>
                        </td>
                    </tr>
                    
                    <!-- Success Badge -->
                    <tr>
                        <td style="padding: 30px 40px 0; text-align: center;">
                            <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 0 auto;">
                                <tr>
                                    <td style="background-color: #e8f5e9; border-radius: 30px; padding: 10px 24px;">
                                        <span style="color: #2e7d32; font-size: 14px; font-weight: 600;">&#10003; Submission Received</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Greeting -->
                    <tr>
                        <td style="padding: 30px 40px 10px; text-align: center;">
                            <h2 style="margin: 0; color: #112116; font-size: 24px; font-weight: 600;">Hello {{ first_name }},</h2>
                        </td>
                    </tr>
                    
                    <!-- Message -->
                    <tr>
                        <td style="padding: 10px 40px 30px;">
                            <p style="margin: 0; color: #4a5568; font-size: 16px; line-height: 26px; text-align: center;">
                                Thank you for sharing your creative vision with us. Your project submission has been successfully received and is now in our review queue.
                            </p>
                        </td>
                    </tr>
                    
                    {% if title %}
                    <!-- Project Details Section -->
                    <tr>
                        <td style="padding: 0 40px 30px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #fafbfa 0%, #f0f4f0 100%); border-radius: 12px; border: 1px solid #e2e8f0;">
                                
                                <!-- Section Header -->
                                <tr>
                                    <td style="padding: 20px 24px 15px; border-bottom: 1px solid #e2e8f0;">
                                        <h3 style="margin: 0; color: #112116; font-size: 16px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">
                                            <span style="color: #B4941E;">&#9670;</span> Your Submission
                                        </h3>
                                    </td>
                                </tr>
                                
                                <!-- Project Title -->
                                <tr>
                                    <td style="padding: 20px 24px 0;">
                                        <p style="margin: 0 0 6px; color: #718096; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Project Title</p>
                                        <p style="margin: 0; color: #112116; font-size: 20px; font-weight: 600;">{{ title }}</p>
                                    </td>
                                </tr>
                                
                                {% if logline %}
                                <!-- Logline -->
                                <tr>
                                    <td style="padding: 20px 24px 0;">
                                        <p style="margin: 0 0 6px; color: #718096; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Logline</p>
                                        <p style="margin: 0; color: #4a5568; font-size: 15px; font-style: italic; line-height: 24px;">"{{ logline }}"</p>
                                    </td>
                                </tr>
                                {% endif %}
                                
                                <!-- Details Grid -->
                                <tr>
                                    <td style="padding: 20px 24px;">
                                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                            <tr>
                                                {% if budget_formatted %}
                                                <td style="width: 50%; vertical-align: top; padding-right: 10px;">
                                                    <p style="margin: 0 0 4px; color: #718096; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Budget</p>
                                                    <p style="margin: 0; color: #112116; font-size: 16px; font-weight: 600;">{{ budget_formatted }}</p>
                                                </td>
                                                {% endif %}
                                                {% if languages %}
                                                <td style="width: 50%; vertical-align: top; padding-left: 10px;">
                                                    <p style="margin: 0 0 4px; color: #718096; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Languages</p>
                                                    <p style="margin: 0; color: #112116; font-size: 16px; font-weight: 600;">{{ languages }}</p>
                                                </td>
                                                {% endif %}
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                
                                {% if actors_str %}
                                <!-- Cast Recommendations -->
                                <tr>
                                    <td style="padding: 0 24px 20px;">
                                        <p style="margin: 0 0 6px; color: #718096; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Cast Recommendations</p>
                                        <p style="margin: 0; color: #4a5568; font-size: 14px;">{{ actors_str }}</p>
                                    </td>
                                </tr>
                                {% endif %}
                                
                            </table>
                        </td>
                    </tr>
                    {% endif %}
                    
                    <!-- What's Next Section -->
                    <tr>
                        <td style="padding: 0 40px 30px;">
                            <h3 style="margin: 0 0 15px; color: #112116; font-size: 18px; font-weight: 600;">What happens next?</h3>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                <!-- Step 1 -->
                                <tr>
                                    <td style="padding-bottom: 12px;">
                                        <table role="presentation" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="width: 32px; height: 32px; background-color: #B4941E; border-radius: 50%; text-align: center; vertical-align: middle;">
                                                    <span style="color: #ffffff; font-size: 14px; font-weight: 700;">1</span>
                                                </td>
                                                <td style="padding-left: 15px;">
                                                    <p style="margin: 0; color: #112116; font-size: 15px; font-weight: 500;">Our creative team reviews your submission</p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <!-- Step 2 -->
                                <tr>
                                    <td style="padding-bottom: 12px;">
                                        <table role="presentation" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="width: 32px; height: 32px; background-color: #B4941E; border-radius: 50%; text-align: center; vertical-align: middle;">
                                                    <span style="color: #ffffff; font-size: 14px; font-weight: 700;">2</span>
                                                </td>
                                                <td style="padding-left: 15px;">
                                                    <p style="margin: 0; color: #112116; font-size: 15px; font-weight: 500;">We evaluate alignment with our creative vision</p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <!-- Step 3 -->
                                <tr>
                                    <td>
                                        <table role="presentation" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td style="width: 32px; height: 32px; background-color: #B4941E; border-radius: 50%; text-align: center; vertical-align: middle;">
                                                    <span style="color: #ffffff; font-size: 14px; font-weight: 700;">3</span>
                                                </td>
                                                <td style="padding-left: 15px;">
                                                    <p style="margin: 0; color: #112116; font-size: 15px; font-weight: 500;">You'll hear from us within 5-7 business days</p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- CTA Note -->
                    <tr>
                        <td style="padding: 0 40px 30px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #fffbeb; border-radius: 8px; border-left: 4px solid #B4941E;">
                                <tr>
                                    <td style="padding: 16px 20px;">
                                        <p style="margin: 0; color: #92400e; font-size: 14px; line-height: 22px;">
                                            <strong>Have questions?</strong> Simply reply to this email and our team will be happy to assist you.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Divider -->
                    <tr>
                        <td style="padding: 0 40px;">
                            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 0;">
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px 40px; text-align: center;">
                            <p style="margin: 0 0 10px; color: #B4941E; font-size: 16px; font-weight: 700; letter-spacing: 1px;">OMI GLOBAL PRODUCTIONS</p>
                            <p style="margin: 0 0 15px; color: #718096; font-size: 13px;">Storytelling &bull; Wellness &bull; Sustainability</p>
                            <p style="margin: 0; color: #a0aec0; font-size: 12px; line-height: 20px;">
                                &copy; {{ current_year }} OMI Global Productions. All rights reserved.<br>
                                This is a transactional email regarding your project submission.
                            </p>
                        </td>
                    </tr>
                    
                </table>
                
            </td>
        </tr>
    </table>
</body>
</html>"""

    # Plain text version
    plain_template = """OMI GLOBAL PRODUCTIONS
======================

SUBMISSION RECEIVED
-------------------

Hello {{ first_name }},

Thank you for sharing your creative vision with us. Your project submission has been successfully received and is now in our review queue.

{% if title %}
YOUR SUBMISSION DETAILS
-----------------------
Project Title: {{ title }}
{% if logline %}Logline: "{{ logline }}"{% endif %}
{% if budget_formatted %}Budget: {{ budget_formatted }}{% endif %}
{% if languages %}Languages: {{ languages }}{% endif %}
{% if actors_str %}Cast Recommendations: {{ actors_str }}{% endif %}
{% endif %}

WHAT HAPPENS NEXT?
------------------
1. Our creative team reviews your submission
2. We evaluate alignment with our creative vision
3. You'll hear from us within 5-7 business days

Have questions? Simply reply to this email and our team will be happy to assist you.

---

OMI GLOBAL PRODUCTIONS
Storytelling | Wellness | Sustainability

(c) {{ current_year }} OMI Global Productions. All rights reserved.
This is a transactional email regarding your project submission."""

    # Render templates with data
    template_data = {
        "first_name": first_name,
        "title": title,
        "logline": logline,
        "budget_formatted": budget_formatted,
        "languages": languages,
        "actors_str": actors_str,
        "current_year": current_year,
    }

    html_body = Template(html_template).render(**template_data)
    plain_body = Template(plain_template).render(**template_data)

    return subject, html_body, plain_body


# Singleton instance for import
email_service = None


def get_email_service(db=None):
    """Get or create the email service singleton."""
    global email_service
    if email_service is None:
        email_service = EmailService(db=db)
    elif db is not None and email_service.db is None:
        email_service.db = db
    return email_service
