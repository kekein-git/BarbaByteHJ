"""Factory principal da aplicacao Flask."""

from flask import Flask, url_for
from flask_login import current_user
from sqlalchemy.exc import OperationalError
from sqlalchemy import inspect, text

from .config import Config
from .extensions import db, login_manager
from .models import EmailSettings, User, UserRole
from .routes import main_bp
from .services import has_active_notifications


def create_app():
    """Cria a aplicacao configurando backend e frontend separados."""

    app = Flask(
        __name__,
        template_folder="../front/templates",
        static_folder="../front/static",
        static_url_path="/static",
    )
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    app.register_blueprint(main_bp)
    register_context_processors(app)

    with app.app_context():
        db.create_all()
        ensure_schema_updates()
        ensure_default_admin()
        ensure_default_email_settings()

    return app


def ensure_default_admin():
    """Garante um ADMIN inicial para acesso ao sistema."""

    if User.query.filter_by(role=UserRole.ADMIN.value).first():
        return

    admin = User(
        full_name="Administrador Master",
        email="admin@crmbarbearia.local",
        role=UserRole.ADMIN.value,
        company_id=None,
    )
    admin.set_password("admin123")
    db.session.add(admin)
    db.session.commit()


def ensure_schema_updates():
    """Aplica migracoes simples para o SQLite local."""

    inspector = inspect(db.engine)

    company_columns = {column["name"] for column in inspector.get_columns("company")}
    company_alters = {
        "document_number": "ALTER TABLE company ADD COLUMN document_number VARCHAR(20)",
        "plan_name": "ALTER TABLE company ADD COLUMN plan_name VARCHAR(80) DEFAULT 'Plano Padrao' NOT NULL",
        "monthly_fee": "ALTER TABLE company ADD COLUMN monthly_fee FLOAT DEFAULT 0 NOT NULL",
        "billing_day": "ALTER TABLE company ADD COLUMN billing_day INTEGER DEFAULT 5 NOT NULL",
        "subscription_status": "ALTER TABLE company ADD COLUMN subscription_status VARCHAR(30) DEFAULT 'ATIVA' NOT NULL",
        "allow_online_booking": "ALTER TABLE company ADD COLUMN allow_online_booking BOOLEAN DEFAULT 1 NOT NULL",
        "allow_financial_dashboard": "ALTER TABLE company ADD COLUMN allow_financial_dashboard BOOLEAN DEFAULT 1 NOT NULL",
        "allow_barber_notifications": "ALTER TABLE company ADD COLUMN allow_barber_notifications BOOLEAN DEFAULT 1 NOT NULL",
    }

    user_columns = {column["name"] for column in inspector.get_columns("user")}
    user_alters = {
        "cpf": "ALTER TABLE user ADD COLUMN cpf VARCHAR(14)",
        "rg": "ALTER TABLE user ADD COLUMN rg VARCHAR(20)",
        "work_card": "ALTER TABLE user ADD COLUMN work_card VARCHAR(30)",
        "birth_date": "ALTER TABLE user ADD COLUMN birth_date DATE",
        "employment_start_date": "ALTER TABLE user ADD COLUMN employment_start_date DATE",
    }
    notification_columns = {column["name"] for column in inspector.get_columns("notification")}
    notification_alters = {
        "deleted_at": "ALTER TABLE notification ADD COLUMN deleted_at DATETIME",
    }
    table_names = set(inspector.get_table_names())

    with db.engine.begin() as connection:
        for column, sql in company_alters.items():
            if column not in company_columns:
                try:
                    connection.execute(text(sql))
                except OperationalError as exc:
                    if "duplicate column name" not in str(exc).lower():
                        raise
        for column, sql in user_alters.items():
            if column not in user_columns:
                try:
                    connection.execute(text(sql))
                except OperationalError as exc:
                    if "duplicate column name" not in str(exc).lower():
                        raise
        for column, sql in notification_alters.items():
            if column not in notification_columns:
                try:
                    connection.execute(text(sql))
                except OperationalError as exc:
                    if "duplicate column name" not in str(exc).lower():
                        raise
        connection.execute(
            text(
                "UPDATE company SET plan_name = COALESCE(plan_name, 'Plano Padrao'), "
                "monthly_fee = COALESCE(monthly_fee, 0), "
                "billing_day = COALESCE(billing_day, 5), "
                "subscription_status = COALESCE(subscription_status, 'ATIVA'), "
                "allow_online_booking = COALESCE(allow_online_booking, 1), "
                "allow_financial_dashboard = COALESCE(allow_financial_dashboard, 1), "
                "allow_barber_notifications = COALESCE(allow_barber_notifications, 1)"
            )
        )

        if "email_settings" in table_names:
            email_columns = {column["name"] for column in inspector.get_columns("email_settings")}
            email_alters = {
                "mail_enabled": "ALTER TABLE email_settings ADD COLUMN mail_enabled BOOLEAN DEFAULT 0 NOT NULL",
                "mail_host": "ALTER TABLE email_settings ADD COLUMN mail_host VARCHAR(255)",
                "mail_port": "ALTER TABLE email_settings ADD COLUMN mail_port INTEGER DEFAULT 587 NOT NULL",
                "mail_username": "ALTER TABLE email_settings ADD COLUMN mail_username VARCHAR(255)",
                "mail_password": "ALTER TABLE email_settings ADD COLUMN mail_password VARCHAR(255)",
                "mail_use_tls": "ALTER TABLE email_settings ADD COLUMN mail_use_tls BOOLEAN DEFAULT 1 NOT NULL",
                "mail_from": "ALTER TABLE email_settings ADD COLUMN mail_from VARCHAR(255)",
            }
            for column, sql in email_alters.items():
                if column not in email_columns:
                    try:
                        connection.execute(text(sql))
                    except OperationalError as exc:
                        if "duplicate column name" not in str(exc).lower():
                            raise


def register_context_processors(app):
    """Disponibiliza menus por perfil para a interface."""

    @app.context_processor
    def inject_role_menu():
        role_menus = {
            UserRole.ADMIN.value: [
                {"label": "Dashboard de empresas", "href": url_for("main.admin_dashboard_page")},
                {"label": "Cadastro de empresas", "href": url_for("main.admin_companies_page")},
                {"label": "Perfis de empresas", "href": url_for("main.admin_company_profiles_page")},
                {"label": "Pagamentos", "href": url_for("main.admin_payments_page")},
                {"label": "E-mail SMTP", "href": url_for("main.admin_email_settings_page")},
            ],
            UserRole.COMPANY.value: [
                {"label": "Dashboard empresa", "href": url_for("main.company_dashboard_page")},
                {"label": "Cadastro de barbeiro", "href": url_for("main.company_barbers_page")},
                {"label": "Clientes", "href": url_for("main.company_clients_page")},
                {"label": "Cadastro de servicos", "href": url_for("main.company_services_page")},
                {"label": "Agendamentos", "href": url_for("main.company_appointments_page")},
            ],
            UserRole.BARBER.value: [
                {"label": "Recebimento de marcacoes", "href": url_for("main.barber_appointments_page")},
                {"label": "Horarios", "href": url_for("main.barber_schedule")},
            ],
            UserRole.CLIENT.value: [
                {"label": "Barbeiros", "href": url_for("main.client_barbers_page")},
                {"label": "Nova marcacao", "href": url_for("main.client_booking_page")},
                {"label": "Minhas marcacoes", "href": url_for("main.client_bookings_page")},
            ],
        }
        items = []
        if current_user.is_authenticated:
            items = role_menus.get(current_user.role, [])
            if current_user.role == UserRole.BARBER.value and has_active_notifications(current_user):
                items = items + [{"label": "Notificacoes", "href": url_for("main.barber_notifications_page")}]
        return {"role_menu_items": items}


def ensure_default_email_settings():
    """Garante um registro base para configuracao SMTP dinamica."""

    if EmailSettings.query.first():
        return

    settings = EmailSettings(
        mail_enabled=Config.MAIL_ENABLED,
        mail_host=Config.MAIL_HOST or None,
        mail_port=Config.MAIL_PORT,
        mail_username=Config.MAIL_USERNAME or None,
        mail_password=Config.MAIL_PASSWORD or None,
        mail_use_tls=Config.MAIL_USE_TLS,
        mail_from=Config.MAIL_FROM or None,
    )
    db.session.add(settings)
    db.session.commit()
