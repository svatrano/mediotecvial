import os
import sys
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def seed_fuel_types(db_session):
    """Inserta los 8 tipos oficiales de combustible si no existen"""
    from librerias.models import FuelType, OFFICIAL_FUEL_TYPES

    inserted = 0
    for item in OFFICIAL_FUEL_TYPES:
        existing = db_session.query(FuelType).filter_by(tipo=item['tipo']).first()
        if not existing:
            fuel = FuelType(
                tipo=item['tipo'],
                descripcion=item['descripcion']
            )
            db_session.add(fuel)
            inserted += 1
        else:
            # Asegurar que la descripción técnica oficial esté actualizada
            existing.descripcion = item['descripcion']

    if inserted > 0:
        db_session.commit()
        logger.info(f"Se insertaron {inserted} tipos de combustible oficiales.")
    else:
        db_session.commit()
        logger.info("Catálogo de tipos de combustible verificado (sin cambios).")


def seed_admin_user(db_session):
    """Crea o actualiza el usuario administrador con las credenciales de las variables de entorno"""
    from librerias.models import User

    admin_username = os.environ.get('USER_ADMIN', 'admin')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'contraseña')
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@mediotecvial.com')

    admin = db_session.query(User).filter_by(username=admin_username).first()
    if not admin:
        admin = User(
            username=admin_username,
            email=admin_email,
            role='admin'
        )
        admin.set_password(admin_password)
        db_session.add(admin)
        db_session.commit()
        logger.info(f"Usuario administrador creado: {admin_username}")
    else:
        # Sincronizar email y contraseña desde las variables de entorno
        admin.email = admin_email
        admin.set_password(admin_password)
        db_session.commit()
        logger.info(f"Usuario administrador actualizado: {admin_username}")


def seed_sample_vehicle_templates(db_session):
    """Carga modelos de ejemplo en Vehicle_templates si la tabla está vacía"""
    from librerias.models import VehicleTemplate

    count = db_session.query(VehicleTemplate).count()
    if count == 0:
        sample_templates = [
            ("TOYOTA", "Corolla", 2023, "https://firewatchstorage.blob.core.windows.net/firewatch-plans/toyota-corolla-2023.pdf"),
            ("TOYOTA", "Hilux", 2024, "https://firewatchstorage.blob.core.windows.net/firewatch-plans/toyota-hilux-2024.pdf"),
            ("TOYOTA", "Yaris", 2022, "https://firewatchstorage.blob.core.windows.net/firewatch-plans/toyota-yaris-2022.pdf"),
            ("FORD", "Ranger", 2023, "https://firewatchstorage.blob.core.windows.net/firewatch-plans/ford-ranger-2023.pdf"),
            ("FORD", "Focus", 2020, "https://firewatchstorage.blob.core.windows.net/firewatch-plans/ford-focus-2020.pdf"),
            ("VOLKSWAGEN", "Amarok", 2024, "https://firewatchstorage.blob.core.windows.net/firewatch-plans/vw-amarok-2024.pdf"),
            ("VOLKSWAGEN", "Gol Trend", 2021, "https://firewatchstorage.blob.core.windows.net/firewatch-plans/vw-gol-2021.pdf"),
            ("CHEVROLET", "Cruze", 2023, "https://firewatchstorage.blob.core.windows.net/firewatch-plans/chevrolet-cruze-2023.pdf"),
            ("RENAULT", "Kangoo", 2022, "https://firewatchstorage.blob.core.windows.net/firewatch-plans/renault-kangoo-2022.pdf"),
            ("PEUGEOT", "208", 2023, "https://firewatchstorage.blob.core.windows.net/firewatch-plans/peugeot-208-2023.pdf"),
        ]
        for brand, model, year, url in sample_templates:
            vt = VehicleTemplate(
                brand=brand,
                model=model,
                year=year,
                rescue_sheet_url=url,
                rescue_sheet_filename=f"{brand.lower()}_{model.lower()}_{year}.pdf"
            )
            db_session.add(vt)
        db_session.commit()
        logger.info(f"Se cargaron {len(sample_templates)} plantillas de vehículos iniciales.")


def run_all_seeds(db_session):
    """Ejecuta todos los seeds necesarios"""
    seed_fuel_types(db_session)
    seed_admin_user(db_session)
    seed_sample_vehicle_templates(db_session)


if __name__ == '__main__':
    from app import create_app
    from librerias.models import db

    app = create_app()
    with app.app_context():
        db.create_all()
        run_all_seeds(db.session)
        print("✅ Seeds ejecutados exitosamente.")
