import hashlib
import shutil
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple

logger = logging.getLogger("archiver")

class ArchiverService:
    def __init__(self, base_path: str = "/app/data/archive"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def compute_sha256(self, file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def archive_file(self, source_path: Path, import_date: datetime) -> Tuple[str, str]:
        """
        Moves file to archive/YYYY/MM/DD/filename
        Returns (archive_path, file_hash)
        Raises Exception if hash mismatch or move failed.
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source file {source_path} not found")

        # 1. Compute initial hash
        initial_hash = self.compute_sha256(source_path)
        
        # 2. Determine destination
        year = import_date.strftime("%Y")
        month = import_date.strftime("%m")
        day = import_date.strftime("%d")
        
        target_dir = self.base_path / year / month / day
        target_dir.mkdir(parents=True, exist_ok=True)
        
        filename = source_path.name
        target_path = target_dir / filename
        
        # 3. Handle collision (suffixing)
        counter = 1
        while target_path.exists():
            # Check if it's strictly identical (same content)
            existing_hash = self.compute_sha256(target_path)
            if existing_hash == initial_hash:
                logger.info(f"File {filename} already exists with same hash in archive. Returning existing path.")
                return str(target_path), initial_hash
            
            # Different content, rename
            name_stem = source_path.stem
            ext = source_path.suffix
            target_path = target_dir / f"{name_stem}_{counter}{ext}"
            counter += 1

        # 4. Copy file (Copy then delete to ensure safety)
        try:
            shutil.copy2(source_path, target_path)
            logger.info(f"Copied {source_path} to {target_path}")
            
            # 5. Verify Hash
            final_hash = self.compute_sha256(target_path)
            if final_hash != initial_hash:
                # CRITICAL ERROR
                os.remove(target_path) # Rollback
                raise ValueError(f"Bit-exact verification failed! Src: {initial_hash} vs Dest: {final_hash}")
                
            # 6. Delete source (since we are moving)
            os.remove(source_path)
            
            return str(target_path), initial_hash
            
        except Exception as e:
            logger.error(f"Archival failed: {e}")
            raise e
