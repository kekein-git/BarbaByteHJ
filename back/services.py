"""Regras de negocio, autorizacao e consultas agregadas."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from email.message import EmailMessage
import smtplib

from flask import abort, current_app

from .extensions import db
from .models import (
    Appointment,
    AppointmentStatus,
    Company,
    EmailSettings,
    Notification,
    Payment,
    PaymentStatus,
    Service,
    User,
    UserRole,
)


def ensure_role(user, *roles):
    """Bloqueia acesso quando o usuario nao pertence aos papeis esperados."""

    if user.role not in roles:
        abort(403)


def ensure_has_company(user):
    """Garante que usuarios nao-admin tenham empresa vinculada."""

    if user.role != UserRole.ADMIN.value and not user.company_id:
        abort(403)


def ensure_company_scope(user, company_id: int | None):
    """Impede acesso cruzado entre empresas."""

    ensure_has_company(user)
    if user.role != UserRole.ADMIN.value and user.company_id != company_id:
        abort(403)


def slugify_company_name(name: str) -> str:
    base = "-".join(name.lower().strip().split())
    slug = base
    counter = 1
    while Company.query.filter_by(slug=slug).first():
        counter += 1
        slug = f"{base}-{counter}"
    return slug


def create_notification(user_id: int, title: str, message: str) -> None:
    notification = Notification(user_id=user_id, title=title, message=message)
    db.session.add(notification)
    db.session.commit()
    send_email_notification(user_id, title, message)


def active_notifications_for_user(user):
    """Retorna somente notificacoes nao arquivadas."""

    return sorted(
        [item for item in user.notifications if item.deleted_at is None],
        key=lambda item: item.created_at,
        reverse=True,
    )


def has_active_notifications(user) -> bool:
    return any(item.deleted_at is None for item in user.notifications)


def get_email_settings():
    """Busca configuracao SMTP salva no banco com fallback no config."""

    settings = EmailSettings.query.order_by(EmailSettings.id.asc()).first()
    if settings:
        return {
            "enabled": settings.mail_enabled,
            "host": settings.mail_host or "",
            "port": settings.mail_port or 587,
            "username": settings.mail_username or "",
            "password": settings.mail_password or "",
            "use_tls": settings.mail_use_tls,
            "from_email": settings.mail_from or "",
        }
    return {
        "enabled": current_app.config.get("MAIL_ENABLED", False),
        "host": current_app.config.get("MAIL_HOST", ""),
        "port": current_app.config.get("MAIL_PORT", 587),
        "username": current_app.config.get("MAIL_USERNAME", ""),
        "password": current_app.config.get("MAIL_PASSWORD", ""),
        "use_tls": current_app.config.get("MAIL_USE_TLS", True),
        "from_email": current_app.config.get("MAIL_FROM", ""),
    }


def send_smtp_email(recipient: str, subject: str, body: str) -> bool:
    """Envia um e-mail via SMTP usando a configuracao atual."""

    settings = get_email_settings()
    if not settings["enabled"] or not settings["host"] or not recipient:
        return False

    email_message = EmailMessage()
    email_message["Subject"] = subject
    email_message["From"] = settings["from_email"] or settings["username"] or "no-reply@crmbarbearia.local"
    email_message["To"] = recipient
    email_message.set_content(body)

    try:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=15) as server:
            if settings["use_tls"]:
                server.starttls()
            if settings["username"]:
                server.login(settings["username"], settings["password"])
            server.send_message(email_message)
        return True
    except Exception:
        current_app.logger.exception("Falha ao enviar e-mail SMTP.")
        return False


def send_email_notification(user_id: int, title: str, message: str) -> None:
    """Envia notificacao por e-mail para o usuario, quando SMTP estiver configurado."""

    user = User.query.get(user_id)
    if not user or not user.email:
        return

    send_smtp_email(
        user.email,
        f"CRM Barbearia - {title}",
        f"Olá {user.full_name},\n\n"
        f"Você recebeu uma nova notificação no CRM Barbearia.\n\n"
        f"Título: {title}\n"
        f"Mensagem: {message}\n\n"
        "Acesse o sistema para mais detalhes.",
    )


def parse_date(date_str: str):
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def is_slot_available(barber_id: int, scheduled_at: datetime, exclude_appointment_id: int | None = None) -> bool:
    start = scheduled_at.replace(minute=0, second=0, microsecond=0) - timedelta(minutes=59)
    end = scheduled_at + timedelta(minutes=59)
    query = Appointment.query.filter(
        Appointment.barber_id == barber_id,
        Appointment.status.in_(
            [
                AppointmentStatus.SCHEDULED.value,
                AppointmentStatus.RESCHEDULED.value,
            ]
        ),
        Appointment.scheduled_at >= start,
        Appointment.scheduled_at <= end,
    )
    if exclude_appointment_id:
        query = query.filter(Appointment.id != exclude_appointment_id)
    return query.first() is None


def barber_metrics(company_id: int):
    """Retorna metricas agregadas por barbeiro para a empresa."""

    metrics = []
    barbers = User.query.filter_by(company_id=company_id, role=UserRole.BARBER.value, active=True).all()
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    for barber in barbers:
        finished = [
            item for item in barber.barber_appointments if item.status == AppointmentStatus.FINISHED.value
        ]
        month_finished = [item for item in finished if item.scheduled_at >= month_start]
        total_value = sum(item.service.price for item in finished)
        month_value = sum(item.service.price for item in month_finished)
        metrics.append(
            {
                "barber": barber,
                "services_total": len(finished),
                "services_month": len(month_finished),
                "total_value": total_value,
                "month_value": month_value,
                "upcoming": len(
                    [
                        item
                        for item in barber.barber_appointments
                        if item.status in [AppointmentStatus.SCHEDULED.value, AppointmentStatus.RESCHEDULED.value]
                    ]
                ),
            }
        )
    return metrics


def company_dashboard_metrics(company_id: int):
    """Consolida dados principais do dashboard da empresa."""

    company = Company.query.get_or_404(company_id)
    if not company.active:
        abort(403)
    appointments = company.appointments
    active_services = [service for service in company.services if service.active]
    clients = [user for user in company.users if user.role == UserRole.CLIENT.value]
    barbers = [user for user in company.users if user.role == UserRole.BARBER.value]
    finished = [item for item in appointments if item.status == AppointmentStatus.FINISHED.value]
    month = datetime.utcnow().month
    year = datetime.utcnow().year
    finished_month = [
        item
        for item in finished
        if item.scheduled_at.month == month and item.scheduled_at.year == year
    ]
    return {
        "company": company,
        "appointments_total": len(appointments),
        "barbers_total": len(barbers),
        "clients_total": len(clients),
        "services_total": len(active_services),
        "revenue_total": sum(item.service.price for item in finished),
        "revenue_month": sum(item.service.price for item in finished_month),
        "finished_month": len(finished_month),
        "barber_metrics": barber_metrics(company_id),
    }


def admin_dashboard_metrics():
    """Indicadores globais do dono da plataforma."""

    companies = Company.query.all()
    users = User.query.all()
    appointments = Appointment.query.all()
    payments = Payment.query.order_by(Payment.due_date.desc()).all()
    company_rows = []
    total_paid = 0.0
    total_pending = 0.0

    for payment in payments:
        if payment.status == PaymentStatus.PAID.value:
            total_paid += payment.amount
        else:
            total_pending += payment.amount

    for company in companies:
        company_users = company.users
        company_appointments = company.appointments
        company_payments = sorted(company.payments, key=lambda item: item.due_date, reverse=True)
        last_appointment = max(
            (item.scheduled_at for item in company_appointments),
            default=None,
        )
        company_rows.append(
            {
                "company": company,
                "users_total": len(company_users),
                "barbers_total": len([u for u in company_users if u.role == UserRole.BARBER.value]),
                "clients_total": len([u for u in company_users if u.role == UserRole.CLIENT.value]),
                "services_total": len(company.services),
                "appointments_total": len(company_appointments),
                "finished_total": len(
                    [a for a in company_appointments if a.status == AppointmentStatus.FINISHED.value]
                ),
                "pending_payments": len(
                    [p for p in company_payments if p.status in [PaymentStatus.PENDING.value, PaymentStatus.OVERDUE.value]]
                ),
                "paid_total": sum(
                    p.amount for p in company_payments if p.status == PaymentStatus.PAID.value
                ),
                "last_appointment": last_appointment,
                "last_payment": company_payments[0] if company_payments else None,
            }
        )

    return {
        "companies_total": len(companies),
        "active_companies": len([company for company in companies if company.active]),
        "users_total": len(users),
        "appointments_total": len(appointments),
        "payments_total": len(payments),
        "revenue_paid_total": total_paid,
        "revenue_pending_total": total_pending,
        "company_rows": company_rows,
        "recent_payments": payments[:10],
    }


def client_available_barbers(company_id: int):
    company = Company.query.get_or_404(company_id)
    if not company.active or not company.allow_online_booking:
        return []
    return User.query.filter_by(company_id=company_id, role=UserRole.BARBER.value, active=True).all()


def grouped_week_schedule(barber):
    """Agrupa agendamentos futuros por dia para exibir ao cliente."""

    future_items = (
        Appointment.query.filter(
            Appointment.barber_id == barber.id,
            Appointment.company_id == barber.company_id,
            Appointment.status.in_(
                [
                    AppointmentStatus.SCHEDULED.value,
                    AppointmentStatus.RESCHEDULED.value,
                ]
            ),
            Appointment.scheduled_at >= datetime.utcnow(),
        )
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )
    grouped = defaultdict(list)
    for item in future_items:
        grouped[item.scheduled_at.strftime("%d/%m/%Y")].append(item)
    return dict(grouped)


def sync_overdue_payments():
    today = date.today()
    pending = Payment.query.filter(
        Payment.status == PaymentStatus.PENDING.value,
        Payment.due_date < today,
    ).all()
    for payment in pending:
        payment.status = PaymentStatus.OVERDUE.value
    if pending:
        db.session.commit()


def purge_old_deleted_notifications():
    """Apaga definitivamente notificacoes arquivadas ha mais de 3 meses."""

    cutoff = datetime.utcnow() - timedelta(days=90)
    old_items = Notification.query.filter(
        Notification.deleted_at.isnot(None),
        Notification.deleted_at < cutoff,
    ).all()
    for item in old_items:
        db.session.delete(item)
    if old_items:
        db.session.commit()
