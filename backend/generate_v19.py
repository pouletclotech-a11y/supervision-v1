import pandas as pd

# Nordedata TSV v19
df_nord = pd.DataFrame([
    ['02/03/2026', '19:30:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V19 APPARITION'],
    ['02/03/2026', '19:35:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V19 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])

path_nord = '/app/data/ingress/nordedata_final_v19.xls'
with open(path_nord, 'w', encoding='latin-1') as f:
    df_nord.to_csv(f, sep='\t', index=False, header=False)

# SPGO XLSX v19
df_spgo = pd.DataFrame([
    ['02/03/2026', '19:31:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V19 APPARITION'],
    ['02/03/2026', '19:36:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V19 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])
path_spgo = '/app/data/ingress/spgo_final_v19.xlsx'
df_spgo.to_excel(path_spgo, index=False, header=False, engine='openpyxl')

print("Tests v19 created")
