# code-cards

Flash cards de terminal para desenvolvedores: pratique a leitura e a revisão de código (inclusive código gerado por IA) com repetição espaçada [FSRS](https://github.com/open-spaced-repetition/py-fsrs), syntax highlight e uma CLI em JSON que permite a LLMs criar decks e cards.

Cada card mostra um trecho de código. Você tenta lembrar o que ele faz, revela a descrição e dá uma nota: **Ótimo**, **Parcial** ou **Não lembro**. O FSRS decide quando o card volta.

```
 Python async                          Novos 12 · Revisar 5
 ┌ código ─────────────────────────────────────────────┐
 │ 1  async def main():                                │
 │ 2      await asyncio.gather(a(), b())               │
 └─────────────────────────────────────────────────────┘
 ┌ descrição ──────────────────────────────────────────┐
 │ Roda a() e b() concorrentemente e espera as duas.   │
 └─────────────────────────────────────────────────────┘
  A Ótimo · 4d    S Parcial · 1d    D Não lembro · 10min    U desfazer
```

## Instalação

Requer Python 3.11 ou mais recente.

Com [uv](https://docs.astral.sh/uv/):

```sh
uv tool install .            # a partir de um clone do repositório
```

Ou com [pipx](https://pipx.pypa.io/):

```sh
pipx install .
```

Depois, o comando `code-cards` fica disponível no terminal.

## Uso rápido

```sh
code-cards                   # abre a TUI
```

1. No painel, aperte **Enter** em **+ Criar deck** e dê um nome.
2. Em **+ Adicionar card**, cole um trecho de código, escreva a descrição e salve com **Ctrl+S**.
3. Volte ao painel, selecione o deck e aperte **Enter** para estudar.

### Teclas

| Onde | Tecla | Ação |
|---|---|---|
| Painel | `Enter` | estudar o deck / executar a ação selecionada |
| | `G` | gerenciar o deck selecionado |
| | `Q` | sair |
| Estudo | `Espaço` | mostrar a descrição |
| | `A` / `S` / `D` | Ótimo / Parcial / Não lembro |
| | `U` | desfazer a última resposta |
| | `Esc` | voltar |
| Gerenciar deck | `Enter` | editar o card |
| | `Del` | apagar o card |
| | `N` | novo card |
| | `R` | renomear o deck |
| | `X` | apagar o deck (pede o nome para confirmar) |
| Editor de card | `Ctrl+S` | salvar |
| | `Esc` | cancelar |
| | `Ctrl+↓` / `Ctrl+↑` | próximo campo / campo anterior |
| Painel, estudo e gerenciar | `?` | mostrar/esconder a barra de ajuda |

As teclas do estudo podem ser trocadas em **⚙ Configurações**, junto com a barra de ajuda, os limites diários (50 cards novos e 200 revisões por deck), a retenção desejada e a hora em que o dia de estudo vira (4h, como no Anki).

## CLI

Com argumentos, `code-cards` vira uma CLI que responde sempre em JSON e nunca pergunta nada. É pensada para scripts e LLMs.

```sh
code-cards deck create "Python async"
code-cards card add --deck "Python async" --code-file app.py --lines 10-40 \
                    --description "Abre a conexão e repete em caso de timeout."
code-cards card list --deck "Python async"
code-cards import lote.json              # vários cards de uma vez, tudo ou nada
```

```json
{ "ok": true, "data": { "deck_id": "k3f9a2", "card_ids": ["c7d1e0b2"] }, "warnings": [] }
```

A referência completa está em [docs/CLI.md](docs/CLI.md), que também traz um trecho pronto para colar no prompt de um LLM e deixá-lo gerar cards.

## Dados

Decks, histórico e configurações ficam em arquivos JSON na pasta de dados do sistema (`~/.local/share/code-cards/` no Linux). A variável `CODE_CARDS_HOME` troca a pasta, o que permite separar perfis ou versionar os decks num repositório. `code-cards where` mostra a pasta em uso. Detalhes em [docs/DADOS.md](docs/DADOS.md).

## Desenvolvimento

```sh
uv sync                      # cria o ambiente com as dependências de desenvolvimento
uv run code-cards            # roda a partir do código-fonte
uv run pytest                # testes
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

Os testes usam `CODE_CARDS_HOME` numa pasta temporária e um relógio fixo, então não tocam nos seus dados.

Arquitetura em uma frase: a TUI ([Textual](https://textual.textualize.io/)) e a CLI ([Typer](https://typer.tiangolo.com/)) só falam com a camada de serviços (`src/code_cards/services/`), que concentra as regras (limite de 100 cards, validação, lote tudo ou nada) e usa o armazenamento em JSON e o adaptador do FSRS.

## Licença

[MIT](LICENSE)
