from extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# --- MODELOS DE LA RULETA (Preservados para futuros eventos) ---
class Evento(db.Model):
    __tablename__ = 'eventos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    fecha_expiracion = db.Column(db.DateTime, nullable=False)
    activo = db.Column(db.Boolean, default=True)
    premios = db.relationship('Premio', backref='evento', lazy=True, cascade="all, delete-orphan")
    ganadores = db.relationship('Ganador', backref='evento', lazy=True, cascade="all, delete-orphan")

class Premio(db.Model):
    __tablename__ = 'premios'
    id = db.Column(db.Integer, primary_key=True)
    evento_id = db.Column(db.Integer, db.ForeignKey('eventos.id'), nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    probabilidad = db.Column(db.Integer, nullable=False, default=10)
    es_joker = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)

class Ganador(db.Model):
    __tablename__ = 'ganadores'
    id = db.Column(db.Integer, primary_key=True)
    evento_id = db.Column(db.Integer, db.ForeignKey('eventos.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(30), nullable=False)
    premio = db.Column(db.String(100), nullable=False)
    codigo_ticket = db.Column(db.String(50), unique=True, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    reclamado = db.Column(db.Boolean, default=False)


# --- NUEVOS MODELOS: SISTEMA DE RRPP Y TICKETING VIP ---
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre_completo = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default='rrpp') # 'admin', 'supervisor', 'rrpp'
    activo = db.Column(db.Boolean, default=True)
    
    tickets = db.relationship('TicketQR', backref='vendedor', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class TicketQR(db.Model):
    __tablename__ = 'tickets_qr'
    id = db.Column(db.Integer, primary_key=True)
    codigo_qr = db.Column(db.String(50), unique=True, nullable=False, index=True)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    titular_nombre = db.Column(db.String(100), nullable=False)
    titular_dni = db.Column(db.String(20), nullable=False)
    titular_whatsapp = db.Column(db.String(30), nullable=False)
    
    total_entradas = db.Column(db.Integer, nullable=False, default=1)
    entradas_usadas = db.Column(db.Integer, nullable=False, default=0)
    estado = db.Column(db.String(20), nullable=False, default='pendiente') # 'pendiente', 'parcial', 'canjeado'
    
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    historial = db.relationship('HistorialCanje', backref='ticket', lazy=True, cascade="all, delete-orphan")

    def actualizar_estado(self):
        if self.entradas_usadas == 0:
            self.estado = 'pendiente'
        elif 0 < self.entradas_usadas < self.total_entradas:
            self.estado = 'parcial'
        else:
            self.estado = 'canjeado'

class HistorialCanje(db.Model):
    __tablename__ = 'historial_canjes'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets_qr.id'), nullable=False)
    entradas_ingresadas = db.Column(db.Integer, nullable=False)
    validador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_canje = db.Column(db.DateTime, default=datetime.utcnow)