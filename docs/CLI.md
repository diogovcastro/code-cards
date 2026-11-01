# Referência da CLI

`code-cards` sem argumentos abre a TUI. Com argumentos, vira uma CLI pensada para scripts e LLMs:

- responde **sempre em JSON** no stdout, inclusive em erros;
- nunca pergunta nada: comandos que apagam exigem `--yes` e falham sem ele;
- `<deck>` aceita o **nome** (sem diferenciar maiúsculas) ou o **id** do deck.

## Saída

Sucesso:

```json
{ "ok": true, "data": { "deck_id": "k3f9a2", "card_ids": ["c7d1e0b2"] }, "warnings": [] }
```

Erro:

```json
{ "ok": false, "error": { "code": "DECK_FULL", "message": "O deck 'Python async' já tem 100 cards.", "details": { "deck_id": "k3f9a2", "available": 0, "requested": 1 } } }
```

`warnings` traz avisos que não impedem a operação, como `UNKNOWN_LANGUAGE` (linguagem sem highlight: o card é salvo e aparece como texto puro).

| Código de saída | Quando | Códigos de erro |
|---|---|---|
| 0 | sucesso | |
| 1 | erro interno | `INTERNAL_ERROR`, `STORAGE_ERROR` |
| 2 | parâmetro ou JSON inválido | `VALIDATION_ERROR`, `CONFIRMATION_REQUIRED` |
| 3 | não encontrado | `DECK_NOT_FOUND`, `CARD_NOT_FOUND` |
| 4 | conflito | `DECK_FULL`, `DECK_EXISTS` |

## Regras

- Um deck tem no máximo **100 cards**. Cada card está em um único deck.
- O nome do deck é único (sem diferenciar maiúsculas) e tem até 80 caracteres.
- Código e descrição são obrigatórios. Código: até 20.000 caracteres. Descrição: até 5.000.
- `language` padrão: detectada pela extensão de `--code-file`; senão, `python`. Hoje só `python` tem highlight; `text` é texto puro.
- Até 20 tags por card, cada uma com até 40 caracteres.

## Comandos

### Geral

```sh
code-cards where           # pasta de dados em uso (CODE_CARDS_HOME ou a padrão do sistema)
code-cards --version
code-cards schema          # JSON Schema do lote de importação (--raw: sem o envelope)
```

### Decks

```sh
code-cards deck list
code-cards deck create "Python async"
code-cards deck rename <deck> "Novo nome"
code-cards deck delete <deck> --yes        # apaga o deck, os cards e o histórico
```

`deck list` devolve, para cada deck: `id`, `name`, `created_at`, `cards` (total), `available` (vagas), `new_today` e `due_today` (o que há para estudar hoje).

### Cards

```sh
# Código por parâmetro
code-cards card add --deck <deck> --code "await asyncio.sleep(1)" \
                    --description "Pausa a corrotina por 1 segundo." --tag asyncio

# Código de um arquivo, recortando as linhas 10 a 40 (a indentação comum é removida)
code-cards card add --deck <deck> --code-file app.py --lines 10-40 --description "..."

# Código pelo stdin e descrição de um arquivo
cat trecho.py | code-cards card add --deck <deck> --code - --description-file desc.md

code-cards card list [--deck <deck>]       # sem --deck: todos os decks
code-cards card show <card-id>
code-cards card edit <card-id> [--code ... | --code-file ... [--lines A-B]] \
                     [--description ... | --description-file ...] [--language ...] \
                     [--tag x --tag y | --clear-tags] [--deck <outro>]
code-cards card delete <card-id> --yes
```

- `--lines` aceita `10-40`, `10-` (até o fim) ou `12` (uma linha).
- Só um parâmetro pode ler do stdin (`-`) por comando.
- `card edit` altera só os campos informados. `--tag` substitui todas as tags. `--deck` move o card, se o destino tiver vaga. Editar não reinicia o agendamento do card.

Um card na saída tem: `id`, `deck_id`, `deck_name`, `language`, `highlight`, `code`, `description`, `tags`, `created_at`, `updated_at`, `is_new`, `introduced_at` e `due` (próxima revisão, `null` se ainda não foi estudado). Horários em UTC, ISO 8601.

### Importação em lote

```sh
code-cards import lote.json
cat lote.json | code-cards import -
```

```json
{
  "deck": "Python async",
  "create_deck_if_missing": true,
  "cards": [
    { "code": "...", "description": "...", "language": "python", "tags": ["asyncio"] }
  ]
}
```

- `deck` (obrigatório): nome ou id. Com `create_deck_if_missing: true`, cria o deck se não existir.
- `cards` (obrigatório): de 1 a 100 itens; cada um com `code` e `description` obrigatórios e `language` e `tags` opcionais. Campos desconhecidos são rejeitados.
- **Tudo ou nada:** se algum card for inválido ou não houver vagas suficientes, nada é gravado. O erro de validação lista todos os problemas em `error.details.errors` (`path` + `message`); o `DECK_FULL` informa as vagas em `error.details.available`.
- Resposta: `deck_id`, `deck_name`, `deck_created` e `card_ids` (na ordem do lote).

O schema completo está em [`batch.schema.json`](batch.schema.json) e em `code-cards schema --raw`.

## Trecho para o prompt de um LLM

Copie e cole no prompt do assistente que vai gerar os cards:

````markdown
Você tem acesso ao comando `code-cards`, um app de flash cards para treinar leitura de código.
Cada card mostra um trecho de código (frente) e uma descrição do que ele faz (verso).

Para criar cards, monte um lote JSON e envie pelo stdin:

```sh
code-cards import - <<'JSON'
{
  "deck": "NOME DO DECK",
  "create_deck_if_missing": true,
  "cards": [
    {
      "code": "trecho de código curto e autocontido",
      "description": "o que o código faz e por quê, em 1 a 3 frases",
      "language": "python",
      "tags": ["tema"]
    }
  ]
}
JSON
```

Regras:
- A resposta é sempre JSON. Confira `"ok"`. Se for `false`, leia `error.code` e `error.message`, corrija e tente de novo.
- O lote é tudo ou nada. Um deck aceita no máximo 100 cards; veja as vagas com `code-cards deck list` (campo `available`).
- `code` e `description` são obrigatórios. Não use campos fora de `code`, `description`, `language` e `tags`.
- Prefira trechos de 3 a 30 linhas, focados em uma ideia. A descrição explica o comportamento, não repete o código.
- Para conferir o resultado: `code-cards card list --deck "NOME DO DECK"`.
````
