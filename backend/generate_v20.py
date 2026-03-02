import pandas as pd

# Nordedata TSV v20
df_nord = pd.DataFrame([
    ['02/03/2026', '20:00:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V20 APPARITION'],
    ['02/03/2026', '20:05:00', 'C-69123', 'A1', 'TEST NORDEDATA PHASE 3 V20 DISPARITION']
], columns=['Date', 'Heure', 'Site', 'Code', 'Message'])

path_nord = '/app/data/ingress/nordedata_final_v20.xls'
with open(path_nord, 'w', encoding='latin-1') as f:
    df_nord.to_csv(f, sep='\t', index=False, header=False)

print("Tests v20 created")
