# Onde e como os dados ficam salvos

O code-cards guarda tudo em arquivos de texto (JSON e JSONL), sem banco de dados. Dá para fazer backup copiando a pasta, versionar os decks num repositório git e ler os arquivos com qualquer editor.

## Pasta de dados

Por padrão, a pasta de dados do sistema:

| Sistema | Caminho |
|---|---|
| Linux | `~/.local/share/code-cards/` |
| macOS | `~/Library/Application Support/code-cards/` |
| Windows | `%LOCALAPPDATA%\code-cards\` |

A variável de ambiente `CODE_CARDS_HOME` substitui esse caminho:

```sh
# Perfil separado
CODE_CARDS_HOME=~/estudos/trabalho code-cards

# Decks versionados num repositório
export CODE_CARDS_HOME=~/repos/meus-decks
```

Para ver a pasta em uso:

```sh
code-cards where
```

## Estrutura

```
code-cards/
├── settings.json          # configurações
├── decks/
│   └── <deck-id>.json     # deck + cards + estado de agendamento atual
├── reviews/
│   └── <deck-id>.jsonl    # histórico de revisões (só acréscimo)
└── .locks/                # travas entre processos (pode ser apagada com o app fechado)
```

### Deck (`decks/<deck-id>.json`)

```json
{
  "schema_version": 1,
  "id": "k3f9a2",
  "name": "Python async",
  "created_at": "2026-11-01T14:00:00Z",
  "cards": [
    {
      "id": "c7d1e0b2",
      "language": "python",
      "code": "async def main():\n    await asyncio.gather(a(), b())",
      "description": "Roda a() e b() concorrentemente e espera as duas.",
      "tags": [],
      "created_at": "2026-11-01T14:00:00Z",
      "updated_at": "2026-11-01T14:00:00Z",
      "introduced_at": null,
      "fsrs": { "card_id": 0, "state": 1, "step": 0, "stability": null, "difficulty": null, "due": "2026-11-01T14:00:00+00:00", "last_review": null }
    }
  ]
}
```

- `id`: 6 caracteres para o deck, 8 para o card. O nome do deck é único, sem diferenciar maiúsculas.
- Um deck tem no máximo 100 cards; cada card está em um único deck.
- `introduced_at`: momento da primeira revisão (`null` = card novo). Serve para o limite de cards novos por dia.
- `fsrs`: estado do agendador [py-fsrs](https://github.com/open-spaced-repetition/py-fsrs), gravado como a biblioteca o serializa. Só o módulo `scheduling.py` lê esse campo.
- Todos os horários estão em **UTC**. A TUI exibe no fuso local.

### Histórico (`reviews/<deck-id>.jsonl`)

Uma linha por evento. O arquivo só recebe linhas novas, nunca é reescrito:

```json
{"type":"review","id":"r91a0x2k","card_id":"c7d1e0b2","grade":"great","rating":3,"reviewed_at":"2026-11-01T14:03:00Z"}
{"type":"undo","review_id":"r91a0x2k","at":"2026-11-01T14:03:05Z"}
```

- `grade`: `great` (Ótimo), `partial` (Parcial) ou `forgot` (Não lembro). `rating` é a nota correspondente do FSRS (3, 2 e 1).
- Um evento `undo` anula a revisão com aquele `review_id`.
- O histórico é usado para contar as revisões do dia e fica disponível para estatísticas e para o otimizador do FSRS no futuro.

### Configurações (`settings.json`)

```json
{
  "schema_version": 1,
  "keys": { "great": "a", "partial": "s", "forgot": "d", "reveal": "space", "undo": "u" },
  "show_help": true,
  "new_cards_per_day": 50,
  "reviews_per_day": 200,
  "desired_retention": 0.9,
  "day_starts_at_hour": 4,
  "editor_theme": "monokai"
}
```

| Campo | Significado |
|---|---|
| `keys` | Teclas do estudo, com os nomes do Textual (`a`, `space`, `j`, `f1`...). `Esc`, `Q` e `?` são reservadas. |
| `show_help` | Mostra a barra de ajuda. As teclas funcionam mesmo com ela desligada (`?` mostra a barra temporariamente). |
| `new_cards_per_day` | Cards novos por dia, por deck. |
| `reviews_per_day` | Revisões por dia, por deck. |
| `desired_retention` | Retenção desejada pelo FSRS (0,80 a 0,97). Mais alta = revisões mais frequentes. |
| `day_starts_at_hour` | Hora local em que o dia de estudo vira (como no Anki). Quem estuda à 1h ainda está no dia anterior. |
| `editor_theme` | Tema de cores do código: `monokai`, `dracula`, `github_light`, `vscode_dark` ou `css`. |

Se o arquivo não existir, valem os padrões acima.

## Segurança dos arquivos

- **Escrita atômica:** cada arquivo é gravado num temporário na mesma pasta e trocado com `os.replace`. Se o app cair no meio, o arquivo antigo continua intacto.
- **Trava entre processos:** a CLI (um LLM, por exemplo) pode adicionar cards com a TUI aberta. Cada deck é travado durante leitura → alteração → escrita, e a TUI relê os decks ao voltar ao painel e antes de cada resposta.
- **Versão do formato:** todo arquivo tem `schema_version`. Ao abrir um arquivo antigo, o app migra para o formato atual. Um arquivo gravado por uma versão mais nova do code-cards é recusado, em vez de ser sobrescrito.
- **Diffs legíveis:** JSON com indentação de 2 espaços e chaves em ordem fixa.

## Editando à mão

Os arquivos podem ser editados com o app fechado. Prefira a CLI (`code-cards card edit ...`), que valida os dados. Se editar `decks/*.json` diretamente, mantenha `schema_version`, os ids e o campo `fsrs` intactos.
