# CRM de Barbearia em Flask

Projeto web de CRM para barbearias com 4 niveis de acesso:

- `ADMIN`: dono da plataforma, responsavel por cadastrar empresas.
- `EMPRESA`: barbearia cliente do sistema, responsavel por barbeiros, clientes, servicos e resultados.
- `BARBEIRO`: recebe notificacoes de marcacoes e acompanha sua agenda.
- `CLIENTE`: visualiza barbeiros e servicos, marca, remarca e cancela horarios.

## Estrutura

- `back/`: backend Flask, modelos SQL, regras e rotas.
- `front/`: templates HTML, CSS e JS.
- `docs/`: documentacao por pasta e por arquivos principais.
- `run.py`: ponto de entrada local.

## Tecnologias

- Python
- Flask
- Flask-Login
- Flask-SQLAlchemy
- SQLite

## Evolucao comercial e cadastral

- Dashboard do `ADMIN` com uso por empresa.
- Controle de pagamentos da compra/assinatura do sistema.
- Empresa com documento fiscal, plano, mensalidade, dia de cobranca e permissoes operacionais.
- Cliente com nome, CPF, email e data de nascimento.
- Barbeiro com nome, email, CPF, RG, carteira de trabalho, data de nascimento e data de inicio.
- Configuracao SMTP pelo painel do `ADMIN` para qualquer provedor de e-mail.

## Como executar

1. Crie um ambiente virtual:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

2. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

3. Rode o sistema:

```powershell
python run.py
```

4. Acesse:

- `http://127.0.0.1:5000`

## Usuario inicial

- Email: `admin@crmbarbearia.local`
- Senha: `admin123`

## Banco de dados

O banco SQLite e criado automaticamente em `data/barbershop_crm.db`.

## Observacoes

- O frontend usa azul escuro, branco e tons neutros.
- A aplicacao esta organizada com `back` e `front` separados, mas servidos pelo Flask.
- As notificacoes dos barbeiros sao gravadas no banco e exibidas no dashboard.
