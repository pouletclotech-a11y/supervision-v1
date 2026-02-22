import pytest
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
from pathlib import Path
from app.ingestion.adapters.email import EmailAdapter
from app.ingestion.adapters.base import AdapterItem
from datetime import datetime

import shutil
import os

@pytest.fixture
def email_adapter():
    temp_dir = "/tmp/email_test"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    yield EmailAdapter(temp_dir=temp_dir)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

@pytest.mark.asyncio
async def test_email_adapter_poll_with_bookmark(email_adapter):
    """Test that polling starts from last_uid + 1."""
    with patch("app.ingestion.adapters.email.EmailAdapter._get_imap_config") as mock_config:
        mock_config.return_value = {
            "imap_host": "imap.test.com", "imap_user": "u", "imap_password": "p", "whitelist_senders": "[]"
        }
        
        with patch("app.ingestion.adapters.email.EmailAdapter._get_last_uid", new_callable=AsyncMock) as mock_get_uid:
            mock_get_uid.return_value = 100
            
            with patch("app.ingestion.adapters.email.EmailAdapter._is_processed", new_callable=AsyncMock) as mock_is_proc:
                mock_is_proc.return_value = False
            
                with patch("imaplib.IMAP4_SSL") as mock_imap:
                    instance = mock_imap.return_value
                    # SEARCH UID 101:*
                    instance.uid.side_effect = [
                        ("OK", [b"101 102"]), # SEARCH
                        ("OK", [(None, b"Message-ID: <msg101>\r\nFrom: s@t.com\r\n\r\n")]), # FETCH 101 Headers
                        ("OK", [(None, b"Content-Type: text/plain\r\n\r\n")]), # FETCH 101 Body
                        ("OK", [(None, b"Message-ID: <msg102>\r\nFrom: s@t.com\r\n\r\n")]), # FETCH 102 Headers
                        ("OK", [(None, b'Content-Disposition: attachment; filename="a.xls"\r\n\r\n')]) # FETCH 102 Body
                    ]
                    
                    with patch("app.ingestion.adapters.email.EmailAdapter._update_last_uid", new_callable=AsyncMock) as mock_update:
                        items = await email_adapter.poll()
                        assert len(items) == 1
                        assert items[0].metadata["imap_uid"] == "102"
                        mock_update.assert_any_call("inbox", 101)

@pytest.mark.asyncio
async def test_email_adapter_resilience_worker_off_on(email_adapter):
    """Simulate Worker Off -> 3 emails received -> Worker On."""
    with patch("app.ingestion.adapters.email.EmailAdapter._get_imap_config") as mock_config:
        mock_config.return_value = {"imap_host": "h", "imap_user": "u", "imap_password": "p", "whitelist_senders": "[]"}
        
        with patch("app.ingestion.adapters.email.EmailAdapter._get_last_uid", new_callable=AsyncMock) as mock_get_uid:
            mock_get_uid.return_value = 500
            
            with patch("app.ingestion.adapters.email.EmailAdapter._is_processed", new_callable=AsyncMock) as mock_is_proc:
                mock_is_proc.return_value = False
            
                with patch("imaplib.IMAP4_SSL") as mock_imap:
                    instance = mock_imap.return_value
                    instance.uid.side_effect = [
                        ("OK", [b"501 502 503"]), # SEARCH 501:*
                        ("OK", [(None, b"Message-ID: <m1>\r\n\r\n")]), # 501 H
                        ("OK", [(None, b'Content-Disposition: attachment; filename="1.xls"\r\n\r\n')]), # 501 B
                        ("OK", [(None, b"Message-ID: <m2>\r\n\r\n")]), # 502 H
                        ("OK", [(None, b'Content-Disposition: attachment; filename="2.xls"\r\n\r\n')]), # 502 B
                        ("OK", [(None, b"Message-ID: <m3>\r\n\r\n")]), # 503 H
                        ("OK", [(None, b'Content-Disposition: attachment; filename="3.xls"\r\n\r\n')]), # 503 B
                    ]
                    
                    items = await email_adapter.poll()
                    assert len(items) == 3

@pytest.mark.asyncio
async def test_email_adapter_ack_success_updates_bookmark(email_adapter):
    """Verify that successful processing advances the DB bookmark."""
    item = AdapterItem(
        path="/tmp/email_test/test.xls",
        filename="test.xls",
        size_bytes=100,
        mtime=datetime.utcnow(),
        source="email",
        metadata={"imap_uid": "600", "imap_folder": "inbox"}
    )
    # Create dummy file for cleanup test
    Path(item.path).parent.mkdir(parents=True, exist_ok=True)
    Path(item.path).touch()
    
    with patch("app.ingestion.adapters.email.EmailAdapter._update_last_uid", new_callable=AsyncMock) as mock_update:
        with patch("app.ingestion.adapters.email.EmailAdapter._imap_action", new_callable=AsyncMock) as mock_action:
            await email_adapter.ack_success(item, 123)
            mock_update.assert_called_with("inbox", 600)
            mock_action.assert_called_with("600", "SUCCESS")

@pytest.mark.asyncio
async def test_email_adapter_error_does_not_update_bookmark(email_adapter):
    """Verify that error does NOT advance the bookmark."""
    item = AdapterItem(
        path="/tmp/email_test/test_err.xls",
        filename="test.xls",
        size_bytes=100,
        mtime=datetime.utcnow(),
        source="email",
        metadata={"imap_uid": "700", "imap_folder": "inbox"}
    )
    Path(item.path).parent.mkdir(parents=True, exist_ok=True)
    Path(item.path).touch()
    
    with patch("app.ingestion.adapters.email.EmailAdapter._update_last_uid", new_callable=AsyncMock) as mock_update:
        await email_adapter.ack_error(item, "Crash")
        mock_update.assert_not_called()

@pytest.mark.asyncio
async def test_email_adapter_histoxlsx_matching(email_adapter):
    """Verify that HISTO.xlsx is correctly picked up and matching is possible via original filename."""
    with patch("app.ingestion.adapters.email.EmailAdapter._get_imap_config") as mock_config:
        mock_config.return_value = {"imap_host": "h", "imap_user": "u", "imap_password": "p", "whitelist_senders": "[]"}
        
        with patch("app.ingestion.adapters.email.EmailAdapter._get_last_uid", new_callable=AsyncMock) as mock_get_uid:
            mock_get_uid.return_value = 800
            with patch("app.ingestion.adapters.email.EmailAdapter._is_processed", new_callable=AsyncMock) as mock_is_proc:
                mock_is_proc.return_value = False
                
                with patch("imaplib.IMAP4_SSL") as mock_imap:
                    instance = mock_imap.return_value
                    instance.uid.side_effect = [
                        ("OK", [b"801"]), # SEARCH
                        ("OK", [(None, b"Message-ID: <m801>\r\n\r\n")]), # FETCH Headers
                        ("OK", [(None, b'Content-Disposition: attachment; filename="2026_HISTO.xlsx"\r\n\r\n')]) # FETCH Body
                    ]
                    
                    items = await email_adapter.poll()
                    
                    assert len(items) == 1
                    item = items[0]
                    assert item.filename == "2026_HISTO.xlsx"
                    # The path should end with /801/2026_HISTO.xlsx (or use OS separators)
                    assert Path(item.path).name == "2026_HISTO.xlsx"
                    assert Path(item.path).parent.name == "801"


@pytest.mark.asyncio
async def test_email_adapter_per_item_isolation(email_adapter):
    """
    Per-item isolation: UID1 raises an exception on FETCH.
    UID2 must still be processed successfully.
    The poll must NOT abort entirely.
    Bookmark must NOT advance for UID1 (retry later).
    """
    with patch("app.ingestion.adapters.email.EmailAdapter._get_imap_config") as mock_config:
        mock_config.return_value = {"imap_host": "h", "imap_user": "u", "imap_password": "p", "whitelist_senders": "[]"}
        
        with patch("app.ingestion.adapters.email.EmailAdapter._get_last_uid", new_callable=AsyncMock) as mock_get_uid:
            mock_get_uid.return_value = 900
            
            with patch("app.ingestion.adapters.email.EmailAdapter._is_processed", new_callable=AsyncMock) as mock_is_proc:
                mock_is_proc.return_value = False
                
                with patch("imaplib.IMAP4_SSL") as mock_imap:
                    instance = mock_imap.return_value
                    
                    # SEARCH returns 2 UIDs
                    # UID 901: FETCH raises exception (simulates IMAP glitch)
                    # UID 902: normal with attachment
                    def uid_side_effect(*args, **kwargs):
                        cmd = args[0]
                        uid_arg = args[1] if len(args) > 1 else None
                        if cmd == 'SEARCH':
                            return ("OK", [b"901 902"])
                        if cmd == 'FETCH' and uid_arg == '901':
                            raise RuntimeError("IMAP glitch on UID 901")
                        if cmd == 'FETCH' and uid_arg == '902':
                            # First FETCH (headers)
                            if '(BODY[HEADER' in (args[2] if len(args) > 2 else ''):
                                return ("OK", [(None, b"Message-ID: <m902>\r\n\r\n")])
                            else:
                                # Second FETCH (body)
                                return ("OK", [(None, b'Content-Disposition: attachment; filename="ok.xls"\r\n\r\n')])
                        return ("OK", [b""])
                    
                    instance.uid.side_effect = uid_side_effect
                    
                    with patch("app.ingestion.adapters.email.EmailAdapter._update_last_uid", new_callable=AsyncMock) as mock_update:
                        items = await email_adapter.poll()
                    
                    # UID 902 must have yielded 1 item
                    assert len(items) == 1
                    assert items[0].metadata["imap_uid"] == "902"
                    
                    # UID 901 must NOT have advanced the bookmark (no update call with 901)
                    update_calls = [c.args for c in mock_update.call_args_list]
                    uid_updated = [c[1] for c in update_calls if len(c) > 1]
                    assert 901 not in uid_updated, "Bookmark must NOT advance for failed UID=901"


@pytest.mark.asyncio
async def test_email_adapter_imap_copy_fails_soft(email_adapter):
    """
    Fail-soft COPY: if IMAP COPY returns unexpected status (e.g. 'NO'),
    the adapter must:
    - Log a warning
    - NOT call STORE (no \\Deleted flag)
    - NOT call ack_success (item stays in INBOX for retry)
    - NOT advance the bookmark
    """
    with patch("app.ingestion.adapters.email.EmailAdapter._get_imap_config") as mock_config:
        mock_config.return_value = {
            "imap_host": "h", "imap_user": "u", "imap_password": "p",
            "imap_folder": "Processed", "cleanup_mode": "MOVE"
        }
        
        with patch("imaplib.IMAP4_SSL") as mock_imap:
            instance = mock_imap.return_value
            
            # SEARCH finds the UID, but COPY returns "NO"
            uid_calls = []
            def uid_side_effect(*args, **kwargs):
                cmd = args[0]
                uid_calls.append(cmd)
                if cmd == 'SEARCH':
                    return ("OK", [b"950"])
                if cmd == 'COPY':
                    return ("NO", [b"[CANNOT] Mailbox full"])
                if cmd == 'STORE':
                    return ("OK", [b""])
                return ("OK", [b""])
            
            instance.uid.side_effect = uid_side_effect
            
            # Call _imap_action directly
            await email_adapter._imap_action("950", "SUCCESS")
            
            # STORE must NOT have been called (no deletion if COPY failed)
            assert 'STORE' not in uid_calls, \
                f"STORE must NOT be called when COPY fails. Actual calls: {uid_calls}"
            
            # COPY must have been called
            assert 'COPY' in uid_calls
