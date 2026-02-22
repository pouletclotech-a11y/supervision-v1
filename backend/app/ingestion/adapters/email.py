import imaplib
import email
import os
import json
import logging
import traceback as tb
import uuid
from datetime import datetime
from email.header import decode_header
from pathlib import Path
from typing import Iterable, List, Tuple, Optional

from sqlalchemy import select
from app.db.models import Setting, ImportLog, EmailBookmark
from app.db.session import AsyncSessionLocal
from app.ingestion.adapters.base import BaseAdapter, AdapterItem
from app.core.config import settings

logger = logging.getLogger("email-adapter")

class EmailAdapter(BaseAdapter):
    def __init__(self, temp_dir: str = "/app/data/email_ingress"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def _get_imap_config(self) -> dict:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Setting))
            return {s.key: s.value for s in result.scalars().all()}

    async def _get_last_uid(self, folder: str) -> int:
        async with AsyncSessionLocal() as session:
            stmt = select(EmailBookmark).where(EmailBookmark.folder == folder)
            result = await session.execute(stmt)
            bookmark = result.scalars().first()
            return bookmark.last_uid if bookmark else 0

    async def _update_last_uid(self, folder: str, uid: int):
        async with AsyncSessionLocal() as session:
            stmt = select(EmailBookmark).where(EmailBookmark.folder == folder)
            result = await session.execute(stmt)
            bookmark = result.scalars().first()
            if not bookmark:
                bookmark = EmailBookmark(folder=folder, last_uid=uid)
                session.add(bookmark)
            else:
                if uid > bookmark.last_uid:
                    bookmark.last_uid = uid
            await session.commit()

    async def _is_processed(self, message_id: str) -> bool:
        """Check if Message-ID or UID was already processed successfully."""
        if not message_id:
            return False
        async with AsyncSessionLocal() as session:
            stmt = select(ImportLog).where(
                ImportLog.source_message_id == message_id,
                ImportLog.status == "SUCCESS"
            )
            result = await session.execute(stmt)
            return result.scalars().first() is not None

    async def poll(self, poll_run_id: str = "") -> Iterable[AdapterItem]:
        """Poll IMAP for new emails. poll_run_id is used for log correlation."""
        config = await self._get_imap_config()
        imap_cfg = settings.INGESTION
        host = config.get('imap_host') or imap_cfg.get('imap_host')
        user = config.get('imap_user') or imap_cfg.get('imap_user')
        password = config.get('imap_password') or imap_cfg.get('imap_password')

        # Hardened port casting
        try:
            port_val = config.get('imap_port') or imap_cfg.get('imap_port') or 993
            port = int(port_val)
        except (ValueError, TypeError):
            port = 993

        whitelist_raw = config.get('whitelist_senders') or json.dumps(imap_cfg.get('whitelist_senders', []))
        whitelist = json.loads(whitelist_raw)
        folder = "inbox"

        if not host or not user or not password:
            logger.debug("Email configuration missing. Skipping poll.")
            return []

        last_uid = await self._get_last_uid(folder)
        items = []

        try:
            mail = imaplib.IMAP4_SSL(host, port)
            mail.login(user, password)
            mail.select(folder)

            # Search by UID range
            search_crit = f"UID {last_uid + 1}:*"
            status, messages = mail.uid('SEARCH', None, search_crit)

            if status != 'OK' or not messages[0]:
                mail.logout()
                return []

            # Simple and robust UID extraction
            raw_uids = messages[0]
            if isinstance(raw_uids, bytes):
                uids_strings = raw_uids.decode().split()
            else:
                uids_strings = str(raw_uids).split()

            # Keep UIDs as STRINGS for imaplib calls
            uids_to_process = []
            for u_str in uids_strings:
                if u_str.isdigit():
                    u_int = int(u_str)
                    if u_int > last_uid:
                        uids_to_process.append((u_int, u_str))

            # Sort by integer value
            uids_to_process.sort()

            for uid_int, uid_str in uids_to_process:
                # ── Per-item isolation: one email failing must not abort poll ──
                try:
                    # Fetch headers
                    res, header_data = mail.uid('FETCH', uid_str, '(BODY[HEADER.FIELDS (MESSAGE-ID FROM SUBJECT)])')
                    if not header_data or not header_data[0]:
                        logger.warning(f"[EmailAdapter] Empty header response for UID={uid_str} run_id={poll_run_id}")
                        continue

                    header_raw = header_data[0][1]
                    msg_headers = email.message_from_bytes(header_raw)

                    msg_id_raw = msg_headers.get("Message-ID")
                    msg_id = msg_id_raw.strip("<>") if msg_id_raw else ""
                    from_raw = msg_headers.get("From")
                    sender = email.utils.parseaddr(from_raw)[1] if from_raw else ""

                    bookmark_id = f"email:{msg_id or uid_str}"

                    if await self._is_processed(bookmark_id):
                        logger.debug(f"[EmailAdapter] Already processed UID={uid_str} run_id={poll_run_id}")
                        await self._update_last_uid(folder, uid_int)
                        continue

                    if whitelist and sender not in whitelist:
                        logger.warning(f"[EmailAdapter] Sender={sender} not in whitelist UID={uid_str} run_id={poll_run_id}")
                        await self._update_last_uid(folder, uid_int)
                        continue

                    # Fetch full message
                    res, msg_data = mail.uid('FETCH', uid_str, '(RFC822)')
                    if not msg_data or not msg_data[0]:
                        logger.warning(f"[EmailAdapter] Empty body response for UID={uid_str} run_id={poll_run_id}")
                        continue

                    raw_msg = msg_data[0][1]
                    msg = email.message_from_bytes(raw_msg)

                    # Subject for logging
                    subject, encoding = decode_header(msg.get("Subject", ""))[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")

                    has_relevant_attachment = False
                    for part in msg.walk():
                        if part.get_content_maintype() == 'multipart':
                            continue
                        if part.get('Content-Disposition') is None:
                            continue

                        filename = part.get_filename()
                        if filename:
                            ext = Path(filename).suffix.lower()
                            if ext in ['.pdf', '.xlsx', '.xls']:
                                uid_dir = self.temp_dir / uid_str
                                uid_dir.mkdir(parents=True, exist_ok=True)
                                save_path = uid_dir / filename

                                with open(save_path, "wb") as f:
                                    f.write(part.get_payload(decode=True))

                                items.append(AdapterItem(
                                    path=str(save_path),
                                    filename=filename,
                                    size_bytes=save_path.stat().st_size,
                                    mtime=datetime.utcnow(),
                                    source="email",
                                    source_message_id=bookmark_id,
                                    metadata={
                                        "sender_email": sender,
                                        "subject": subject,
                                        "imap_uid": uid_str,
                                        "message_id": msg_id,
                                        "imap_folder": folder,
                                        "poll_run_id": poll_run_id,
                                    }
                                ))
                                has_relevant_attachment = True

                    # Advance bookmark only if no attachment (attachment = ack_success will advance)
                    if not has_relevant_attachment:
                        await self._update_last_uid(folder, uid_int)

                except Exception as item_err:
                    # ── Per-item fail soft: log full traceback, do NOT advance bookmark ──
                    # This allows natural retry on next poll cycle.
                    logger.error(
                        f"[EmailAdapter] Per-item error UID={uid_str} run_id={poll_run_id}: {item_err}",
                        exc_info=True
                    )
                    # Bookmark intentionally NOT advanced → retry on next poll

            mail.logout()

        except Exception as e:
            logger.error(f"[EmailAdapter] Poll Error run_id={poll_run_id}: {e}", exc_info=True)

        return items

    async def _imap_action(self, uid: str, action: str):
        """
        Perform action (MOVE/DELETE/SEEN) on an email by UID.
        Fail-soft: unexpected IMAP statuses are logged as warnings.
        INVARIANT: on COPY failure → item stays in INBOX (no delete, no bookmark advance from here).
        """
        config = await self._get_imap_config()
        host = config.get('imap_host')
        user = config.get('imap_user')
        password = config.get('imap_password')

        # Safe port casting
        try:
            port_val = config.get('imap_port') or settings.INGESTION.get('imap_port') or 993
            port = int(port_val)
        except (ValueError, TypeError):
            port = 993

        processed_folder = config.get('imap_folder', 'Processed')
        cleanup_mode = config.get('cleanup_mode', 'MOVE')

        try:
            mail = imaplib.IMAP4_SSL(host, port)
            mail.login(user, password)
            mail.select("inbox")

            uid_str = str(uid)
            status, data = mail.uid('SEARCH', None, uid_str)

            if status == 'OK' and data[0]:
                if action == 'SUCCESS':
                    if cleanup_mode == 'MOVE':
                        mail.create(processed_folder)
                        copy_res, _ = mail.uid('COPY', uid_str, processed_folder)
                        if copy_res == 'OK':
                            store_res, _ = mail.uid('STORE', uid_str, '+FLAGS', '\\Deleted')
                            if store_res != 'OK':
                                # Warn but do NOT raise — item was copied, just flag failed
                                logger.warning(
                                    f"[EmailAdapter] IMAP STORE unexpected status={store_res} "
                                    f"UID={uid_str}. Item copied but not flagged deleted."
                                )
                        else:
                            # COPY failed → item stays in INBOX → will be retried
                            # Do NOT proceed with STORE (no delete, no ack-complete)
                            logger.warning(
                                f"[EmailAdapter] IMAP COPY failed status={copy_res} "
                                f"UID={uid_str}. Item stays in INBOX for retry."
                            )
                            mail.logout()
                            return  # Early return: do not expunge, do not mark as deleted
                    elif cleanup_mode == 'DELETE':
                        store_res, _ = mail.uid('STORE', uid_str, '+FLAGS', '\\Deleted')
                        if store_res != 'OK':
                            logger.warning(
                                f"[EmailAdapter] IMAP STORE (DELETE mode) unexpected status={store_res} "
                                f"UID={uid_str}."
                            )

                elif action == 'SEEN':
                    store_res, _ = mail.uid('STORE', uid_str, '+FLAGS', '\\Seen')
                    if store_res != 'OK':
                        logger.warning(
                            f"[EmailAdapter] IMAP STORE (SEEN) unexpected status={store_res} "
                            f"UID={uid_str}."
                        )

            mail.expunge()
            mail.logout()

        except Exception as e:
            logger.error(f"[EmailAdapter] Action Error ({action}) UID={uid}: {e}", exc_info=True)

    async def ack_success(self, item: AdapterItem, import_id: int):
        uid = item.metadata.get("imap_uid")
        folder = item.metadata.get("imap_folder", "inbox")
        run_id = item.metadata.get("poll_run_id", "")
        if uid:
            await self._update_last_uid(folder, int(uid))
            await self._imap_action(uid, 'SUCCESS')
        if Path(item.path).exists():
            Path(item.path).unlink()
        logger.info(f"[METRIC] event=import_success adapter=email run_id={run_id} import_id={import_id} file={item.filename} uid={uid}")

    async def ack_duplicate(self, item: AdapterItem, existing_import_id: int):
        uid = item.metadata.get("imap_uid")
        folder = item.metadata.get("imap_folder", "inbox")
        run_id = item.metadata.get("poll_run_id", "")
        if uid:
            await self._update_last_uid(folder, int(uid))
            await self._imap_action(uid, 'SEEN')
        if Path(item.path).exists():
            Path(item.path).unlink()
        logger.info(f"[METRIC] event=import_duplicate adapter=email run_id={run_id} file={item.filename} uid={uid} existing_import_id={existing_import_id}")

    async def ack_unmatched(self, item: AdapterItem, reason: str):
        uid = item.metadata.get("imap_uid")
        folder = item.metadata.get("imap_folder", "inbox")
        run_id = item.metadata.get("poll_run_id", "")
        if uid:
            # Advance bookmark even on unmatched — prevents infinite stall on bad files
            await self._update_last_uid(folder, int(uid))
            await self._imap_action(uid, 'SEEN')
        if Path(item.path).exists():
            Path(item.path).unlink()
        logger.warning(f"[METRIC] event=import_unmatched adapter=email run_id={run_id} file={item.filename} uid={uid} reason={reason}")

    async def ack_error(self, item: AdapterItem, reason: str):
        # On processing error: DO NOT advance bookmark → allows retry on restart
        run_id = item.metadata.get("poll_run_id", "")
        if Path(item.path).exists():
            Path(item.path).unlink()
        logger.error(f"[METRIC] event=import_error adapter=email run_id={run_id} file={item.filename} reason={reason}")
