"""
Suite de Pruebas de Verificación de Correcciones (Tareas 1 a 8) - MediotecVial
"""
import io
import zipfile
from app import create_app
from librerias.models import db, User, Client, Asset, VehicleTemplate, CodigoQR, FuelType

def run_tests():
    print("=" * 70)
    print("🧪 INICIANDO VERIFICACIÓN DE LAS 8 TAREAS DE CORRECCIÓN")
    print("=" * 70)

    app = create_app('testing')
    client = app.test_client()

    with app.app_context():
        # 1. Login como admin
        login_resp = client.post('/login', data={'username': 'admin', 'password': 'contraseña'}, follow_redirects=True)
        assert login_resp.status_code == 200, "Fallo login admin"
        print("  ✅ [Auth] Admin autenticado correctamente")

        # ---------------------------------------------------------------------
        # TAREA 3: Verificación de /perfil y cambio de contraseña
        # ---------------------------------------------------------------------
        print("\n[Tarea 3] Verificando ruta /perfil sin error 500...")
        resp_perfil = client.get('/perfil')
        assert resp_perfil.status_code == 200, f"Fallo /perfil esperado 200, obtenido {resp_perfil.status_code}"
        assert b"admin" in resp_perfil.data, "El nombre de usuario admin debe aparecer en /perfil"
        print("  ✅ GET /perfil -> 200 OK (renderiza correctamente con user/current_user)")

        # ---------------------------------------------------------------------
        # TAREA 1 y 4: Vehicle Templates con subida de archivo y 'Ver documento'
        # ---------------------------------------------------------------------
        print("\n[Tarea 1 y 4] Verificando creación de VehicleTemplate con archivo y endpoint de documento...")
        dummy_pdf = io.BytesIO(b"%PDF-1.4 dummy pdf content for testing")
        data = {
            'brand': 'RENAULT',
            'model': 'KANGOO',
            'year': 2024,
            'file': (dummy_pdf, 'renault_kangoo_2024.pdf')
        }
        resp_create_vt = client.post('/admin/vehicle_templates/crear', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert resp_create_vt.status_code == 200

        vt = VehicleTemplate.query.filter_by(brand='RENAULT', model='KANGOO', year=2024).first()
        assert vt is not None, "El VehicleTemplate debe existir en base de datos"
        assert vt.rescue_sheet_url is not None and len(vt.rescue_sheet_url) > 0, "rescue_sheet_url debe estar persistida"
        print(f"  ✅ Plantilla creada en BD con URL persistida: {vt.rescue_sheet_url}")

        # Ver Documento (Tarea 4)
        resp_doc = client.get(f'/admin/vehicle_templates/{vt.id}/documento')
        assert resp_doc.status_code in [302, 200], f"Fallo /documento: {resp_doc.status_code}"
        print("  ✅ GET /admin/vehicle_templates/<id>/documento -> Redirige correctamente al archivo")

        # ---------------------------------------------------------------------
        # TAREA 2 y 7: admin/qr/gestion (ZIP, CSV, Borrar/Liberar)
        # ---------------------------------------------------------------------
        print("\n[Tarea 2 y 7] Verificando generación y empaquetado ZIP de QRs y acciones en bloque...")
        # Generar un lote de 3 QRs
        resp_gen = client.post('/admin/qr/generar', data={'cantidad': 3, 'lote': 'LOTE-ZIP-TEST'}, follow_redirects=True)
        assert resp_gen.status_code == 200
        qrs = CodigoQR.query.filter_by(lote_impresion='LOTE-ZIP-TEST').all()
        assert len(qrs) == 3
        qr_ids = [q.id for q in qrs]
        print(f"  ✅ Lote generado con {len(qrs)} QRs")

        # Descarga ZIP de seleccionados
        resp_zip = client.post('/admin/qr/acciones/zip', data={'qr_ids': qr_ids})
        assert resp_zip.status_code == 200
        assert resp_zip.headers.get('Content-Type') == 'application/zip'
        with zipfile.ZipFile(io.BytesIO(resp_zip.data)) as zf:
            namelist = zf.namelist()
            assert len(namelist) == 3
            for qid in qr_ids:
                assert f"qr_{qid}.png" in namelist
        print(f"  ✅ POST /admin/qr/acciones/zip -> Archivo ZIP válido recibido con {len(namelist)} PNGs")

        # Descarga CSV de seleccionados
        resp_csv = client.post('/admin/qr/acciones/csv', data={'qr_ids': qr_ids})
        assert resp_csv.status_code == 200
        for qid in qr_ids:
            assert qid.encode() in resp_csv.data
        print("  ✅ POST /admin/qr/acciones/csv -> CSV válido recibido con URLs y UUIDs")

        # Borrar QRs seleccionados
        resp_del = client.post('/admin/qr/acciones/eliminar', data={'qr_ids': qr_ids, 'accion_tipo': 'borrar'}, follow_redirects=True)
        assert resp_del.status_code == 200
        qrs_remaining = CodigoQR.query.filter(CodigoQR.id.in_(qr_ids)).count()
        assert qrs_remaining == 0
        print("  ✅ POST /admin/qr/acciones/eliminar -> Códigos QR eliminados correctamente de la BD")

        # ---------------------------------------------------------------------
        # TAREA 6: Restablecimiento de contraseña desde la web
        # ---------------------------------------------------------------------
        print("\n[Tarea 6] Verificando restablecimiento de contraseña de usuario por admin...")
        # Crear usuario de prueba
        user_test = User(username='test_reset_user', email='test_reset@mediotec.com', role='cliente')
        user_test.set_password('initialpass123')
        db.session.add(user_test)
        db.session.commit()

        resp_reset = client.post(f'/admin/usuarios/{user_test.id}/reset_password', data={'new_password': 'supernewpassword456'}, follow_redirects=True)
        assert resp_reset.status_code == 200
        user_test_updated = User.query.get(user_test.id)
        assert user_test_updated.check_password('supernewpassword456')
        print("  ✅ POST /admin/usuarios/<id>/reset_password -> Contraseña actualizada y validada con nuevo hash")

        # ---------------------------------------------------------------------
        # TAREA 5: Baja física de cliente con activos asociados
        # ---------------------------------------------------------------------
        print("\n[Tarea 5] Verificando baja física de cliente y liberación de QRs...")
        client_test = Client(nombre='Empresa Baja S.A.', dni_cuit='30-77665544-2', mail='baja@empresa.com', user_id=user_test.id)
        db.session.add(client_test)
        db.session.commit()

        fuel = FuelType.query.first()
        asset_test = Asset(client_id=client_test.id, name='Camioneta Rescate', domain='XX111YY', fuel_type_id=fuel.id)
        db.session.add(asset_test)
        db.session.commit()

        qr_asset = CodigoQR(id='99999999-9999-9999-9999-999999999999', lote_impresion='LOTE-BAJA', estado='ACTIVADO', activo_id=asset_test.id)
        db.session.add(qr_asset)
        db.session.commit()

        # Guardar IDs antes de borrar
        client_test_id = client_test.id
        user_test_id = user_test.id
        asset_test_id = asset_test.id

        # Ejecutar baja física con eliminación de vehículos
        resp_baja = client.post(f'/admin/usuarios/{user_test_id}/baja_cliente', data={'eliminar_vehiculos': '1'}, follow_redirects=True)
        assert resp_baja.status_code == 200

        # Verificar que el cliente, usuario y activo ya no existen
        assert Client.query.get(client_test_id) is None
        assert User.query.get(user_test_id) is None
        assert Asset.query.get(asset_test_id) is None

        # Verificar que el QR fue liberado y volvió a estado VIRGEN
        qr_freed = CodigoQR.query.get('99999999-9999-9999-9999-999999999999')
        assert qr_freed is not None
        assert qr_freed.activo_id is None
        assert qr_freed.estado == 'VIRGEN'
        print("  ✅ POST /admin/usuarios/<id>/baja_cliente -> Cliente, usuario y activo eliminados físicamente, y QR liberado a VIRGEN")

        # ---------------------------------------------------------------------
        # TAREA 8: Renderizado de listas de Clientes y Activos
        # ---------------------------------------------------------------------
        print("\n[Tarea 8] Verificando vistas en formato lista de /admin/clientes y /admin/activos...")
        # Crear cliente y activo para verificar tabla
        user_c = User(username='cliente_vista', email='vista@mediotec.com', role='cliente')
        user_c.set_password('pass1234')
        db.session.add(user_c)
        db.session.commit()

        client_c = Client(nombre='Empresa Lista S.A.', dni_cuit='30-11223344-5', mail='vista@mediotec.com', user_id=user_c.id)
        db.session.add(client_c)
        db.session.commit()

        asset_c = Asset(client_id=client_c.id, name='Móvil Prueba', domain='AA123BB', fuel_type_id=fuel.id)
        db.session.add(asset_c)
        db.session.commit()

        resp_clientes = client.get('/admin/clientes')
        assert resp_clientes.status_code == 200
        assert b"<table" in resp_clientes.data and b"Cliente / Raz" in resp_clientes.data
        print("  ✅ GET /admin/clientes -> Formato lista/tabla verificado correctamente")

        resp_activos = client.get('/admin/activos')
        assert resp_activos.status_code == 200
        assert b"<table" in resp_activos.data and b"Activo / Dominio" in resp_activos.data
        print("  ✅ GET /admin/activos -> Formato lista/tabla verificado correctamente")

    print("\n" + "=" * 70)
    print("🎉 TODAS LAS PRUEBAS DE LAS 8 TAREAS PASARON EXITOSAMENTE (0 ERRORES)")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
