# IRSEN Python client

Отдельный транспортный клиент, без сторонних зависимостей. Python 3.9+.
TCP endpoint: `127.0.0.1:47621`. Протокол: UTF-8, newline-delimited JSON;
одна строка на request и одна строка на response.

1. Запустить IRSEN с `DEV_MODE = false` и `AGENT_MODE = true`.
2. Вручную зайти в бой.
3. Дождаться player turn (`ready == true`).
4. В папке этого проекта выполнить `python smoke_test.py`.
   На Windows также можно использовать `py smoke_test.py`.

Smoke test печатает ping, before, доступные actions и выбранный action,
выполняет **ровно первый action с `type == "skill"`**, ждёт завершения
действия/enemy phase и печатает result и after. Соединение закрывается
в `finally`. Успех: код выхода 0; ошибка: сообщение в stderr и код 1.
Скрипт выполняет реальное действие в игре; автоматического игрового цикла нет.

## Клиент

```python
from irsen_client import IrsenClient

client = IrsenClient()  # timeout=5.0, action_timeout=120.0
try:
    client.connect()
    print(client.ping())
    print(client.get_combat_state())
    print(client.get_available_actions())
    # client.perform_action(action_id)  # ID из get_available_actions()
finally:
    client.close()
```

Методы возвращают поле `result` (actions — список). `_request()` автоматически
генерирует числовые ID; response ID `1.0` соответствует request ID `1`.
Внутренний байтовый buffer хранит остаток после `\n` и незавершённые строки,
включая разрезанные UTF-8 символы. На одном TCP connection можно выполнять
несколько последовательных requests. Клиент синхронный, не потокобезопасный.

Обычные команды и подключение имеют timeout 5 секунд; `perform_action` —
120 секунд. Timeout ограничивает весь обмен request/response, а не отдельный
`recv()`. Ожидание блокирующее, без busy polling, повторных отправок и reconnect.

- `IrsenConnectionError`: нет соединения, отказ подключения, обрыв или EOF.
- `IrsenTimeoutError`: превышен timeout подключения/команды.
- `IrsenProtocolError`: bridge вернул `ok: false`, неверный UTF-8/JSON,
  несовпадающий ID или неправильный формат ответа.
- `ValueError`: пустой/нестроковый `action_id` или некорректные timeout.

Все ошибки клиента наследуются от `IrsenError`; исходные транспортные ошибки
сохраняются через exception chaining. После обрыва, timeout или повреждённого
ответа соединение закрывается, чтобы поздний ответ не попал в следующий request.
Корректный ответ с `ok: false` оставляет соединение доступным.
Timeout/обрыв не отменяет уже принятое игровое действие: перед повтором
проверьте состояние игры. LLM, стратегии и автономный агент отсутствуют.

## MCP stdio server (Step 5)

`mcp_server.py` использует официальный MCP Python SDK v2; проверен с `mcp 2.2.0`.
Для MCP нужен Python 3.10+; существующая `.venv` использует Python 3.14.
Единственная прямая зависимость в `requirements.txt`: `mcp>=2,<3`.
При необходимости установить её: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

Ручной запуск из PowerShell:

```powershell
cd D:\godot\irsen_agent
.\.venv\Scripts\python.exe mcp_server.py
```

Сервер ждёт MCP-сообщения на stdin и отвечает на stdout. Это не интерактивная
консоль; без MCP host он просто ждёт ввода. Остановить можно через Ctrl+C.
В stdout нет обычных логов; SDK направляет диагностику в stderr.

Архитектура: MCP host → MCP stdio → `mcp_server.py` → `IrsenClient`
→ TCP `127.0.0.1:47621` → IRSEN.

Ровно четыре инструмента:

| MCP tool | Метод IrsenClient |
| --- | --- |
| `irsen_ping()` | `ping()` |
| `irsen_get_combat_state()` | `get_combat_state()` |
| `irsen_get_available_actions()` | `get_available_actions()` |
| `irsen_perform_action(action_id: str)` | `perform_action(action_id)` |

Каждый вызов создаёт новый клиент, подключается, выполняет одну операцию
и закрывает соединение в `finally`, включая случаи ошибки. При запуске сервера
TCP-подключения нет, поэтому IRSEN может быть выключена. Состояние соединений
не сохраняется; повторных отправок нет. Таймауты остаются в `IrsenClient`:
5 секунд для обычных команд, 120 секунд для `perform_action`. MCP host должен
дать вызову действия достаточно времени (больше 120 секунд с запасом на подключение).

Python-функции возвращают полный исходный словарь/список без изменений.
SDK сериализует словари в MCP `structuredContent` напрямую, а полный список
actions — в `structuredContent.result` (стандартная обёртка SDK для списка).
Никакие поля или actions не отбрасываются.

`IrsenError` и `ValueError` преобразуются в `ToolError`: MCP host получает
`isError: true` с понятным сообщением, а сервер продолжает работать.
Ошибки аргументов обрабатывает SDK. Timeout не отменяет уже принятое действие.
MCP-слой не выбирает actions, не содержит боевых правил, циклов, scoring,
retries или автономной игры. Настройка Codex и поддержка world/gene map
в этот шаг не входят.
