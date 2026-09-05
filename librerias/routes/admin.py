import os
import uuid
import logging
from datetime import datetime
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, abort, jsonify, send_file, current_app
)
from flask_login import login_required, current_user
from librerias.models import (
    db, User, Client, Asset, VehicleTemplate, FuelType, CodigoQR, EmergencyPlan
)
from librerias.services.qr_service import generate_qr_image_bytes

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso restringido a Administradores.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


# -------------------------------------------------------------------------
# DASHBOARD GENERAL
# -------------------------------------------------------------------------

@admin_bp.route('/dashboard', methods=['GET'])
@login_required
@admin_required
def dashboard():
    """Panel general de administración con métricas de sistema y bloque QR"""
    total_users = User.query.count()
    total_clients = Client.query.count()
    total_assets = Asset.query.count()
    total_templates = VehicleTemplate.query.count()

    # Métricas de QRs en tiempo real
    total_qrs = CodigoQR.query.count()
    virgenes_disponibles = CodigoQR.query.filter_by(estado='VIRGEN').count()
    qrs_activados = CodigoQR.query.filter_by(estado='ACTIVADO').count()

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_clients=total_clients,
        total_assets=total_assets,
        total_templates=total_templates,
        total_qrs=total_qrs,
        virgenes_disponibles=virgenes_disponibles,
        qrs_activados=qrs_activados,
        current_year=datetime.utcnow().year
    )


# -------------------------------------------------------------------------
# GESTIÓN DE CLIENTES
# -------------------------------------------------------------------------

@admin_bp.route('/clientes', methods=['GET'])
@login_required
@admin_required
def list_clients():
    page = request.args.get('page', 1, type=int)
    clients_paginated = Client.query.order_by(Client.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    return render_template('admin/clients/list.html', clients=clients_paginated)


@admin_bp.route('/clientes/crear', methods=['GET', 'POST'])
@login_required
@admin_required
def create_client():
    """Carga manual interna de clientes"""
    if request.method == 'POST':
        nombre = request.form.get('nombre') or request.form.get('name', '').strip()
        dni_cuit = request.form.get('dni_cuit') or request.form.get('id_number', '').strip()
        mail = request.form.get('mail') or request.form.get('contact_email', '').strip()
        telefono = request.form.get('telefono') or request.form.get('phone', '').strip()
        direccion = request.form.get('direccion') or request.form.get('address', '').strip()
        user_id = request.form.get('user_id', type=int)

        if not nombre or not dni_cuit or not mail:
            flash('Nombre, DNI/CUIT y Email son campos obligatorios.', 'danger')
            return render_template('admin/clients/create.html', users=User.query.filter_by(role='cliente').all())

        if Client.query.filter_by(dni_cuit=dni_cuit).first():
            flash(f'El DNI/CUIT {dni_cuit} ya está registrado.', 'danger')
            return render_template('admin/clients/create.html', users=User.query.filter_by(role='cliente').all())

        # Si no se seleccionó un usuario existente, crear uno automáticamente
        if not user_id:
            username = mail.split('@')[0] + "_" + dni_cuit[-4:]
            counter = 1
            base_username = username
            while User.query.filter_by(username=username).first():
                username = f"{base_username}_{counter}"
                counter += 1

            new_user = User(
                username=username,
                email=mail,
                role='cliente'
            )
            new_user.set_password('cambiar123')
            db.session.add(new_user)
            db.session.flush()
            user_id = new_user.id

        client = Client(
            nombre=nombre,
            dni_cuit=dni_cuit,
            mail=mail,
            telefono=telefono,
            direccion=direccion,
            user_id=user_id
        )

        try:
            db.session.add(client)
            db.session.commit()
            flash('Cliente creado exitosamente.', 'success')
            return redirect(url_for('admin.list_clients'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear cliente: {str(e)}', 'danger')

    available_users = User.query.filter(User.role == 'cliente', ~User.client.has()).all()
    return render_template('admin/clients/create.html', users=available_users)


@admin_bp.route('/clientes/<int:client_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)

    if request.method == 'POST':
        client.nombre = request.form.get('nombre') or request.form.get('name', '').strip()
        client.dni_cuit = request.form.get('dni_cuit') or request.form.get('id_number', '').strip()
        client.mail = request.form.get('mail') or request.form.get('contact_email', '').strip()
        client.telefono = request.form.get('telefono') or request.form.get('phone', '').strip()
        client.direccion = request.form.get('direccion') or request.form.get('address', '').strip()

        try:
            db.session.commit()
            flash('Cliente actualizado correctamente.', 'success')
            return redirect(url_for('admin.list_clients'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar cliente: {str(e)}', 'danger')

    return render_template('admin/clients/edit.html', client=client)


# -------------------------------------------------------------------------
# GESTIÓN DE USUARIOS
# -------------------------------------------------------------------------

@admin_bp.route('/usuarios', methods=['GET'])
@login_required
@admin_required
def list_users():
    page = request.args.get('page', 1, type=int)
    users_paginated = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    return render_template('admin/users/list.html', users=users_paginated)


@admin_bp.route('/usuarios/crear', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    roles = ['admin', 'cliente', 'firefighter']
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'cliente')

        if not username or not email or not password:
            flash('Todos los campos son obligatorios.', 'danger')
            return render_template('admin/users/create.html', roles=roles)

        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya está en uso.', 'danger')
            return render_template('admin/users/create.html', roles=roles)

        user = User(username=username, email=email, role=role)
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
            flash('Usuario creado exitosamente.', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear usuario: {str(e)}', 'danger')

    return render_template('admin/users/create.html', roles=roles)


@admin_bp.route('/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    roles = ['admin', 'cliente', 'firefighter']

    if request.method == 'POST':
        user.email = request.form.get('email', '').strip()
        user.role = request.form.get('role', user.role)
        user.is_active = bool(request.form.get('is_active'))
        new_password = request.form.get('password', '').strip()
        if new_password:
            user.set_password(new_password)

        try:
            db.session.commit()
            flash('Usuario actualizado correctamente.', 'success')
            return redirect(url_for('admin.list_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar usuario: {str(e)}', 'danger')

    return render_template('admin/users/edit.html', user=user, roles=roles)


@admin_bp.route('/usuarios/<int:user_id>/eliminar', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('No puedes eliminar tu propia cuenta de usuario.', 'danger')
        return redirect(url_for('admin.list_users'))

    try:
        db.session.delete(user)
        db.session.commit()
        flash('Usuario eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar usuario: {str(e)}', 'danger')

    return redirect(url_for('admin.list_users'))


# -------------------------------------------------------------------------
# GESTIÓN DE ACTIVOS
# -------------------------------------------------------------------------

@admin_bp.route('/activos', methods=['GET'])
@login_required
@admin_required
def list_assets():
    page = request.args.get('page', 1, type=int)
    client_id = request.args.get('client_id', type=int)

    query = Asset.query
    if client_id:
        query = query.filter_by(client_id=client_id)

    assets_paginated = query.order_by(Asset.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    clients = Client.query.order_by(Client.nombre).all()

    return render_template(
        'admin/assets/list.html',
        assets=assets_paginated,
        clients=clients,
        selected_client_id=client_id
    )


@admin_bp.route('/activos/crear', methods=['GET', 'POST'])
@login_required
@admin_required
def create_asset():
    """Carga manual interna de activos con catálogo y fuel_type_id"""
    clients = Client.query.order_by(Client.nombre).all()
    vehicle_templates = VehicleTemplate.query.order_by(VehicleTemplate.brand, VehicleTemplate.model).all()
    fuel_types = FuelType.query.order_by(FuelType.id).all()

    if request.method == 'POST':
        client_id = request.form.get('client_id', type=int)
        asset_type = request.form.get('asset_type', 'vehicle')
        name = request.form.get('name', '').strip()
        address_or_model = request.form.get('address_or_model', '').strip()
        domain = request.form.get('domain', '').strip().upper() or None
        manufacturing_year = request.form.get('manufacturing_year', type=int)
        vehicle_template_id = request.form.get('vehicle_template_id', type=int) or None
        fuel_type_id = request.form.get('fuel_type_id', type=int) or None
        description = request.form.get('description', '').strip()

        if not client_id or not name:
            flash('Cliente y Nombre del activo son campos obligatorios.', 'danger')
            return render_template(
                'admin/assets/create.html',
                clients=clients,
                vehicle_templates=vehicle_templates,
                fuel_types=fuel_types
            )

        if domain and Asset.query.filter_by(domain=domain).first():
            flash(f'El dominio/patente {domain} ya está registrado.', 'danger')
            return render_template(
                'admin/assets/create.html',
                clients=clients,
                vehicle_templates=vehicle_templates,
                fuel_types=fuel_types
            )

        asset = Asset(
            client_id=client_id,
            asset_type=asset_type,
            name=name,
            address_or_model=address_or_model,
            domain=domain,
            manufacturing_year=manufacturing_year,
            vehicle_template_id=vehicle_template_id,
            fuel_type_id=fuel_type_id,
            description=description
        )

        try:
            db.session.add(asset)
            db.session.commit()
            flash('Activo creado exitosamente.', 'success')
            return redirect(url_for('admin.list_assets'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear activo: {str(e)}', 'danger')

    return render_template(
        'admin/assets/create.html',
        clients=clients,
        vehicle_templates=vehicle_templates,
        fuel_types=fuel_types
    )


@admin_bp.route('/activos/<int:asset_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    clients = Client.query.order_by(Client.nombre).all()
    vehicle_templates = VehicleTemplate.query.order_by(VehicleTemplate.brand, VehicleTemplate.model).all()
    fuel_types = FuelType.query.order_by(FuelType.id).all()

    if request.method == 'POST':
        asset.client_id = request.form.get('client_id', type=int)
        asset.name = request.form.get('name', '').strip()
        asset.address_or_model = request.form.get('address_or_model', '').strip()
        new_domain = request.form.get('domain', '').strip().upper() or None
        if new_domain != asset.domain:
            if new_domain and Asset.query.filter_by(domain=new_domain).first():
                flash(f'El dominio {new_domain} ya está registrado.', 'danger')
                return render_template('admin/assets/edit.html', asset=asset, clients=clients, vehicle_templates=vehicle_templates, fuel_types=fuel_types)
            asset.domain = new_domain

        asset.manufacturing_year = request.form.get('manufacturing_year', type=int)
        asset.vehicle_template_id = request.form.get('vehicle_template_id', type=int) or None
        asset.fuel_type_id = request.form.get('fuel_type_id', type=int) or None
        asset.description = request.form.get('description', '').strip()

        try:
            db.session.commit()
            flash('Activo actualizado exitosamente.', 'success')
            return redirect(url_for('admin.list_assets'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar activo: {str(e)}', 'danger')

    return render_template(
        'admin/assets/edit.html',
        asset=asset,
        clients=clients,
        vehicle_templates=vehicle_templates,
        fuel_types=fuel_types
    )


# -------------------------------------------------------------------------
# CATÁLOGO DE PLANTILLAS VEHICULARES
# -------------------------------------------------------------------------

@admin_bp.route('/vehicle_templates', methods=['GET'])
@login_required
@admin_required
def list_vehicle_templates():
    templates = VehicleTemplate.query.order_by(VehicleTemplate.brand, VehicleTemplate.model, VehicleTemplate.year).all()
    return render_template('admin/vehicle_templates/list.html', templates=templates)


@admin_bp.route('/vehicle_templates/crear', methods=['POST'])
@login_required
@admin_required
def create_vehicle_template():
    brand = request.form.get('brand', '').strip().upper()
    model = request.form.get('model', '').strip()
    year = request.form.get('year', type=int)
    rescue_sheet_url = request.form.get('rescue_sheet_url', '').strip()

    if not brand or not model or not year:
        flash('Marca, Modelo y Año son campos requeridos.', 'danger')
        return redirect(url_for('admin.list_vehicle_templates'))

    vt = VehicleTemplate(
        brand=brand,
        model=model,
        year=year,
        rescue_sheet_url=rescue_sheet_url,
        rescue_sheet_filename=f"{brand}_{model}_{year}.pdf"
    )

    try:
        db.session.add(vt)
        db.session.commit()
        flash('Modelo vehicular añadido al catálogo.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al añadir modelo: {str(e)}', 'danger')

    return redirect(url_for('admin.list_vehicle_templates'))


@admin_bp.route('/vehicle_templates/<int:template_id>/editar', methods=['POST'])
@login_required
@admin_required
def edit_vehicle_template(template_id):
    vt = VehicleTemplate.query.get_or_404(template_id)
    vt.brand = request.form.get('brand', vt.brand).strip().upper()
    vt.model = request.form.get('model', vt.model).strip()
    vt.year = request.form.get('year', type=int) or vt.year
    vt.rescue_sheet_url = request.form.get('rescue_sheet_url', vt.rescue_sheet_url).strip()

    try:
        db.session.commit()
        flash('Plantilla vehicular actualizada.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('admin.list_vehicle_templates'))


@admin_bp.route('/vehicle_templates/<int:template_id>/actualizar', methods=['POST'])
@login_required
@admin_required
def update_vehicle_template(template_id):
    """Alias para actualizar plantilla vehicular según list.html"""
    return edit_vehicle_template(template_id)


@admin_bp.route('/vehicle_templates/<int:template_id>/eliminar', methods=['POST'])
@login_required
@admin_required
def delete_vehicle_template(template_id):
    vt = VehicleTemplate.query.get_or_404(template_id)
    if vt.assets.count() > 0:
        flash('No se puede eliminar porque existen vehículos vinculados a esta plantilla.', 'warning')
        return redirect(url_for('admin.list_vehicle_templates'))

    try:
        db.session.delete(vt)
        db.session.commit()
        flash('Plantilla eliminada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('admin.list_vehicle_templates'))


# -------------------------------------------------------------------------
# GENERACIÓN DE QRS Y DESCARGA DE OBLEAS
# -------------------------------------------------------------------------

@admin_bp.route('/activos/<int:asset_id>/qr_autogestion', methods=['GET'])
@login_required
@admin_required
def download_qr_autogestion(asset_id):
    """Genera imagen QR descargable que apunta a la ficha o autogestión"""
    asset = Asset.query.get_or_404(asset_id)
    target_url = f"{request.host_url.rstrip('/')}/hoja-rescate/{asset.id}"
    img_io = generate_qr_image_bytes(target_url)
    filename = f"qr_{asset.domain or asset.id}.png"
    return send_file(img_io, mimetype='image/png', as_attachment=True, download_name=filename)


@admin_bp.route('/activos/<int:asset_id>/obleas', methods=['GET'])
@login_required
@admin_required
def asset_obleas(asset_id):
    """Pantalla con las obleas de emergencia del activo listas para imprimir"""
    asset = Asset.query.get_or_404(asset_id)
    qr_url = f"{request.host_url.rstrip('/')}/hoja-rescate/{asset.id}"
    return render_template('admin/assets/pagina-descargas.html', asset=asset, qr_url=qr_url)


# -------------------------------------------------------------------------
# PLANOS / DOCUMENTOS
# -------------------------------------------------------------------------

@admin_bp.route('/activos/<int:asset_id>/planes', methods=['GET'])
@login_required
@admin_required
def list_plans(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    page = request.args.get('page', 1, type=int)
    plans_pag = asset.emergency_plans.order_by(EmergencyPlan.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    return render_template('admin/plans/list.html', asset=asset, plans=plans_pag)


@admin_bp.route('/activos/<int:asset_id>/planes/subir', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_plan(asset_id):
    asset = Asset.query.get_or_404(asset_id)

    if request.method == 'POST':
        file = request.files.get('file')
        file_name = request.form.get('file_name', '').strip()
        version = request.form.get('version', 1, type=int)

        if not file_name:
            file_name = file.filename if file else 'documento.pdf'

        plan = EmergencyPlan(
            asset_id=asset.id,
            file_name=file_name,
            file_path=file_name,
            file_type='pdf',
            version=version,
            is_active=True
        )

        try:
            db.session.add(plan)
            db.session.commit()
            flash('Documento subido correctamente.', 'success')
            return redirect(url_for('admin.list_plans', asset_id=asset.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al subir plano: {str(e)}', 'danger')

    return render_template('admin/plans/upload.html', asset=asset)


@admin_bp.route('/planes/<int:plan_id>/qr', methods=['GET'])
@login_required
@admin_required
def download_qr(plan_id):
    plan = EmergencyPlan.query.get_or_404(plan_id)
    target_url = f"{request.host_url.rstrip('/')}/hoja-rescate/{plan.asset_id}"
    img_io = generate_qr_image_bytes(target_url)
    return send_file(img_io, mimetype='image/png', as_attachment=True, download_name=f"plan_{plan_id}_qr.png")


@admin_bp.route('/planes/<int:plan_id>/eliminar', methods=['POST'])
@login_required
@admin_required
def delete_plan(plan_id):
    plan = EmergencyPlan.query.get_or_404(plan_id)
    asset_id = plan.asset_id
    try:
        db.session.delete(plan)
        db.session.commit()
        flash('Plano eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('admin.list_plans', asset_id=asset_id))

