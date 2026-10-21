from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
from extensions import db
from models import Evento, Premio, Ganador
from datetime import datetime
import random
import urllib.parse
import uuid
import io
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

def registrar_rutas(app):

    # --- AUTENTICACIÓN ADMIN ---
    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if request.method == 'POST':
            usuario = request.form.get('usuario')
            password = request.form.get('password')
            if usuario == 'admin' and password == '123456':
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
        premios = Premio.query.filter_by(evento_id=evento_activo.id, activo=True).all() if evento_activo else []
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

        num_whatsapp = "5493874000000" # Reemplazar por tu número
        mensaje = f"¡Hola! Gané en ANANA CLUB 🎉\n🎁 Premio: {datos['premio']}\n👤 Nombre: {datos['nombre']}\n🎫 Ticket: {datos['codigo_ticket']}"
        link_whatsapp = f"https://wa.me/{num_whatsapp}?text={urllib.parse.quote(mensaje)}"

        return render_template('gracias.html', datos=datos, link_whatsapp=link_whatsapp)

    # --- DESCARGA DE TICKET PDF (DISPONIBLE PARA EL GANADOR) ---
    @app.route('/descargar_ticket/<codigo_ticket>')
    def descargar_ticket_publico(codigo_ticket):
        ganador = Ganador.query.filter_by(codigo_ticket=codigo_ticket).first_or_404()
        evento = Evento.query.get(ganador.evento_id)

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # Tarjeta Ticket VIP Oscura
        c.setFillColor(colors.HexColor('#0d0d14'))
        c.roundRect(40, 360, 532, 340, 15, fill=1, stroke=0)

        # Borde Doble Dorado
        c.setStrokeColor(colors.HexColor('#d4af37'))
        c.setLineWidth(3)
        c.roundRect(40, 360, 532, 340, 15, fill=0, stroke=1)
        c.setLineWidth(1)
        c.roundRect(45, 365, 522, 330, 12, fill=0, stroke=1)

        # Encabezado Marca y Evento
        c.setFillColor(colors.HexColor('#d4af37'))
        c.setFont("Helvetica-Bold", 24)
        c.drawString(70, 655, "ANANA CLUB 🍍")
        
        c.setFillColor(colors.HexColor('#ffffff'))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(70, 635, "PASAPORTE VIP / TICKET OFICIAL")

        c.setStrokeColor(colors.HexColor('#333344'))
        c.line(70, 620, 520, 620)

        # Nombre del Evento
        c.setFillColor(colors.HexColor('#f9e076'))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(70, 595, f"EVENTO: {evento.nombre if evento else 'ANANA NIGHTS'}")

        # Datos del Ganador
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(70, 560, "TITULAR:")
        c.setFont("Helvetica", 11)
        c.drawString(150, 560, ganador.nombre.upper())

        c.setFont("Helvetica-Bold", 11)
        c.drawString(70, 530, "PREMIO:")
        c.setFillColor(colors.HexColor('#d4af37'))
        c.drawString(150, 530, ganador.premio.upper())

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(70, 500, "CÓDIGO ID:")
        c.setFont("Helvetica", 11)
        c.drawString(150, 500, ganador.codigo_ticket)

        c.setFont("Helvetica-Bold", 11)
        c.drawString(70, 470, "FECHA:")
        c.setFont("Helvetica", 11)
        c.drawString(150, 470, ganador.fecha.strftime('%d/%m/%Y - %H:%M hs'))

        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(colors.HexColor('#aaaa88'))
        c.drawString(70, 410, "* Presentá este código QR en puerta o barra para validar tu beneficio.")

        # Generación de QR con URL directa de validación
        url_validacion = url_for('escaneo_validar', codigo=ganador.codigo_ticket, _external=True)
        
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(url_validacion)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")

        img_buffer = io.BytesIO()
        img_qr.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(img_buffer), 380, 440, width=150, height=150)

        c.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Ticket_{ganador.codigo_ticket}.pdf", mimetype='application/pdf')

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
    @app.route('/admin')
    def admin_dashboard():
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))

        eventos = Evento.query.order_by(Evento.id.desc()).all()
        evento_seleccionado_id = request.args.get('evento_id', type=int)
        
        evento_actual = Evento.query.get(evento_seleccionado_id) if evento_seleccionado_id else (Evento.query.filter_by(activo=True).first() or Evento.query.order_by(Evento.id.desc()).first())

        premios = Premio.query.filter_by(evento_id=evento_actual.id).all() if evento_actual else []
        ganadores = Ganador.query.filter_by(evento_id=evento_actual.id).order_by(Ganador.fecha.desc()).all() if evento_actual else []

        return render_template('admin/dashboard.html', eventos=eventos, evento_actual=evento_actual, premios=premios, ganadores=ganadores)

    @app.route('/admin/evento/agregar', methods=['POST'])
    def agregar_evento():
        if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
        nombre, fecha_exp = request.form.get('nombre'), request.form.get('fecha_expiracion')
        if nombre and fecha_exp:
            db.session.add(Evento(nombre=nombre, fecha_expiracion=datetime.strptime(fecha_exp, '%Y-%m-%dT%H:%M'), activo=True))
            db.session.commit()
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