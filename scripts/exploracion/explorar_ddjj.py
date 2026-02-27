import requests
import json
import warnings
warnings.filterwarnings('ignore')

r = requests.post(
    "https://www2.jus.gov.ar/consultaddjj/Home/ObtenerDeclaracionesJuradas",
    data={
        "Apellido": "POLINI",
        "Nombres": "",
        "CUIT": "",
        "page": 1,
        "Cargo": "",
        "Anio": 2024,
        "rows": 10,
        "recordsPage": 10,
        "NombreApellidoConsultante": "",
        "TipoDocumentoConsultante": "",
        "DocumentoConsultante": "",
        "DomicilioConsultante": "",
        "TelefonoConsultante": "",
        "OcupacionConsultante": "",
        "EmailConsultante": "",
        "MotivoConsulta": "",
        "OtroMotivoConsulta": "",
        "DestinoConsulta": "",
        "RazonSocialSolicitante": "",
        "DireccionTelefonoSolicitante": "",
        "acepta": "true",
    },
    timeout=10, verify=False
)
print(f"Status: {r.status_code}")
print(r.text[:2000])