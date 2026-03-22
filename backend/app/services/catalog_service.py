import csv
import os
import logging
from datetime import datetime
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("catalog-service")

class CatalogService:
    @staticmethod
    async def generate_catalog(docs_dir: str = "docs"):
        """
        Génère l'annuaire des codes et messages à partir des données réelles.
        Distingue les entrées par prestataire.
        """
        logger.info("🚀 Génération du catalogue des codes et messages...")
        
        async with AsyncSessionLocal() as session:
            repo = EventRepository(session)
            # For the file export, we want a large limit to catch everything
            rows = await repo.get_event_catalog(limit=50000)
            
            os.makedirs(docs_dir, exist_ok=True)
            
            csv_path = os.path.join(docs_dir, "ANNUAIRE_CODES.csv")
            md_path = os.path.join(docs_dir, "ANNUAIRE_CODES.md")
            
            now = datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            date_today = now.strftime("%d/%m/%Y")
            
            # 1. Génération CSV
            try:
                with open(csv_path, mode='w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Code", "Message", "Provider", "Catégorie", "Occurrences", "Dernière_Occurrence", "Date_Mise_A_Jou"])
                    for r in rows:
                        writer.writerow([
                            r.code, 
                            r.message, 
                            r.provider, 
                            r.category, 
                            r.occurrences, 
                            r.last_seen.strftime("%Y-%m-%d %H:%M:%S") if r.last_seen else "",
                            now_str
                        ])
                logger.info(f"✅ CSV généré : {csv_path}")
            except Exception as e:
                logger.error(f"Erreur lors de la génération du CSV : {e}")

            # 2. Génération Markdown (Top 200)
            try:
                with open(md_path, mode='w', encoding='utf-8') as f:
                    f.write("# Annuaire des Codes et Messages (Top 200)\n\n")
                    f.write(f"*Dernière mise à jour globale : {now_str}*\n\n")
                    f.write("| Code | Message | Provider | Cat | Occ. | Dernière vue | MàJ |\n")
                    f.write("| :--- | :--- | :--- | :--- | :---: | :--- | :--- |\n")
                    
                    for r in rows[:200]:
                        last_seen_str = r.last_seen.strftime('%d/%m/%Y %H:%M') if r.last_seen else '-'
                        f.write(f"| `{r.code}` | {r.message} | {r.provider} | {r.category} | {r.occurrences} | {last_seen_str} | {date_today} |\n")
                logger.info(f"✅ Markdown généré : {md_path}")
            except Exception as e:
                logger.error(f"Erreur lors de la génération du Markdown : {e}")
            
            return len(rows)
