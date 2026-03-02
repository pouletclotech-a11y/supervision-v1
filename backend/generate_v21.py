import pandas as pd

# Nordedata TSV v21
df_nord = pd.DataFrame([
    ['02/03/2026', '20:30:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V21 APPARITION'],
    ['02/03/2026', '20:35:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V21 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])

path_nord = '/app/data/ingress/nordedata_final_v21.xls'
with open(path_nord, 'w', encoding='latin-1') as f:
    df_nord.to_csv(f, sep='\t', index=False, header=False)

# SPGO XLSX v21
df_spgo = pd.DataFrame([
    ['02/03/2026', '20:31:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V21 APPARITION'],
    ['02/03/2026', '20:36:00', 'C-75456', 'B2', 'TEST SPGO PHASE 3 V21 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])
path_spgo = '/app/data/ingress/spgo_final_v21.xlsx'
df_spgo.to_excel(path_spgo, index=False, header=False, engine='openpyxl')

print("Tests v21 created")
