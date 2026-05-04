# Documentacao dos codigos

## `run.py`

Inicializa a aplicacao Flask e permite a execucao local do sistema.

## `back/config.py`

Define a configuracao central, incluindo `SECRET_KEY` e o caminho do banco SQLite.

## `back/extensions.py`

Centraliza a criacao de objetos compartilhados como `db` e `login_manager`.

## `back/models.py`

Define os modelos do banco de dados:

- `Company`
- `User`
- `Service`
- `Appointment`
- `Notification`
- `Payment`

Tambem define:

- `UserRole`
- `AppointmentStatus`
- `PaymentStatus`
- tabela de relacao `barber_services`

## `back/services.py`

Reune regras de negocio:

- validacao de papel por rota
- criacao de notificacoes
- validacao de horario disponivel
- metricas por barbeiro
- metricas do dashboard da empresa
- metricas do admin
- sincronizacao de pagamentos atrasados
- parse de datas para formularios

## `back/routes.py`

Responsavel pelas rotas HTTP:

- pagina inicial
- login e logout
- cadastro de cliente
- dashboard por perfil
- cadastro de empresa
- cadastro de usuarios da empresa
- cadastro de servicos
- criacao de agendamentos
- remarcacao e cancelamento
- leitura de notificacoes

## `front/templates/base.html`

Template base com topbar, mensagens flash e carregamento de CSS/JS.

## `front/templates/index.html`

Pagina inicial com apresentacao do produto e cadastro de clientes.

## `front/templates/login.html`

Tela de autenticacao de usuarios.

## `front/templates/dashboard_admin.html`

Painel do administrador com criacao e listagem de empresas.

## `front/templates/dashboard_company.html`

Painel da empresa com indicadores, usuarios, servicos e agendamentos.

## `front/templates/dashboard_barber.html`

Painel do barbeiro com notificacoes e agenda recebida.

## `front/templates/dashboard_client.html`

Painel do cliente com criacao, remarcacao e cancelamento de marcacoes.

## `front/templates/barber_schedule.html`

Visao agrupada da agenda futura do barbeiro.

## `front/static/css/styles.css`

Estilos globais do projeto, responsivos e alinhados com a paleta azul escuro e branco.

## `front/static/js/app.js`

Script simples para suavizar o desaparecimento de alertas visuais.
