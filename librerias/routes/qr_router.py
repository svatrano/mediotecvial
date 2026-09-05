import logging
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, abort, jsonify
)
from flask_login import login_required, current_user
from librerias.models import (
    db, CodigoQR, Asset, Client, VehicleTemplate, FuelType, SolicitudVehiculoFaltante
)

logger = logging.getLogger(__name__)

qr_router_bp = Blueprint('qr_router', __name__)


@qr_router_bp.route('/qr/<qr_uuid>', methods=['GET'])
def escanear_qr(qr_uuid):
    """
    Router principal al escanear el QR físico:
    - Inexistente -> 404
    - Estado 'VIRGEN' -> Redirige a /activacion/<qr_uuid>
    - Estado 'ACTIVADO' -> Redirige a /hoja-rescate/<activo_id>
    """
    qr_item = CodigoQR.query.filter_by(id=qr_uuid).first()

    if not qr_item:
        logger.warning(f"QR escaneado no existe: {qr_uuid}")
        abort(404)

    if qr_item.estado == 'VIRGEN':
        logger.info(f"QR {qr_uuid} es VIRGEN. Redirigiendo a activación.")
        return redirect(url_for('qr_router.activar_qr', qr_uuid=qr_uuid))

    elif qr_item.estado == 'ACTIVADO':
        if not qr_item.activo_id:
            logger.error(f"QR {qr_uuid} marcado como ACTIVADO pero sin activo_id.")
            abort(404)
        logger.info(f"QR {qr_uuid} está ACTIVADO. Redirigiendo a Hoja de Rescate del activo {qr_item.activo_id}.")
        return redirect(url_for('public.hoja_rescate', uid=qr_item.activo_id))

    else:
        logger.error(f"Estado de QR desconocido: {qr_item.estado}")
        abort(404)


@qr_router_bp.route('/activacion/<qr_uuid>', methods=['GET', 'POST'])
def activar_qr(qr_uuid):
    """
    Flujo de activación de un código QR virgen:
    - Exige autenticación de usuario. Si no hay sesión, redirige a login con next.
    - Despliega formulario para asociar vehículo al QR.
    """
    # 1. Validar que el QR exista
    qr_item = CodigoQR.query.filter_by(id=qr_uuid).first_or_404()

    # Si ya fue activado, derivar directamente a la hoja de rescate
    if qr_item.estado == 'ACTIVADO' and qr_item.activo_id:
        flash('Este código QR ya ha sido activado previamente.', 'info')
        return redirect(url_for('public.hoja_rescate', uid=qr_item.activo_id))

    # 2. Exigir autenticación (redirección a login con next)
    if not current_user.is_authenticated:
        flash('Para activar un nuevo código QR debes iniciar sesión o registrar tu cuenta de cliente.', 'warning')
        return redirect(url_for('auth.login', next=url_for('qr_router.activar_qr', qr_uuid=qr_uuid)))

    # Asegurar que el usuario tenga perfil de cliente
    cliente = current_user.client
    if not cliente and current_user.role != 'admin':
        flash('Tu cuenta no tiene un perfil de cliente asociado. Por favor completa tu registro.', 'danger')
        return redirect(url_for('auth.registro', next=url_for('qr_router.activar_qr', qr_uuid=qr_uuid)))

    # Catálogos para el formulario
    fuel_types = FuelType.query.order_by(FuelType.id).all()
    brands = VehicleTemplate.get_distinct_brands()

    if request.method == 'POST':
        domain = request.form.get('domain', '').strip().upper()
        brand = request.form.get('brand', '').strip()
        model = request.form.get('model', '').strip()
        manufacturing_year = request.form.get('manufacturing_year', type=int)
        fuel_type_id = request.form.get('fuel_type_id', type=int)
        description = request.form.get('description', '').strip()

        # Si es admin, puede asignar a cualquier cliente; si es cliente, se usa current_user.client.id
        client_id = cliente.id if cliente else None
        if current_user.role == 'admin':
            admin_selected_client = request.form.get('client_id', type=int)
            if admin_selected_client:
                client_id = admin_selected_client

        # Validaciones
        errors = []
        if not domain:
            errors.append('El dominio / patente es obligatorio.')
        else:
            existente = Asset.query.filter_by(domain=domain).first()
            if existente:
                errors.append(f'El dominio/patente "{domain}" ya se encuentra registrado en el sistema.')

        if not brand:
            errors.append('Debe seleccionar la marca del vehículo.')
        if not model:
            errors.append('Debe seleccionar el modelo del vehículo.')
        if not fuel_type_id:
            errors.append('Debe seleccionar el tipo de combustible/propulsión.')

        if not client_id:
            errors.append('No se pudo determinar el cliente propietario del activo.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template(
                'public/activacion_qr.html',
                qr=qr_item,
                fuel_types=fuel_types,
                brands=brands,
                form_data=request.form
            )

        # Buscar la mejor plantilla en VehicleTemplate
        template = VehicleTemplate.query.filter(
            VehicleTemplate.brand.ilike(brand),
            VehicleTemplate.model.ilike(model)
        ).first()

        template_id = template.id if template else None

        # Nombre amigable para el activo
        asset_name = f"{brand} {model} - {domain}"

        # Crear nuevo activo
        nuevo_activo = Asset(
            client_id=client_id,
            asset_type='vehicle',
            name=asset_name,
            address_or_model=f"{brand} {model}",
            domain=domain,
            manufacturing_year=manufacturing_year,
            vehicle_template_id=template_id,
            fuel_type_id=fuel_type_id,
            description=description
        )

        try:
            db.session.add(nuevo_activo)
            db.session.flush()  # Para obtener el ID del nuevo activo

            # Enlazar y cambiar estado en CodigoQR
            qr_item.activo_id = nuevo_activo.id
            qr_item.estado = 'ACTIVADO'

            db.session.commit()
            logger.info(f"QR {qr_uuid} activado exitosamente para el activo {nuevo_activo.id} ({domain})")
            flash('¡Vehículo registrado y código QR activado con éxito!', 'success')
            return redirect(url_for('public.hoja_rescate', uid=nuevo_activo.id))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al activar QR {qr_uuid}: {str(e)}")
            flash(f'Ocurrió un error al guardar el vehículo: {str(e)}', 'danger')

    return render_template(
        'public/activacion_qr.html',
        qr=qr_item,
        fuel_types=fuel_types,
        brands=brands,
        form_data={}
    )
