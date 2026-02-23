import requests
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.senado.gob.ar"
url = f"{BASE}/parlamentario/sesiones/11-02-2026/13/downloadTac"

r = requests.get(url, timeout=15, verify=False)
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type')}")
print(f"Content-Disposition: {r.headers.get('content-disposition', 'N/A')}")
print(f"\nPrimeros 500 chars:")
print(r.text[:500])