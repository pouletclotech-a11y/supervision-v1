import imaplib
import email
import os
import json
import logging
from datetime import datetime
from email.header import decode_header
from sqlalchemy import select
from app.db.models import Setting, ImportLog, MonitoringProvider
from app.services.provider_resolver import ProviderResolver

class EmailFetcher:
    def __init__(self, db_session=None):
        self.db = db_session
        self.resolver = ProviderResolver()

    async def get_settings(self):
        """Fetch all settings as a dict"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Setting))
            settings = {s.key: s.value for s in result.scalars().all()}
        return settings

    async def fetch_emails(self):
        from app.db.session import AsyncSessionLocal
        config = await self.get_settings()
        
        host = config.get('imap_host')
        user = config.get('imap_user')
        password = config.get('imap_password')
        global_whitelist = json.loads(config.get('whitelist_senders', '[]'))
        cleanup_mode = config.get('cleanup_mode', 'MOVE')
        processed_folder = config.get('imap_folder', 'Processed')
        
        # Default policy for unclassified emails
        default_formats = ["pdf", "xls", "xlsx"]
        
        if not host or not user or not password:
            logger.warning("Email configuration missing. Skipping fetch.")
            return

        async with AsyncSessionLocal() as db:
            try:
                # Connect
                mail = imaplib.IMAP4_SSL(host, int(config.get('imap_port', 993)))
                mail.login(user, password)
                mail.select("inbox")

                status, messages = mail.search(None, '(UNSEEN)')
                if status != 'OK':
                    return
                
                email_ids = messages[0].split()
                logger.info(f"Found {len(email_ids)} unread emails.")

                for e_id in email_ids:
                    res, msg_data = mail.fetch(e_id, '(RFC822)')
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding if encoding else "utf-8")
                            
                            sender = msg.get("From")
                            sender_email = email.utils.parseaddr(sender)[1].lower()
                            
                            # 1. Resolve Rule and Provider
                            rule = await self.resolver.resolve_provider(sender_email, db)
                            provider = None
                            if rule:
                                provider = await self.resolver.get_provider_by_id(rule.provider_id, db)
                            
                            # 2. Keyword Check (Phase Architecture)
                            if provider and provider.email_match_keyword:
                                keyword = provider.email_match_keyword.lower().strip()
                                if keyword not in subject.lower():
                                    logger.info(f"Keyword '{keyword}' not found in subject for provider {provider.code}. Skipping.")
                                    # Create IGNORED Log (KEYWORD_MISMATCH)
                                    import_log = ImportLog(
                                        filename=f"Email: {subject[:50]}...",
                                        status="IGNORED",
                                        error_message=f"KEYWORD_MISMATCH: Expected subject to contain '{keyword}'",
                                        provider_id=provider.id,
                                        raw_payload=f"From: {sender_email}\nSubject: {subject}\nRule: {rule.match_value if rule else 'N/A'}"
                                    )
                                    db.add(import_log)
                                    await db.commit()
                                    continue
                            
                            # 3. Global Whitelist Fallback (Security Deprecated)
                            if not provider and global_whitelist and sender_email not in global_whitelist:
                                logger.warning(f"Unclassified sender {sender_email} not in global whitelist. Ignoring.")
                                continue

                            # 4. Process Attachments with Provider-specific format validation
                            has_attachment = False
                            allowed_formats = provider.accepted_attachment_types if provider else default_formats
                            
                            # Backend Normalization of allowed_formats
                            allowed_formats = [f.lower().strip().replace('.', '') for f in allowed_formats if f]
                            allowed_formats = [f for f in allowed_formats if f and len(f) <= 10 and f.isalnum()]

                            for part in msg.walk():
                                if part.get_content_maintype() == 'multipart': continue
                                if part.get('Content-Disposition') is None: continue
                                    
                                filename = part.get_filename()
                                if filename:
                                    ext = filename.split('.')[-1].lower() if '.' in filename else ""
                                    
                                    if ext in allowed_formats:
                                        # Save to Dropbox Ingress
                                        filepath = os.path.join("/app/data/ingress", filename)
                                        with open(filepath, "wb") as f:
                                            f.write(part.get_payload(decode=True))
                                        logger.info(f"Downloaded attachment: {filename} (Provider: {provider.code if provider else 'UNCLASSIFIED'})")
                                        has_attachment = True
                                        
                                        # Save metadata
                                        meta_filepath = filepath + ".meta.json"
                                        
                                        # Frequency hierarchy: Rule-specific > Provider-specific > System Defaults
                                        # (Metadata is consumed by worker.py later to update internal state)
                                        meta_data = {
                                            "sender_email": sender_email,
                                            "subject": subject,
                                            "provider_id": provider.id if provider else None,
                                            "rule_id": rule.id if rule else None,
                                            "fetched_at": datetime.now().isoformat()
                                        }
                                        with open(meta_filepath, "w", encoding="utf-8") as mf:
                                            json.dump(meta_data, mf)
                                    else:
                                        logger.warning(f"Format .{ext} not allowed for provider {provider.code if provider else 'UNCLASSIFIED'}")
                                        # Create IGNORED Log (FORMAT_REJECTED)
                                        import_log = ImportLog(
                                            filename=filename,
                                            status="IGNORED",
                                            error_message=f"FORMAT_REJECTED: Extension .{ext} not in {allowed_formats}",
                                            provider_id=provider.id if provider else None,
                                            raw_payload=f"From: {sender_email}\nSubject: {subject}\nFilename: {filename}"
                                        )
                                        db.add(import_log)
                                        await db.commit()

                            # Cleanup
                            if has_attachment:
                                if cleanup_mode == 'DELETE':
                                    mail.store(e_id, '+FLAGS', '\\Deleted')
                                elif cleanup_mode == 'MOVE':
                                    mail.copy(e_id, processed_folder)
                                    mail.store(e_id, '+FLAGS', '\\Deleted')
                            else:
                                # Mark as read anyway even if no attachment matched
                                # (unless it was already skipped by keyword mismatch)
                                mail.store(e_id, '+FLAGS', '\\Seen')
                    
                mail.expunge()
                mail.close()
                mail.logout()
                
            except Exception as e:
                logger.error(f"Email Fetch Error: {e}")
                await db.rollback()
                    
                mail.expunge()
                mail.close()
                mail.logout()
                
            except Exception as e:
                logger.error(f"Email Fetch Error: {e}")
                await db.rollback()
