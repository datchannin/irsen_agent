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
проверьте состояние игры. MCP, LLM, стратегии и автономный агент отсутствуют.
