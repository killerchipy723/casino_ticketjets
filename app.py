from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import urllib.parse

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clave_secreta_super_segura_boliche_2026'

# --- CONFIGURACIÓN DE CONEXIÓN A MYSQL (WORKBENCH) ---
DB_USER = 'root'            # Tu usuario de MySQL Workbench
DB_PASSWORD = 'admin123'    # Tu contraseña de MySQL Workbench
DB_HOST = 'localhost'       # Servidor (127.0.0.1)
DB_PORT = '3306'            # Puerto por defecto de MySQL
DB_NAME = 'ruleta_boliche'  # Nombre de la base de datos

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS DE BASE DE DATOS (Mapeados a MySQL) ---

class Premio(db.Model):
    __tablename__ = 'premios'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    titulo = db.Column(db.String(150), nullable=False)        # Ej: "Combo 5 Amigos + 1 Botella"
    probabilidad = db.Column(db.Integer, default=10)         # Peso/frecuencia del premio
    es_joker = db.Column(db.Boolean, default=False)          # Indica si es el premio comodín/Joker
    activo = db.Column(db.Boolean, default=True)

class Ganador(db.Model):
    __tablename__ = 'ganadores'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(30), nullable=False)
    premio = db.Column(db.String(150), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    reclamado = db.Column(db.Boolean, default=False)

# Crear las tablas en MySQL e insertar premios por defecto si la tabla está vacía
with app.app_context():
    db.create_all()
    if Premio.query.count() == 0:
        premios_iniciales = [
            Premio(titulo="Combo 5 Entradas + 1 Fernet", probabilidad=20, es_joker=False),
            Premio(titulo="2x1 en Barra hasta las 2 AM", probabilidad=40, es_joker=False),
            Premio(titulo="Consumición Gratis", probabilidad=30, es_joker=False),
            Premio(titulo="🃏 JOKER: VIP Pass + Botella Champagne", probabilidad=10, es_joker=True)
        ]
        db.session.bulk_save_objects(premios_iniciales)
        db.session.commit()
        print("-> Se crearon las tablas y premios iniciales en MySQL Workbench.")


# --- RUTAS PRINCIPALES (VISTA PÚBLICA / CELULAR) ---

@app.route('/')
def index():
    premios = Premio.query.filter_by(activo=True).all()
    return render_template('index.html', premios=premios)

@app.route('/girar', methods=['POST'])
def girar():
    premios_activos = Premio.query.filter_by(activo=True).all()
    if not premios_activos:
        return jsonify({"error": "No hay premios disponibles en este momento."}), 400

    # Lógica de Sorteo Ponderada
    pesos = [p.probabilidad for p in premios_activos]
    premio_ganado = random.choices(premios_activos, weights=pesos, k=1)[0]

    # Guardamos provisionalmente el premio obtenido en la sesión antes de pedir datos
    session['premio_provisional'] = {
        'premio': premio_ganado.titulo,
        'es_joker': premio_ganado.es_joker
    }

    return jsonify({
        "success": True,
        "premio": premio_ganado.titulo,
        "es_joker": premio_ganado.es_joker
    })

@app.route('/guardar_ganador', methods=['POST'])
def guardar_ganador():
    datos_json = request.get_json(force=True, silent=True) or request.form
    nombre = datos_json.get('nombre')
    telefono = datos_json.get('telefono')
    
    premio_prov = session.get('premio_provisional')
    if not premio_prov or not nombre or not telefono:
        return jsonify({"error": "Datos incompletos o sesión expirada."}), 400

    # Guardado definitivo del ganador en MySQL Workbench
    nuevo_ganador = Ganador(
        nombre=nombre,
        telefono=telefono,
        premio=premio_prov['premio']
    )
    db.session.add(nuevo_ganador)
    db.session.commit()

    # Consolidamos los datos finales en la sesión para la pantalla de agradecimiento/WhatsApp
    session['ultimo_ganador'] = {
        'nombre': nombre,
        'telefono': telefono,
        'premio': premio_prov['premio'],
        'es_joker': premio_prov['es_joker']
    }
    
    # Limpiamos el provisional
    session.pop('premio_provisional', None)

    return jsonify({"success": True})

@app.route('/reclamar')
def reclamar():
    datos = session.get('ultimo_ganador')
    if not datos:
        return redirect(url_for('index'))

    num_whatsapp_boliche = "5493874000000"  # Reemplazar por tu número real de WhatsApp
    
    mensaje = (
        f"¡Hola! Gané en la Ruleta del Boliche 🎉\n"
        f"🎁 Premio: {datos['premio']}\n"
        f"👤 Nombre: {datos['nombre']}\n"
        f"📱 Teléfono: {datos['telefono']}"
    )
    
    link_whatsapp = f"https://wa.me/{num_whatsapp_boliche}?text={urllib.parse.quote(mensaje)}"
    
    return render_template('gracias.html', datos=datos, link_whatsapp=link_whatsapp)


# --- PANEL DE ADMINISTRACIÓN ---

@app.route('/admin')
def admin_dashboard():
    premios = Premio.query.order_by(Premio.id.desc()).all()
    ganadores = Ganador.query.order_by(Ganador.fecha.desc()).all()
    return render_template('admin/dashboard.html', premios=premios, ganadores=ganadores)

@app.route('/admin/premio/agregar', methods=['POST'])
def agregar_premio():
    titulo = request.form.get('titulo')
    probabilidad = request.form.get('probabilidad', type=int, default=10)
    es_joker = 'es_joker' in request.form

    if titulo:
        nuevo_premio = Premio(
            titulo=titulo,
            probabilidad=probabilidad,
            es_joker=es_joker
        )
        db.session.add(nuevo_premio)
        db.session.commit()
        flash('Premio agregado correctamente', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/premio/estado/<int:id>')
def cambiar_estado_premio(id):
    premio = Premio.query.get_or_404(id)
    premio.activo = not premio.activo
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/premio/eliminar/<int:id>')
def eliminar_premio(id):
    premio = Premio.query.get_or_404(id)
    db.session.delete(premio)
    db.session.commit()
    flash('Premio eliminado de MySQL', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/ganador/reclamado/<int:id>')
def marcar_reclamado(id):
    ganador = Ganador.query.get_or_404(id)
    ganador.reclamado = not ganador.reclamado
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)