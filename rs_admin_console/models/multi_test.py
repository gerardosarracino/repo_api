import requests
import time

def probar_login_uhuu(num_pruebas=10):
    url = "https://apiqa.myuhuu.com/odoo/login"
    payload = {
        "url": "https://montaura.odoo-erp.online/",
        "db": "montaura",
        "usr": "fernandoh@merxbp.com",
        "pwd": "q1w2e3r4"
    }
    headers = {
        "Content-Type": "application/json"
    }

    for i in range(num_pruebas):
        print(f"\n🔁 Prueba #{i+1}")
        try:
            start = time.time()
            response = requests.post(url, json=payload, headers=headers)
            elapsed = time.time() - start

            print(f"⏱ Tiempo de respuesta: {elapsed:.2f} segundos")
            print(f"📦 Código de estado: {response.status_code}")
            try:
                print("📨 Respuesta JSON:", response.json())
            except Exception:
                print("📨 Respuesta cruda:", response.text)
        except Exception as e:
            print(f"❌ Error al realizar la prueba #{i+1}: {e}")

# 🔧 Llamar la función con el número de pruebas que quieras
probar_login_uhuu(num_pruebas=30)  # Cambia a 20, 50, etc.
