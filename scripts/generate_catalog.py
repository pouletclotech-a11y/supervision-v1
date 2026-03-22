import asyncio
import csv
import os
from datetime import datetime
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.core.config import settings

async def generate_catalog():
    print("🚀 Démarrage de la génération du catalogue...")
    async with AsyncSessionLocal() as session:
        # Requête d'agrégation
        # On regroupe par code, message, provider et catégorie
        sql = """
        SELECT 
            COALESCE(e.raw_code, '') as code,
            COALESCE(e.normalized_message, '') as message,
            p.code as provider,
            COALESCE(e.category, 'UNK') as category,
            COUNT(*) as occurrences,
            MAX(e.time) as last_seen
        FROM events e
        JOIN imports i ON e.import_id = i.id
        JOIN monitoring_providers p ON i.provider_id = p.id
        GROUP BY 1, 2, 3, 4
        ORDER BY occurrences DESC, last_seen DESC
        """
        
        result = await session.execute(text(sql))
        rows = result.all()
        
        # 1. Génération CSV
        csv_path = "docs/ANNUAIRE_CODES.csv"
        os.makedirs("docs", exist_ok=True)
        
        with open(csv_path, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Code", "Message", "Provider", "Catégorie", "Occurrences", "Dernière_Occurrence", "Date_Mise_A_Jour"])
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        
        print(f"✅ CSV généré : {csv_path}")
        
        # 2. Génération Markdown (Top 100 pour lisibilité)
        md_path = "docs/ANNUAIRE_CODES.md"
        with open(md_path, mode='w', encoding='utf-8') as f:
            f.write("# Annuaire des Codes et Messages (Top 100)\n\n")
            f.write(f"*Dernière mise à jour globale : {now_str}*\n\n")
            f.write("| Code | Message | Provider | Cat | Occ. | Dernière vue | MàJ |\n")
            f.write("| :--- | :--- | :--- | :--- | :---: | :--- | :--- |\n")
            
            for r in rows[:100]:
                f.write(f"| `{r.code}` | {r.message} | {r.provider} | {r.category} | {r.occurrences} | {r.last_seen.strftime('%d/%m/%Y %H:%M') if r.last_seen else '-'} | {datetime.now().strftime('%d/%m/%Y')} |\n")
                
        print(f"✅ Markdown généré : {md_path}")

if __name__ == "__main__":
    asyncio.run(generate_catalog())
