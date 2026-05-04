"""Rotas Flask para autenticacao, dashboards e operacoes do CRM."""

from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import Appointment, AppointmentStatus, Company, EmailSettings, Payment, PaymentStatus, Service, User, UserRole
from .services import (
    active_notifications_for_user,
    admin_dashboard_metrics,
    client_available_barbers,
    company_dashboard_metrics,
    create_notification,
    ensure_company_scope,
    ensure_has_company,
    ensure_role,
    grouped_week_schedule,
    has_active_notifications,
    is_slot_available,
    parse_date,
    purge_old_deleted_notifications,
    send_smtp_email,
    slugify_company_name,
    sync_overdue_payments,
)


main_bp = Blueprint("main", __name__)


def role_home_endpoint(role: str) -> str:
    mapping = {
        UserRole.ADMIN.value: "main.admin_dashboard_page",
        UserRole.COMPANY.value: "main.company_dashboard_page",
        UserRole.BARBER.value: "main.barber_appointments_page",
        UserRole.CLIENT.value: "main.client_booking_page",
    }
    return mapping.get(role, "main.index")


def company_manager(company_id: int):
    return User.query.filter_by(company_id=company_id, role=UserRole.COMPANY.value).order_by(User.id.asc()).first()


@main_bp.route("/")
def index():
    sync_overdue_payments()
    purge_old_deleted_notifications()
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(role_home_endpoint(current_user.role)))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, active=True).first()
        if user and user.check_password(password):
            if user.role != UserRole.ADMIN.value and not user.company_id:
                flash("Usuario sem empresa vinculada.", "danger")
                return redirect(url_for("main.login"))
            login_user(user)
            flash("Login realizado com sucesso.", "success")
            return redirect(url_for(role_home_endpoint(user.role)))
        flash("Credenciais invalidas.", "danger")
    return render_template("login.html")


@main_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sessao encerrada.", "info")
    return redirect(url_for("main.login"))


@main_bp.route("/register/client", methods=["POST"])
def register_client():
    full_name = request.form.get("full_name", "").strip()
    cpf = request.form.get("cpf", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    birth_date = parse_date(request.form.get("birth_date", "").strip())
    company_id = request.form.get("company_id", type=int)

    if not all([full_name, cpf, email, password, company_id, birth_date]):
        flash("Preencha todos os campos obrigatorios do cliente.", "danger")
        return redirect(url_for("main.index"))

    if User.query.filter_by(email=email).first():
        flash("Ja existe um usuario com este email.", "danger")
        return redirect(url_for("main.index"))

    if User.query.filter(User.cpf == cpf, User.cpf.isnot(None)).first():
        flash("Ja existe um usuario com este CPF.", "danger")
        return redirect(url_for("main.index"))

    company = Company.query.get_or_404(company_id)
    if not company.active:
        flash("Esta empresa nao esta disponivel para novos cadastros.", "danger")
        return redirect(url_for("main.index"))
    user = User(
        full_name=full_name,
        email=email,
        cpf=cpf,
        birth_date=birth_date,
        role=UserRole.CLIENT.value,
        company_id=company.id,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash("Cadastro do cliente realizado. Agora faca login.", "success")
    return redirect(url_for("main.login"))


@main_bp.route("/register/client", methods=["GET"])
def client_register_page():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    companies = Company.query.filter_by(active=True).order_by(Company.name.asc()).all()
    return render_template("register_client.html", companies=companies)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    sync_overdue_payments()
    purge_old_deleted_notifications()
    return redirect(url_for(role_home_endpoint(current_user.role)))


@main_bp.route("/admin/dashboard")
@login_required
def admin_dashboard_page():
    ensure_role(current_user, UserRole.ADMIN.value)
    return render_template(
        "admin_dashboard.html",
        metrics=admin_dashboard_metrics(),
    )


@main_bp.route("/admin/companies")
@login_required
def admin_companies_page():
    ensure_role(current_user, UserRole.ADMIN.value)
    return render_template(
        "admin_companies.html",
        companies=Company.query.order_by(Company.created_at.desc()).all(),
    )


@main_bp.route("/admin/payments")
@login_required
def admin_payments_page():
    ensure_role(current_user, UserRole.ADMIN.value)
    return render_template(
        "admin_payments.html",
        companies=Company.query.order_by(Company.name.asc()).all(),
        payments=Payment.query.order_by(Payment.due_date.desc()).all(),
        payment_statuses=[item.value for item in PaymentStatus],
    )


@main_bp.route("/admin/company-profiles")
@login_required
def admin_company_profiles_page():
    ensure_role(current_user, UserRole.ADMIN.value)
    companies = Company.query.order_by(Company.name.asc()).all()
    profile_rows = [{"company": company, "manager": company_manager(company.id)} for company in companies]
    return render_template("admin_company_profiles.html", profile_rows=profile_rows)


@main_bp.route("/admin/email-settings")
@login_required
def admin_email_settings_page():
    ensure_role(current_user, UserRole.ADMIN.value)
    settings = EmailSettings.query.order_by(EmailSettings.id.asc()).first()
    return render_template("admin_email_settings.html", settings=settings)


@main_bp.route("/company/dashboard")
@login_required
def company_dashboard_page():
    ensure_role(current_user, UserRole.COMPANY.value)
    ensure_has_company(current_user)
    return render_template(
        "company_dashboard.html",
        metrics=company_dashboard_metrics(current_user.company_id),
        appointments=Appointment.query.filter_by(company_id=current_user.company_id)
        .order_by(Appointment.scheduled_at.desc())
        .all(),
    )


@main_bp.route("/company/barbers")
@login_required
def company_barbers_page():
    ensure_role(current_user, UserRole.COMPANY.value)
    ensure_has_company(current_user)
    users = User.query.filter_by(company_id=current_user.company_id).order_by(User.full_name.asc()).all()
    return render_template(
        "company_barbers.html",
        metrics=company_dashboard_metrics(current_user.company_id),
        barbers=[user for user in users if user.role == UserRole.BARBER.value],
    )


@main_bp.route("/company/clients")
@login_required
def company_clients_page():
    ensure_role(current_user, UserRole.COMPANY.value)
    ensure_has_company(current_user)
    clients = User.query.filter_by(
        company_id=current_user.company_id,
        role=UserRole.CLIENT.value,
    ).order_by(User.full_name.asc()).all()
    return render_template(
        "company_clients.html",
        metrics=company_dashboard_metrics(current_user.company_id),
        clients=clients,
    )


@main_bp.route("/company/services")
@login_required
def company_services_page():
    ensure_role(current_user, UserRole.COMPANY.value)
    ensure_has_company(current_user)
    users = User.query.filter_by(company_id=current_user.company_id).order_by(User.full_name.asc()).all()
    return render_template(
        "company_services.html",
        metrics=company_dashboard_metrics(current_user.company_id),
        users=users,
        services=Service.query.filter_by(company_id=current_user.company_id).order_by(Service.name.asc()).all(),
    )


@main_bp.route("/company/appointments")
@login_required
def company_appointments_page():
    ensure_role(current_user, UserRole.COMPANY.value)
    ensure_has_company(current_user)
    status_filter = request.args.get("status", "").strip()
    barber_filter = request.args.get("barber_id", type=int)
    client_filter = request.args.get("client_id", type=int)
    date_from = parse_date(request.args.get("date_from", "").strip())
    date_to = parse_date(request.args.get("date_to", "").strip())

    query = Appointment.query.filter_by(company_id=current_user.company_id)
    if status_filter and status_filter in [item.value for item in AppointmentStatus]:
        query = query.filter(Appointment.status == status_filter)
    if barber_filter:
        query = query.filter(Appointment.barber_id == barber_filter)
    if client_filter:
        query = query.filter(Appointment.client_id == client_filter)
    if date_from:
        query = query.filter(Appointment.scheduled_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(Appointment.scheduled_at <= datetime.combine(date_to, datetime.max.time()))

    users = User.query.filter_by(company_id=current_user.company_id).order_by(User.full_name.asc()).all()
    return render_template(
        "company_appointments.html",
        metrics=company_dashboard_metrics(current_user.company_id),
        appointments=query.order_by(Appointment.scheduled_at.desc()).all(),
        appointment_statuses=[item.value for item in AppointmentStatus],
        barbers=[user for user in users if user.role == UserRole.BARBER.value],
        clients=[user for user in users if user.role == UserRole.CLIENT.value],
        filters={
            "status": status_filter,
            "barber_id": barber_filter,
            "client_id": client_filter,
            "date_from": request.args.get("date_from", "").strip(),
            "date_to": request.args.get("date_to", "").strip(),
        },
    )


@main_bp.route("/barber/appointments")
@login_required
def barber_appointments_page():
    ensure_role(current_user, UserRole.BARBER.value)
    ensure_has_company(current_user)
    purge_old_deleted_notifications()
    appointments = (
        Appointment.query.filter_by(barber_id=current_user.id, company_id=current_user.company_id)
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )
    return render_template(
        "barber_appointments.html",
        appointments=appointments,
        notifications=active_notifications_for_user(current_user),
    )


@main_bp.route("/barber/notifications")
@login_required
def barber_notifications_page():
    ensure_role(current_user, UserRole.BARBER.value)
    ensure_has_company(current_user)
    purge_old_deleted_notifications()
    if not has_active_notifications(current_user):
        return redirect(url_for("main.barber_appointments_page"))
    return render_template(
        "barber_notifications.html",
        notifications=active_notifications_for_user(current_user),
    )


@main_bp.route("/client/barbers")
@login_required
def client_barbers_page():
    ensure_role(current_user, UserRole.CLIENT.value)
    ensure_has_company(current_user)
    return render_template(
        "client_barbers.html",
        barbers=client_available_barbers(current_user.company_id),
        company=Company.query.get(current_user.company_id),
    )


@main_bp.route("/client/booking")
@login_required
def client_booking_page():
    ensure_role(current_user, UserRole.CLIENT.value)
    ensure_has_company(current_user)
    return render_template(
        "client_booking.html",
        barbers=client_available_barbers(current_user.company_id),
        services=Service.query.filter_by(company_id=current_user.company_id, active=True).all(),
        company=Company.query.get(current_user.company_id),
    )


@main_bp.route("/client/bookings")
@login_required
def client_bookings_page():
    ensure_role(current_user, UserRole.CLIENT.value)
    ensure_has_company(current_user)
    appointments = (
        Appointment.query.filter_by(client_id=current_user.id, company_id=current_user.company_id)
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )
    return render_template(
        "client_bookings.html",
        appointments=appointments,
        company=Company.query.get(current_user.company_id),
    )


@main_bp.route("/admin/company/create", methods=["POST"])
@login_required
def create_company():
    ensure_role(current_user, UserRole.ADMIN.value)
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    document_number = request.form.get("document_number", "").strip()
    plan_name = request.form.get("plan_name", "").strip() or "Plano Padrao"
    monthly_fee = request.form.get("monthly_fee", type=float) or 0.0
    billing_day = request.form.get("billing_day", type=int) or 5
    subscription_status = request.form.get("subscription_status", "").strip() or "ATIVA"
    manager_name = request.form.get("manager_name", "").strip()
    manager_email = request.form.get("manager_email", "").strip().lower()
    manager_password = request.form.get("manager_password", "").strip()
    manager_cpf = request.form.get("manager_cpf", "").strip()
    allow_online_booking = bool(request.form.get("allow_online_booking"))
    allow_financial_dashboard = bool(request.form.get("allow_financial_dashboard"))
    allow_barber_notifications = bool(request.form.get("allow_barber_notifications"))

    if not all([name, email, document_number, manager_name, manager_email, manager_password]):
        flash("Preencha todos os campos obrigatorios da empresa.", "danger")
        return redirect(url_for("main.dashboard"))

    if Company.query.filter((Company.name == name) | (Company.email == email)).first():
        flash("Empresa ja cadastrada com este nome ou email.", "danger")
        return redirect(url_for("main.dashboard"))

    if User.query.filter_by(email=manager_email).first():
        flash("Ja existe um usuario com o email do gestor.", "danger")
        return redirect(url_for("main.dashboard"))

    company = Company(
        name=name,
        email=email,
        phone=phone,
        slug=slugify_company_name(name),
        document_number=document_number,
        plan_name=plan_name,
        monthly_fee=monthly_fee,
        billing_day=billing_day,
        subscription_status=subscription_status,
        allow_online_booking=allow_online_booking,
        allow_financial_dashboard=allow_financial_dashboard,
        allow_barber_notifications=allow_barber_notifications,
    )
    db.session.add(company)
    db.session.flush()

    manager = User(
        full_name=manager_name,
        email=manager_email,
        phone=phone,
        cpf=manager_cpf,
        role=UserRole.COMPANY.value,
        company_id=company.id,
    )
    manager.set_password(manager_password)
    db.session.add(manager)
    db.session.commit()
    flash("Empresa criada com gestor vinculado.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/admin/payment/create", methods=["POST"])
@login_required
def create_payment():
    ensure_role(current_user, UserRole.ADMIN.value)
    company_id = request.form.get("company_id", type=int)
    reference_month = request.form.get("reference_month", "").strip()
    amount = request.form.get("amount", type=float) or 0.0
    due_date = parse_date(request.form.get("due_date", "").strip())
    paid_at = parse_date(request.form.get("paid_at", "").strip())
    status = request.form.get("status", "").strip() or PaymentStatus.PENDING.value
    notes = request.form.get("notes", "").strip()

    if not all([company_id, reference_month, amount, due_date]) or status not in [item.value for item in PaymentStatus]:
        flash("Preencha corretamente os dados do pagamento.", "danger")
        return redirect(url_for("main.dashboard"))

    payment = Payment(
        company_id=company_id,
        reference_month=reference_month,
        amount=amount,
        due_date=due_date,
        paid_at=paid_at,
        status=status,
        notes=notes,
    )
    db.session.add(payment)
    db.session.commit()
    flash("Pagamento/assinatura registrado.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/admin/company/<int:company_id>/access", methods=["POST"])
@login_required
def update_company_access(company_id):
    ensure_role(current_user, UserRole.ADMIN.value)
    company = Company.query.get_or_404(company_id)
    manager = company_manager(company.id)

    company_email = request.form.get("company_email", "").strip().lower()
    manager_email = request.form.get("manager_email", "").strip().lower()
    manager_password = request.form.get("manager_password", "").strip()

    if not company_email:
        flash("Informe o email da empresa.", "danger")
        return redirect(url_for("main.admin_company_profiles_page"))

    if Company.query.filter(Company.email == company_email, Company.id != company.id).first():
        flash("Ja existe outra empresa com este email.", "danger")
        return redirect(url_for("main.admin_company_profiles_page"))

    company.email = company_email

    if manager:
        if not manager_email:
            flash("Informe o email do gestor.", "danger")
            return redirect(url_for("main.admin_company_profiles_page"))

        if User.query.filter(User.email == manager_email, User.id != manager.id).first():
            flash("Ja existe outro usuario com este email.", "danger")
            return redirect(url_for("main.admin_company_profiles_page"))

        manager.email = manager_email
        if manager_password:
            manager.set_password(manager_password)

    db.session.commit()
    flash("Perfil de acesso da empresa atualizado.", "success")
    return redirect(url_for("main.admin_company_profiles_page"))


@main_bp.route("/admin/email-settings/save", methods=["POST"])
@login_required
def save_email_settings():
    ensure_role(current_user, UserRole.ADMIN.value)
    settings = EmailSettings.query.order_by(EmailSettings.id.asc()).first()
    if not settings:
        settings = EmailSettings()
        db.session.add(settings)

    settings.mail_enabled = bool(request.form.get("mail_enabled"))
    settings.mail_host = request.form.get("mail_host", "").strip() or None
    settings.mail_port = request.form.get("mail_port", type=int) or 587
    settings.mail_username = request.form.get("mail_username", "").strip() or None

    new_password = request.form.get("mail_password", "").strip()
    if new_password:
        settings.mail_password = new_password

    settings.mail_use_tls = bool(request.form.get("mail_use_tls"))
    settings.mail_from = request.form.get("mail_from", "").strip() or None
    db.session.commit()
    flash("Configuracao de e-mail salva.", "success")
    return redirect(url_for("main.admin_email_settings_page"))


@main_bp.route("/admin/email-settings/test", methods=["POST"])
@login_required
def test_email_settings():
    ensure_role(current_user, UserRole.ADMIN.value)
    recipient = request.form.get("test_recipient", "").strip().lower() or current_user.email
    ok = send_smtp_email(
        recipient,
        "Teste de configuracao SMTP",
        "Este e um teste de envio do CRM Barbearia. Se voce recebeu esta mensagem, a configuracao esta funcionando.",
    )
    if ok:
        flash(f"E-mail de teste enviado para {recipient}.", "success")
    else:
        flash("Falha ao enviar e-mail de teste. Revise host, porta, usuario, senha e TLS.", "danger")
    return redirect(url_for("main.admin_email_settings_page"))


@main_bp.route("/company/user/create", methods=["POST"])
@login_required
def create_company_user():
    ensure_role(current_user, UserRole.COMPANY.value)
    ensure_has_company(current_user)
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    phone = request.form.get("phone", "").strip()
    cpf = request.form.get("cpf", "").strip()
    rg = request.form.get("rg", "").strip()
    work_card = request.form.get("work_card", "").strip()
    birth_date = parse_date(request.form.get("birth_date", "").strip())
    employment_start_date = parse_date(request.form.get("employment_start_date", "").strip())
    role = request.form.get("role", "").strip()

    if role not in [UserRole.BARBER.value, UserRole.CLIENT.value]:
        flash("Perfil invalido para cadastro.", "danger")
        return redirect(url_for("main.dashboard"))

    if not all([full_name, email, password, cpf]):
        flash("Preencha os campos obrigatorios do usuario.", "danger")
        return redirect(url_for("main.dashboard"))

    if role == UserRole.CLIENT.value and not birth_date:
        flash("Cliente precisa de data de nascimento.", "danger")
        return redirect(url_for("main.dashboard"))

    if role == UserRole.BARBER.value and not all([rg, work_card, birth_date, employment_start_date]):
        flash("Barbeiro precisa de CPF, RG, carteira de trabalho, data de nascimento e inicio de trabalho.", "danger")
        return redirect(url_for("main.dashboard"))

    if User.query.filter_by(email=email).first():
        flash("Ja existe usuario com este email.", "danger")
        return redirect(url_for("main.dashboard"))

    if User.query.filter(User.cpf == cpf, User.cpf.isnot(None)).first():
        flash("Ja existe usuario com este CPF.", "danger")
        return redirect(url_for("main.dashboard"))

    user = User(
        full_name=full_name,
        email=email,
        phone=phone,
        cpf=cpf,
        rg=rg or None,
        work_card=work_card or None,
        birth_date=birth_date,
        employment_start_date=employment_start_date,
        role=role,
        company_id=current_user.company_id,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash("Usuario cadastrado com sucesso.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/company/client/<int:client_id>/update", methods=["POST"])
@login_required
def update_company_client(client_id):
    ensure_role(current_user, UserRole.COMPANY.value)
    ensure_has_company(current_user)
    client = User.query.get_or_404(client_id)
    ensure_company_scope(current_user, client.company_id)

    if client.role != UserRole.CLIENT.value:
        flash("Este cadastro nao pertence a um cliente.", "danger")
        return redirect(url_for("main.company_clients_page"))

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    cpf = request.form.get("cpf", "").strip()
    birth_date = parse_date(request.form.get("birth_date", "").strip())
    new_password = request.form.get("password", "").strip()

    if not all([full_name, email, cpf, birth_date]):
        flash("Preencha nome, email, CPF e data de nascimento do cliente.", "danger")
        return redirect(url_for("main.company_clients_page"))

    if User.query.filter(User.email == email, User.id != client.id).first():
        flash("Ja existe outro usuario com este email.", "danger")
        return redirect(url_for("main.company_clients_page"))

    if User.query.filter(User.cpf == cpf, User.id != client.id, User.cpf.isnot(None)).first():
        flash("Ja existe outro usuario com este CPF.", "danger")
        return redirect(url_for("main.company_clients_page"))

    client.full_name = full_name
    client.email = email
    client.phone = phone or None
    client.cpf = cpf
    client.birth_date = birth_date
    if new_password:
        client.set_password(new_password)

    db.session.commit()
    flash("Cliente atualizado com sucesso.", "success")
    return redirect(url_for("main.company_clients_page"))


@main_bp.route("/company/service/create", methods=["POST"])
@login_required
def create_service():
    ensure_role(current_user, UserRole.COMPANY.value)
    ensure_has_company(current_user)
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    price = request.form.get("price", type=float)
    duration_minutes = request.form.get("duration_minutes", type=int) or 30
    barber_ids = request.form.getlist("barber_ids")

    if not all([name, price]):
        flash("Informe nome e preco do servico.", "danger")
        return redirect(url_for("main.dashboard"))

    service = Service(
        name=name,
        description=description,
        price=price,
        duration_minutes=duration_minutes,
        company_id=current_user.company_id,
    )
    if barber_ids:
        barbers = User.query.filter(
            User.id.in_(barber_ids),
            User.company_id == current_user.company_id,
            User.role == UserRole.BARBER.value,
        ).all()
        service.barbers = barbers

    db.session.add(service)
    db.session.commit()
    flash("Servico cadastrado.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/company/appointment/<int:appointment_id>/status", methods=["POST"])
@login_required
def company_change_appointment_status(appointment_id):
    ensure_role(current_user, UserRole.COMPANY.value)
    ensure_has_company(current_user)
    appointment = Appointment.query.get_or_404(appointment_id)
    ensure_company_scope(current_user, appointment.company_id)

    status = request.form.get("status")
    if status not in [item.value for item in AppointmentStatus]:
        flash("Status invalido.", "danger")
        return redirect(url_for("main.dashboard"))

    appointment.status = status
    if status == AppointmentStatus.CANCELLED.value:
        appointment.cancellation_reason = request.form.get("cancellation_reason", "").strip() or "Cancelado pela empresa"
    else:
        appointment.cancellation_reason = None
    db.session.commit()
    create_notification(
        appointment.barber_id,
        "Atualizacao de agenda",
        f"O agendamento de {appointment.client.full_name} agora esta como {appointment.status.lower()}.",
    )
    flash("Agendamento atualizado.", "success")
    return redirect(request.referrer or url_for("main.company_appointments_page"))


@main_bp.route("/client/appointment/create", methods=["POST"])
@login_required
def create_appointment():
    ensure_role(current_user, UserRole.CLIENT.value)
    ensure_has_company(current_user)
    company = Company.query.get_or_404(current_user.company_id)
    if not company.allow_online_booking:
        flash("A empresa desativou o agendamento online.", "danger")
        return redirect(url_for("main.dashboard"))

    barber_id = request.form.get("barber_id", type=int)
    service_id = request.form.get("service_id", type=int)
    scheduled_at_raw = request.form.get("scheduled_at", "").strip()
    note = request.form.get("note", "").strip()

    if not all([barber_id, service_id, scheduled_at_raw]):
        flash("Preencha os dados da marcacao.", "danger")
        return redirect(url_for("main.dashboard"))

    scheduled_at = datetime.strptime(scheduled_at_raw, "%Y-%m-%dT%H:%M")
    barber = User.query.get_or_404(barber_id)
    service = Service.query.get_or_404(service_id)

    ensure_company_scope(current_user, barber.company_id)
    ensure_company_scope(current_user, service.company_id)
    if barber.role != UserRole.BARBER.value or not barber.active:
        flash("Barbeiro ou servico invalidos para sua empresa.", "danger")
        return redirect(url_for("main.dashboard"))

    if service.barbers and barber not in service.barbers:
        flash("Este servico nao esta liberado para o barbeiro selecionado.", "danger")
        return redirect(url_for("main.dashboard"))

    if not is_slot_available(barber_id, scheduled_at):
        flash("Horario indisponivel para o barbeiro.", "danger")
        return redirect(url_for("main.dashboard"))

    appointment = Appointment(
        scheduled_at=scheduled_at,
        note=note,
        company_id=current_user.company_id,
        barber_id=barber_id,
        client_id=current_user.id,
        service_id=service_id,
        status=AppointmentStatus.SCHEDULED.value,
    )
    db.session.add(appointment)
    db.session.commit()
    if company.allow_barber_notifications:
        create_notification(
            barber_id,
            "Nova marcacao",
            f"{current_user.full_name} marcou {service.name} para {scheduled_at.strftime('%d/%m/%Y %H:%M')}.",
        )
    flash("Marcacao criada.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/client/appointment/<int:appointment_id>/update", methods=["POST"])
@login_required
def update_client_appointment(appointment_id):
    ensure_role(current_user, UserRole.CLIENT.value)
    ensure_has_company(current_user)
    appointment = Appointment.query.get_or_404(appointment_id)
    ensure_company_scope(current_user, appointment.company_id)
    if appointment.client_id != current_user.id:
        return redirect(url_for("main.dashboard"))
    company = Company.query.get_or_404(current_user.company_id)

    action = request.form.get("action")
    if action == "cancel":
        appointment.status = AppointmentStatus.CANCELLED.value
        appointment.cancellation_reason = "Cancelado pelo cliente"
        db.session.commit()
        if company.allow_barber_notifications:
            create_notification(
                appointment.barber_id,
                "Marcacao cancelada",
                f"{current_user.full_name} cancelou o horario de {appointment.scheduled_at.strftime('%d/%m/%Y %H:%M')}.",
            )
        flash("Marcacao cancelada.", "info")
        return redirect(url_for("main.dashboard"))

    scheduled_at_raw = request.form.get("scheduled_at", "").strip()
    note = request.form.get("note", "").strip()
    if not scheduled_at_raw:
        flash("Informe o novo horario.", "danger")
        return redirect(url_for("main.dashboard"))

    scheduled_at = datetime.strptime(scheduled_at_raw, "%Y-%m-%dT%H:%M")
    if not is_slot_available(appointment.barber_id, scheduled_at, exclude_appointment_id=appointment.id):
        flash("Horario indisponivel para remarcar.", "danger")
        return redirect(url_for("main.dashboard"))

    appointment.scheduled_at = scheduled_at
    appointment.note = note
    appointment.status = AppointmentStatus.RESCHEDULED.value
    db.session.commit()
    if company.allow_barber_notifications:
        create_notification(
            appointment.barber_id,
            "Marcacao remarcada",
            f"{current_user.full_name} remarcou para {scheduled_at.strftime('%d/%m/%Y %H:%M')}.",
        )
    flash("Marcacao atualizada.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/barber/notification/<int:notification_id>/read", methods=["POST"])
@login_required
def read_notification(notification_id):
    ensure_role(current_user, UserRole.BARBER.value)
    ensure_has_company(current_user)
    notification = next((item for item in current_user.notifications if item.id == notification_id), None)
    if notification and notification.deleted_at is None:
        notification.is_read = True
        db.session.commit()
    return redirect(url_for("main.dashboard"))


@main_bp.route("/barber/notification/<int:notification_id>/delete", methods=["POST"])
@login_required
def delete_notification(notification_id):
    ensure_role(current_user, UserRole.BARBER.value)
    ensure_has_company(current_user)
    notification = next((item for item in current_user.notifications if item.id == notification_id), None)
    if notification and notification.deleted_at is None:
        notification.deleted_at = datetime.utcnow()
        db.session.commit()
        flash("Notificacao removida da sua tela.", "info")
    return redirect(request.referrer or url_for("main.barber_notifications_page"))


@main_bp.route("/barber/appointment/<int:appointment_id>/finish", methods=["POST"])
@login_required
def finish_barber_appointment(appointment_id):
    ensure_role(current_user, UserRole.BARBER.value)
    ensure_has_company(current_user)
    appointment = Appointment.query.get_or_404(appointment_id)
    ensure_company_scope(current_user, appointment.company_id)

    if appointment.barber_id != current_user.id:
        return redirect(url_for("main.dashboard"))

    if appointment.status in [AppointmentStatus.CANCELLED.value, AppointmentStatus.FINISHED.value]:
        flash("Esta marcacao nao pode ser finalizada.", "danger")
        return redirect(url_for("main.barber_appointments_page"))

    appointment.status = AppointmentStatus.FINISHED.value
    db.session.commit()
    flash("Marcacao finalizada com sucesso.", "success")
    return redirect(url_for("main.barber_appointments_page"))


@main_bp.route("/barber/schedule")
@login_required
def barber_schedule():
    ensure_role(current_user, UserRole.BARBER.value)
    ensure_has_company(current_user)
    return render_template("barber_schedule.html", schedule=grouped_week_schedule(current_user))
