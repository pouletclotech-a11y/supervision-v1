import pandas as pd
import os

# Nordedata TSV v10
df_nord = pd.DataFrame([
    ['02/03/2026', '15:10:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V10 APPARITION'],
    ['02/03/2026', '15:15:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V10 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])

path_nord = '/app/data/ingress/nordedata_final_v10.xls'
with open(path_nord, 'w', encoding='latin-1') as f:
    df_nord.to_csv(f, sep='\t', index=False, header=False)

# SPGO XLSX v10
df_spgo = pd.DataFrame([
    ['02/03/2026', '15:11:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V10 APPARITION'],
    ['02/03/2026', '15:16:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V10 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])
path_spgo = '/app/data/ingress/spgo_final_v10.xlsx'
df_spgo.to_excel(path_spgo, index=False, header=False, engine='openpyxl')

print("Tests v10 created inside /app/data/ingress/")
