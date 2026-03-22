import asyncio
import logging
import os
import sys

# Ajouter le chemin du projet pour permettre les imports app.*
sys.path.append(os.getcwd())

from app.services.catalog_service import CatalogService

# Configuration du logging minimal pour le script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    # Par défaut, on génère dans backend/docs/ (car le script tourne dans /app/)
    # Mais si on l'appelle depuis la racine du projet, on veut docs/
    docs_dir = "docs"
    count = await CatalogService.generate_catalog(docs_dir=docs_dir)
    print(f"✅ Terminé : {count} entrées traitées.")

if __name__ == "__main__":
    asyncio.run(main())
