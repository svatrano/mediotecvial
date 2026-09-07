import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# 8 tipos de combustible oficiales permitidos exclusivamente
OFFICIAL_FUEL_TYPES = [
    {
        "tipo": "Nafta",
        "descripcion": "Motor de combustión interna alimentado por nafta/gasolina refinada derivada del petróleo."
    },
    {
        "tipo": "Gasoil",
        "descripcion": "Motor de combustión interna por compresión alimentado por gasoil/diésel."
    },
    {
        "tipo": "Gas",
        "descripcion": "Motor adaptado para combustible gaseoso a presión (GNC/GLP) con tanque cilíndrico de alta resistencia."
    },
    {
        "tipo": "Nitro",
        "descripcion": "Sistema de propulsión con asistencia o inyección de óxido nitroso o aditivos de alta reactividad."
    },
    {
        "tipo": "Híbrido",
        "descripcion": "Sistema de propulsión combinado con motor térmico y uno o más motores eléctricos con batería de alto voltaje."
    },
    {
        "tipo": "Eléctrico",
        "descripcion": "Vehículo de cero emisiones propulsado exclusivamente por motores eléctricos con banco de baterías de alto voltaje (HV)."
    },
    {
        "tipo": "Eléctrico/Hybrido",
        "descripcion": "Vehículo con arquitectura eléctrica híbrida enchufable o dual de alta tensión y tracción combinada."
    },
    {
        "tipo": "Sin descripcion",
        "descripcion": "Sin información técnica de motorización o combustible adicional registrada."
    }
]


class User(UserMixin, db.Model):
    """Modelo de Usuario del Sistema"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='cliente')  # 'admin', 'cliente', 'firefighter'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relación uno a uno con Client
    client = db.relationship('Client', back_populates='user', uselist=False, cascade='all, delete-orphan')

    def set_password(self, password):
        """Genera hash de contraseña seguro"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica la contraseña contra el hash almacenado"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class Client(db.Model):
    """Modelo de Cliente institucional o particular"""
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(150), nullable=False)
    dni_cuit = db.Column(db.String(50), unique=True, nullable=False, index=True)
    direccion = db.Column(db.String(255), nullable=True)
    telefono = db.Column(db.String(50), nullable=True)
    mail = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    user = db.relationship('User', back_populates='client')
    assets = db.relationship('Asset', back_populates='client', cascade='all, delete-orphan', lazy='dynamic')
    solicitudes = db.relationship('SolicitudVehiculoFaltante', back_populates='client', cascade='all, delete-orphan', lazy='dynamic')

    # Propiedades de compatibilidad hacia atrás
    @property
    def name(self):
        return self.nombre

    @name.setter
    def name(self, val):
        self.nombre = val

    @property
    def contact_email(self):
        return self.mail

    @contact_email.setter
    def contact_email(self, val):
        self.mail = val

    @property
    def phone(self):
        return self.telefono

    @phone.setter
    def phone(self, val):
        self.telefono = val

    @property
    def address(self):
        return self.direccion

    @address.setter
    def address(self, val):
        self.direccion = val

    @property
    def id_number(self):
        return self.dni_cuit

    @id_number.setter
    def id_number(self, val):
        self.dni_cuit = val

    @property
    def id_type(self):
        return 'DNI/CUIT'

    def __repr__(self):
        return f'<Client {self.nombre} ({self.dni_cuit})>'


class FuelType(db.Model):
    """Catálogo Oficial de Tipos de Combustible y Propulsión"""
    __tablename__ = 'fuel_type'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=False)

    # Relación con activos
    assets = db.relationship('Asset', back_populates='fuel_type', lazy='dynamic')

    def __repr__(self):
        return f'<FuelType {self.tipo}>'


class VehicleTemplate(db.Model):
    """Catálogo Vehicular y Hojas de Rescate Estandarizadas"""
    __tablename__ = 'Vehicle_templates'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    brand = db.Column(db.String(100), nullable=False, index=True)
    model = db.Column(db.String(100), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False)
    rescue_sheet_url = db.Column(db.String(500), nullable=True)
    rescue_sheet_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relación con activos vinculados
    assets = db.relationship('Asset', back_populates='vehicle_template', lazy='dynamic')

    @classmethod
    def get_distinct_brands(cls):
        """Marcas: SELECT DISTINCT brand FROM Vehicle_templates"""
        records = db.session.query(cls.brand).distinct().order_by(cls.brand).all()
        return [r[0] for r in records if r[0]]

    @classmethod
    def get_distinct_models(cls, brand):
        """Modelos: SELECT DISTINCT model FROM Vehicle_templates WHERE brand = :brand"""
        records = db.session.query(cls.model).filter(cls.brand.ilike(brand)).distinct().order_by(cls.model).all()
        return [r[0] for r in records if r[0]]

    @classmethod
    def get_distinct_years(cls, brand, model):
        """Años para marca y modelo"""
        records = db.session.query(cls.year).filter(cls.brand.ilike(brand), cls.model.ilike(model)).distinct().order_by(cls.year.desc()).all()
        return [r[0] for r in records if r[0]]

    def __repr__(self):
        return f'<VehicleTemplate {self.brand} {self.model} ({self.year})>'


class Asset(db.Model):
    """Activo vehicular o edilicio registrado"""
    __tablename__ = 'assets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    asset_type = db.Column(db.String(50), default='vehicle', nullable=False)  # 'vehicle' o 'building'
    name = db.Column(db.String(150), nullable=False)
    address_or_model = db.Column(db.String(255), nullable=True)
    domain = db.Column(db.String(20), unique=True, nullable=True, index=True)  # Patente/Dominio único
    manufacturing_year = db.Column(db.Integer, nullable=True)
    vehicle_template_id = db.Column(db.Integer, db.ForeignKey('Vehicle_templates.id'), nullable=True)
    fuel_type_id = db.Column(db.Integer, db.ForeignKey('fuel_type.id'), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relaciones
    client = db.relationship('Client', back_populates='assets')
    vehicle_template = db.relationship('VehicleTemplate', back_populates='assets')
    fuel_type = db.relationship('FuelType', back_populates='assets')
    codigo_qr = db.relationship('CodigoQR', back_populates='activo', uselist=False)
    emergency_plans = db.relationship('EmergencyPlan', back_populates='asset', cascade='all, delete-orphan', lazy='dynamic')

    # Propiedades dinámicas auxiliares
    @property
    def brand(self):
        if self.vehicle_template:
            return self.vehicle_template.brand
        return ''

    @property
    def model_name(self):
        if self.vehicle_template:
            return self.vehicle_template.model
        return ''

    @property
    def additional_fuel(self):
        if self.fuel_type:
            return self.fuel_type.tipo
        return 'Sin descripcion'

    def __repr__(self):
        return f'<Asset {self.name} ({self.domain})>'


class CodigoQR(db.Model):
    """Gestión física y de estado de códigos QR impresos"""
    __tablename__ = 'CodigoQR'

    id = db.Column(db.String(36), primary_key=True)  # UUID v4 como String
    lote_impresion = db.Column(db.String(50), nullable=False, index=True)
    estado = db.Column(db.String(20), nullable=False, default='VIRGEN', index=True)  # 'VIRGEN', 'ACTIVADO'
    fecha_generacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    activo_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True) #quité , unique=True

    # Relación uno a uno con Asset
    activo = db.relationship('Asset', back_populates='codigo_qr')

    def __repr__(self):
        return f'<CodigoQR {self.id} (Lote: {self.lote_impresion}, Estado: {self.estado})>'


class SolicitudVehiculoFaltante(db.Model):
    """Solicitudes de inclusión de marcas/modelos no encontrados en el catálogo"""
    __tablename__ = 'solicitudes_vehiculo_faltante'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    marca = db.Column(db.String(100), nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    anio = db.Column(db.Integer, nullable=True)
    contacto = db.Column(db.String(150), nullable=True)
    observaciones = db.Column(db.Text, nullable=True)
    estado = db.Column(db.String(20), default='PENDIENTE', nullable=False)  # 'PENDIENTE', 'EN_REVISION', 'RESUELTO', 'RECHAZADO'
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    client = db.relationship('Client', back_populates='solicitudes')

    def __repr__(self):
        return f'<SolicitudVehiculoFaltante {self.marca} {self.modelo} ({self.estado})>'


class EmergencyPlan(db.Model):
    """Planos técnicos o documentos complementarios de emergencia"""
    __tablename__ = 'emergency_plans'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    version = db.Column(db.Integer, default=1, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    asset = db.relationship('Asset', back_populates='emergency_plans')

    def __repr__(self):
        return f'<EmergencyPlan {self.file_name} v{self.version}>'
