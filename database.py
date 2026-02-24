import sqlite3

DB_NAME = "rental.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        dni TEXT UNIQUE,
        telefono TEXT,
        email TEXT,
        domicilio TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rentals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        equipo TEXT,
        fecha_retiro TEXT,
        fecha_devolucion TEXT,
        direccion_evento TEXT,
        observaciones TEXT,
        estado TEXT DEFAULT 'activo',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    )
    """)

    conn.commit()
    conn.close()