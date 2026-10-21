from extensions import db
from datetime import datetime

class Evento(db.Model):
    __tablename__ = 'eventos'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(150), nullable=False)               # Ej: "Noche de Casino - Sáb 24.10"
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow) # Capturada automáticamente
    fecha_expiracion = db.Column(db.DateTime, nullable=False)        # Límite de la jornada
    activo = db.Column(db.Boolean, default=True)                     # Estado del evento

    premios = db.relationship('Premio', backref='evento', lazy=True, cascade="all, delete-orphan")

class Premio(db.Model):
    __tablename__ = 'premios'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    evento_id = db.Column(db.Integer, db.ForeignKey('eventos.id'), nullable=False)
    titulo = db.Column(db.String(150), nullable=False)               # Ej: "Combo 5 Amigos + 1 Botella"
    probabilidad = db.Column(db.Integer, default=10)                 # Peso/frecuencia
    es_joker = db.Column(db.Boolean, default=False)                  # Comodín/Joker
    activo = db.Column(db.Boolean, default=True)

class Ganador(db.Model):
    __tablename__ = 'ganadores'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    evento_id = db.Column(db.Integer, db.ForeignKey('eventos.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(30), nullable=False)
    premio = db.Column(db.String(150), nullable=False)
    codigo_ticket = db.Column(db.String(50), unique=True, nullable=False) # Código único para el QR
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    reclamado = db.Column(db.Boolean, default=False)