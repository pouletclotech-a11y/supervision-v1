import os

xls_path = "/app/data/ingress/YPSILON_STAB_FINAL.xls"
meta_path = xls_path + ".meta.json"

content = [
    "TITRE EXPORT\t\t\t\t\t",
    "69000\tCLIENT ALPHA\t27/01/2026 10:00:00\tAPPARITION\tCODE1\tDETAILS 1",
    "\tLUN\t10:05:00\tDISPARITION\tCODE1\tDETAILS 1",
    "75001\tCLIENT BETA\t28/01/2026 11:00:00\tMISE EN SERVICE\tCODE2\tDETAILS 2",
]

with open(xls_path, 'w') as f:
    f.write("\n".join(content))

with open(meta_path, 'w') as f:
    f.write('{"sender_email": "test@supervision.local"}')

print(f"Created {xls_path}")
