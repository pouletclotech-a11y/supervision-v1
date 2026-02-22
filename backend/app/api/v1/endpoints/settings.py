from typing import Any, List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
import imaplib
import smtplib
from email.mime.text import MIMEText

from app.db.session import get_db
from app.db.models import Setting

router = APIRouter()

class SettingIn(BaseModel):
    value: str

class SettingOut(BaseModel):
    key: str
    value: str
    description: str | None

@router.get("/", response_model=List[SettingOut])
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting))
    return result.scalars().all()

@router.post("/", response_model=Dict[str, str])
async def update_settings(
    settings: Dict[str, str], # Expecting {"key": "value"}
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk update settings.
    """
    for key, value in settings.items():
        # Upsert logic manually or check existence
        # Simple update if exists, else invalid for V1 (seed ensures existence)
        # Actually proper upsert:
        stmt = select(Setting).where(Setting.key == key)
        result = await db.execute(stmt)
        obj = result.scalar_one_or_none()
        
        if obj:
            obj.value = value
        else:
            # allow creating new keys? sure
            db.add(Setting(key=key, value=str(value), description="User Defined"))
    
    await db.commit()
    return {"status": "updated"}

@router.post("/test-imap")
async def test_imap(settings: Dict[str, str]):
    host = settings.get('imap_host')
    user = settings.get('imap_user')
    password = settings.get('imap_password')
    port = int(settings.get('imap_port', 993))
    
    try:
        mail = imaplib.IMAP4_SSL(host, port)
        mail.login(user, password)
        mail.logout()
        return {"status": "success", "message": "IMAP Connection Successful"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"IMAP Connection Failed: {str(e)}")

@router.post("/test-smtp")
async def test_smtp(payload: Dict[str, Any]):
    # Payload: { settings: {...}, recipient: "foo@bar.com" }
    settings = payload.get('settings', {})
    recipient = payload.get('recipient')
    
    host = settings.get('smtp_host', 'ssl0.ovh.net')
    port = int(settings.get('smtp_port', 465))
    user = settings.get('imap_user') # Usually same as IMAP
    password = settings.get('imap_password')
    
    if not recipient:
         raise HTTPException(status_code=400, detail="Recipient address required.")

    try:
        msg = MIMEText("This is a test email from Supervision System.")
        msg['Subject'] = "Supervision Test Email"
        msg['From'] = user
        msg['To'] = recipient

        with smtplib.SMTP_SSL(host, port) as server:
            server.login(user, password)
            server.sendmail(user, recipient, msg.as_string())
            
        return {"status": "success", "message": f"Email sent to {recipient}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SMTP Send Failed: {str(e)}")
