# Grupos de chat

As rotas HTTP exigem autenticação (por exemplo, `Authorization: Bearer <access_token>`).

- `POST /api/groups/`: cria um grupo. Exemplo: `{"name": "dev", "users": [2, 3]}`.
  `users` é opcional e contém IDs de usuários existentes. O criador sempre é associado.
  Nomes podem se repetir; cada grupo tem seu próprio `id`.
- `GET /api/groups/`: lista todos os grupos.
- `GET /api/groups/me/`: lista os grupos associados ao usuário autenticado.
- `POST /api/groups/<id>/users/`: adiciona usuários a um grupo, com
  `{"users": [2, 3]}`. Exige autenticação e retorna o grupo atualizado (200).
  Preserva os participantes existentes e ignora associações repetidas.
  Lista vazia ou IDs inválidos retornam 400, sem adicionar nenhum usuário;
  grupo inexistente retorna 404. Qualquer usuário autenticado pode usar esta rota,
  seguindo o comportamento aberto dos grupos.

As respostas incluem `id`, `name`, `users`, `created_by` e `created_at`.
As associações também podem ser editadas no Django Admin.

## WebSocket

Em `/ws/group-text/`, envie:

```json
{"action": "create", "group": "dev"}
{"action": "list"}
{"action": "join", "group_id": 1}
{"action": "message", "group_id": 1, "message": "Olá!"}
{"action": "leave", "group_id": 1}
```

`create` salva um novo grupo e associa o criador. `join` inscreve a conexão
para receber mensagens e associa o usuário; `leave` remove essa associação.
Desconectar mantém as associações no banco. Uma nova conexão entra automaticamente
no grupo geral; para receber mensagens de outros grupos, envie `join` para cada ID.
Os grupos continuam abertos à entrada de qualquer usuário autenticado.

As mensagens e confirmações incluem `group_id` e o nome em `group`.
`groups` nas confirmações contém IDs das inscrições da conexão;
`list` retorna objetos com `id` e `name`.
O campo antigo `group` ainda aceita nomes quando identificam um único grupo;
nomes repetidos exigem `group_id`. Um `join` por nome inexistente cria o grupo.

## Contatos

Contatos são usuários cadastrados salvos na lista particular do usuário autenticado.
A associação é unilateral: salvar alguém não altera a lista de contatos dessa pessoa.
Todas as rotas exigem autenticação.

- `POST /api/contacts/` com `{"user": 2}` salva o usuário de ID 2 (201).
  Se já estiver salvo, retorna o mesmo contato (200), sem duplicar.
- `GET /api/contacts/` lista apenas os contatos do usuário autenticado.
- `DELETE /api/contacts/<id>/` remove um contato (204), usando o `id` do registro
  retornado pela API, não o ID do usuário. Não exclui a conta do contato.

As respostas de criação/listagem incluem `id`, `user`, `username` e `created_at`.
Não é possível salvar a si mesmo ou um usuário inexistente (400).
Excluir contato inexistente ou pertencente a outra pessoa retorna 404.

## Banco e testes

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py test
```

A migração associa os criadores dos grupos já existentes.
