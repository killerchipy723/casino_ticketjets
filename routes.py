from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
from extensions import db
from models import Evento, Premio, Ganador
from datetime import datetime, timedelta
import random
import urllib.parse
import uuid
import io
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

def registrar_rutas(app):

    # --- AUTENTICACIÓN ADMIN ---
    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if request.method == 'POST':
            usuario = request.form.get('usuario')
            password = request.form.get('password')
            if usuario and usuario.strip().lower() == 'admin' and password == '123456':
                session['admin_logged_in'] = True
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Credenciales incorrectas.', 'danger')
        return render_template('admin/login.html')

    @app.route('/admin/logout')
    def admin_logout():
        session.pop('admin_logged_in', None)
        return redirect(url_for('admin_login'))

    # --- RUTAS PÚBLICAS (JUEGO Y RECLAMO) ---
    @app.route('/')
    def index():
        evento_activo = Evento.query.filter_by(activo=True).first()
        
        premios_db = Premio.query.filter_by(evento_id=evento_activo.id, activo=True).all() if evento_activo else []
        
        premios = [{
            'id': p.id,
            'titulo': p.titulo,
            'probabilidad': p.probabilidad,
            'es_joker': p.es_joker
        } for p in premios_db]
        
        return render_template('index.html', premios=premios, evento=evento_activo)

    @app.route('/girar', methods=['POST'])
    def girar():
        evento_activo = Evento.query.filter_by(activo=True).first()
        if not evento_activo:
            return jsonify({"error": "No hay un evento activo."}), 400

        premios_activos = Premio.query.filter_by(evento_id=evento_activo.id, activo=True).all()
        if not premios_activos:
            return jsonify({"error": "No hay premios configurados."}), 400

        pesos = [p.probabilidad for p in premios_activos]
        premio_ganado = random.choices(premios_activos, weights=pesos, k=1)[0]

        session['premio_provisional'] = {
            'evento_id': evento_activo.id,
            'premio': premio_ganado.titulo,
            'es_joker': premio_ganado.es_joker
        }

        return jsonify({"success": True, "premio": premio_ganado.titulo, "es_joker": premio_ganado.es_joker})

    @app.route('/guardar_ganador', methods=['POST'])
    def guardar_ganador():
        datos_json = request.get_json(force=True, silent=True) or request.form
        nombre = datos_json.get('nombre')
        telefono = datos_json.get('telefono')
        
        premio_prov = session.get('premio_provisional')
        if not premio_prov or not nombre or not telefono:
            return jsonify({"error": "Sesión expirada o datos incompletos."}), 400

        codigo_ticket = f"ANANA-{uuid.uuid4().hex[:8].upper()}"

        nuevo_ganador = Ganador(
            evento_id=premio_prov['evento_id'],
            nombre=nombre,
            telefono=telefono,
            premio=premio_prov['premio'],
            codigo_ticket=codigo_ticket
        )
        db.session.add(nuevo_ganador)
        db.session.commit()

        session['ultimo_ganador'] = {
            'id': nuevo_ganador.id,
            'nombre': nombre,
            'telefono': telefono,
            'premio': premio_prov['premio'],
            'codigo_ticket': codigo_ticket
        }
        session.pop('premio_provisional', None)
        return jsonify({"success": True})

    @app.route('/reclamar')
    def reclamar():
        datos = session.get('ultimo_ganador')
        if not datos:
            return redirect(url_for('index'))

        num_whatsapp = "5493876552273"
        mensaje = f"¡Hola! Gané en ANANA CLUB 🎉\n🎁 Premio: {datos['premio']}\n👤 Nombre: {datos['nombre']}\n🎫 Ticket: {datos['codigo_ticket']}"
        link_whatsapp = f"https://wa.me/{num_whatsapp}?text={urllib.parse.quote(mensaje)}"

        return render_template('gracias.html', datos=datos, link_whatsapp=link_whatsapp)

    # --- DESCARGA DE TICKET PDF VERTICAL VIP (CASINO GOLD) ---
    @app.route('/descargar_ticket/<codigo_ticket>')
    def descargar_ticket_publico(codigo_ticket):
        ganador = Ganador.query.filter_by(codigo_ticket=codigo_ticket).first_or_404()
        evento = Evento.query.get(ganador.evento_id)

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # Dimensiones de la tarjeta vertical centrada en hoja Letter (Ancho: 420, Alto: 640)
        card_x = 96
        card_y = 76
        card_w = 420
        card_h = 640

        # Fondo Oscuro Casino
        c.setFillColor(colors.HexColor('#12121a'))
        c.roundRect(card_x, card_y, card_w, card_h, 16, fill=1, stroke=0)

        # Borde Doble Dorado Elegante
        c.setStrokeColor(colors.HexColor('#d4af37'))
        c.setLineWidth(2.5)
        c.roundRect(card_x, card_y, card_w, card_h, 16, fill=0, stroke=1)
        c.setLineWidth(1)
        c.roundRect(card_x + 6, card_y + 6, card_w - 12, card_h - 12, 12, fill=0, stroke=1)

        # --- ENCABEZADO ---
        c.setFillColor(colors.HexColor('#d4af37'))
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(card_x + (card_w / 2), card_y + card_h - 45, "ANANA CLUB 🍍")
        
        c.setFillColor(colors.HexColor('#ffffff'))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(card_x + (card_w / 2), card_y + card_h - 65, "PASAPORTE VIP / TICKET OFICIAL")

        # Línea divisoria
        c.setStrokeColor(colors.HexColor('#333344'))
        c.line(card_x + 30, card_y + card_h - 80, card_x + card_w - 30, card_y + card_h - 80)

        # --- SECCIÓN GANASTE / PREMIO ---
        c.setFillColor(colors.HexColor('#d4af37'))
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(card_x + (card_w / 2), card_y + card_h - 105, "¡GANASTE EL PREMIO!")

        c.setFillColor(colors.HexColor('#ffffff'))
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(card_x + (card_w / 2), card_y + card_h - 135, ganador.premio.upper())

        # --- DATOS DEL GANADOR ---
        c.setFillColor(colors.HexColor('#aaaaaa'))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(card_x + 40, card_y + card_h - 180, "TITULAR:")
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(card_x + 120, card_y + card_h - 180, ganador.nombre.upper())

        c.setFillColor(colors.HexColor('#aaaaaa'))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(card_x + 40, card_y + card_h - 210, "TELÉFONO:")
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 11)
        c.drawString(card_x + 120, card_y + card_h - 210, str(ganador.telefono))

        c.setFillColor(colors.HexColor('#aaaaaa'))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(card_x + 40, card_y + card_h - 240, "CÓDIGO ID:")
        c.setFillColor(colors.HexColor('#d4af37'))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(card_x + 120, card_y + card_h - 240, ganador.codigo_ticket)

        # --- CÓDIGO QR CON DOMINIO PÚBLICO OFICIAL (SIN IP LOCAL) ---
        url_validacion = f"https://ananaclub.online/admin/validar/{ganador.codigo_ticket}"
        
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
        qr.add_data(url_validacion)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")

        img_buffer = io.BytesIO()
        img_qr.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        # Posicionar QR Grande en el centro inferior
        qr_size = 150
        c.drawImage(ImageReader(img_buffer), card_x + (card_w - qr_size) / 2, card_y + 115, width=qr_size, height=qr_size)

        # --- LÓGICA DE FECHA Y VALIDEZ (02:30 AM DÍA SIGUIENTE) ---
        try:
            fecha_base = evento.fecha_expiracion if (evento and hasattr(evento, 'fecha_expiracion') and evento.fecha_expiracion) else ganador.fecha
            if isinstance(fecha_base, datetime):
                dia_siguiente = fecha_base.date() + timedelta(days=1)
            else:
                dia_siguiente = fecha_base + timedelta(days=1)
            vencimiento_str = dia_siguiente.strftime('%d/%m/%Y')
        except Exception:
            vencimiento_str = "Fecha siguiente"

        texto_validez = f"⚠️ Válido hasta el {vencimiento_str} a las 02:30 hs."
        c.setFillColor(colors.HexColor('#ff6b6b'))
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(card_x + (card_w / 2), card_y + 90, texto_validez)

        c.setFillColor(colors.HexColor('#888899'))
        c.setFont("Helvetica-Oblique", 8)
        c.drawCentredString(card_x + (card_w / 2), card_y + 45, "Presentá este código QR en barra o puerta para canjear.")

        c.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Ticket_VIP_{ganador.codigo_ticket}.pdf", mimetype='application/pdf')
    # --- RUTA DE ESCANEO / VALIDACIÓN TÁCTIL (PARA PERSONAL) ---
    @app.route('/admin/escaneo')
    def admin_escaneo():
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return render_template('admin/escaneo.html')

    @app.route('/admin/validar/<codigo>', methods=['GET', 'POST'])
    def escaneo_validar(codigo):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))

        ganador = Ganador.query.filter_by(codigo_ticket=codigo).first()
        if not ganador:
            return render_template('admin/resultado_scan.html', error="❌ Ticket no encontrado en la base de datos.")

        if request.method == 'POST':
            ganador.reclamado = True
            db.session.commit()
            flash('✅ Ticket canjeado e inhabilitado correctamente.', 'success')

        return render_template('admin/resultado_scan.html', ganador=ganador)

    # --- PANEL ADMIN DASHBOARD ---
    from sqlalchemy import func

    @app.route('/admin')
    def admin_dashboard():
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))

        eventos = Evento.query.order_by(Evento.id.desc()).all()
        evento_seleccionado_id = request.args.get('evento_id', type=int)
        
        evento_actual = Evento.query.get(evento_seleccionado_id) if evento_seleccionado_id else (Evento.query.filter_by(activo=True).first() or Evento.query.order_by(Evento.id.desc()).first())

        premios = Premio.query.filter_by(evento_id=evento_actual.id).all() if evento_actual else []
        ganadores = Ganador.query.filter_by(evento_id=evento_actual.id).order_by(Ganador.fecha.desc()).all() if evento_actual else []

        # --- NUEVAS ESTADÍSTICAS (Equivalente a tu SQL agrupado por premio) ---
        total_participantes = 0
        stats_premios = []
        
        if evento_actual:
            total_participantes = Ganador.query.filter_by(evento_id=evento_actual.id).count()
            
            stats_premios = db.session.query(
                Ganador.premio, 
                func.count(Ganador.id).label('cantidad')
            ).filter_by(evento_id=evento_actual.id)\
            .group_by(Ganador.premio)\
            .order_by(func.count(Ganador.id).desc()).all()

        return render_template(
            'admin/dashboard.html', 
            eventos=eventos, 
            evento_actual=evento_actual, 
            premios=premios, 
            ganadores=ganadores,
            total_participantes=total_participantes,
            stats_premios=stats_premios
        )

    @app.route('/admin/evento/agregar', methods=['POST'])
    def agregar_evento():
        if not session.get('admin_logged_in'): 
            return redirect(url_for('admin_login'))
            
        nombre = request.form.get('nombre')
        fecha_exp = request.form.get('fecha_expiracion')
        
        if nombre and fecha_exp:
            # 1. Desactivar todos los eventos anteriores para que solo uno esté activo a la vez
            Evento.query.update({Evento.activo: False})
            
            # 2. Crear el nuevo evento como activo
            nuevo_evento = Evento(
                nombre=nombre, 
                fecha_expiracion=datetime.strptime(fecha_exp, '%Y-%m-%dT%H:%M'), 
                activo=True
            )
            db.session.add(nuevo_evento)
            db.session.commit()
            
            # 3. Copiar automáticamente los premios del evento anterior (o crear por defecto si es el primero)
            evento_anterior = Evento.query.filter(Evento.id != nuevo_evento.id).order_by(Evento.id.desc()).first()
            
            if evento_anterior:
                premios_anteriores = Premio.query.filter_by(evento_id=evento_anterior.id).all()
                for p in premios_anteriores:
                    nuevo_premio = Premio(
                        evento_id=nuevo_evento.id,
                        titulo=p.titulo,
                        probabilidad=p.probabilidad,
                        es_joker=p.es_joker,
                        activo=p.activo
                    )
                    db.session.add(nuevo_premio)
                db.session.commit()
            else:
                # Premios base por defecto si es el primer evento del sistema
                premios_default = [
                    Premio(evento_id=nuevo_evento.id, titulo="Trago Gratis", probabilidad=30, es_joker=False, activo=True),
                    Premio(evento_id=nuevo_evento.id, titulo="Ingreso VIP", probabilidad=20, es_joker=False, activo=True),
                    Premio(evento_id=nuevo_evento.id, titulo="Chupito en Barra", probabilidad=40, es_joker=False, activo=True),
                    Premio(evento_id=nuevo_evento.id, titulo="Botella de Champagne", probabilidad=10, es_joker=True, activo=True),
                ]
                db.session.add_all(premios_default)
                db.session.commit()
            
            # 4. Redirigir al panel admin mostrando directamente el nuevo evento
            return redirect(url_for('admin_dashboard', evento_id=nuevo_evento.id))
            
        return redirect(url_for('admin_dashboard'))

    @app.route('/admin/premio/agregar', methods=['POST'])
    def agregar_premio():
        if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
        evento_id, titulo = request.form.get('evento_id', type=int), request.form.get('titulo')
        if titulo and evento_id:
            db.session.add(Premio(evento_id=evento_id, titulo=titulo, probabilidad=request.form.get('probabilidad', type=int, default=10), es_joker='es_joker' in request.form))
            db.session.commit()
        return redirect(url_for('admin_dashboard', evento_id=evento_id))

    @app.route('/admin/premio/editar/<int:id>', methods=['POST'])
    def editar_premio(id):
        if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
        premio = Premio.query.get_or_404(id)
        premio.titulo = request.form.get('titulo')
        premio.probabilidad = request.form.get('probabilidad', type=int)
        premio.es_joker = 'es_joker' in request.form
        db.session.commit()
        return redirect(url_for('admin_dashboard', evento_id=premio.evento_id))

    @app.route('/admin/premio/eliminar/<int:id>')
    def eliminar_premio(id):
        if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
        premio = Premio.query.get_or_404(id)
        evento_id = premio.evento_id
        db.session.delete(premio)
        db.session.commit()
        return redirect(url_for('admin_dashboard', evento_id=evento_id))

    @app.route('/admin/ganador/reclamado/<int:id>')
    def marcar_reclamado(id):
        if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
        ganador = Ganador.query.get_or_404(id)
        ganador.reclamado = not ganador.reclamado
        db.session.commit()
        return redirect(url_for('admin_dashboard', evento_id=ganador.evento_id))

    @app.route('/admin/resetear_pruebas')
    def resetear_pruebas():
        try:
            Ganador.query.delete()
            db.session.commit()
            return """
            <script>
                localStorage.clear();
                alert('✅ Base de datos y memoria local limpiadas con éxito.');
                window.location.href = '/admin';
            </script>
            """
        except Exception as e:
            db.session.rollback()
            return f"<h1>❌ Error al resetear: {str(e)}</h1>"