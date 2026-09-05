import os
import logging
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request
from flask_login import LoginManager, current_user
from flask_cors import CORS
from config import config

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mediotec.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """Factory principal para crear e inicializar la aplicación Flask"""

    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Rutas absolutas para templates y static (soporta librerias/ y raíz)
    template_dir = os.path.join(base_dir, 'librerias', 'templates')
    if not os.path.exists(template_dir):
        template_dir = os.path.join(base_dir, 'templates')

    static_dir = os.path.join(base_dir, 'librerias', 'static')
    if not os.path.exists(static_dir):
        static_dir = os.path.join(base_dir, 'static')

    logger.info(f"Modo: {config_name}")
    logger.info(f"Directorio de plantillas: {template_dir}")
    logger.info(f"Directorio de estáticos: {static_dir}")

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(config.get(config_name, config['default']))

    # Inicializar extensiones
    from librerias.models import db, User
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, inicia sesión primero para continuar.'
    login_manager.login_message_category = 'warning'

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # User loader para Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Registrar Blueprints modulares
    from librerias.routes.public import public_bp
    from librerias.routes.auth import auth_bp
    from librerias.routes.admin import admin_bp
    from librerias.routes.admin_qr import admin_qr_bp
    from librerias.routes.qr_router import qr_router_bp
    from librerias.routes.activos import activos_bp
    from librerias.routes.emergency import emergency_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_qr_bp)
    app.register_blueprint(qr_router_bp)
    app.register_blueprint(activos_bp)
    app.register_blueprint(emergency_bp)

    # Alias y compatibilidad de endpoints para plantillas preexistentes
    @app.route('/', endpoint='index')
    def index():
        from librerias.routes.public import index as public_index
        return public_index()

    @app.route('/home', endpoint='mediotec_home')
    def mediotec_home():
        from librerias.routes.public import home as public_home
        return public_home()

    @app.route('/faq', endpoint='faq')
    def faq():
        from librerias.routes.public import faq as public_faq
        return public_faq()

    @app.route('/noticias', endpoint='noticias')
    @app.route('/actualidad', endpoint='actualidad')
    def noticias():
        from librerias.routes.public import actualidad as public_actualidad
        return public_actualidad()

    @app.route('/politicas-privacidad', endpoint='privacy_policy')
    def privacy_policy():
        from librerias.routes.public import politicas_privacidad as public_privacy
        return public_privacy()

    @app.route('/terminos', endpoint='terms_of_service')
    def terms_of_service():
        from librerias.routes.public import terminos as public_terms
        return public_terms()

    # Manejadores de errores
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Error interno del servidor (500): {error}")
        return render_template('errors/500.html'), 500

    import sqlalchemy.exc
    @app.errorhandler(sqlalchemy.exc.OperationalError)
    @app.errorhandler(sqlalchemy.exc.InterfaceError)
    @app.errorhandler(sqlalchemy.exc.DatabaseError)
    def database_error(error):
        logger.error(f"Error de base de datos: {error}")
        return render_template('errors/db_error.html', error_message=str(error)), 500

    # Inyección de variables globales en plantillas Jinja2
    @app.context_processor
    def inject_globals():
        return {
            'current_year': datetime.utcnow().year,
            'app_name': 'Mediotec Vial',
            'app_version': '3.0.0',
        }

    # Inicialización de tablas y seed automático al iniciar la aplicación
    with app.app_context():
        try:
            db.create_all()
            logger.info("Base de datos verificada/creada exitosamente.")

            # Ejecución de seeds iniciales
            from seed_data import run_all_seeds
            run_all_seeds(db.session)

        except Exception as e:
            logger.warning(f"Aviso durante la inicialización de la base de datos: {e}")

    logger.info(f"Aplicación MediotecVial iniciada correctamente en modo: {config_name}")
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=True
    )
