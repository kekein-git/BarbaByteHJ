# Pasta `back`

Contem toda a logica do backend Flask.

## Arquivos

- `__init__.py`: factory da aplicacao, integracao entre backend e frontend, criacao do banco e admin inicial.
- `config.py`: configuracoes da aplicacao e banco SQL.
- `extensions.py`: instancias das extensoes Flask.
- `models.py`: tabelas do banco, relacionamentos e enums de papel/status.
- `models.py`: tabelas do banco, relacionamentos, cadastros fiscais e pagamentos do sistema.
- `routes.py`: rotas HTTP e fluxos de autenticacao, dashboards e agendamentos.
- `services.py`: regras de negocio, metricas e funcoes auxiliares.
