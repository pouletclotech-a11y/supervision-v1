import pandas as pd
import os

# Nordedata TSV
df_nord = pd.DataFrame([
    ['02/03/2026', '14:30:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 APPARITION'],
    ['02/03/2026', '14:35:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])

path_nord = '/app/data/ingress/nordedata_final_v5.xls'
with open(path_nord, 'w', encoding='latin-1') as f:
    df_nord.to_csv(f, sep='\t', index=False, header=False)

# SPGO XLSX
df_spgo = pd.DataFrame([
    ['02/03/2026', '14:31:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 APPARITION'],
    ['02/03/2026', '14:36:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])
path_spgo = '/app/data/ingress/spgo_final_v5.xlsx'
df_spgo.to_excel(path_spgo, index=False, header=False, engine='openpyxl')

print("Tests created inside /app/data/ingress/")
