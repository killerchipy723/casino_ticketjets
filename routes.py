from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
from extensions import db
from models import Evento, Premio, Ganador, Usuario, TicketQR, HistorialCanje
from datetime import datetime, timedelta
from functools import wraps
import random
import urllib.parse
import uuid
import io
import qrcode
from sqlalchemy import func
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import qrcode
# --- DECORADOR DE ROLES ---
def login_required(roles=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'usuario_id' not in session:
                flash('Por favor inicia sesión.', 'warning')
                return redirect(url_for('login'))
            if roles and session.get('usuario_rol') not in roles:
                flash('No tienes permisos para acceder aquí.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def registrar_rutas(app): 

    # ==========================================
    # 🎰 RUTAS DE LA RULETA (PRESERVADAS)
    # ==========================================
    @app.route('/ruleta')
    def index():
        evento_activo = Evento.query.filter_by(activo=True).first()
        premios_db = Premio.query.filter_by(evento_id=evento_activo.id, activo=True).all() if evento_activo else []

    @app.route('/girar', methods=['POST'])
    def girar():
        evento_activo = Evento.query.filter_by(activo=True).first()
        if not evento_activo: return jsonify({"error": "No hay un evento activo."}), 400
        premios_activos = Premio.query.filter_by(evento_id=evento_activo.id, activo=True).all()
        if not premios_activos: return jsonify({"error": "No hay premios."}), 400
        pesos = [p.probabilidad for p in premios_activos]
        premio_ganado = random.choices(premios_activos, weights=pesos, k=1)[0]
        session['premio_provisional'] = {'evento_id': evento_activo.id, 'premio': premio_ganado.titulo, 'es_joker': premio_ganado.es_joker}
        return jsonify({"success": True, "premio": premio_ganado.titulo, "es_joker": premio_ganado.es_joker})

    @app.route('/guardar_ganador', methods=['POST'])
    def guardar_ganador():
        datos_json = request.get_json(force=True, silent=True) or request.form
        nombre, telefono = datos_json.get('nombre'), datos_json.get('telefono')
        premio_prov = session.get('premio_provisional')
        if not premio_prov or not nombre or not telefono: return jsonify({"error": "Sesión expirada."}), 400
        codigo_ticket = f"ANANA-{uuid.uuid4().hex[:8].upper()}"
        nuevo_ganador = Ganador(evento_id=premio_prov['evento_id'], nombre=nombre, telefono=telefono, premio=premio_prov['premio'], codigo_ticket=codigo_ticket)
        db.session.add(nuevo_ganador)
        db.session.commit()
        session['ultimo_ganador'] = {'id': nuevo_ganador.id, 'nombre': nombre, 'telefono': telefono, 'premio': premio_prov['premio'], 'codigo_ticket': codigo_ticket}
        session.pop('premio_provisional', None)
        return jsonify({"success": True})

    @app.route('/reclamar')
    def reclamar():
        datos = session.get('ultimo_ganador')
        if not datos: return redirect(url_for('index'))
        num_whatsapp = "5493876552273"
        mensaje = f"¡Hola! Gané en ANANA CLUB 🎉\n🎁 Premio: {datos['premio']}\n👤 Nombre: {datos['nombre']}\n🎫 Ticket: {datos['codigo_ticket']}"
        link_whatsapp = f"https://wa.me/{num_whatsapp}?text={urllib.parse.quote(mensaje)}"
        return render_template('gracias.html', datos=datos, link_whatsapp=link_whatsapp)

    @app.route('/descargar_ticket/<codigo_ticket>')
    def descargar_ticket_publico(codigo_ticket):
        ganador = Ganador.query.filter_by(codigo_ticket=codigo_ticket).first_or_404()
        evento = Evento.query.get(ganador.evento_id)
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        card_x, card_y, card_w, card_h = 96, 76, 420, 640
        c.setFillColor(colors.HexColor('#12121a'))
        c.roundRect(card_x, card_y, card_w, card_h, 16, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor('#d4af37'))
        c.setLineWidth(2.5)
        c.roundRect(card_x, card_y, card_w, card_h, 16, fill=0, stroke=1)
        
        c.setFillColor(colors.HexColor('#d4af37'))
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(card_x + (card_w / 2), card_y + card_h - 45, "ANANA CLUB 🍍")
        
        url_validacion = f"https://ananaclub.online/admin/validar/{ganador.codigo_ticket}"
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(url_validacion)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        img_buffer = io.BytesIO()
        img_qr.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        c.drawImage(ImageReader(img_buffer), card_x + 135, card_y + 115, width=150, height=150)
        c.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Ticket_{ganador.codigo_ticket}.pdf", mimetype='application/pdf')


    # ==========================================
    # 🔐 AUTENTICACIÓN MULTINIVEL (LOGIN GENERAL)
    # ==========================================
    @app.route('/', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            usuario = Usuario.query.filter_by(username=username, activo=True).first()
            if usuario and usuario.check_password(password):
                session['usuario_id'] = usuario.id
                session['usuario_nombre'] = usuario.nombre_completo
                session['usuario_rol'] = usuario.rol
                return redirect(url_for('dashboard'))
            else:
                flash('Usuario o contraseña incorrectos.', 'danger')
                
        return render_template('auth/login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/dashboard')
    @login_required()
    def dashboard():
        rol = session.get('usuario_rol')
        if rol == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif rol == 'supervisor':
            return redirect(url_for('supervisor_dashboard'))
        else:
            return redirect(url_for('rrpp_dashboard'))


    # ==========================================
    # 🎟️ PANEL RRPP / VENDEDORES
    # ==========================================
    @app.route('/rrpp')
    @login_required(roles=['rrpp', 'supervisor', 'admin'])
    def rrpp_dashboard():
        usuario_id = session.get('usuario_id')
        tickets = TicketQR.query.filter_by(vendedor_id=usuario_id).order_by(TicketQR.fecha_creacion.desc()).all()
        
        total_generados = len(tickets)
        total_canjeados = sum(1 for t in tickets if t.estado == 'canjeado')
        total_parciales = sum(1 for t in tickets if t.estado == 'parcial')

        return render_template('rrpp/dashboard.html', 
                               tickets=tickets, 
                               total_generados=total_generados, 
                               total_canjeados=total_canjeados, 
                               total_parciales=total_parciales)

    @app.route('/rrpp/generar_pase', methods=['POST'])
    @login_required(roles=['rrpp', 'supervisor', 'admin'])
    def generar_pase():
        # Leer datos ya sea por JSON (fetch) o formulario tradicional
        datos_json = request.get_json(force=True, silent=True) or request.form
        
        nombre = datos_json.get('nombre')
        dni = datos_json.get('dni')
        whatsapp = str(datos_json.get('whatsapp', '')).replace('+', '').replace(' ', '').replace('-', '')
        
        try:
            cantidad = int(datos_json.get('cantidad', 1))
        except (ValueError, TypeError):
            cantidad = 1

        if not nombre or not dni or not whatsapp or cantidad < 1:
            return jsonify({"success": False, "error": "Todos los campos son obligatorios."}), 400

        codigo_ticket = f"ANANA-PASS-{uuid.uuid4().hex[:8].upper()}"

        nuevo_ticket = TicketQR(
            codigo_qr=codigo_ticket,
            vendedor_id=session['usuario_id'],
            titular_nombre=nombre,
            titular_dni=dni,
            titular_whatsapp=whatsapp,
            total_entradas=cantidad,
            entradas_usadas=0,
            estado='pendiente'
        )
        db.session.add(nuevo_ticket)
        db.session.commit()

        link_pdf = url_for('descargar_pdf_rrpp', codigo=codigo_ticket, _external=True)
        mensaje = (
            f"¡Hola {nombre}! 🎉 Aquí tienes tu Pase VIP para ANANA CLUB.\n\n"
            f"🎫 Titular: {nombre}\n"
            f"👥 Cantidad de entradas: {cantidad}\n"
            f"🆔 Código: {codigo_ticket}\n\n"
            f"Descarga tu ticket digital con QR aquí:\n{link_pdf}"
        )
        link_wa = f"https://wa.me/{whatsapp}?text={urllib.parse.quote(mensaje)}"
        
        return jsonify({"success": True, "link_whatsapp": link_wa, "codigo_ticket": codigo_ticket})

    # PDF del Pase RRPP
    @app.route('/rrpp/ticket/pdf/<codigo>')
    def descargar_pdf_rrpp(codigo):
        ticket = TicketQR.query.filter_by(codigo_qr=codigo).first_or_404()
        
        # 1. Generar código QR en memoria
        qr_img = qrcode.make(ticket.codigo_qr)
        qr_path = f"temp_qr_{codigo}.png"
        qr_img.save(qr_path)

        # 2. Configurar PDF (Tamaño tarjeta/recibo vertical elegante)
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40, leftMargin=40,
            topMargin=40, bottomMargin=40
        )
        
        story = []
        styles = getSampleStyleSheet()

        # Estilos personalizados Gold & Dark
        estilo_titulo = ParagraphStyle(
            'TituloVIP',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=18,
            textColor=colors.HexColor('#D4AF37'),
            alignment=1, # Centrado
            spaceAfter=10
        )
        
        estilo_sub = ParagraphStyle(
            'SubVIP',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor('#AAAAAA'),
            alignment=1,
            spaceAfter=15
        )

        estilo_texto = ParagraphStyle(
            'TextoVIP',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=12,
            textColor=colors.HexColor('#333333'),
            alignment=1,
            spaceAfter=6
        )

        estilo_codigo = ParagraphStyle(
            'CodigoVIP',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=colors.HexColor('#D4AF37'),
            alignment=1,
            spaceAfter=10
        )

        # 3. Logo Oficial (Asegúrate de tener la ruta correcta o usar el archivo estático)
        # Si tienes el logo en static/images/anana_logo_transparente.png:
        logo_path = "static/images/anana_logo_transparente.png"
        try:
            story.append(Image(logo_path, width=120, height=60))
            story.append(Spacer(1, 10))
        except:
            pass

        story.append(Paragraph("ANANA CLUB — VIP PASS", estilo_titulo))
        story.append(Paragraph("PRESENTAR ESTE QR EN PUERTA", estilo_sub))
        story.append(Spacer(1, 10))

        # 4. Imagen del Código QR en el centro
        story.append(Image(qr_path, width=160, height=160))
        story.append(Spacer(1, 15))

        # 5. Datos del Titular dentro de una tarjeta con bordes dorados
        data_tabla = [
            [Paragraph(f"<b>TITULAR:</b> {ticket.titular_nombre}", estilo_texto)],
            [Paragraph(f"<b>DNI:</b> {ticket.titular_dni}", estilo_texto)],
            [Paragraph(f"<b>ACCESOS EN EL PACK:</b> {ticket.total_entradas} Persona(s)", estilo_texto)],
            [Paragraph(f"<b>CÓDIGO:</b> {ticket.codigo_qr}", estilo_codigo)]
        ]

        tabla_ticket = Table(data_tabla, colWidths=[300])
        tabla_ticket.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FDFBF7')), # Fondo marfil muy elegante
            ('BOX', (0,0), (-1,-1), 2, colors.HexColor('#D4AF37')),     # Marco dorado principal
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5D8B0')),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))

        story.append(tabla_ticket)
        story.append(Spacer(1, 20))
        
        # Pie de página elegante
        estilo_footer = ParagraphStyle(
            'FooterVIP',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=8,
            textColor=colors.HexColor('#888888'),
            alignment=1
        )
        story.append(Paragraph("Este pase es personal e intransferible. Válido única vez según capacidad del pack.", estilo_footer))

        # Construir PDF
        doc.build(story)
        
        # Limpiar archivo temporal de QR
        import os
        if os.path.exists(qr_path):
            os.remove(qr_path)

        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"ANANA_VIP_{ticket.codigo_qr}.pdf",
            mimetype='application/pdf'
        )

    # ==========================================
    # 📷 ESCANEO Y VALIDACIÓN PARCIAL (PUERTA)
    # ==========================================
   # --- PANTALLA DE CONTROL Y VALIDACIÓN DE QR ---
    @app.route('/admin/escaneo')
    @login_required(roles=['admin', 'supervisor', 'rrpp'])
    def vista_escaneo():
        return render_template('admin/escaneo.html')

    @app.route('/admin/validar/<codigo>', methods=['GET', 'POST'])
    @login_required(roles=['admin', 'supervisor', 'rrpp'])
    def validar_ticket(codigo):
        ticket = TicketQR.query.filter_by(codigo_qr=codigo).first()

        if request.method == 'POST':
            if not ticket:
                flash('El ticket no existe.', 'danger')
                return redirect(url_for('vista_escaneo'))

            disponibles = ticket.total_entradas - ticket.entradas_usadas
            
            try:
                ingresan = int(request.form.get('entradas_a_ingresar', 0))
            except ValueError:
                ingresan = 0

            if ingresan <= 0 or ingresan > disponibles:
                flash('Cantidad de ingresos no válida.', 'danger')
                return redirect(url_for('validar_ticket', codigo=codigo))

            # Actualizar contador
            ticket.entradas_usadas += ingresan
            
            # Actualizar estado según cantidad restante
            if ticket.entradas_usadas >= ticket.total_entradas:
                ticket.estado = 'canjeado'
            else:
                ticket.estado = 'parcial'

            db.session.commit()
            flash(f'✅ Ingreso autorizado para {ingresan} persona(s).', 'success')
            return redirect(url_for('validar_ticket', codigo=codigo))

        return render_template('admin/resultado_scan.html', ticket=ticket)
    # ==========================================
    # 📊 PANEL SUPERVISOR / ADMIN GENERAL
    # ==========================================
    @app.route('/admin/dashboard')
    @login_required(roles=['admin', 'supervisor'])
    def admin_dashboard():
        tickets = TicketQR.query.order_by(TicketQR.fecha_creacion.desc()).all()
        vendedores = Usuario.query.filter_by(rol='rrpp').all()
        return render_template('admin/dashboard_rrpp.html', tickets=tickets, vendedores=vendedores)

    @app.route('/supervisor')
    @login_required(roles=['supervisor', 'admin'])
    def supervisor_dashboard():
        return redirect(url_for('admin_dashboard'))


    @app.route('/admin/usuario/agregar', methods=['POST'])
    @login_required(roles=['admin'])
    def agregar_usuario():
        nombre_completo = request.form.get('nombre_completo')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        rol = request.form.get('rol', 'rrpp')

        if not nombre_completo or not username or not password:
            flash('Todos los campos son requeridos.', 'danger')
            return redirect(url_for('admin_dashboard'))

        usuario_existente = Usuario.query.filter_by(username=username).first()
        if usuario_existente:
            flash('El nombre de usuario ya existe. Por favor elija otro.', 'danger')
            return redirect(url_for('admin_dashboard'))

        nuevo_usuario = Usuario(
            username=username,
            nombre_completo=nombre_completo,
            rol=rol,
            activo=True
        )
        nuevo_usuario.set_password(password)
        db.session.add(nuevo_usuario)
        db.session.commit()

        flash(f'✅ Usuario {username} ({rol.upper()}) creado con éxito.', 'success')
        return redirect(url_for('admin_dashboard'))


    # --- EDITAR USUARIO / VENDEDOR ---
    @app.route('/admin/usuario/editar/<int:id>', methods=['POST'])
    @login_required(roles=['admin'])
    def editar_usuario(id):
        usuario = Usuario.query.get_or_404(id)
        
        nombre_completo = request.form.get('nombre_completo')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        rol = request.form.get('rol', 'rrpp')

        if not nombre_completo or not username:
            flash('Nombre y Usuario son campos obligatorios.', 'danger')
            return redirect(url_for('admin_dashboard'))

        # Verificar si cambió el username y que no esté duplicado
        usuario_existente = Usuario.query.filter(Usuario.username == username, Usuario.id != id).first()
        if usuario_existente:
            flash('Ese nombre de usuario ya está ocupado por otra persona.', 'danger')
            return redirect(url_for('admin_dashboard'))

        usuario.nombre_completo = nombre_completo
        usuario.username = username
        usuario.rol = rol

        # Cambiar contraseña únicamente si la completó
        if password:
            usuario.set_password(password)

        db.session.commit()
        flash(f'✅ Usuario {username} actualizado correctamente.', 'success')
        return redirect(url_for('admin_dashboard'))

    # --- ELIMINAR USUARIO / VENDEDOR ---
    @app.route('/admin/usuario/eliminar/<int:id>')
    @login_required(roles=['admin'])
    def eliminar_usuario(id):
        # Evitar que el administrador se elimine a sí mismo
        if id == session.get('usuario_id'):
            flash('No puedes eliminar tu propio usuario activo.', 'danger')
            return redirect(url_for('admin_dashboard'))

        usuario = Usuario.query.get_or_404(id)
        db.session.delete(usuario)
        db.session.commit()

        flash(f'🗑️ Usuario {usuario.username} eliminado correctamente.', 'success')
        return redirect(url_for('admin_dashboard'))