import io
import csv
import uuid
import logging
from datetime import datetime
from functools import wraps
from zipfile import ZipFile
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, Response, send_file, current_app
)
from flask_login import login_required, current_user
from sqlalchemy import or_
from librerias.models import db, CodigoQR, Asset, Client
from librerias.services.qr_service import generate_qr_image_bytes

logger = logging.getLogger(__name__)

admin_qr_bp = Blueprint('admin_qr', __name__, url_prefix='/admin/qr')


def admin_required(f):
    """Decorador para restringir acceso exclusivamente a administradores"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado: se requieren permisos de Administrador.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@admin_qr_bp.route('/gestion', methods=['GET'])
@login_required
@admin_required
def gestion_qrs():
    """Pantalla dedicada de gestión de QRs e impresión de lotes"""
    # Métricas
    total_qrs = CodigoQR.query.count()
    virgenes = CodigoQR.query.filter_by(estado='VIRGEN').count()
    activados = CodigoQR.query.filter_by(estado='ACTIVADO').count()

    # Filtros
    estado_filtro = request.args.get('estado', '').strip()
    lote_filtro = request.args.get('lote', '').strip()
    busqueda = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    query = CodigoQR.query.outerjoin(Asset, CodigoQR.activo_id == Asset.id).outerjoin(Client, Asset.client_id == Client.id)

    if estado_filtro in ['VIRGEN', 'ACTIVADO']:
        query = query.filter(CodigoQR.estado == estado_filtro)

    if lote_filtro:
        query = query.filter(CodigoQR.lote_impresion == lote_filtro)

    if busqueda:
        query = query.filter(
            or_(
                CodigoQR.id.ilike(f'%{busqueda}%'),
                CodigoQR.lote_impresion.ilike(f'%{busqueda}%'),
                Asset.domain.ilike(f'%{busqueda}%'),
                Asset.name.ilike(f'%{busqueda}%'),
                Client.nombre.ilike(f'%{busqueda}%')
            )
        )

    qrs_paginados = query.order_by(CodigoQR.fecha_generacion.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    # Lista de lotes únicos para el filtro
    lotes = [r[0] for r in db.session.query(CodigoQR.lote_impresion).distinct().order_by(CodigoQR.lote_impresion.desc()).all() if r[0]]

    return render_template(
        'admin/qr_gestion.html',
        total_qrs=total_qrs,
        virgenes=virgenes,
        activados=activados,
        qrs=qrs_paginados,
        lotes=lotes,
        estado_filtro=estado_filtro,
        lote_filtro=lote_filtro,
        busqueda=busqueda
    )


@admin_qr_bp.route('/generar', methods=['POST'])
@login_required
@admin_required
def generar_lote():
    """Genera lote de UUIDs en estado 'VIRGEN'"""
    # Acepta tanto JSON como Form Data
    if request.is_json:
        data = request.get_json() or {}
        cantidad = int(data.get('cantidad', 0))
        lote = str(data.get('lote', '')).strip()
    else:
        try:
            cantidad = int(request.form.get('cantidad', 0))
        except (ValueError, TypeError):
            cantidad = 0
        lote = request.form.get('lote', '').strip()

    if cantidad <= 0 or cantidad > 10000:
        msg = 'La cantidad debe ser un número entero positivo entre 1 y 10.000.'
        if request.is_json:
            return jsonify({'success': False, 'error': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('admin_qr.gestion_qrs'))

    if not lote:
        lote = f"LOTE-{datetime.utcnow().strftime('%Y%m%d-%H%M')}"

    nuevos_qrs = []
    ahora = datetime.utcnow()
    for _ in range(cantidad):
        nuevo_id = str(uuid.uuid4())
        qr_obj = CodigoQR(
            id=nuevo_id,
            lote_impresion=lote,
            estado='VIRGEN',
            fecha_generacion=ahora,
            activo_id=None
        )
        nuevos_qrs.append(qr_obj)

    try:
        db.session.bulk_save_objects(nuevos_qrs)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        msg = f'Error al generar lote de QRs: {str(e)}'
        if request.is_json:
            return jsonify({'success': False, 'error': msg}), 500
        flash(msg, 'danger')
        return redirect(url_for('admin_qr.gestion_qrs'))

    success_msg = f'Se generaron exitosamente {cantidad} códigos QR vírgenes para el lote "{lote}".'
    if request.is_json:
        return jsonify({
            'success': True,
            'message': success_msg,
            'lote': lote,
            'cantidad': cantidad
        }), 201

    return build_qrs_zip(nuevos_qrs, f"lote_{lote}_qrs.zip")


@admin_qr_bp.route('/estado', methods=['GET'])
@login_required
@admin_required
def estado_metricas():
    """Devuelve resumen de métricas en formato JSON"""
    total_qrs = CodigoQR.query.count()
    virgenes = CodigoQR.query.filter_by(estado='VIRGEN').count()
    activados = CodigoQR.query.filter_by(estado='ACTIVADO').count()
    lotes = [r[0] for r in db.session.query(CodigoQR.lote_impresion).distinct().all() if r[0]]

    return jsonify({
        'total_impresos': total_qrs,
        'virgenes_disponibles': virgenes,
        'qrs_activados': activados,
        'total_lotes': len(lotes),
        'lotes': lotes,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@admin_qr_bp.route('/listar', methods=['GET'])
@login_required
@admin_required
def listar_qrs():
    """Listado paginado y filtrable de QRs en JSON"""
    estado = request.args.get('estado', '').strip()
    lote = request.args.get('lote', '').strip()
    busqueda = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    query = CodigoQR.query.outerjoin(Asset, CodigoQR.activo_id == Asset.id).outerjoin(Client, Asset.client_id == Client.id)

    if estado:
        query = query.filter(CodigoQR.estado == estado)
    if lote:
        query = query.filter(CodigoQR.lote_impresion == lote)
    if busqueda:
        query = query.filter(
            or_(
                CodigoQR.id.ilike(f'%{busqueda}%'),
                CodigoQR.lote_impresion.ilike(f'%{busqueda}%'),
                Asset.domain.ilike(f'%{busqueda}%')
            )
        )

    pag = query.order_by(CodigoQR.fecha_generacion.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    base_url = request.host_url.rstrip('/')
    items = []
    for qr_item in pag.items:
        items.append({
            'uuid': qr_item.id,
            'url': f"{base_url}/qr/{qr_item.id}",
            'lote': qr_item.lote_impresion,
            'estado': qr_item.estado,
            'fecha_generacion': qr_item.fecha_generacion.isoformat() if qr_item.fecha_generacion else None,
            'activo_id': qr_item.activo_id,
            'activo_dominio': qr_item.activo.domain if qr_item.activo else None,
            'activo_nombre': qr_item.activo.name if qr_item.activo else None,
            'cliente_nombre': qr_item.activo.client.nombre if qr_item.activo and qr_item.activo.client else None
        })

    return jsonify({
        'total': pag.total,
        'pages': pag.pages,
        'current_page': pag.page,
        'per_page': pag.per_page,
        'items': items
    }), 200


@admin_qr_bp.route('/exportar/<lote>', methods=['GET'])
@login_required
@admin_required
def exportar_lote_csv(lote):
    """Descarga archivo CSV/TXT con el listado de URLs para la imprenta"""
    qrs = CodigoQR.query.filter_by(lote_impresion=lote).order_by(CodigoQR.fecha_generacion.asc()).all()

    if not qrs:
        flash(f'No se encontraron códigos QR para el lote "{lote}".', 'warning')
        return redirect(url_for('admin_qr.gestion_qrs'))

    base_url = request.host_url.rstrip('/')
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['UUID', 'URL_DESTINO', 'LOTE', 'ESTADO', 'FECHA_GENERACION'])

    for qr_item in qrs:
        writer.writerow([
            qr_item.id,
            f"{base_url}/qr/{qr_item.id}",
            qr_item.lote_impresion,
            qr_item.estado,
            qr_item.fecha_generacion.strftime('%Y-%m-%d %H:%M:%S') if qr_item.fecha_generacion else ''
        ])

    csv_data = output.getvalue()
    filename = f"lote_{lote}_urls_imprenta.csv"

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


def build_qrs_zip(qr_objects, zip_filename="qrs.zip"):
    """Genera archivo ZIP en memoria con imágenes PNG para los códigos QR dados"""
    base_url = request.host_url.rstrip('/')
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, 'w') as zf:
        for qr in qr_objects:
            target_url = f"{base_url}/qr/{qr.id}"
            img_io = generate_qr_image_bytes(target_url)
            zf.writestr(f"qr_{qr.id}.png", img_io.getvalue())
    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    )


@admin_qr_bp.route('/lote/<lote>/zip', methods=['GET'])
@login_required
@admin_required
def descargar_lote_zip(lote):
    """Descarga archivo ZIP con todas las imágenes PNG del lote"""
    qrs = CodigoQR.query.filter_by(lote_impresion=lote).order_by(CodigoQR.fecha_generacion.asc()).all()
    if not qrs:
        flash(f'No se encontraron códigos QR para el lote "{lote}".', 'warning')
        return redirect(url_for('admin_qr.gestion_qrs'))

    filename = f"lote_{lote}_pngs.zip"
    return build_qrs_zip(qrs, filename)


@admin_qr_bp.route('/acciones/zip', methods=['POST'])
@login_required
@admin_required
def descargar_seleccionados_zip():
    """Genera y descarga archivo ZIP con imágenes PNG de los QRs seleccionados"""
    qr_ids = request.form.getlist('qr_ids')
    if not qr_ids:
        flash('No se seleccionó ningún código QR para exportar imágenes.', 'warning')
        return redirect(url_for('admin_qr.gestion_qrs'))

    qrs = CodigoQR.query.filter(CodigoQR.id.in_(qr_ids)).order_by(CodigoQR.fecha_generacion.asc()).all()
    filename = f"qrs_seleccionados_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
    return build_qrs_zip(qrs, filename)


@admin_qr_bp.route('/acciones/csv', methods=['POST'])
@login_required
@admin_required
def exportar_seleccionados_csv():
    """Genera y descarga CSV con las URLs de activación/rescate de los QRs seleccionados"""
    qr_ids = request.form.getlist('qr_ids')
    if not qr_ids:
        flash('No se seleccionó ningún código QR para exportar CSV.', 'warning')
        return redirect(url_for('admin_qr.gestion_qrs'))

    qrs = CodigoQR.query.filter(CodigoQR.id.in_(qr_ids)).order_by(CodigoQR.fecha_generacion.asc()).all()
    base_url = request.host_url.rstrip('/')
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['UUID', 'URL_DESTINO', 'LOTE', 'ESTADO', 'FECHA_GENERACION'])

    for qr_item in qrs:
        writer.writerow([
            qr_item.id,
            f"{base_url}/qr/{qr_item.id}",
            qr_item.lote_impresion,
            qr_item.estado,
            qr_item.fecha_generacion.strftime('%Y-%m-%d %H:%M:%S') if qr_item.fecha_generacion else ''
        ])

    csv_data = output.getvalue()
    filename = f"qrs_seleccionados_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@admin_qr_bp.route('/acciones/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar_o_liberar_seleccionados():
    """Borra QRs vírgenes seleccionados y libera (desvincula) QRs activados seleccionados"""
    qr_ids = request.form.getlist('qr_ids')
    accion = request.form.get('accion_tipo', 'auto')
    if not qr_ids:
        flash('No se seleccionó ningún código QR para eliminar o liberar.', 'warning')
        return redirect(url_for('admin_qr.gestion_qrs'))

    qrs = CodigoQR.query.filter(CodigoQR.id.in_(qr_ids)).all()
    borrados = 0
    liberados = 0

    try:
        for qr in qrs:
            if qr.estado == 'VIRGEN' or accion == 'borrar':
                if qr.activo_id:
                    qr.activo_id = None
                db.session.delete(qr)
                borrados += 1
            else:
                qr.activo_id = None
                qr.estado = 'VIRGEN'
                liberados += 1

        db.session.commit()
        logger.info(f"QRs procesados en lote: {borrados} borrados, {liberados} liberados a VIRGEN.")
        flash(f'Operación completada: {borrados} QRs eliminados y {liberados} QRs liberados a estado VIRGEN.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al eliminar/liberar QRs: {str(e)}")
        flash(f'Error al procesar la acción sobre los QRs: {str(e)}', 'danger')

    return redirect(url_for('admin_qr.gestion_qrs'))
