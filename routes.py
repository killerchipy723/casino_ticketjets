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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from werkzeug.utils import secure_filename
import os

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
        evento_activo = Evento.query.filter_by(es_evento_actual=True, estado='activo').first()
        premios_db = Premio.query.filter_by(evento_id=evento_activo.id, activo=True).all() if evento_activo else []
        return render_template('index.html', premios=premios_db)

    @app.route('/girar', methods=['POST'])
    def girar():
        evento_activo = Evento.query.filter_by(es_evento_actual=True, estado='activo').first()
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
            
            # Verificamos usuario y que esté activo
            usuario = Usuario.query.filter_by(username=username, activo=True).first()
            
            # Opcional: Para darle un mensaje más claro si está inhabilitado
            usuario_inactivo = Usuario.query.filter_by(username=username, activo=False).first()

            if usuario and usuario.check_password(password):
                session['usuario_id'] = usuario.id
                session['usuario_nombre'] = usuario.nombre_completo
                session['usuario_rol'] = usuario.rol
                return redirect(url_for('dashboard'))
            elif usuario_inactivo and usuario_inactivo.check_password(password):
                flash('🚫 Tu cuenta ha sido inhabilitada por la administración.', 'danger')
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
        elif rol == 'portero':
            return redirect(url_for('portero_dashboard'))
        else:
            return redirect(url_for('rrpp_dashboard'))


    # ==========================================
    # 🎟️ PANEL RRPP / VENDEDORES (MULTIEVENTO)
    # ==========================================
    @app.route('/rrpp')
    @login_required(roles=['rrpp', 'supervisor', 'admin'])
    def rrpp_dashboard():
        usuario_id = session.get('usuario_id')
        evento_activo = Evento.query.filter_by(es_evento_actual=True, estado='activo').first()

        if evento_activo:
            tickets = TicketQR.query.filter_by(vendedor_id=usuario_id, evento_id=evento_activo.id).order_by(TicketQR.fecha_creacion.desc()).all()
        else:
            tickets = []
        
        total_generados = len(tickets)
        total_canjeados = sum(1 for t in tickets if t.estado == 'canjeado')
        total_parciales = sum(1 for t in tickets if t.estado == 'parcial')

        return render_template('rrpp/dashboard.html', 
                               tickets=tickets, 
                               evento_activo=evento_activo,
                               total_generados=total_generados, 
                               total_canjeados=total_canjeados, 
                               total_parciales=total_parciales)

    @app.route('/rrpp/generar_pase', methods=['POST'])
    @login_required(roles=['rrpp', 'supervisor', 'admin'])
    def generar_pase():
        evento_activo = Evento.query.filter_by(es_evento_actual=True, estado='activo').first()
        if not evento_activo:
            return jsonify({"success": False, "error": "No hay ningún evento activo configurado para emitir pases."}), 400

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
            evento_id=evento_activo.id,
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
            f"¡Hola {nombre}! 🎉 Aquí tienes tu Pase VIP para ANANA CLUB ({evento_activo.nombre}).\n\n"
            f"🎫 Titular: {nombre}\n"
            f"👥 Cantidad de entradas: {cantidad}\n"
            f"🆔 Código: {codigo_ticket}\n\n"
            f"Descarga tu ticket digital con QR aquí:\n{link_pdf}"
        )
        link_wa = f"https://wa.me/{whatsapp}?text={urllib.parse.quote(mensaje)}"
        
        return jsonify({"success": True, "link_whatsapp": link_wa, "codigo_ticket": codigo_ticket})

    # PDF del Pase RRPP (Público para descarga desde WhatsApp)
    @app.route('/rrpp/ticket/pdf/<codigo>')
    def descargar_pdf_rrpp(codigo):
        ticket = TicketQR.query.filter_by(codigo_qr=codigo).first_or_404()
        
        qr_img = qrcode.make(ticket.codigo_qr)
        qr_path = f"temp_qr_{codigo}.png"
        qr_img.save(qr_path)

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40, leftMargin=40,
            topMargin=40, bottomMargin=40
        )
        
        story = []
        styles = getSampleStyleSheet()

        estilo_titulo = ParagraphStyle(
            'TituloVIP', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=18,
            textColor=colors.HexColor('#D4AF37'), alignment=1, spaceAfter=10
        )
        
        estilo_sub = ParagraphStyle(
            'SubVIP', parent=styles['Normal'],
            fontName='Helvetica', fontSize=10,
            textColor=colors.HexColor('#AAAAAA'), alignment=1, spaceAfter=15
        )

        estilo_texto = ParagraphStyle(
            'TextoVIP', parent=styles['Normal'],
            fontName='Helvetica', fontSize=12,
            textColor=colors.HexColor('#333333'), alignment=1, spaceAfter=6
        )

        estilo_codigo = ParagraphStyle(
            'CodigoVIP', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=14,
            textColor=colors.HexColor('#D4AF37'), alignment=1, spaceAfter=10
        )

        logo_path = "static/images/anana_logo_transparente.png"
        try:
            story.append(Image(logo_path, width=120, height=60))
            story.append(Spacer(1, 10))
        except:
            pass

        # --- FLYER DINÁMICO DEL EVENTO ---
        if ticket.evento and ticket.evento.imagen_flyer:
            flyer_path = os.path.join('static', 'uploads', ticket.evento.imagen_flyer)
            if os.path.exists(flyer_path):
                try:
                    img_read = ImageReader(flyer_path)
                    orig_w, orig_h = img_read.getSize()
                    
                    max_w = 180
                    aspect_ratio = orig_h / orig_w
                    new_h = max_w * aspect_ratio
                    
                    story.append(Image(flyer_path, width=max_w, height=new_h))
                    story.append(Spacer(1, 10))
                except Exception as e:
                    print(f"Error al cargar flyer en PDF: {e}")

        evento_nombre = ticket.evento.nombre if ticket.evento else "ANANA CLUB"
        story.append(Paragraph(f"{evento_nombre} — VIP PASS", estilo_titulo))
        story.append(Paragraph("PRESENTAR ESTE QR EN PUERTA", estilo_sub))
        story.append(Spacer(1, 10))

        story.append(Image(qr_path, width=160, height=160))
        story.append(Spacer(1, 15))

        data_tabla = [
            [Paragraph(f"<b>TITULAR:</b> {ticket.titular_nombre}", estilo_texto)],
            [Paragraph(f"<b>DNI:</b> {ticket.titular_dni}", estilo_texto)],
            [Paragraph(f"<b>ACCESOS EN EL PACK:</b> {ticket.total_entradas} Persona(s)", estilo_texto)],
            [Paragraph(f"<b>CÓDIGO:</b> {ticket.codigo_qr}", estilo_codigo)]
        ]

        tabla_ticket = Table(data_tabla, colWidths=[300])
        tabla_ticket.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FDFBF7')),
            ('BOX', (0,0), (-1,-1), 2, colors.HexColor('#D4AF37')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5D8B0')),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))

        story.append(tabla_ticket)
        story.append(Spacer(1, 20))
        
        # Obtenemos las fechas formateadas del evento activo o asignado al ticket
        f_inicio_fmt = ticket.evento.fecha_inicio.strftime('%d/%m/%Y a las %H:%M hs') if ticket.evento else "Fecha indicada"
        f_fin_fmt = ticket.evento.fecha_fin.strftime('%d/%m/%Y a las %H:%M hs') if ticket.evento else "Hora indicada"

        estilo_footer = ParagraphStyle(
            'FooterVIP', parent=styles['Normal'],
            fontName='Helvetica-Oblique', fontSize=8,
            textColor=colors.HexColor('#888888'), alignment=1
        )
        texto_leyenda = f"Este pase es personal e intransferible. Válido **únicamente para el día del evento** indicado: del {f_inicio_fmt} al {f_fin_fmt}. Uso único según capacidad del pack."
        story.append(Paragraph(texto_leyenda, estilo_footer))
        doc.build(story)
        
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
    # 🚪 PANEL DE PORTERÍA Y SEGURIDAD
    # ==========================================
    @app.route('/portero')
    @login_required(roles=['portero', 'admin', 'supervisor'])
    def portero_dashboard():
        evento_activo = Evento.query.filter_by(es_evento_actual=True, estado='activo').first()
        
        if evento_activo:
            tickets = TicketQR.query.filter_by(evento_id=evento_activo.id).all()
        else:
            tickets = []
        
        pendientes = sum(1 for t in tickets if t.estado == 'pendiente')
        parciales = sum(1 for t in tickets if t.estado == 'parcial')
        canjeados = sum(1 for t in tickets if t.estado == 'canjeado')
        vencidos = sum(1 for t in tickets if t.estado == 'vencido')
        anulados = sum(1 for t in tickets if t.estado == 'anulado')
        total_pases = len(tickets)

        return render_template('portero/dashboard.html',
                               evento_activo=evento_activo,
                               pendientes=pendientes,
                               parciales=parciales,
                               canjeados=canjeados,
                               vencidos=vencidos,
                               anulados=anulados,
                               total_pases=total_pases)

    # ==========================================
    # 📷 ESCANEO Y VALIDACIÓN (ADMIN, SUP, PORTERO)
    # ==========================================
    @app.route('/admin/escaneo')
    @login_required(roles=['admin', 'supervisor', 'portero'])
    def vista_escaneo():
        return render_template('admin/escaneo.html')

    @app.route('/admin/validar/<codigo>', methods=['GET', 'POST'])
    @login_required(roles=['admin', 'supervisor', 'portero'])
    def validar_ticket(codigo):
        ticket = TicketQR.query.filter_by(codigo_qr=codigo).first()
        
        # Si el ticket existe y NO está anulado, actualizamos su estado por fecha/uso
        if ticket and ticket.estado != 'anulado':
            ticket.actualizar_estado()
            db.session.commit()

        if request.method == 'POST':
            if not ticket:
                flash('El ticket no existe.', 'danger')
                return redirect(url_for('vista_escaneo'))

            # Bloqueo estricto para tickets anulados
            if ticket.estado == 'anulado':
                flash('🚫 ESTE PASE FUE ANULADO POR LA ADMINISTRACIÓN.', 'danger')
                return redirect(url_for('validar_ticket', codigo=codigo))

            if ticket.estado == 'vencido':
                flash('❌ Este pase corresponde a un evento vencido.', 'danger')
                return redirect(url_for('validar_ticket', codigo=codigo))

            disponibles = ticket.total_entradas - ticket.entradas_usadas
            
            try:
                ingresan = int(request.form.get('entradas_a_ingresar', 0))
            except ValueError:
                ingresan = 0

            if ingresan <= 0 or ingresan > disponibles:
                flash('Cantidad de ingresos no válida.', 'danger')
                return redirect(url_for('validar_ticket', codigo=codigo))

            ticket.entradas_usadas += ingresan
            ticket.actualizar_estado()

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
        evento_id_filtro = request.args.get('evento_id', type=int)
        eventos = Evento.query.order_by(Evento.fecha_inicio.desc()).all()
        evento_activo = Evento.query.filter_by(es_evento_actual=True, estado='activo').first()

        if evento_id_filtro:
            tickets = TicketQR.query.filter_by(evento_id=evento_id_filtro).order_by(TicketQR.fecha_creacion.desc()).all()
        elif evento_activo:
            tickets = TicketQR.query.filter_by(evento_id=evento_activo.id).order_by(TicketQR.fecha_creacion.desc()).all()
        else:
            tickets = TicketQR.query.order_by(TicketQR.fecha_creacion.desc()).all()

        vendedores = Usuario.query.filter(Usuario.rol != 'admin').all()
        
        return render_template('admin/dashboard_rrpp.html', 
                               tickets=tickets, 
                               vendedores=vendedores, 
                               eventos=eventos, 
                               evento_activo=evento_activo,
                               evento_id_filtro=evento_id_filtro)

    @app.route('/supervisor')
    @login_required(roles=['supervisor', 'admin'])
    def supervisor_dashboard():
        return redirect(url_for('admin_dashboard'))

    # --- GESTIÓN DE EVENTOS ---
    @app.route('/admin/eventos/crear', methods=['POST'])
    @login_required(roles=['admin'])
    def crear_evento():
        nombre = request.form.get('nombre')
        f_inicio_str = request.form.get('fecha_inicio')
        f_fin_str = request.form.get('fecha_fin')
        
        imagen_filename = None
        if 'imagen_flyer' in request.files:
            file = request.files['imagen_flyer']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                upload_folder = 'static/uploads'
                os.makedirs(upload_folder, exist_ok=True)
                
                imagen_filename = f"flyer_{uuid.uuid4().hex[:6]}_{filename}"
                file.save(os.path.join(upload_folder, imagen_filename))

        if not nombre or not f_inicio_str or not f_fin_str:
            flash('Todos los campos obligatorios del evento son requeridos.', 'danger')
            return redirect(url_for('admin_dashboard'))

        try:
            f_inicio = datetime.strptime(f_inicio_str, '%Y-%m-%dT%H:%M')
            f_fin = datetime.strptime(f_fin_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Formato de fecha inválido.', 'danger')
            return redirect(url_for('admin_dashboard'))

        nuevo_evento = Evento(
            nombre=nombre,
            fecha_inicio=f_inicio,
            fecha_fin=f_fin,
            estado='activo',
            es_evento_actual=False,
            imagen_flyer=imagen_filename
        )
        db.session.add(nuevo_evento)
        db.session.commit()

        flash(f'✅ Evento "{nombre}" creado con éxito.', 'success')
        return redirect(url_for('admin_dashboard'))

    @app.route('/admin/eventos/activar/<int:evento_id>')
    @login_required(roles=['admin'])
    def activar_evento(evento_id):
        Evento.query.update({Evento.es_evento_actual: False})
        evento = Evento.query.get_or_404(evento_id)
        evento.es_evento_actual = True
        evento.estado = 'activo'
        db.session.commit()
        
        flash(f'⭐ Evento "{evento.nombre}" marcado como evento activo actual.', 'success')
        return redirect(url_for('admin_dashboard'))

    # --- GESTIÓN DE USUARIOS ---
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
            flash('El nombre de usuario ya existe.', 'danger')
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
        flash('✅ Usuario registrado con éxito.', 'success')
        return redirect(url_for('admin_dashboard'))

    # --- ANULACION DE QR GENERADOS POR VENDEDORES ---
    # --- ANULACIÓN DE QR Y BLOQUEO DE VENDEDOR ---
    @app.route('/admin/vendedor/anular_pases/<int:vendedor_id>', methods=['POST'])
    @login_required(roles=['admin', 'supervisor'])
    def anular_pases_vendedor(vendedor_id):
        evento_activo = Evento.query.filter_by(es_evento_actual=True, estado='activo').first()
        if not evento_activo:
            flash('No hay ningún evento activo configurado.', 'warning')
            return redirect(url_for('admin_dashboard'))
        
        # 1. Inhabilitamos al vendedor para que no pueda seguir emitiendo pases
        vendedor = Usuario.query.get_or_404(vendedor_id)
        vendedor.activo = False

        # 2. Anulamos todos los tickets activos/pendientes/parciales del vendedor para este evento
        tickets = TicketQR.query.filter_by(vendedor_id=vendedor_id, evento_id=evento_activo.id).all()
        
        contador = 0
        for t in tickets:
            if t.estado in ['pendiente', 'parcial']:
                t.estado = 'anulado'
                contador += 1
                
        db.session.commit()
        flash(f'⛔ Se inhabilitó al vendedor {vendedor.nombre_completo} y se anularon sus {contador} pases activos.', 'danger')
        return redirect(url_for('admin_dashboard'))

    #DESACTIVAR USUARIO 
    @app.route('/admin/usuario/toggle_activo/<int:usuario_id>')
    @login_required(roles=['admin'])
    def toggle_activo_usuario(usuario_id):
        usuario = Usuario.query.get_or_404(usuario_id)
        if usuario.id == session.get('usuario_id'):
            flash('No puedes desactivar tu propia cuenta.', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        usuario.activo = not usuario.activo
        db.session.commit()
        
        estado_txt = "activado" if usuario.activo else "inhabilitado"
        flash(f'👤 El usuario {usuario.nombre_completo} ha sido {estado_txt}.', 'warning')
        return redirect(url_for('admin_dashboard'))

    # ACTIVAR USUARIO
    @app.route('/admin/vendedor/reactivar/<int:vendedor_id>', methods=['POST'])
    @login_required(roles=['admin', 'supervisor'])
    def reactivar_vendedor(vendedor_id):
        vendedor = Usuario.query.get_or_404(vendedor_id)
        vendedor.activo = True
        db.session.commit()
        
        flash(f'✅ El vendedor {vendedor.nombre_completo} ha sido reactivado y ya puede ingresar a emitir pases.', 'success')
        return redirect(url_for('admin_dashboard'))