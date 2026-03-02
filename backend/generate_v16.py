import pandas as pd
import os

# Nordedata TSV v16
df_nord = pd.DataFrame([
    ['02/03/2026', '18:00:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V16 APPARITION'],
    ['02/03/2026', '18:05:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V16 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])

path_nord = '/app/data/ingress/nordedata_final_v16.xls'
with open(path_nord, 'w', encoding='latin-1') as f:
    df_nord.to_csv(f, sep='\t', index=False, header=False)

# SPGO XLSX v16
df_spgo = pd.DataFrame([
    ['02/03/2026', '18:01:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V16 APPARITION'],
    ['02/03/2026', '18:06:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V16 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])
path_spgo = '/app/data/ingress/spgo_final_v16.xlsx'
df_spgo.to_excel(path_spgo, index=False, header=False, engine='openpyxl')

print("Tests v16 created inside /app/data/ingress/")
