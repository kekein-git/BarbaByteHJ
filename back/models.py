"""Modelos SQL do CRM de barbearia."""

from datetime import date, datetime
from enum import Enum

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    COMPANY = "EMPRESA"
    BARBER = "BARBEIRO"
    CLIENT = "CLIENTE"


barber_services = db.Table(
    "barber_services",
    db.Column("barber_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("service_id", db.Integer, db.ForeignKey("service.id"), primary_key=True),
)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Company(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    phone = db.Column(db.String(30), nullable=True)
    document_number = db.Column(db.String(20), nullable=False)
    plan_name = db.Column(db.String(80), nullable=False, default="Plano Padrao")
    monthly_fee = db.Column(db.Float, nullable=False, default=0.0)
    billing_day = db.Column(db.Integer, nullable=False, default=5)
    subscription_status = db.Column(db.String(30), nullable=False, default="ATIVA")
    allow_online_booking = db.Column(db.Boolean, default=True, nullable=False)
    allow_financial_dashboard = db.Column(db.Boolean, default=True, nullable=False)
    allow_barber_notifications = db.Column(db.Boolean, default=True, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    users = db.relationship("User", back_populates="company", lazy=True)
    services = db.relationship("Service", back_populates="company", lazy=True)
    appointments = db.relationship("Appointment", back_populates="company", lazy=True)
    payments = db.relationship("Payment", back_populates="company", lazy=True)


class User(UserMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    phone = db.Column(db.String(30), nullable=True)
    cpf = db.Column(db.String(14), nullable=True)
    rg = db.Column(db.String(20), nullable=True)
    work_card = db.Column(db.String(30), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    employment_start_date = db.Column(db.Date, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=True)
    company = db.relationship("Company", back_populates="users")

    barber_services = db.relationship(
        "Service",
        secondary=barber_services,
        back_populates="barbers",
        lazy="subquery",
    )
    barber_appointments = db.relationship(
        "Appointment", foreign_keys="Appointment.barber_id", back_populates="barber", lazy=True
    )
    client_appointments = db.relationship(
        "Appointment", foreign_keys="Appointment.client_id", back_populates="client", lazy=True
    )
    notifications = db.relationship("Notification", back_populates="user", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value


class Service(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=30)
    active = db.Column(db.Boolean, default=True, nullable=False)

    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    company = db.relationship("Company", back_populates="services")
    appointments = db.relationship("Appointment", back_populates="service", lazy=True)
    barbers = db.relationship(
        "User",
        secondary=barber_services,
        back_populates="barber_services",
        lazy="subquery",
    )


class AppointmentStatus(str, Enum):
    SCHEDULED = "AGENDADO"
    RESCHEDULED = "REMARCADO"
    CANCELLED = "CANCELADO"
    FINISHED = "FINALIZADO"


class Appointment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=AppointmentStatus.SCHEDULED.value)
    note = db.Column(db.Text, nullable=True)
    cancellation_reason = db.Column(db.String(255), nullable=True)

    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    barber_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)

    company = db.relationship("Company", back_populates="appointments")
    barber = db.relationship("User", foreign_keys=[barber_id], back_populates="barber_appointments")
    client = db.relationship("User", foreign_keys=[client_id], back_populates="client_appointments")
    service = db.relationship("Service", back_populates="appointments")


class Notification(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="notifications")


class PaymentStatus(str, Enum):
    PENDING = "PENDENTE"
    PAID = "PAGO"
    OVERDUE = "ATRASADO"


class Payment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference_month = db.Column(db.String(7), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    paid_at = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=PaymentStatus.PENDING.value)
    notes = db.Column(db.String(255), nullable=True)

    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    company = db.relationship("Company", back_populates="payments")


class EmailSettings(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mail_enabled = db.Column(db.Boolean, default=False, nullable=False)
    mail_host = db.Column(db.String(255), nullable=True)
    mail_port = db.Column(db.Integer, default=587, nullable=False)
    mail_username = db.Column(db.String(255), nullable=True)
    mail_password = db.Column(db.String(255), nullable=True)
    mail_use_tls = db.Column(db.Boolean, default=True, nullable=False)
    mail_from = db.Column(db.String(255), nullable=True)


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))
