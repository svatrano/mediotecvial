import logging
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, current_app
)
from flask_login import login_user, logout_user, login_required, current_user
from librerias.models import db, User, Client

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Inicio de sesión para administradores y clientes"""
    next_url = request.args.get('next') or request.form.get('next')

    if current_user.is_authenticated:
        if next_url:
            return redirect(next_url)
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('activos.mis_activos'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember_me = bool(request.form.get('remember_me'))

        if not username or not password:
            flash('Por favor ingresa usuario y contraseña.', 'warning')
            return render_template('auth/login.html', next_url=next_url)

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Esta cuenta se encuentra desactivada.', 'danger')
                return render_template('auth/login.html', next_url=next_url)

            login_user(user, remember=remember_me)
            logger.info(f"Usuario {user.username} ha iniciado sesión con rol {user.role}")

            if next_url:
                return redirect(next_url)

            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('activos.mis_activos'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html', next_url=next_url)


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    """Cierre de sesión seguro"""
    username = current_user.username if current_user.is_authenticated else 'Anon'
    logout_user()
    logger.info(f"Usuario {username} ha cerrado sesión")
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('public.index'))


@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """Formulario e inscripción de nuevos clientes desde la interfaz web"""
    next_url = request.args.get('next') or request.form.get('next')

    if current_user.is_authenticated:
        if next_url:
            return redirect(next_url)
        return redirect(url_for('activos.mis_activos'))

    if request.method == 'POST':
        result = _procesar_registro_cliente(request.form)
        if result['success']:
            user = result['user']
            login_user(user)
            flash('¡Registro completado exitosamente! Tu cuenta de cliente ha sido creada.', 'success')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('activos.mis_activos'))
        else:
            flash(result['error'], 'danger')
            return render_template('auth/registro.html', next_url=next_url, form_data=request.form)

    return render_template('auth/registro.html', next_url=next_url, form_data={})


@auth_bp.route('/api/clientes/registro', methods=['POST'])
def api_registro_cliente():
    """API para registro de nuevos clientes (JSON o Form Data)"""
    data = request.get_json() if request.is_json else request.form
    result = _procesar_registro_cliente(data)

    if result['success']:
        user = result['user']
        client = result['client']
        return jsonify({
            'success': True,
            'message': 'Cliente registrado exitosamente',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            },
            'client': {
                'id': client.id,
                'nombre': client.nombre,
                'dni_cuit': client.dni_cuit,
                'mail': client.mail,
                'telefono': client.telefono,
                'direccion': client.direccion
            }
        }), 201
    else:
        return jsonify({'success': False, 'error': result['error']}), 400


def _procesar_registro_cliente(data):
    """Lógica unificada para validar y crear User (role='cliente') y Client"""
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    nombre = data.get('nombre', '').strip()
    dni_cuit = data.get('dni_cuit', '').strip()
    telefono = data.get('telefono', '').strip()
    direccion = data.get('direccion', '').strip()

    # Si username no fue provisto, usar email o dni_cuit
    if not username:
        username = email or dni_cuit

    if not nombre:
        return {'success': False, 'error': 'El nombre es obligatorio.'}
    if not dni_cuit:
        return {'success': False, 'error': 'El DNI o CUIT es obligatorio.'}
    if not email:
        return {'success': False, 'error': 'El correo electrónico es obligatorio.'}
    if not password or len(password) < 6:
        return {'success': False, 'error': 'La contraseña debe tener al menos 6 caracteres.'}

    # Verificar unicidad de username, email y dni_cuit
    if User.query.filter_by(username=username).first():
        return {'success': False, 'error': f'El nombre de usuario "{username}" ya está registrado.'}

    if User.query.filter_by(email=email).first():
        return {'success': False, 'error': f'El correo "{email}" ya está asociado a otra cuenta.'}

    if Client.query.filter_by(dni_cuit=dni_cuit).first():
        return {'success': False, 'error': f'El DNI/CUIT "{dni_cuit}" ya está registrado en el sistema.'}

    try:
        # 1. Crear Usuario con role = "cliente"
        nuevo_user = User(
            username=username,
            email=email,
            role='cliente',
            is_active=True
        )
        nuevo_user.set_password(password)
        db.session.add(nuevo_user)
        db.session.flush()

        # 2. Crear Cliente asociado
        nuevo_client = Client(
            nombre=nombre,
            dni_cuit=dni_cuit,
            direccion=direccion,
            telefono=telefono,
            mail=email,
            user_id=nuevo_user.id
        )
        db.session.add(nuevo_client)
        db.session.commit()

        logger.info(f"Nuevo cliente registrado: {nombre} ({dni_cuit}) con usuario ID {nuevo_user.id}")
        return {'success': True, 'user': nuevo_user, 'client': nuevo_client}

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error registrando cliente: {str(e)}")
        return {'success': False, 'error': f'Error interno en el registro: {str(e)}'}


@auth_bp.route('/perfil', methods=['GET'])
@login_required
def profile():
    """Perfil del usuario logueado"""
    return render_template('auth/profile.html')


@auth_bp.route('/perfil/cambiar-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Cambio de contraseña"""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash('La contraseña actual no es correcta.', 'danger')
            return render_template('auth/change_password.html')

        if len(new_password) < 6:
            flash('La nueva contraseña debe tener al menos 6 caracteres.', 'warning')
            return render_template('auth/change_password.html')

        if new_password != confirm_password:
            flash('Las nuevas contraseñas no coinciden.', 'warning')
            return render_template('auth/change_password.html')

        current_user.set_password(new_password)
        db.session.commit()
        flash('Contraseña actualizada correctamente.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/change_password.html')
