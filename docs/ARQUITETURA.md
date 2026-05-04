# Arquitetura do CRM

## Separacao entre front e back

- O backend fica em `back/`.
- O frontend fica em `front/`.
- O Flask carrega os templates de `front/templates` e os arquivos estaticos de `front/static`.

## Perfis do sistema

### ADMIN

- Cadastra empresas.
- Cria o gestor principal da empresa.
- Visualiza indicadores globais.
- Visualiza uso por empresa.
- Controla pagamentos da assinatura/compra do sistema CRM.

### EMPRESA

- Cadastra barbeiros e clientes.
- Cadastra servicos.
- Vincula servicos a barbeiros especificos.
- Acompanha faturamento total e mensal.
- Ve lucros e quantidade de servicos por barbeiro.
- Pode alterar status do agendamento.

### BARBEIRO

- Recebe notificacoes ao receber nova marcacao, remarcacao ou cancelamento.
- Ve clientes, servicos e observacoes dos agendamentos.
- Acompanha sua agenda futura.

### CLIENTE

- Ve os barbeiros da empresa vinculada.
- Consulta servicos disponiveis.
- Cria agendamentos com observacao.
- Pode remarcar ou cancelar seus horarios.

## Banco de dados

### Tabelas principais

- `company`: empresas cadastradas pelo admin.
- `user`: usuarios de todos os perfis.
- `service`: servicos da empresa.
- `appointment`: marcacoes entre cliente, barbeiro e servico.
- `notification`: notificacoes do barbeiro.
- `payment`: cobrancas e pagamentos da empresa ao dono do CRM.
- `barber_services`: tabela de associacao entre barbeiros e servicos.

## Fluxo principal

1. O admin cria uma empresa.
2. A empresa recebe um gestor do tipo `EMPRESA`.
3. O gestor cria barbeiros, clientes e servicos.
4. O cliente marca um servico com um barbeiro.
5. O barbeiro recebe notificacao.
6. A empresa acompanha status e receitas.
