from openpyxl import Workbook
from datetime import datetime, timedelta
import os

def generate_test_v13():
    now = datetime.now()
    
    # 1. FILE V13 (Site 69013)
    wb_v13 = Workbook()
    ws_v13 = wb_v13.active
    ws_v13.append(['TITRE EXPORT'])
    test_data = [
        ['69013', 'CLIENT_V13', (now - timedelta(minutes=130)).strftime('%d/%m/%Y %H:%M:%S'), 'DEFAUT SECTEUR', '301', 'ZONE 1'],
        ['69013', 'CLIENT_V13', (now - timedelta(minutes=128)).strftime('%d/%m/%Y %H:%M:%S'), 'RETOUR SECTEUR', '301R', 'ZONE 1'],
        ['69013', 'CLIENT_V13', (now - timedelta(minutes=125)).strftime('%d/%m/%Y %H:%M:%S'), 'ALARME IP', '710', 'ETH'],
        ['69013', 'CLIENT_V13', (now - timedelta(minutes=123)).strftime('%d/%m/%Y %H:%M:%S'), 'RETOUR IP', '710R', 'ETH'],
        ['69013', 'CLIENT_V13', (now - timedelta(minutes=120)).strftime('%d/%m/%Y %H:%M:%S'), 'EJECTION ZONE', '570', 'Z4'],
        ['69013', 'CLIENT_V13', (now - timedelta(minutes=115)).strftime('%d/%m/%Y %H:%M:%S'), 'ALARME INTRUSION ZONE 2', '01', 'BUREAU']
    ]
    for row in test_data: ws_v13.append(row)
    wb_v13.save('/app/data/ingress/YPSILON_TEST_ROADMAP11_V13.xlsx')
    print("Generated V13")

if __name__ == "__main__":
    generate_test_v13()
