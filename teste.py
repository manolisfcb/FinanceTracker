import requests

# URL que apuntaste
url = "https://www.rad.cvm.gov.br/ENET/frmExibirArquivoIPEExterno.aspx?NumeroProtocoloEntrega=1363564"

# Headers simulando navegador (algunos servidores los requieren)
headers = {
    "User-Agent": "Mozilla/5.0"
}

# Hacemos la solicitud
response = requests.get(url, headers=headers)
print(response)
# Verificamos que la respuesta sea exitosa y contenga un PDF
if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
    with open("arquivo_cvm.pdf", "wb") as f:
        f.write(response.content)
    print("PDF descargado exitosamente.")
else:
    print("No se pudo descargar el PDF. Status:", response.status_code)