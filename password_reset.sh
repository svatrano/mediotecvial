#!/usr/bin/env bash
# ==============================================================================
# Script: password_reset.sh - MediotecVial
# Propósito: Restablecer la contraseña de un usuario en Azure SQL Database
#           validando existencia, solicitando contraseña de forma oculta y
#           aplicando el hash seguro correspondiente.
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
import getpass
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from librerias.models import db, User

app = create_app(os.environ.get('FLASK_ENV', 'development'))

with app.app_context():
    print("=" * 70)
    print("🔑 RESTABLECIMIENTO DE CONTRASEÑA - MEDIOTECVIAL")
    print("=" * 70)

    username = None
    if len(sys.argv) > 1:
        username = sys.argv[1].strip()

    if not username:
        username = input("👉 Ingrese el nombre de usuario (username): ").strip()

    if not username:
        print("❌ Error: No se ingresó ningún nombre de usuario.")
        sys.exit(1)

    user = User.query.filter(User.username.ilike(username)).first()
    if not user:
        print(f"❌ Error: El usuario '{username}' no existe en la base de datos.")
        sys.exit(1)

    print(f"\n👤 Usuario encontrado: {user.username} (ID: {user.id}) | Email: {user.email} | Rol: {user.role}")

    while True:
        p1 = getpass.getpass("\n🔒 Ingrese la NUEVA contraseña (mínimo 6 caracteres): ")
        if len(p1) < 6:
            print("⚠️  La contraseña debe tener al menos 6 caracteres. Intente nuevamente.")
            continue

        p2 = getpass.getpass("🔒 Confirme la NUEVA contraseña: ")
        if p1 != p2:
            print("⚠️  Las contraseñas no coinciden. Intente nuevamente.")
            continue

        break

    try:
        user.set_password(p1)
        db.session.commit()
        print(f"\n✅ Contraseña actualizada exitosamente para el usuario '{user.username}'.")
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Error al actualizar la contraseña en la base de datos: {str(e)}")
        sys.exit(1)
EOF
