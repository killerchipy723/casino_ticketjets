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
    @login_required(roles=['rrpp', 'supervisor', 'admin'])
    def descargar_pdf_rrpp(codigo):
        ticket = TicketQR.query.filter_by(codigo_qr=codigo).first_or_404()
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        card_x, card_y, card_w, card_h = 96, 76, 420, 640
        
        c.setFillColor(colors.HexColor('#12121a'))
        c.roundRect(card_x, card_y, card_w, card_h, 16, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor('#d4af37'))
        c.setLineWidth(2.5)
        c.roundRect(card_x, card_y, card_w, card_h, 16, fill=0, stroke=1)
        
        c.setFillColor(colors.HexColor('#d4af37'))
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(card_x + (card_w / 2), card_y + card_h - 45, "ANANA CLUB 🍍")
        
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(card_x + (card_w / 2), card_y + card_h - 70, "PASE VIP OFICIAL / RRPP")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(card_x + 40, card_y + card_h - 130, f"TITULAR: {ticket.titular_nombre.upper()}")
        c.drawString(card_x + 40, card_y + card_h - 160, f"DNI: {ticket.titular_dni}")
        c.drawString(card_x + 40, card_y + card_h - 190, f"ENTRADAS ADQUIRIDAS: {ticket.total_entradas}")
        c.drawString(card_x + 40, card_y + card_h - 220, f"CÓDIGO: {ticket.codigo_qr}")

        url_validacion = f"https://ananaclub.online/admin/validar/{ticket.codigo_qr}"
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(url_validacion)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        img_buffer = io.BytesIO()
        img_qr.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        
        c.drawImage(ImageReader(img_buffer), card_x + 135, card_y + 110, width=150, height=150)
        c.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Pase_VIP_{ticket.codigo_qr}.pdf", mimetype='application/pdf')


    # ==========================================
    # 📷 ESCANEO Y VALIDACIÓN PARCIAL (PUERTA)
    # ==========================================
    @app.route('/admin/escaneo')
    @login_required(roles=['admin', 'supervisor', 'rrpp'])
    def admin_escaneo():
        return render_template('admin/escaneo.html')

    @app.route('/admin/validar/<codigo>', methods=['GET', 'POST'])
    @login_required(roles=['admin', 'supervisor', 'rrpp'])
    def escaneo_validar(codigo):
        ticket = TicketQR.query.filter_by(codigo_qr=codigo).first()
        if not ticket:
            return render_template('admin/resultado_scan.html', error="❌ Pase QR no encontrado en el sistema.")

        if request.method == 'POST':
            try:
                entradas_a_ingresar = int(request.form.get('entradas_a_ingresar', 1))
            except ValueError:
                entradas_a_ingresar = 1

            restantes = ticket.total_entradas - ticket.entradas_usadas
            if entradas_a_ingresar <= 0:
                flash('Cantidad inválida.', 'danger')
            elif entradas_a_ingresar > restantes:
                flash(f'⚠️ No se pueden ingresar {entradas_a_ingresar} personas. Solo quedan {restantes} disponibles.', 'danger')
            else:
                ticket.entradas_usadas += entradas_a_ingresar
                ticket.actualizar_estado()
                
                # Registrar en el historial de canjes
                canje = HistorialCanje(
                    ticket_id=ticket.id,
                    entradas_ingresadas=entradas_a_ingresar,
                    validador_id=session['usuario_id']
                )
                db.session.add(canje)
                db.session.commit()
                flash(f'✅ ¡Ingreso autorizado para {entradas_a_ingresar} persona(s)! Restantes: {ticket.total_entradas - ticket.entradas_usadas}', 'success')

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