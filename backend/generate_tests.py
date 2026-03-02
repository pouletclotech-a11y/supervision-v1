import pandas as pd
import os

# Nordedata TSV (Disguised .xls)
nord_file = "dropbox_in/nordedata_final_v3.xls"
df_nord = pd.DataFrame([
    ["02/03/2026", "14:30:00", "C-69123", "A1", "TEST NORDEDATA PHASE 3 APPARITION"],
    ["02/03/2026", "14:35:00", "C-69123", "A1", "TEST NORDEDATA PHASE 3 DISPARITION"]
], columns=["Date", "Heure", "Site", "Code", "Message"])

# Write as TSV with latin-1
with open(nord_file, "w", encoding="latin-1") as f:
    df_nord.to_csv(f, sep="\t", index=False, header=False)

print(f"Created {nord_file}")

# SPGO XLSX
spgo_file = "dropbox_in/spgo_final_v3.xlsx"
df_spgo = pd.DataFrame([
    ["02/03/2026", "14:31:00", "C-75456", "B2", "TEST SPGO PHASE 3 APPARITION"],
    ["02/03/2026", "14:36:00", "C-75456", "B2", "TEST SPGO PHASE 3 DISPARITION"]
], columns=["Date", "Heure", "Site", "Code", "Message"])

df_spgo.to_excel(spgo_file, index=False, header=False, engine='openpyxl')

print(f"Created {spgo_file}")
