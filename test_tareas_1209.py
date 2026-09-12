"""Pruebas focalizadas para las seis tareas de correccion 1209."""

import io
import zipfile

from app import create_app
from librerias.models import Asset, Client, CodigoQR, FuelType, User, VehicleTemplate, db


def run_tests():
    """Ejecuta las verificaciones nuevas de documentos, QR y portal cliente."""
    app = create_app('testing')
    client = app.test_client()

    with app.app_context():
        admin_login = client.post(
            '/login',
            data={'username': 'admin', 'password': 'contraseña'},
            follow_redirects=False,
        )
        assert admin_login.status_code == 302

        template_response = client.post(
            '/admin/vehicle_templates/crear',
            data={
                'brand': 'FORD',
                'model': 'MUSTANG',
                'year': 2025,
                'file': (io.BytesIO(b'%PDF-1.4 rescue sheet'), 'mustang.pdf'),
            },
            content_type='multipart/form-data',
        )
        assert template_response.status_code == 302
        template = VehicleTemplate.query.filter_by(brand='FORD', model='MUSTANG').first()
        assert template is not None

        user = User(username='cliente_1209', email='cliente_1209@test.local', role='cliente')
        user.set_password('Password123!')
        db.session.add(user)
        db.session.flush()
        owner = Client(
            nombre='Titular que no debe aparecer',
            dni_cuit='20-12091209-1',
            mail='titular@test.local',
            telefono='5555-1209',
            user_id=user.id,
        )
        db.session.add(owner)
        db.session.flush()
        fuel = FuelType.query.filter_by(tipo='Nafta').first()
        asset = Asset(
            client_id=owner.id,
            name='Unidad publica 1209',
            domain='AA1209AA',
            vehicle_template_id=template.id,
            fuel_type_id=fuel.id,
        )
        db.session.add(asset)
        db.session.flush()
        qr = CodigoQR(
            id='12091209-1209-1209-1209-120912091209',
            lote_impresion='LOTE-1209',
            estado='ACTIVADO',
            activo_id=asset.id,
        )
        db.session.add(qr)
        db.session.commit()

        document_response = client.get(
            f'/admin/vehicle_templates/{template.id}/documento'
        )
        assert document_response.status_code == 200
        assert document_response.data.startswith(b'%PDF')
        assert b'blob.core.windows.net' not in document_response.data

        public_response = client.get(f'/hoja-rescate/{asset.id}')
        assert public_response.status_code == 200
        assert b'Titular que no debe aparecer' not in public_response.data
        assert b'20-12091209-1' not in public_response.data
        assert b'5555-1209' not in public_response.data

        public_document = client.get(f'/hoja-rescate/{asset.id}/documento')
        assert public_document.status_code == 200
        assert public_document.data.startswith(b'%PDF')

        qr.estado = 'VIRGEN'
        db.session.commit()
        assert client.get(f'/hoja-rescate/{asset.id}').status_code == 404
        qr.estado = 'ACTIVADO'
        db.session.commit()

        zip_response = client.post(
            '/admin/qr/generar', data={'cantidad': '2', 'lote': 'LOTE-AUTO-1209'}
        )
        assert zip_response.status_code == 200
        assert zip_response.mimetype == 'application/zip'
        with zipfile.ZipFile(io.BytesIO(zip_response.data)) as archive:
            assert len(archive.namelist()) == 2

        client.get('/logout')
        client_login = client.post(
            '/login',
            data={'username': 'cliente_1209', 'password': 'Password123!'},
            follow_redirects=False,
        )
        assert client_login.status_code == 302
        edit_response = client.post(
            f'/cliente/activos/{asset.id}/editar',
            data={
                'vehicle_template_id': str(template.id),
                'fuel_type_id': str(fuel.id),
                'manufacturing_year': '2025',
                'description': 'Actualizado',
            },
            follow_redirects=False,
        )
        assert edit_response.status_code == 302
        assert db.session.get(Asset, asset.id).vehicle_template_id == template.id

    print('Todas las pruebas de tareas 1209 pasaron correctamente.')


if __name__ == '__main__':
    run_tests()