import os
import shutil
from pathlib import Path

def reinject():
    archive_dir = Path("c:/Users/poule/Documents/TLS YPSILON/supervision-v1/archive")
    ingress_dir = Path("c:/Users/poule/Documents/TLS YPSILON/supervision-v1/dropbox_in")
    
    print(f"--- REINJECTING FROM {archive_dir} TO {ingress_dir} ---")
    
    # 1. Collect all files from archive (processed, duplicates, etc)
    # Focus on duplicates where most of today's files went
    folders_to_scan = [
        archive_dir / "duplicates",
        archive_dir / "2026/02/25",
        archive_dir / "unmatched/2026/02/25",
        archive_dir / "error/2026/02/25"
    ]
    
    count = 0
    for folder in folders_to_scan:
        if not folder.exists():
            continue
            
        print(f"Scanning {folder}...")
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in ['.xls', '.xlsx', '.pdf']:
                # Copy to ingress
                target = ingress_dir / f.name
                shutil.copy2(f, target)
                count += 1
                
    print(f"Re-injected {count} files for replay.")

if __name__ == "__main__":
    reinject()
