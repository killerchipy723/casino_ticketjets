from flask import Flask
from extensions import db
from models import Evento, Premio
from routes import registrar_rutas
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_secreta_super_segura_boliche_2026'
app.config['TEMPLATES_AUTO_RELOAD'] = True  # <--- Esto evita que el servidor guarde caché de los HTML

# --- CONFIGURACIÓN DE CONEXIÓN A MYSQL (WORKBENCH) ---
DB_USER = 'c2710325_killer'            
DB_PASSWORD = 'SistemaIES6021'    
DB_HOST = '200.58.106.156'       
DB_PORT = '3306'            
DB_NAME = 'c2710325_base'  

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar SQLAlchemy con la app
db.init_app(app)

# Registrar las rutas desde el archivo routes.py
registrar_rutas(app)

# Crear las tablas e insertar evento y premios iniciales si la base está vacía
with app.app_context():
    db.create_all()
    if Evento.query.count() == 0:
        evento_demo = Evento(
            nombre="Noche de Casino - Inauguración",
            fecha_expiracion=datetime.now() + timedelta(days=1),
            activo=True
        )
        db.session.add(evento_demo)
        db.session.commit()

        premios_iniciales = [
            Premio(evento_id=evento_demo.id, titulo="Combo 5 Entradas + 1 Fernet", probabilidad=20, es_joker=False),
            Premio(evento_id=evento_demo.id, titulo="2x1 en Barra hasta las 2 AM", probabilidad=40, es_joker=False),
            Premio(evento_id=evento_demo.id, titulo="Consumición Gratis", probabilidad=30, es_joker=False),
            Premio(evento_id=evento_demo.id, titulo="🃏 JOKER: VIP Pass + Botella Champagne", probabilidad=10, es_joker=True)
        ]
        db.session.add_all(premios_iniciales)
        db.session.commit()
        print("-> Se crearon las tablas, el evento inicial y los premios en MySQL.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7300, debug=True)