import imaplib
import email
import os
import json
import logging
from datetime import datetime
from email.header import decode_header
from sqlalchemy import select
from app.db.models import Setting
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("email-fetcher")

class EmailFetcher:
    def __init__(self, db_session=None):
        self.db = db_session # Optional, usually we create one inside methods

    async def get_settings(self):
        """Fetch all settings as a dict"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Setting))
            settings = {s.key: s.value for s in result.scalars().all()}
        return settings

    async def fetch_emails(self):
        config = await self.get_settings()
        
        host = config.get('imap_host')
        user = config.get('imap_user')
        password = config.get('imap_password')
        whitelist = json.loads(config.get('whitelist_senders', '[]'))
        cleanup_mode = config.get('cleanup_mode', 'MOVE')
        processed_folder = config.get('imap_folder', 'Processed')
        
        if not host or not user or not password:
            logger.warning("Email configuration missing. Skipping fetch.")
            return

        try:
            # Connect
            mail = imaplib.IMAP4_SSL(host, int(config.get('imap_port', 993)))
            mail.login(user, password)
            mail.select("inbox")

            # Search Unread
            status, messages = mail.search(None, '(UNSEEN)')
            if status != 'OK':
                return
            
            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} unread emails.")

            for e_id in email_ids:
                # Fetch
                res, msg_data = mail.fetch(e_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Decode Subject
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                        
                        sender = msg.get("From")
                        
                        # Whitelist Check
                        sender_email = email.utils.parseaddr(sender)[1]
                        if whitelist and sender_email not in whitelist:
                            logger.warning(f"Sender {sender_email} not in whitelist. Ignoring.")
                            continue

                        # Process Attachments
                        has_attachment = False
                        for part in msg.walk():
                            if part.get_content_maintype() == 'multipart':
                                continue
                            if part.get('Content-Disposition') is None:
                                continue
                                
                            filename = part.get_filename()
                            if filename:
                                ext_check = filename.lower()
                                if ext_check.endswith('.pdf') or ext_check.endswith('.xlsx') or ext_check.endswith('.xls'):
                                    # Save to Dropbox Ingress
                                    filepath = os.path.join("/app/data/ingress", filename)
                                    with open(filepath, "wb") as f:
                                        f.write(part.get_payload(decode=True))
                                    logger.info(f"Downloaded attachment: {filename}")
                                    has_attachment = True
                                    
                                    # Phase 3: Save metadata for provider resolution
                                    meta_filepath = filepath + ".meta.json"
                                    meta_data = {
                                        "sender_email": sender_email,
                                        "subject": subject if isinstance(subject, str) else str(subject),
                                        "fetched_at": datetime.now().isoformat()
                                    }
                                    with open(meta_filepath, "w", encoding="utf-8") as mf:
                                        json.dump(meta_data, mf)
                                    logger.debug(f"Saved metadata: {meta_filepath}")
                                else:
                                    logger.debug(f"Skipping attachment with extension: {filename}")
                        
                        # Cleanup
                        if has_attachment:
                            if cleanup_mode == 'DELETE':
                                mail.store(e_id, '+FLAGS', '\\Deleted')
                            elif cleanup_mode == 'MOVE':
                                # Create folder if not exists (Best effort)
                                # mail.create(processed_folder) 
                                result = mail.copy(e_id, processed_folder)
                                if result[0] == 'OK':
                                    mail.store(e_id, '+FLAGS', '\\Deleted')
                
            mail.expunge()
            mail.close()
            mail.logout()
            
        except Exception as e:
            logger.error(f"Email Fetch Error: {e}")
