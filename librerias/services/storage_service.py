import os
import uuid
import logging
from werkzeug.utils import secure_filename
from flask import current_app

logger = logging.getLogger(__name__)

def get_blob_service_client():
    """Obtiene cliente de Azure Blob Storage si las credenciales están configuradas"""
    conn_str = current_app.config.get('AZURE_STORAGE_CONNECTION_STRING') or os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    if not conn_str:
        return None

    try:
        from azure.storage.blob import BlobServiceClient
        return BlobServiceClient.from_connection_string(conn_str)
    except Exception as e:
        logger.error(f"Error al inicializar BlobServiceClient de Azure: {str(e)}")
        return None


def upload_rescue_sheet(file_storage, brand: str, model: str, year: int) -> tuple[str, str]:
    """
    Sube un archivo de hoja de rescate vehicular a Azure Storage Blob.
    Si no hay conexión a Azure, realiza fallback al almacenamiento local.

    Returns:
        tuple (url_del_archivo, nombre_del_archivo)
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No se proporcionó ningún archivo para subir.")

    orig_name = secure_filename(file_storage.filename)
    ext = orig_name.rsplit('.', 1)[-1].lower() if '.' in orig_name else 'pdf'
    
    clean_brand = secure_filename(brand).lower()
    clean_model = secure_filename(model).lower()
    unique_suffix = uuid.uuid4().hex[:8]
    stored_filename = f"{clean_brand}_{clean_model}_{year}_{unique_suffix}.{ext}"

    # Detección de Content-Type
    content_type_map = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif'
    }
    content_type = content_type_map.get(ext, 'application/octet-stream')

    # 1. Intentar subir a Azure Storage Blob
    blob_client = get_blob_service_client()
    container_name = current_app.config.get('AZURE_CONTAINER_NAME') or os.environ.get('AZURE_CONTAINER_NAME') or 'mediotec-plans'

    if blob_client:
        try:
            from azure.storage.blob import ContentSettings
            container_client = blob_client.get_container_client(container_name)
            if not container_client.exists():
                logger.info(f"Creando contenedor Azure Blob: {container_name}")
                container_client.create_container()

            blob_file_client = container_client.get_blob_client(stored_filename)
            file_storage.seek(0)
            blob_file_client.upload_blob(
                file_storage.read(),
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type)
            )
            blob_url = blob_file_client.url
            logger.info(f"Archivo {stored_filename} subido exitosamente a Azure Blob Storage: {blob_url}")
            return blob_url, stored_filename
        except Exception as e:
            logger.error(f"Error al subir a Azure Storage Blob ({stored_filename}): {str(e)}. Intentando fallback local.")

    # 2. Fallback local si Azure Storage no está disponible
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'rescue_sheets')
    os.makedirs(upload_dir, exist_ok=True)
    local_path = os.path.join(upload_dir, stored_filename)

    file_storage.seek(0)
    file_storage.save(local_path)
    local_url = f"/static/uploads/rescue_sheets/{stored_filename}"
    logger.info(f"Archivo guardado localmente en fallback: {local_url}")
    return local_url, stored_filename
