# Configuración segura de Azure Blob Storage

La aplicación debe entregar los documentos desde Flask. El contenedor no debe
tener acceso anónimo.

## 1. Crear el contenedor privado

En la cuenta de almacenamiento de Azure:

1. Crear el contenedor `mediotec-plans`.
2. Establecer **Public access level** en `Private (no anonymous access)`.
3. Desactivar el acceso público a blobs y contenedores en la configuración de la cuenta.
4. Verificar que una URL `https://<cuenta>.blob.core.windows.net/mediotec-plans/<archivo>` responda `401` o `403` sin credenciales.

## 2. Variables de Azure App Service

Configurar en **Configuration > Application settings**, sin subir secretos al repositorio:

```text
AZURE_STORAGE_CONNECTION_STRING=<cadena privada de la cuenta>
AZURE_CONTAINER_NAME=mediotec-plans
AZURE_SQL_SERVER=<servidor>
AZURE_SQL_DATABASE=<base de datos>
AZURE_SQL_USER=<usuario>
AZURE_SQL_PASSWORD=<contraseña>
SECRET_KEY=<secreto aleatorio>
```

Como alternativa, usar una identidad administrada con permisos mínimos
`Storage Blob Data Reader` y `Storage Blob Data Contributor` sobre el contenedor.

## 3. Reglas de aplicación

- No guardar URLs públicas como enlaces para el navegador.
- No habilitar SAS públicos permanentes.
- Las rutas de administración deben exigir sesión y rol `admin`.
- La ficha pública debe validar QR `ACTIVADO` y combustible antes de entregar el archivo.
- La aplicación debe responder el archivo con `send_file()` y `Content-Disposition`.
- Revisar los logs de Azure ante errores de lectura, sin registrar cadenas de conexión.

## 4. Verificación

1. Crear una plantilla desde `/admin/vehicle_templates`.
2. Abrirla desde el botón **Ver Documento**.
3. Confirmar que el navegador solo vea una URL de la aplicación.
4. Repetir la prueba en `/hoja-rescate/<id>` con un QR activo.
5. Intentar abrir directamente el blob y confirmar que sea rechazado.