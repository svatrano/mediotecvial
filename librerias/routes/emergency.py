import io
import logging
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, abort, send_file
)
from flask_login import login_required, current_user
from librerias.models import db, Asset, EmergencyPlan, VehicleTemplate, FuelType, Client
from librerias.services.qr_service import generate_qr_image_bytes
from librerias.services.storage_service import read_rescue_sheet

logger = logging.getLogger(__name__)

emergency_bp = Blueprint('emergency', __name__, url_prefix='/emergency')


@emergency_bp.route('/dashboard', methods=['GET'])
def dashboard():
    """Dashboard de emergencia con listado general de activos"""
    assets = Asset.query.order_by(Asset.name).all()
    return render_template('emergency/dashboard.html', assets=assets)


@emergency_bp.route('/search', methods=['GET'])
def search():
    """Buscador rápido de activos por dominio, nombre o dirección"""
    query = request.args.get('q', '').strip()
    results = []
    if query:
        results = Asset.query.filter(
            (Asset.name.ilike(f'%{query}%')) |
            (Asset.domain.ilike(f'%{query}%')) |
            (Asset.address_or_model.ilike(f'%{query}%'))
        ).all()
    return render_template('emergency/search.html', results=results, query=query)


@emergency_bp.route('/asset/<int:asset_id>', methods=['GET'])
def view_asset(asset_id):
    """Vista detallada de emergencia de un activo"""
    asset = Asset.query.get_or_404(asset_id)
    plans = asset.emergency_plans.filter_by(is_active=True).all()
    return render_template('emergency/view_asset.html', asset=asset, plans=plans)


@emergency_bp.route('/asset/<int:asset_id>/hoja-rescate', methods=['GET'])
def view_vehicle_rescue_sheet(asset_id):
    """Ficha de rescate vehicular para un activo"""
    asset = Asset.query.get_or_404(asset_id)
    rescue_sheet = asset.vehicle_template
    file_url = url_for('public.documento_hoja_rescate', uid=asset.id) if rescue_sheet else None
    file_type = 'pdf'
    document_name = rescue_sheet.rescue_sheet_filename if rescue_sheet else ''
    if document_name and document_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
        file_type = 'image'

    return render_template(
        'emergency/view_rescue_sheet.html',
        asset=asset,
        rescue_sheet=rescue_sheet,
        file_url=file_url,
        file_type=file_type
    )


@emergency_bp.route('/asset/<int:asset_id>/qr', methods=['GET'])
def download_vehicle_rescue_sheet_qr(asset_id):
    """Descarga de imagen QR de la hoja de rescate"""
    asset = Asset.query.get_or_404(asset_id)
    target_url = f"{request.host_url.rstrip('/')}/hoja-rescate/{asset.id}"
    img_io = generate_qr_image_bytes(target_url)
    filename = f"hoja_rescate_qr_{asset.domain or asset.id}.png"
    return send_file(img_io, mimetype='image/png', as_attachment=True, download_name=filename)


@emergency_bp.route('/plan/<int:plan_id>', methods=['GET'])
def view_plan(plan_id):
    """Visualizador de un plano individual"""
    plan = EmergencyPlan.query.get_or_404(plan_id)
    file_url = url_for('emergency.download_plan', plan_id=plan.id)
    return render_template(
        'emergency/view_plan.html',
        plan=plan,
        asset=plan.asset,
        file_url=file_url,
        file_type=plan.file_type or 'pdf',
    )


@emergency_bp.route('/plan/<int:plan_id>/documento', methods=['GET'])
def download_plan(plan_id):
    """Entrega un plano de emergencia desde la aplicación, nunca desde Blob."""
    plan = EmergencyPlan.query.get_or_404(plan_id)
    try:
        document, content_type, filename = read_rescue_sheet(plan.file_path, plan.file_name)
    except FileNotFoundError:
        abort(404)

    return send_file(
        document,
        mimetype=content_type,
        as_attachment=request.args.get('download') == '1',
        download_name=filename,
    )


@emergency_bp.route('/asset/<int:asset_id>/autogestion', methods=['GET', 'POST'])
def public_autogestion(asset_id):
    """Validación de seguridad para autogestión de combustible de un activo"""
    asset = Asset.query.get_or_404(asset_id)

    if request.method == 'POST':
        domain = request.form.get('domain', '').strip().upper()
        id_number = request.form.get('id_number', '').strip()

        if asset.domain and asset.domain.upper() == domain:
            client = asset.client
            if client and client.dni_cuit == id_number:
                return render_template('public/autogestion_update.html', asset=asset)

        flash('Los datos ingresados no coinciden con los registros del vehículo.', 'danger')

    return render_template('public/autogestion_login.html', asset=asset)


@emergency_bp.route('/asset/<int:asset_id>/autogestion/update', methods=['POST'])
def public_autogestion_update(asset_id):
    """Actualización del tipo de combustible desde autogestión"""
    asset = Asset.query.get_or_404(asset_id)
    fuel_name = request.form.get('additional_fuel', '').strip()

    if fuel_name:
        fuel = FuelType.query.filter_by(tipo=fuel_name).first()
        if fuel:
            asset.fuel_type_id = fuel.id
        else:
            default_fuel = FuelType.query.filter_by(tipo='Sin descripcion').first()
            if default_fuel:
                asset.fuel_type_id = default_fuel.id
    else:
        default_fuel = FuelType.query.filter_by(tipo='Sin descripcion').first()
        if default_fuel:
            asset.fuel_type_id = default_fuel.id

    try:
        db.session.commit()
        flash('Datos de combustible actualizados exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar datos: {str(e)}', 'danger')

    return redirect(url_for('public.hoja_rescate', uid=asset.id))
