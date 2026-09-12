import logging
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, abort, jsonify
)
from flask_login import login_required, current_user
from librerias.models import (
    db, Asset, Client, VehicleTemplate, FuelType, SolicitudVehiculoFaltante
)

logger = logging.getLogger(__name__)

activos_bp = Blueprint('activos', __name__)


# -------------------------------------------------------------------------
# APIS DINÁMICAS DEL CATÁLOGO VEHICULAR
# -------------------------------------------------------------------------

@activos_bp.route('/api/vehiculos/marcas', methods=['GET'])
def api_marcas():
    """Retorna listado JSON de marcas distintas disponibles en el catálogo"""
    brands = VehicleTemplate.get_distinct_brands()
    return jsonify({'success': True, 'marcas': brands}), 200


@activos_bp.route('/api/vehiculos/modelos', methods=['GET'])
def api_modelos():
    """Retorna listado JSON de modelos distintos para una marca dada"""
    brand = request.args.get('brand', '').strip()
    if not brand:
        return jsonify({'success': False, 'error': 'Parámetro brand requerido'}), 400

    models = VehicleTemplate.get_distinct_models(brand)
    return jsonify({'success': True, 'brand': brand, 'modelos': models}), 200


@activos_bp.route('/api/vehiculos/anios', methods=['GET'])
def api_anios():
    """Retorna listado JSON de años de modelo para una marca y modelo dados"""
    brand = request.args.get('brand', '').strip()
    model = request.args.get('model', '').strip()
    if not brand or not model:
        return jsonify({'success': False, 'error': 'Parámetros brand y model requeridos'}), 400

    years = VehicleTemplate.get_distinct_years(brand, model)
    return jsonify({'success': True, 'brand': brand, 'model': model, 'anios': years}), 200


@activos_bp.route('/api/vehiculos/solicitud-faltante', methods=['POST'])
def api_solicitar_vehiculo_faltante():
    """Permite enviar una solicitud de inclusión de modelo faltante en el catálogo"""
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form

    marca = data.get('marca', '').strip()
    modelo = data.get('modelo', '').strip()
    raw_anio = data.get('anio')
    try:
        anio = int(raw_anio) if raw_anio is not None else None
    except (ValueError, TypeError):
        anio = None
    contacto = data.get('contacto', '').strip()
    observaciones = data.get('observaciones', '').strip()

    if not marca or not modelo:
        return jsonify({'success': False, 'error': 'Marca y modelo son obligatorios.'}), 400

    client_id = None
    if current_user.is_authenticated and current_user.client:
        client_id = current_user.client.id
        if not contacto:
            contacto = current_user.client.mail

    solicitud = SolicitudVehiculoFaltante(
        client_id=client_id,
        marca=marca,
        modelo=modelo,
        anio=anio,
        contacto=contacto,
        observaciones=observaciones,
        estado='PENDIENTE'
    )

    try:
        db.session.add(solicitud)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Solicitud registrada correctamente. Nuestro equipo técnico incorporará la hoja de rescate a la brevedad.',
            'solicitud_id': solicitud.id
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# -------------------------------------------------------------------------
# GESTIÓN DE ACTIVOS POR PARTE DEL CLIENTE (AUTORIZACIÓN ESTRICTA)
# -------------------------------------------------------------------------

@activos_bp.route('/cliente/activos', methods=['GET'])
@login_required
def mis_activos():
    """Listado de activos pertenecientes exclusivamente al cliente en sesión"""
    if current_user.role == 'admin':
        return redirect(url_for('admin.list_assets'))

    if not current_user.client:
        flash('Tu cuenta no tiene un perfil de cliente asignado.', 'warning')
        return redirect(url_for('public.index'))

    client_id = current_user.client.id
    activos = Asset.query.filter_by(client_id=client_id).order_by(Asset.created_at.desc()).all()

    return render_template('public/cliente_activos.html', activos=activos)


@activos_bp.route('/cliente/activos/<int:asset_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_mi_activo(asset_id):
    """
    Edición de un activo vehicular propio del cliente.
    REGLA DE AUTORIZACIÓN: asset.client_id == current_user.client.id
    """
    asset = Asset.query.get_or_404(asset_id)

    # Verificación estricta de autorización
    if current_user.role != 'admin':
        if not current_user.client or asset.client_id != current_user.client.id:
            logger.warning(
                f"Usuario {current_user.username} intentó acceder indebidamente al activo {asset_id} de otro cliente."
            )
            flash('No tienes permiso para ver o modificar este activo.', 'danger')
            abort(403)

    fuel_types = FuelType.query.order_by(FuelType.id).all()
    vehicle_templates = VehicleTemplate.query.order_by(
        VehicleTemplate.brand, VehicleTemplate.model, VehicleTemplate.year
    ).all()

    if request.method == 'POST':
        fuel_type_id = request.form.get('fuel_type_id', type=int)
        description = request.form.get('description', '').strip()
        manufacturing_year = request.form.get('manufacturing_year', type=int)
        vehicle_template_id = request.form.get('vehicle_template_id', type=int)

        vehicle_template = VehicleTemplate.query.get(vehicle_template_id) if vehicle_template_id else None
        if vehicle_template_id and not vehicle_template:
            flash('La hoja de rescate seleccionada no existe.', 'danger')
            return render_template(
                'public/cliente_activo_editar.html',
                asset=asset,
                fuel_types=fuel_types,
                vehicle_templates=vehicle_templates,
            )

        if fuel_type_id:
            asset.fuel_type_id = fuel_type_id
        if manufacturing_year:
            asset.manufacturing_year = manufacturing_year
        if vehicle_template:
            asset.vehicle_template_id = vehicle_template.id
        asset.description = description

        try:
            db.session.commit()
            flash('Datos del vehículo actualizados correctamente.', 'success')
            if current_user.role == 'admin':
                return redirect(url_for('admin.list_assets'))
            return redirect(url_for('activos.mis_activos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar cambios: {str(e)}', 'danger')

    return render_template(
        'public/cliente_activo_editar.html',
        asset=asset,
        fuel_types=fuel_types,
        vehicle_templates=vehicle_templates,
    )
