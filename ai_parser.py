import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"

PROMPT = """
Vas a recibir texto libre con datos de una persona que alquila equipamiento.

El texto puede venir sin etiquetas, desordenado o en líneas separadas.

Tu tarea es INFERIR y EXTRAER los siguientes campos:

- nombre (nombre completo si es posible)
- dni (solo números, típico argentino 7-8 dígitos)
- telefono (normalizar a formato +549XXXXXXXXX si es posible)
- email (corregir si falta .com)
- domicilio (dirección personal del cliente si aparece)
- fecha_retiro (YYYY-MM-DD)
- fecha_devolucion (YYYY-MM-DD)
- equipo (producto alquilado)
- direccion_evento (lugar donde se usa el equipo)
- observaciones (cualquier otro dato relevante)

Reglas:
- Si ves un número de 7-8 dígitos aislado, probablemente es DNI.
- Si ves algo con @, probablemente es email.
- Si ves número largo tipo celular argentino, es teléfono.
- Si un dato no existe, devolver null.
- NO inventar datos.
- Responder SOLO JSON válido.
- NO agregar texto fuera del JSON.
"""

def extract_json_from_text(text):
    """
    Extrae el primer bloque JSON válido dentro del texto,
    incluso si viene envuelto en ```json ... ```
    """
    text = text.strip()

    # Si viene en markdown ```json ... ```
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("{") and part.endswith("}"):
                return part

    # Si no tiene markdown, buscar primer {...}
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:
        return text[start:end+1]

    return text

def parse_text(texto):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": PROMPT + "\n\nTexto:\n" + texto,
            "stream": False
        }
    )

    if response.status_code != 200:
        raise Exception(f"Error Ollama: {response.text}")

    result = response.json()
    raw_output = result.get("response", "")

    cleaned_json = extract_json_from_text(raw_output)

    try:
        data = json.loads(cleaned_json)
    except json.JSONDecodeError:
        print("Respuesta cruda del modelo:\n", raw_output)
        raise Exception("El modelo devolvió un JSON inválido.")

    # Asegurar que siempre existan las claves esperadas
    expected_fields = [
        "nombre",
        "dni",
        "telefono",
        "email",
        "domicilio",
        "fecha_retiro",
        "fecha_devolucion",
        "equipo",
        "direccion_evento",
        "observaciones"
    ]

    for field in expected_fields:
        if field not in data:
            data[field] = None

    return data