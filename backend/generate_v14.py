import pandas as pd
import os

# Nordedata TSV v14
df_nord = pd.DataFrame([
    ['02/03/2026', '17:00:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V14 APPARITION'],
    ['02/03/2026', '17:05:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V14 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])

path_nord = '/app/data/ingress/nordedata_final_v14.xls'
with open(path_nord, 'w', encoding='latin-1') as f:
    df_nord.to_csv(f, sep='\t', index=False, header=False)

# SPGO XLSX v14
df_spgo = pd.DataFrame([
    ['02/03/2026', '17:01:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V14 APPARITION'],
    ['02/03/2026', '17:06:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V14 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])
path_spgo = '/app/data/ingress/spgo_final_v14.xlsx'
df_spgo.to_excel(path_spgo, index=False, header=False, engine='openpyxl')

print("Tests v14 created inside /app/data/ingress/")
