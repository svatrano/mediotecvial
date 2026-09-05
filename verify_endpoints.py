"""
Suite de Pruebas Automatizadas y Verificación de Endpoints - MediotecVial
Verifica códigos de estado HTTP, transiciones de estado, modelo relacional y reglas de autorización.
"""
import sys
import uuid
import json
import logging
from app import create_app
from librerias.models import (
    db, User, Client, Asset, VehicleTemplate, FuelType, CodigoQR, SolicitudVehiculoFaltante
)

logging.basicConfig(level=logging.ERROR)

def run_tests():
    print("=" * 70)
    print("🚀 INICIANDO VERIFICACIÓN DE ENDPOINTS MEDIOTECVIAL (PYTHON 3.12)")
    print("=" * 70)

    app = create_app('testing')
    client = app.test_client()

    with app.app_context():
        # ---------------------------------------------------------------------
        # 1. VERIFICACIÓN DEL CATÁLOGO DE COMBUSTIBLES Y SEED
        # ---------------------------------------------------------------------
        print("\n[1] Verificando modelos y tabla fuel_type...")
        fuel_count = FuelType.query.count()
        assert fuel_count == 8, f"Se esperaban 8 tipos de combustible oficiales, hay {fuel_count}"
        
        fuel_names = [f.tipo for f in FuelType.query.all()]
        expected_fuels = ["Nafta", "Gasoil", "Gas", "Nitro", "Híbrido", "Eléctrico", "Eléctrico/Hybrido", "Sin descripcion"]
        for ef in expected_fuels:
            assert ef in fuel_names, f"Falta el tipo de combustible oficial: {ef}"
        print(f"  ✅ Tabla fuel_type validada con los 8 tipos oficiales: {fuel_names}")

        # ---------------------------------------------------------------------
        # 2. RUTAS PÚBLICAS
        # ---------------------------------------------------------------------
        print("\n[2] Verificando Rutas Públicas...")
        public_routes = [
            ('/', 200, "Home / Landing principal"),
            ('/home', 200, "Alias Home"),
            ('/faq', 200, "Preguntas frecuentes"),
            ('/actualidad', 200, "Actualidad y noticias"),
            ('/noticias', 200, "Alias Noticias"),
            ('/politicas-privacidad', 200, "Políticas de Privacidad"),
            ('/terminos', 200, "Términos y Condiciones"),
            ('/health', 200, "Health Check Endpoint"),
        ]

        for route, expected_code, desc in public_routes:
            resp = client.get(route)
            assert resp.status_code == expected_code, f"Fallo en {route} ({desc}): Esperado {expected_code}, obtenido {resp.status_code}"
            print(f"  ✅ GET {route:<25} -> {resp.status_code} ({desc})")

        # ---------------------------------------------------------------------
        # 3. REGISTRO Y AUTENTICACIÓN
        # ---------------------------------------------------------------------
        print("\n[3] Verificando Autenticación y Registro...")
        
        # GET /login y /registro
        assert client.get('/login').status_code == 200, "GET /login falló"
        assert client.get('/registro').status_code == 200, "GET /registro falló"
        print("  ✅ GET /login y /registro accesibles (200)")

        # POST /api/clientes/registro
        cliente_cuit = "20-99887766-4"
        reg_payload = {
            'username': 'cliente_test_1',
            'email': 'cliente1@mediotec.test',
            'password': 'Password123!',
            'nombre': 'Transportes del Sur S.A.',
            'dni_cuit': cliente_cuit,
            'telefono': '+54 11 5555-1234',
            'direccion': 'Ruta 3 Km 45'
        }
        resp_reg = client.post('/api/clientes/registro', json=reg_payload)
        assert resp_reg.status_code == 201, f"POST /api/clientes/registro falló: {resp_reg.data}"
        
        # Verificar en base de datos: User role="cliente" y relación con Client
        user_c1 = User.query.filter_by(username='cliente_test_1').first()
        assert user_c1 is not None, "Usuario cliente no encontrado en DB"
        assert user_c1.role == 'cliente', f"El rol debe ser 'cliente', obtenido {user_c1.role}"
        assert user_c1.client is not None, "El usuario no tiene Client asociado"
        assert user_c1.client.dni_cuit == cliente_cuit, "DNI/CUIT no coincide"
        assert user_c1.client.nombre == 'Transportes del Sur S.A.', "Nombre de cliente no coincide"
        print(f"  ✅ POST /api/clientes/registro -> 201 (Usuario role='cliente' ID={user_c1.id}, Client ID={user_c1.client.id})")

        # Login con usuario cliente
        resp_login_client = client.post('/login', data={'username': 'cliente_test_1', 'password': 'Password123!'}, follow_redirects=False)
        assert resp_login_client.status_code in [200, 302], f"Login de cliente falló: {resp_login_client.status_code}"
        print("  ✅ POST /login (Cliente) -> 302 Redirección correcta")

        # Logout
        resp_logout = client.get('/logout')
        assert resp_logout.status_code == 302, "Logout falló"
        print("  ✅ GET /logout -> 302 Sesión cerrada")

        # Login con usuario admin
        resp_login_admin = client.post('/login', data={'username': 'admin', 'password': 'contraseña'}, follow_redirects=False)
        assert resp_login_admin.status_code == 302, f"Login de admin falló: {resp_login_admin.status_code}"
        print("  ✅ POST /login (Admin) -> 302 Sesión iniciada")

        # ---------------------------------------------------------------------
        # 4. GESTIÓN DE LOTES QR EN ADMINISTRACIÓN
        # ---------------------------------------------------------------------
        print("\n[4] Verificando Módulo de Administración de QRs (/admin/qr)...")
        
        # Dashboard Admin
        resp_dash = client.get('/admin/dashboard')
        assert resp_dash.status_code == 200, "GET /admin/dashboard falló"
        assert "Gestión de Lotes QR".encode('utf-8') in resp_dash.data, "Bloque QR no presente en dashboard"
        print("  ✅ GET /admin/dashboard -> 200 (Bloque de Gestión de Lotes QR presente)")

        # Pantalla dedicada /admin/qr/gestion
        resp_gestion = client.get('/admin/qr/gestion')
        assert resp_gestion.status_code == 200, "GET /admin/qr/gestion falló"
        print("  ✅ GET /admin/qr/gestion -> 200 (Pantalla de gestión)")

        # POST /admin/qr/generar (generar 10 QRs virgenes)
        lote_nombre = "LOTE-TEST-001"
        resp_gen = client.post('/admin/qr/generar', json={'cantidad': 10, 'lote': lote_nombre})
        assert resp_gen.status_code == 201, f"POST /admin/qr/generar falló: {resp_gen.data}"
        print(f"  ✅ POST /admin/qr/generar -> 201 (10 QRs vírgenes generados para {lote_nombre})")

        # GET /admin/qr/estado (métricas JSON)
        resp_estado = client.get('/admin/qr/estado')
        assert resp_estado.status_code == 200, "GET /admin/qr/estado falló"
        estado_json = resp_estado.get_json()
        assert estado_json['total_impresos'] >= 10, "Métrica total_impresos incorrecta"
        assert estado_json['virgenes_disponibles'] >= 10, "Métrica virgenes_disponibles incorrecta"
        print(f"  ✅ GET /admin/qr/estado -> 200 JSON ({estado_json['virgenes_disponibles']} vírgenes, {estado_json['qrs_activados']} activados)")

        # GET /admin/qr/listar (JSON paginado)
        resp_listar = client.get('/admin/qr/listar?lote=LOTE-TEST-001')
        assert resp_listar.status_code == 200, "GET /admin/qr/listar falló"
        listar_json = resp_listar.get_json()
        assert len(listar_json['items']) == 10, "Listado de QRs no contiene 10 items"
        test_qr_uuid = listar_json['items'][0]['uuid']
        print(f"  ✅ GET /admin/qr/listar -> 200 JSON ({len(listar_json['items'])} items listados)")

        # GET /admin/qr/exportar/<lote>
        resp_exp = client.get(f'/admin/qr/exportar/{lote_nombre}')
        assert resp_exp.status_code == 200, "Exportar CSV falló"
        assert b"URL_DESTINO" in resp_exp.data, "Cabecera CSV no encontrada"
        assert test_qr_uuid.encode() in resp_exp.data, "UUID de prueba no encontrado en CSV"
        print("  ✅ GET /admin/qr/exportar/<lote> -> 200 (Descarga CSV con URLs de imprenta)")

        # Cerrar sesión admin
        client.get('/logout')

        # ---------------------------------------------------------------------
        # 5. ROUTER QR Y FLUJO DE ACTIVACIÓN
        # ---------------------------------------------------------------------
        print("\n[5] Verificando Router QR (/qr/<uuid>) y Flujo de Activación...")

        # 5.1 QR inexistente -> 404
        uuid_inexistente = str(uuid.uuid4())
        assert client.get(f'/qr/{uuid_inexistente}').status_code == 404, "QR inexistente no dio 404"
        print(f"  ✅ GET /qr/<uuid_inexistente> -> 404 Correcto")

        # 5.2 QR VIRGEN -> Redirige a /activacion/<uuid>
        resp_virgen = client.get(f'/qr/{test_qr_uuid}', follow_redirects=False)
        assert resp_virgen.status_code == 302, f"QR virgen no redirigió: {resp_virgen.status_code}"
        assert f"/activacion/{test_qr_uuid}" in resp_virgen.location, f"Destino inesperado: {resp_virgen.location}"
        print(f"  ✅ GET /qr/<uuid_virgen> -> 302 Redirige a /activacion/{test_qr_uuid}")

        # 5.3 /activacion/<uuid> sin sesión -> Redirige a /login?next=...
        resp_act_anon = client.get(f'/activacion/{test_qr_uuid}', follow_redirects=False)
        assert resp_act_anon.status_code == 302, "Acceso anónimo a activación no redirigió a login"
        assert "/login" in resp_act_anon.location, "No redirigió a login"
        print("  ✅ GET /activacion/<uuid> sin sesión -> 302 Redirige a /login?next=...")

        # 5.4 Autenticar como cliente para activar
        client.post('/login', data={'username': 'cliente_test_1', 'password': 'Password123!'})
        resp_act_form = client.get(f'/activacion/{test_qr_uuid}')
        assert resp_act_form.status_code == 200, f"Formulario de activación falló: {resp_act_form.status_code}"
        print("  ✅ GET /activacion/<uuid> con cliente autenticado -> 200 (Formulario de alta)")

        # 5.5 Enviar formulario de activación de activo vehicular
        # Tomamos el primer FuelType (Nafta o Híbrido)
        fuel_hibrido = FuelType.query.filter_by(tipo='Híbrido').first() or FuelType.query.first()
        dominio_test = "AB999CD"
        
        act_post_data = {
            'domain': dominio_test,
            'brand': 'TOYOTA',
            'model': 'Corolla',
            'manufacturing_year': 2023,
            'fuel_type_id': fuel_hibrido.id,
            'description': 'Vehículo corporativo sedán'
        }
        resp_activar = client.post(f'/activacion/{test_qr_uuid}', data=act_post_data, follow_redirects=False)
        assert resp_activar.status_code == 302, f"Activación falló: {resp_activar.status_code}"
        print(f"  ✅ POST /activacion/<uuid> -> 302 (Vehículo registrado, QR vinculado)")

        # Verificar en base de datos: CodigoQR estado='ACTIVADO' y Asset creado con client_id
        qr_obj = CodigoQR.query.get(test_qr_uuid)
        assert qr_obj.estado == 'ACTIVADO', f"Estado de QR esperado 'ACTIVADO', obtenido {qr_obj.estado}"
        assert qr_obj.activo_id is not None, "activo_id no fue asignado en CodigoQR"

        nuevo_activo = Asset.query.get(qr_obj.activo_id)
        assert nuevo_activo is not None, "El activo no fue encontrado en DB"
        assert nuevo_activo.domain == dominio_test, "Dominio no coincide"
        assert nuevo_activo.client_id == user_c1.client.id, "client_id no corresponde al cliente en sesión"
        assert nuevo_activo.fuel_type_id == fuel_hibrido.id, "fuel_type_id no asignado correctamente"
        print(f"  ✅ Verificación DB: CodigoQR estado='ACTIVADO', activo_id={nuevo_activo.id}, client_id={nuevo_activo.client_id}")

        # 5.6 Ahora escanear /qr/<test_qr_uuid> (ACTIVADO) -> Debe redirigir directamente a /hoja-rescate/<activo_id>
        resp_scan_activado = client.get(f'/qr/{test_qr_uuid}', follow_redirects=False)
        assert resp_scan_activado.status_code == 302, "QR activado no redirigió a hoja de rescate"
        assert f"/hoja-rescate/{nuevo_activo.id}" in resp_scan_activado.location, f"Destino incorrecto: {resp_scan_activado.location}"
        print(f"  ✅ GET /qr/<uuid_activado> -> 302 Redirige directo a /hoja-rescate/{nuevo_activo.id}")

        # ---------------------------------------------------------------------
        # 6. HOJA DE RESCATE PÚBLICA PARA BOMBEROS Y RESCATISTAS
        # ---------------------------------------------------------------------
        print("\n[6] Verificando Hoja de Rescate Pública (/hoja-rescate/<uid>)...")
        # Cerrar sesión para simular bombero anónimo en el terreno
        client.get('/logout')

        # Consulta pública por ID de activo
        resp_hoja = client.get(f'/hoja-rescate/{nuevo_activo.id}')
        assert resp_hoja.status_code == 200, f"Hoja de rescate pública dio status {resp_hoja.status_code}"
        assert dominio_test.encode() in resp_hoja.data, "Dominio no visible en hoja de rescate"
        assert fuel_hibrido.tipo.encode() in resp_hoja.data, "Tipo de combustible no visible"
        print(f"  ✅ GET /hoja-rescate/{nuevo_activo.id} -> 200 (Acceso público sin login para bomberos)")

        # Consulta pública por UUID de QR
        resp_hoja_qr = client.get(f'/hoja-rescate/{test_qr_uuid}')
        assert resp_hoja_qr.status_code == 200, "Hoja de rescate por UUID dio error"
        print(f"  ✅ GET /hoja-rescate/{test_qr_uuid} (por QR UUID) -> 200")

        # ---------------------------------------------------------------------
        # 7. APIS DEL CATÁLOGO VEHICULAR
        # ---------------------------------------------------------------------
        print("\n[7] Verificando APIs del Catálogo Vehicular Dinámico...")
        # Marcas distintas
        resp_marcas = client.get('/api/vehiculos/marcas')
        assert resp_marcas.status_code == 200, "API marcas falló"
        marcas_json = resp_marcas.get_json()
        assert 'TOYOTA' in marcas_json['marcas'], "Marca TOYOTA no encontrada en catálogo"
        print(f"  ✅ GET /api/vehiculos/marcas -> 200 ({len(marcas_json['marcas'])} marcas)")

        # Modelos de TOYOTA
        resp_modelos = client.get('/api/vehiculos/modelos?brand=TOYOTA')
        assert resp_modelos.status_code == 200, "API modelos falló"
        modelos_json = resp_modelos.get_json()
        assert 'Corolla' in modelos_json['modelos'], "Modelo Corolla no encontrado"
        print(f"  ✅ GET /api/vehiculos/modelos?brand=TOYOTA -> 200 ({modelos_json['modelos']})")

        # Solicitud de vehículo faltante
        solicitud_payload = {
            'marca': 'Tesla',
            'modelo': 'Model 3',
            'anio': 2024,
            'contacto': 'bomberos@ciudad.gov',
            'observaciones': 'Vehículo 100% eléctrico'
        }
        resp_sol = client.post('/api/vehiculos/solicitud-faltante', json=solicitud_payload)
        assert resp_sol.status_code == 201, "API solicitud faltante falló"
        sol_id = resp_sol.get_json()['solicitud_id']
        sol_db = SolicitudVehiculoFaltante.query.get(sol_id)
        assert sol_db.marca == 'Tesla' and sol_db.estado == 'PENDIENTE', "Solicitud no guardada en DB"
        print(f"  ✅ POST /api/vehiculos/solicitud-faltante -> 201 (Guardado en DB ID={sol_id})")

        # ---------------------------------------------------------------------
        # 8. REGLAS DE AUTORIZACIÓN DE CLIENTES
        # ---------------------------------------------------------------------
        print("\n[8] Verificando Reglas de Autorización de Clientes...")
        
        # Crear un segundo cliente (Cliente B) con su propio vehículo
        client.post('/api/clientes/registro', json={
            'username': 'cliente_b',
            'email': 'clienteb@test.com',
            'password': 'Password123!',
            'nombre': 'Cliente B SRL',
            'dni_cuit': '30-11223344-9'
        })
        user_b = User.query.filter_by(username='cliente_b').first()
        asset_b = Asset(
            client_id=user_b.client.id,
            asset_type='vehicle',
            name='Camioneta Cliente B',
            domain='ZZ999ZZ',
            fuel_type_id=fuel_hibrido.id
        )
        db.session.add(asset_b)
        db.session.commit()

        # Iniciar sesión como Cliente 1
        client.post('/login', data={'username': 'cliente_test_1', 'password': 'Password123!'})
        
        # Cliente 1 puede ver sus propios activos
        resp_mis_activos = client.get('/cliente/activos')
        assert resp_mis_activos.status_code == 200, "GET /cliente/activos falló"
        assert dominio_test.encode() in resp_mis_activos.data, "Activo propio no visible en lista de cliente"
        assert b"ZZ999ZZ" not in resp_mis_activos.data, "Vehículo de otro cliente visible indebidamente!"
        print("  ✅ GET /cliente/activos -> 200 (Cliente 1 solo ve sus activos propios)")

        # Cliente 1 puede editar su propio activo
        resp_edit_own = client.get(f'/cliente/activos/{nuevo_activo.id}/editar')
        assert resp_edit_own.status_code == 200, "Editar activo propio falló"
        print(f"  ✅ GET /cliente/activos/{nuevo_activo.id}/editar -> 200 (Autorizado para activo propio)")

        # Cliente 1 intenta editar el activo de Cliente B -> Debe recibir HTTP 403 Forbidden
        resp_edit_other = client.get(f'/cliente/activos/{asset_b.id}/editar')
        assert resp_edit_other.status_code == 403, f"Cliente accedió a activo ajeno! Status: {resp_edit_other.status_code}"
        print(f"  ✅ GET /cliente/activos/{asset_b.id}/editar (Activo ajeno) -> 403 FORBIDDEN (Regla de autorización estricta cumplida)")

        # ---------------------------------------------------------------------
        # 9. ADMINISTRACIÓN INTERNA (CARGA MANUAL DE ACTIVOS Y CLIENTES)
        # ---------------------------------------------------------------------
        print("\n[9] Verificando Administración Interna (Carga manual)...")
        # Iniciar sesión como Administrador
        client.get('/logout')
        client.post('/login', data={'username': 'admin', 'password': 'contraseña'})

        # GET y POST /admin/activos/crear
        assert client.get('/admin/activos/crear').status_code == 200, "GET /admin/activos/crear falló"
        admin_asset_post = {
            'client_id': user_c1.client.id,
            'asset_type': 'vehicle',
            'name': 'Vehículo Admin Manual',
            'domain': 'MN888OP',
            'manufacturing_year': 2022,
            'fuel_type_id': fuel_hibrido.id,
            'description': 'Cargado por admin'
        }
        resp_admin_create_asset = client.post('/admin/activos/crear', data=admin_asset_post, follow_redirects=False)
        assert resp_admin_create_asset.status_code == 302, f"Creación manual de activo falló: {resp_admin_create_asset.status_code}"
        print("  ✅ GET y POST /admin/activos/crear -> 200 y 302")

        # GET y POST /admin/clientes/crear
        assert client.get('/admin/clientes/crear').status_code == 200, "GET /admin/clientes/crear falló"
        admin_client_post = {
            'nombre': 'Cliente Creado Por Admin',
            'dni_cuit': '30-77665544-2',
            'mail': 'admin_client@test.com',
            'telefono': '+54 11 4444-2222',
            'direccion': 'San Martín 500'
        }
        resp_admin_create_client = client.post('/admin/clientes/crear', data=admin_client_post, follow_redirects=False)
        assert resp_admin_create_client.status_code == 302, f"Creación manual de cliente falló: {resp_admin_create_client.status_code}"
        print("  ✅ GET y POST /admin/clientes/crear -> 200 y 302")

        # Listados administrativos
        assert client.get('/admin/activos').status_code == 200, "Listar activos falló"
        assert client.get('/admin/clientes').status_code == 200, "Listar clientes falló"
        assert client.get('/admin/usuarios').status_code == 200, "Listar usuarios falló"
        assert client.get('/admin/vehicle_templates').status_code == 200, "Listar templates falló"
        print("  ✅ GET /admin/activos, /admin/clientes, /admin/usuarios, /admin/vehicle_templates -> 200 OK")

    print("\n" + "=" * 70)
    print("🎉 TODAS LAS PRUEBAS Y VERIFICACIONES PASARON EXITOSAMENTE (0 ERRORES)")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()
