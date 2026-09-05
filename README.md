# 🚒 MediotecVial - Sistema de Gestión de Hojas de Rescate Vehicular

**MediotecVial** es una plataforma integral diseñada para optimizar y asegurar las operaciones de rescate vehicular en accidentes de tránsito e intervenciones de emergencia. Cada vehículo protegido cuenta con una oblea física provista de un código QR estandarizado. Al ser escaneado por personal de bomberos, rescatistas o médicos en el lugar del siniestro, el sistema despliega de forma inmediata y pública la **Ficha Técnica Oficial de Rescate** con información vital (puntos seguros de corte, desconexión de baterías de 12V y alto voltaje, zonas de airbags y riesgos de combustible).

Asimismo, la plataforma provee a la administración herramientas para la generación masiva de lotes de códigos QR para imprenta, gestión de clientes y vehículos, y un flujo interactivo de activación para que los clientes vinculen sus unidades a los códigos físicos.

---

## 📋 Requisitos Previos y Entorno

- **Versión de Python**: Estrictamente **Python 3.12**.
- **Entorno Virtual**: `venv` / `virtualenv`.
- **Base de Datos**: 
  - Producción: **Azure SQL Database (Serverless)** compatible con ODBC Driver 17/18.
  - Desarrollo / Pruebas: **SQLite** (en memoria o archivo local).
- **Almacenamiento en la Nube**: **Azure Storage (Blob Container)** para resguardo de documentos PDF y fichas técnicas.

---

## 🏛️ Arquitectura del Software

```mermaid
graph TD
    A[Bombero / Rescatista] -->|Escanea QR en chasis / parabrisas| B(GET /qr/:uuid)
    B -->|Estado: ACTIVADO| C[GET /hoja-rescate/:uid - Ficha Pública Inmediata]
    B -->|Estado: VIRGEN| D[Redirige a /activacion/:uuid]
    
    E[Cliente] -->|No autenticado| F[GET /login o /registro]
    F -->|Crea User role=cliente y Client| D
    D -->|Asocia Patente, Catálogo y Combustible| G[(Base de Datos: assets & CodigoQR)]
    G -->|Pasa a estado ACTIVADO| C

    H[Administrador] -->|Control total| I[Panel /admin/dashboard]
    I --> J[/admin/qr/gestion - Lotes QR & Imprenta]
    I --> K[/admin/activos - Gestión de Activos]
    I --> L[/admin/clientes - Gestión de Clientes]
    I --> M[/admin/vehicle_templates - Catálogo de Hojas]
```

### Componentes de la Arquitectura:
1. **Frontend / Presentación**: Flask con Jinja2 y Bootstrap 5, respetando estrictamente la paleta corporativa y estilos en `librerias/static/css/styles.css`.
2. **Capa de Controladores (`librerias/routes/`)**:
   - `public.py`: Páginas informativas, landing, preguntas frecuentes y visualizador público de emergencia.
   - `qr_router.py`: Despachador de escaneo físico y asistente de activación de activos.
   - `admin_qr.py`: Generador masivo de lotes QR, métricas y exportación CSV para imprenta.
   - `activos.py`: Portal de autogestión para clientes con control estricto de autorización (`asset.client_id == current_user.client.id`) y endpoints dinámicos del catálogo.
   - `auth.py`: Control de sesiones, login, logout y registro de clientes.
   - `admin.py`: Administración general de clientes, usuarios, catálogo de marcas y modelos, y planos.
   - `emergency.py`: Vistas de búsqueda y contingencia para centros de despacho de emergencias.
3. **Capa de Datos y Modelos (`librerias/models/__init__.py`)**: SQLAlchemy 2.0 con soporte relacional completo.

---

## 🗄️ Modelo Relacional de Datos

| Tabla | Propósito | Clave Primaria | Claves Foráneas / Relaciones |
| :--- | :--- | :--- | :--- |
| `users` | Credenciales y control de acceso (`admin`, `cliente`) | `id` (Integer) | `client` (1 a 1 con `clients`) |
| `clients` | Datos de clientes o empresas propietarias | `id` (Integer) | `user_id` -> `users.id` (UNIQUE) |
| `fuel_type` | Catálogo de 8 tipos oficiales de propulsión y fuente motriz | `id` (Integer) | Relación 1 a N con `assets` |
| `Vehicle_templates` | Catálogo vehicular estandarizado de hojas de rescate | `id` (Integer) | Relación 1 a N con `assets` |
| `assets` | Activos vehiculares registrados con dominio y combustible | `id` (Integer) | `client_id`, `vehicle_template_id`, `fuel_type_id` |
| `CodigoQR` | Control de códigos físicos QR impresos (`VIRGEN` o `ACTIVADO`) | `id` (UUID String) | `activo_id` -> `assets.id` (1 a 1) |
| `solicitudes_vehiculo_faltante` | Pedidos de incorporación de modelos faltantes en catálogo | `id` (Integer) | `client_id` -> `clients.id` |
| `emergency_plans` | Documentos y planos de rescate adjuntos | `id` (Integer) | `asset_id` -> `assets.id` |

> 📌 **Diagrama relacional para DrawDB**: Se incluye el archivo [`drawdb_schema.json`](file:///home/sergio/git/mediotecvial/drawdb_schema.json) en la raíz del proyecto para importar y visualizar el esquema completo en [DrawDB](https://drawdb.app/).

---

## 🔌 Catálogo Detallado de Endpoints

### 1. Rutas Públicas y Emergencia
- `GET /`: Página principal (Landing Page).
- `GET /home`: Alias de la página principal.
- `GET /faq`: Preguntas frecuentes y funcionamiento del sistema.
- `GET /actualidad` o `GET /noticias`: Novedades operativas y de seguridad vial.
- `GET /hoja-rescate/<uid>`: **Ficha técnica interactiva del vehículo**. Acceso público e inmediato para bomberos (por ID de activo o UUID de QR).
- `GET /politicas-privacidad`: Políticas de privacidad de datos.
- `GET /terminos`: Términos y condiciones del servicio.
- `GET /health`: Health-check para balanceadores de carga y Azure App Service.

### 2. Autenticación y Cuentas
- `GET /login`, `POST /login`: Inicio de sesión (soporta parámetro `next` para continuar el flujo de activación QR tras autenticarse).
- `GET /logout`: Cierre seguro de sesión.
- `GET /registro`: Formulario de inscripción web de nuevos clientes.
- `POST /api/clientes/registro` y `POST /registro`: Crea simultáneamente el `User` (con `role = "cliente"`) y el perfil `Client` asociado.
- `GET /perfil`, `POST /perfil/cambiar-password`: Gestión de perfil y contraseña.

### 3. Router QR y Flujo de Activación
- `GET /qr/<qr_uuid>`: Punto de entrada al escanear la oblea física.
  - Si no existe: Retorna HTTP 404.
  - Si es `'VIRGEN'`: Redirige a `/activacion/<qr_uuid>`.
  - Si está `'ACTIVADO'`: Redirige directamente a `/hoja-rescate/<activo_id>`.
- `GET /activacion/<qr_uuid>`: Formulario de activación. Exige inicio de sesión (`@login_required`).
- `POST /activacion/<qr_uuid>`: Asocia la patente, marca, modelo, año y `fuel_type_id`, creando el activo y marcando el QR como `'ACTIVADO'`.

### 4. Portal del Cliente y Catálogo Dinámico
- `GET /cliente/activos`: Lista de vehículos propios del cliente en sesión.
- `GET /cliente/activos/<id>/editar`, `POST /cliente/activos/<id>/editar`: Actualización de datos del vehículo propio (**autorización estricta**: solo si `asset.client_id == current_user.client.id`).
- `GET /api/vehiculos/marcas`: Devuelve marcas únicas en formato JSON (`SELECT DISTINCT brand`).
- `GET /api/vehiculos/modelos?brand=<marca>`: Devuelve modelos para la marca seleccionada (`SELECT DISTINCT model`).
- `GET /api/vehiculos/anios?brand=<marca>&model=<modelo>`: Devuelve años de modelo disponibles.
- `POST /api/vehiculos/solicitud-faltante`: Registra una solicitud en `solicitudes_vehiculo_faltante`.

### 5. Administración Interna y Control de Lotes QR
- `GET /admin/dashboard`: Panel principal con estadísticas globales y bloque destacado de "Gestión de Lotes QR".
- `GET /admin/qr/gestion`: Interfaz administrativa para emisión de lotes, filtros y exportación.
- `POST /admin/qr/generar`: Genera masivamente cantidad "X" de UUIDs vírgenes para un lote dado.
- `GET /admin/qr/estado`: API con resumen de métricas en JSON (`total_impresos`, `virgenes_disponibles`, `qrs_activados`).
- `GET /admin/qr/listar`: API paginada y filtrable de códigos QR.
- `GET /admin/qr/exportar/<lote>`: Descarga archivo CSV con URLs de destino (`https://tudominio.com/qr/<UUID>`) listo para enviar a imprenta.
- `GET /admin/activos/crear`, `POST /admin/activos/crear`: Carga manual interna de activos.
- `GET /admin/clientes/crear`, `POST /admin/clientes/crear`: Carga manual interna de clientes.
- `GET /admin/activos`, `GET /admin/clientes`, `GET /admin/usuarios`, `GET /admin/vehicle_templates`: Listados y gestión de entidades.

---

## ⚙️ Configuración Local y Despliegue

### 1. Clonar el repositorio y configurar entorno
```bash
# Clonar
git clone https://github.com/svatrano/mediotecvial.git
cd mediotecvial

# Crear entorno virtual con Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar variables de entorno (`.env`)
Crear o verificar el archivo `.env` en la raíz del proyecto:
```ini
FLASK_ENV=development
DEBUG=True
SECRET_KEY=tu-clave-secreta-segura
JWT_SECRET_KEY=tu-jwt-secreto

# Base de datos Azure SQL (o dejar vacío para usar SQLite local mediotec.db)
AZURE_SQL_SERVER=mediotec-west-server.database.windows.net
AZURE_SQL_DATABASE=mediotec_db
AZURE_SQL_ADMIN_USER=dbazureadmin
AZURE_SQL_ADMIN_PASSWORD=TuPasswordSegura#

# Azure Storage Blob
AZURE_STORAGE_ACCOUNT_NAME=mediotec72209
AZURE_STORAGE_CONTAINER_NAME=mediotec-plans
```

### 3. Cargar datos iniciales (Seed)
```bash
# Ejecutar seeds de combustibles oficiales y usuario admin
python seed_data.py
```

### 4. Ejecutar la aplicación
```bash
# Modo desarrollo
python app.py
```
La aplicación estará disponible en `http://localhost:5000`.

Credenciales de administrador por defecto:
- **Usuario**: `admin`
- **Contraseña**: `contraseña` (cambiar en producción)

---

## 🧪 Ejecución de la Suite de Pruebas

Para validar automáticamente todos los endpoints, reglas de autorización y códigos de estado HTTP:
```bash
python verify_endpoints.py
```

La suite valida:
- Inserción y exactitud de los 8 tipos de combustible oficiales.
- Códigos HTTP 200 en todas las rutas públicas.
- Flujo completo de registro, login y logout.
- Emisión y métricas de lotes QR en el panel admin.
- Redirección 302 y 404 del router QR según estado (`VIRGEN` vs `ACTIVADO`).
- Alta de activo vehicular y vinculación a cliente.
- Consulta de Hoja de Rescate pública para bomberos sin requerir autenticación.
- Aislamiento y restricción de acceso entre clientes (HTTP 403 en activos ajenos).
- Creación manual interna en el panel de administración.
