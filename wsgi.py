"""
WSGI entry point para Azure App Service / Gunicorn.

Gunicorn/Oryx busca un objeto `app` en este módulo.
Usamos `create_app()` del factory y lo exportamos como `app`.
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run()
