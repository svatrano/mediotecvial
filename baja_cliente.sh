#!/usr/bin/env bash
# ==============================================================================
# Script: baja_cliente.sh - MediotecVial
# Propósito: Realizar la baja física de un cliente directamente en la base de datos
#           (Azure SQL Database o entorno configurado), con opción de eliminar
#           sus vehículos asociados y liberar sus códigos QR físicos.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
fi

$PYTHON_BIN - << 'EOF'
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from librerias.models import db, User, Client, Asset, CodigoQR, EmergencyPlan, SolicitudVehiculoFaltante

app = create_app(os.environ.get('FLASK_ENV', 'development'))

with app.app_context():
    print("=" * 70)
    print("🗑️  BAJA FÍSICA DE CLIENTE - MEDIOTECVIAL (AZURE SQL)")
    print("=" * 70)

    # Identificador ingresado como argumento o solicitado interactivamente
    identificador = None
    if len(sys.argv) > 1:
        identificador = sys.argv[1].strip()
    
    if not identificador:
        identificador = input("👉 Ingrese Username, Email, DNI/CUIT o ID de Cliente: ").strip()

    if not identificador:
        print("❌ Error: No se proporcionó ningún identificador.")
        sys.exit(1)

    # Buscar Cliente
    client = None
    if identificador.isdigit():
        client = Client.query.get(int(identificador))

    if not client:
        client = Client.query.filter(
            (Client.dni_cuit == identificador) |
            (Client.mail.ilike(identificador))
        ).first()

    if not client:
        # Buscar por usuario
        user = User.query.filter(
            (User.username.ilike(identificador)) |
            (User.email.ilike(identificador))
        ).first()
        if user and user.client:
            client = user.client

    if not client:
        print(f"❌ No se encontró ningún cliente asociado a: '{identificador}'")
        sys.exit(1)

    user = client.user
    assets = client.assets.all()
    num_assets = len(assets)

    print("\n📋 DATOS DEL CLIENTE A ELIMINAR:")
    print(f"   • ID Cliente: {client.id}")
    print(f"   • Nombre/Razón Social: {client.nombre}")
    print(f"   • DNI/CUIT: {client.dni_cuit}")
    print(f"   • Email: {client.mail}")
    if user:
        print(f"   • Usuario Asociado: {user.username} (ID: {user.id})")
    print(f"   • Vehículos Registrados: {num_assets}")

    if num_assets > 0:
        print("\n🚗 VEHÍCULOS ASOCIADOS:")
        for idx, a in enumerate(assets, 1):
            print(f"   [{idx}] Dominio: {a.domain or 'S/D'} | {a.brand} {a.model_name} ({a.manufacturing_year}) | ID: {a.id}")

        confirm_veh = input(f"\n⚠️  El cliente posee {num_assets} vehículo(s) activo(s).\n   ¿Desea borrar los vehículos y liberar sus códigos QR a estado VIRGEN? (s/n): ").strip().lower()
        if confirm_veh not in ['s', 'si', 'y', 'yes']:
            print("⛔ Operación cancelada. No se puede eliminar un cliente con vehículos sin confirmar su borrado.")
            sys.exit(0)

    confirm_final = input(f"\n🚨 ¿Confirma la BAJA FÍSICA DEFINITIVA del cliente '{client.nombre}'? (s/n): ").strip().lower()
    if confirm_final not in ['s', 'si', 'y', 'yes']:
        print("⛔ Operación cancelada por el usuario.")
        sys.exit(0)

    try:
        print("\n⚙️  Ejecutando sentencias DELETE en base de datos...")
        activos_ids = [a.id for a in assets]

        if activos_ids:
            # 1. Liberar QRs
            qrs = CodigoQR.query.filter(CodigoQR.activo_id.in_(activos_ids)).all()
            for q in qrs:
                q.activo_id = None
                q.estado = 'VIRGEN'
            print(f"   ✓ {len(qrs)} Código(s) QR desvinculados y restablecidos a estado VIRGEN.")

            # 2. Eliminar planos de emergencia
            num_planes = EmergencyPlan.query.filter(EmergencyPlan.asset_id.in_(activos_ids)).delete(synchronize_session=False)
            print(f"   ✓ {num_planes} plano(s) de emergencia eliminados.")

            # 3. Eliminar vehículos
            num_activos = Asset.query.filter(Asset.id.in_(activos_ids)).delete(synchronize_session=False)
            print(f"   ✓ {num_activos} vehículo(s) eliminado(s) de la tabla assets.")

        # 4. Eliminar solicitudes de faltantes
        num_sol = SolicitudVehiculoFaltante.query.filter_by(client_id=client.id).delete(synchronize_session=False)
        print(f"   ✓ {num_sol} solicitud(es) de vehículo faltante eliminadas.")

        # 5. Eliminar cliente y usuario
        cliente_id = client.id
        db.session.delete(client)
        if user:
            db.session.delete(user)

        db.session.commit()
        print(f"   ✓ Registro del cliente ID={cliente_id} eliminado de la tabla clients.")
        if user:
            print(f"   ✓ Registro del usuario ID={user.id} ({user.username}) eliminado de la tabla users.")

        print("\n✅ BAJA FÍSICA COMPLETADA CON ÉXITO.")

    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Error al ejecutar la baja física: {str(e)}")
        sys.exit(1)
EOF
