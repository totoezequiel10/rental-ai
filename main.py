from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from database import init_db, get_connection
from ai_parser import parse_text
from openpyxl import Workbook
import io

app = FastAPI()
templates = Jinja2Templates(directory="templates")

init_db()


# =============================
# LISTADO CON BUSCADOR
# =============================
def get_full_list(busqueda=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT r.id as rental_id,
           c.nombre, c.dni, c.telefono, c.email, c.domicilio,
           r.equipo, r.fecha_retiro, r.fecha_devolucion,
           r.direccion_evento,
           r.estado, r.observaciones
    FROM clientes c
    JOIN rentals r ON c.id = r.cliente_id
    """

    params = []

    if busqueda:
        query += """
        WHERE
            c.nombre LIKE ?
            OR c.dni LIKE ?
            OR c.telefono LIKE ?
            OR c.email LIKE ?
            OR r.equipo LIKE ?
        """
        like_value = f"%{busqueda}%"
        params = [like_value] * 5

    query += " ORDER BY r.created_at DESC"

    cursor.execute(query, params)

    rows = cursor.fetchall()
    columnas = [col[0] for col in cursor.description]
    lista = [dict(zip(columnas, row)) for row in rows]

    conn.close()
    return lista


# =============================
# HOME
# =============================
@app.get("/", response_class=HTMLResponse)
def home(request: Request, q: str = None):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "lista": get_full_list(q),
        "busqueda": q
    })


# =============================
# PROCESAR INPUT IA
# =============================
@app.post("/procesar", response_class=HTMLResponse)
def procesar(request: Request, texto: str = Form(...)):
    data = parse_text(texto)

    conn = get_connection()
    cursor = conn.cursor()

    mensaje = "Datos guardados correctamente."
    cliente_recurrente = False

    cursor.execute("SELECT id FROM clientes WHERE dni = ?", (data["dni"],))
    cliente = cursor.fetchone()

    if cliente:
        cliente_id = cliente[0]
        cliente_recurrente = True

        cursor.execute("""
            UPDATE clientes
            SET nombre=?, telefono=?, email=?, domicilio=?
            WHERE id=?
        """, (
            data["nombre"],
            data["telefono"],
            data["email"],
            data["domicilio"],
            cliente_id
        ))
    else:
        cursor.execute("""
        INSERT INTO clientes (nombre, dni, telefono, email, domicilio)
        VALUES (?, ?, ?, ?, ?)
        """, (
            data["nombre"],
            data["dni"],
            data["telefono"],
            data["email"],
            data["domicilio"]
        ))
        cliente_id = cursor.lastrowid

    cursor.execute("""
    INSERT INTO rentals (
        cliente_id, equipo, fecha_retiro, fecha_devolucion,
        direccion_evento, observaciones
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        cliente_id,
        data["equipo"],
        data["fecha_retiro"],
        data["fecha_devolucion"],
        data["direccion_evento"],
        data["observaciones"]
    ))

    conn.commit()
    conn.close()

    if cliente_recurrente:
        mensaje = "Cliente recurrente detectado. Rental agregado."

    return templates.TemplateResponse("index.html", {
        "request": request,
        "lista": get_full_list(),
        "mensaje": mensaje,
        "busqueda": None
    })


# =============================
# MARCAR DEVUELTO
# =============================
@app.post("/marcar_devuelto/{rental_id}")
def marcar_devuelto(rental_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE rentals SET estado='devuelto' WHERE id=?", (rental_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)


# =============================
# ELIMINAR
# =============================
@app.post("/eliminar/{rental_id}")
def eliminar_rental(rental_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rentals WHERE id=?", (rental_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)


# =============================
# EDITAR FORM
# =============================
@app.get("/editar/{rental_id}", response_class=HTMLResponse)
def editar_form(request: Request, rental_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT r.id as rental_id,
           c.nombre, c.dni, c.telefono, c.email, c.domicilio,
           r.equipo, r.fecha_retiro, r.fecha_devolucion,
           r.direccion_evento, r.observaciones
    FROM clientes c
    JOIN rentals r ON c.id = r.cliente_id
    WHERE r.id = ?
    """, (rental_id,))

    row = cursor.fetchone()
    columnas = [col[0] for col in cursor.description]
    data = dict(zip(columnas, row))

    conn.close()

    return templates.TemplateResponse("editar.html", {
        "request": request,
        "data": data
    })


# =============================
# GUARDAR EDICIÓN
# =============================
@app.post("/editar/{rental_id}")
def guardar_edicion(
    rental_id: int,
    nombre: str = Form(...),
    telefono: str = Form(...),
    email: str = Form(...),
    domicilio: str = Form(...),
    equipo: str = Form(...),
    fecha_retiro: str = Form(...),
    fecha_devolucion: str = Form(...),
    direccion_evento: str = Form(...),
    observaciones: str = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE clientes
    SET nombre=?, telefono=?, email=?, domicilio=?
    WHERE id = (SELECT cliente_id FROM rentals WHERE id=?)
    """, (nombre, telefono, email, domicilio, rental_id))

    cursor.execute("""
    UPDATE rentals
    SET equipo=?, fecha_retiro=?, fecha_devolucion=?,
        direccion_evento=?, observaciones=?
    WHERE id=?
    """, (
        equipo,
        fecha_retiro,
        fecha_devolucion,
        direccion_evento,
        observaciones,
        rental_id
    ))

    conn.commit()
    conn.close()

    return RedirectResponse("/", status_code=303)


# =============================
# EXPORTAR EXCEL
# =============================
@app.get("/exportar")
def exportar_excel():
    lista = get_full_list()

    wb = Workbook()
    ws = wb.active
    ws.title = "Rentals"

    headers = [
        "Nombre", "DNI", "Teléfono", "Email", "Domicilio",
        "Equipo", "Retiro", "Devolución",
        "Dirección Evento", "Estado", "Observaciones"
    ]

    ws.append(headers)

    for row in lista:
        ws.append([
            row["nombre"],
            row["dni"],
            row["telefono"],
            row["email"],
            row["domicilio"],
            row["equipo"],
            row["fecha_retiro"],
            row["fecha_devolucion"],
            row["direccion_evento"],
            row["estado"],
            row["observaciones"],
        ])

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=rentals.xlsx"}
    )