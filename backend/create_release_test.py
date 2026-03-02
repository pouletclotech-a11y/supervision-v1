import pandas as pd
import datetime
import os

# Format YPSILON EFI: 
# Col A: site_code (ex: 00032009)
# Col B: day (ex: Lun)
# Col C: date (ex: 27/01/2026)
# Col D: time (ex: 16:24:25)
# Col E: ?
# Col F: raw_code
# Col G: action/message

data = [
    ["00032009", "Lun", "27/01/2026", "16:24:25", "", "MVS", "APPARITION ALARME"],
    ["00032009", "Lun", "27/01/2026", "16:25:30", "", "MVS", "DISPARITION ALARME"],
    ["00032111", "Lun", "27/01/2026", "10:00:00", "", "TEST", "TEST CYCLIQUE"],
]

df = pd.DataFrame(data)
dest = "/app/data/ingress/release_v12_0_1_final.xlsx"
df.to_excel(dest, index=False, header=False)
print(f"File {dest} created.")
