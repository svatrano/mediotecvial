import logging
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    abort, jsonify
)
from flask_login import current_user
from librerias.models import Asset, VehicleTemplate, CodigoQR, FuelType

logger = logging.getLogger(__name__)

public_bp = Blueprint('public', __name__)


@public_bp.route('/', methods=['GET'])
def index():
    """Página principal (Home / Landing)"""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('activos.mis_activos'))
    return render_template('public/mediotec_index.html')


@public_bp.route('/home', methods=['GET'])
def home():
    """Alias para la página principal"""
    return render_template('public/mediotec_index.html')


@public_bp.route('/faq', methods=['GET'])
def faq():
    """Sección de preguntas frecuentes"""
    return render_template('public/mediotec_faq.html')


@public_bp.route('/actualidad', methods=['GET'])
@public_bp.route('/noticias', methods=['GET'])
def actualidad():
    """Sección de noticias y novedades de seguridad vial y rescate"""
    return render_template('public/mediotec_noticias.html')


@public_bp.route('/hoja-rescate/<uid>', methods=['GET'])
def hoja_rescate(uid):
    """
    Ficha técnica interactiva del vehículo para rescatistas y bomberos.
    Acceso público inmediato al escanear el QR físico en el lugar del siniestro.
    Permite búsqueda por ID de activo o por UUID de Código QR.
    """
    asset = None

    # 1. Intentar buscar por ID numérico de activo
    if str(uid).isdigit():
        asset = Asset.query.get(int(uid))

    # 2. Si no fue por ID, intentar buscar por UUID de CodigoQR
    if not asset:
        qr = CodigoQR.query.filter_by(id=str(uid)).first()
        if qr and qr.activo_id:
            asset = Asset.query.get(qr.activo_id)

    # 3. Intentar buscar por dominio/patente
    if not asset:
        asset = Asset.query.filter_by(domain=str(uid).upper()).first()

    if not asset:
        logger.warning(f"Hoja de rescate no encontrada para UID: {uid}")
        abort(404)

    # Datos técnicos del activo
    rescue_sheet = asset.vehicle_template
    fuel_type = asset.fuel_type

    # Instrucciones críticas específicas según el tipo de combustible/propulsión
    fuel_hazard_info = _get_fuel_hazard_info(fuel_type.tipo if fuel_type else 'Sin descripcion')

    # Resolver URL del documento PDF de rescate
    file_url = None
    file_type = 'pdf'
    if rescue_sheet and rescue_sheet.rescue_sheet_url:
        file_url = rescue_sheet.rescue_sheet_url
        if file_url.lower().endswith(('.jpg', '.jpeg', '.png')):
            file_type = 'image'

    return render_template(
        'public/hoja_rescate_publica.html',
        asset=asset,
        rescue_sheet=rescue_sheet,
        fuel_type=fuel_type,
        hazard_info=fuel_hazard_info,
        file_url=file_url,
        file_type=file_type,
        now=datetime.utcnow()
    )


@public_bp.route('/politicas-privacidad', methods=['GET'])
def politicas_privacidad():
    """Sección de políticas de privacidad"""
    return render_template('politicas_privacidad.html', now=datetime.utcnow())


@public_bp.route('/terminos', methods=['GET'])
def terminos():
    """Sección de términos y condiciones"""
    return render_template('terminos_condiciones.html', effective_date=datetime.utcnow().date())


@public_bp.route('/health', methods=['GET'])
def health():
    """Endpoint de comprobación de salud para Azure App Service / balanceadores"""
    return jsonify({
        'status': 'healthy',
        'service': 'MediotecVial',
        'version': '3.0.0',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


def _get_fuel_hazard_info(fuel_type_name):
    """Genera recomendaciones críticas de seguridad para el bombero según la propulsión"""
    tipo = (fuel_type_name or '').lower()

    if 'eléctrico' in tipo or 'híbrido' in tipo or 'hybrido' in tipo:
        return {
            'alerta_nivel': 'ALTO RIESGO ELÉCTRICO (ALTA TENSIÓN)',
            'color_badge': 'danger',
            'color_hex': '#E63946',
            'bateria_corte': 'Desconectar primero batería auxiliar de 12V. NUNCA cortar ni tocar cables naranjas de Alta Tensión (HV).',
            'airbags': 'Localizar cápsulas pirotécnicas de inflado en pilares A, B y C antes de realizar cortes con cizalla.',
            'incendio': 'Usar abundante agua para enfriamiento de la celda de baterías (puede ocurrir re-ignición térmica).',
            'icono': 'bi-lightning-charge-fill'
        }
    elif 'gas' in tipo:
        return {
            'alerta_nivel': 'ALTO RIESGO EXPLOSIVO (GAS A PRESIÓN - GNC/GLP)',
            'color_badge': 'warning',
            'color_hex': '#F4A261',
            'bateria_corte': 'Cerrar de inmediato la válvula manual del cilindro de gas en baúl/chasis si es accesible.',
            'airbags': 'Verificar tubos de gas antes de cualquier intervención de expansión en parte trasera o piso.',
            'incendio': 'Controlar fugas con detector de gases explosivos. Mantener perímetro de seguridad.',
            'icono': 'bi-fire'
        }
    elif 'nitro' in tipo:
        return {
            'alerta_nivel': 'RIESGO OXIDANTE / ALTA REACTIVIDAD',
            'color_badge': 'danger',
            'color_hex': '#d90429',
            'bateria_corte': 'Cortar suministro y ventilar habitáculo. Riesgo de aceleración violenta de combustión.',
            'airbags': 'Inspeccionar compartimento motor y maletero con precaución extrema.',
            'incendio': 'Enfriar cilindros presurizados de óxido nitroso desde distancia segura.',
            'icono': 'bi-radioactive'
        }
    elif 'gasoil' in tipo:
        return {
            'alerta_nivel': 'COMBUSTIBLE DIÉSEL / GASOIL',
            'color_badge': 'info',
            'color_hex': '#457b9d',
            'bateria_corte': 'Desconectar borne negativo (-) de batería de 12V para neutralizar circuitos.',
            'airbags': 'Verificar generadores de gas en volantes, tablero y laterales.',
            'incendio': 'Riesgo de ignición por contacto de combustible atomizado con múltiples de escape calientes.',
            'icono': 'bi-fuel-pump-fill'
        }
    else:  # Nafta y por defecto
        return {
            'alerta_nivel': 'COMBUSTIBLE LÍQUIDO INFLAMABLE (NAFTA/GASOLINA)',
            'color_badge': 'primary',
            'color_hex': '#1D3557',
            'bateria_corte': 'Desconectar borne negativo (-) de la batería de 12V.',
            'airbags': 'Respetar distancias de seguridad de airbags no desplegados (15-25 cm).',
            'incendio': 'Extinguir con espuma o polvo químico seco ABC. Mantener línea de agua preventiva cargada.',
            'icono': 'bi-fuel-pump'
        }
