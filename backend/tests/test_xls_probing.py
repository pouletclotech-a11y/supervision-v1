import os
import pytest
from pathlib import Path
from app.ingestion.utils import get_file_probe

def test_xls_probing_skip_blanks(tmp_path):
    """Vérifie que get_file_probe saute les lignes vides pour trouver les entêtes XLS."""
    # Création d'un fichier TSV factice avec des lignes vides au début
    file_path = tmp_path / "test_blanks.xls"
    content = "\n\n\nTITRE EXPORT\tSite\tDate\n1234\tSite A\t2026-02-24\n"
    with open(file_path, "w", encoding="latin-1") as f:
        f.write(content)
        
    headers, text = get_file_probe(file_path)
    
    assert headers is not None
    assert "TITRE EXPORT" in headers
    assert "Site" in headers
    assert len(headers) == 3

def test_xls_probing_no_headers(tmp_path):
    """Vérifie le comportement si aucune ligne n'est trouvée dans les 20 premières."""
    file_path = tmp_path / "empty.xls"
    content = "\n" * 25
    with open(file_path, "w", encoding="latin-1") as f:
        f.write(content)
        
    headers, text = get_file_probe(file_path)
    assert headers is None
