import pandas as pd
import os

# Nordedata TSV v6
df_nord = pd.DataFrame([
    ['02/03/2026', '14:30:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V6 APPARITION'],
    ['02/03/2026', '14:35:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V6 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])

path_nord = '/app/data/ingress/nordedata_final_v6.xls'
with open(path_nord, 'w', encoding='latin-1') as f:
    df_nord.to_csv(f, sep='\t', index=False, header=False)

# SPGO XLSX v6
df_spgo = pd.DataFrame([
    ['02/03/2026', '14:31:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V6 APPARITION'],
    ['02/03/2026', '14:36:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V6 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])
path_spgo = '/app/data/ingress/spgo_final_v6.xlsx'
df_spgo.to_excel(path_spgo, index=False, header=False, engine='openpyxl')

print("Tests v6 created inside /app/data/ingress/")
