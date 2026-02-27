import os
import shutil
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Iterable
from app.ingestion.adapters.base import BaseAdapter, AdapterItem
from app.core.config import settings

logger = logging.getLogger("dropbox-adapter")

class DropboxAdapter(BaseAdapter):
    def __init__(self, ingress_dir: str = None, archive_dir: str = None):
        self.ingress_dir = Path(ingress_dir or "/app/data/ingress")
        self.archive_dir = Path(archive_dir or "/app/data/archive")
        self.unmatched_dir = self.archive_dir / "unmatched"
        self.error_dir = self.archive_dir / "error"
        
        # Ensure directories exist
        for d in [self.ingress_dir, self.archive_dir, self.unmatched_dir, self.error_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _compute_sha256(self, path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    async def poll(self) -> Iterable[AdapterItem]:
        items = []
        # Support common extensions from worker.py logic
        supported_exts = {'.xls', '.xlsx', '.pdf'}
        
        # List files in ingress
        for f in self.ingress_dir.iterdir():
            if f.is_file() and f.suffix.lower() in supported_exts:
                # Ignore .meta.json files if they are handled separately or as part of the item
                if f.name.endswith(".meta.json"):
                    continue
                
                # Metadata loading
                item_metadata = {}
                meta_file = f.parent / (f.name + ".meta.json")
                if meta_file.exists():
                    try:
                        import json
                        with open(meta_file, 'r') as mf:
                            item_metadata = json.load(mf)
                    except Exception as e:
                        logger.error(f"Failed to load metadata for {f.name}: {e}")

                # Basic metadata
                stats = f.stat()
                items.append(AdapterItem(
                    path=str(f),
                    filename=f.name,
                    size_bytes=stats.st_size,
                    mtime=datetime.fromtimestamp(stats.st_mtime),
                    source="dropbox",
                    metadata=item_metadata,
                    source_message_id=item_metadata.get("source_message_id")
                ))
        
        # Sort by mtime ascending for deterministic processing
        items.sort(key=lambda x: x.mtime)
        return items

    def _get_date_path(self, base_dir: Path) -> Path:
        now = datetime.utcnow()
        return base_dir / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")

    def _safe_move(self, src: Path, dest: Path):
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Avoid overwriting existing files by appending timestamp if conflict
        final_dest = dest
        if final_dest.exists():
            final_dest = dest.parent / f"{int(datetime.utcnow().timestamp())}_{dest.name}"
        
        try:
            os.replace(src, final_dest)
        except OSError:
            shutil.move(str(src), str(final_dest))
        
        return final_dest

    async def ack_success(self, item: AdapterItem, import_id: int):
        dest_base = self._get_date_path(self.archive_dir)
        final_path = self._safe_move(Path(item.path), dest_base / item.filename)
        logger.info(f"[DropboxAdapter] Status=SUCCESS File={item.filename} Hash={item.sha256} ImportID={import_id} Dest={final_path}")

    async def ack_duplicate(self, item: AdapterItem, existing_import_id: int):
        dest_base = self.archive_dir / "duplicates"
        final_path = self._safe_move(Path(item.path), dest_base / item.filename)
        logger.info(f"[DropboxAdapter] Status=DUPLICATE File={item.filename} Hash={item.sha256} ExistingImportID={existing_import_id} Dest={final_path}")

    async def ack_unmatched(self, item: AdapterItem, reason: str):
        dest_base = self._get_date_path(self.unmatched_dir)
        final_path = self._safe_move(Path(item.path), dest_base / item.filename)
        logger.warning(f"[DropboxAdapter] Status=UNMATCHED File={item.filename} Hash={item.sha256} Reason={reason} Dest={final_path}")

    async def ack_error(self, item: AdapterItem, reason: str):
        dest_base = self._get_date_path(self.error_dir)
        final_path = self._safe_move(Path(item.path), dest_base / item.filename)
        logger.error(f"[DropboxAdapter] Status=ERROR File={item.filename} Hash={item.sha256} Reason={reason} Dest={final_path}")
