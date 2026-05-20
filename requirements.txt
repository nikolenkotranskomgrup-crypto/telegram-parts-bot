# Telegram Parts Bot

Бот для заявок на запчасти и возврата снятых б/у запчастей.

## Файлы

- `main.py` — основной код бота и веб-страницы.
- `requirements.txt` — зависимости.
- `Procfile` — команда запуска для Render.

## Render Environment Variables

Добавить в Render → Environment:

- `BOT_TOKEN` — токен Telegram-бота от BotFather.
- `PARTS_GROUP_ID` — ID группы “Регионы склад ТКГ”.
- `RETURNS_GROUP_ID` — ID группы “б/у ТКГ регионы”.
- `WEBHOOK_URL` — URL Render-сервиса, например `https://telegram-parts-bot.onrender.com`.
- `ADMIN_ID` — Telegram ID администратора для резервной копии.

## Render Start Command

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Проверка

Открой:

```text
https://твой-сервис.onrender.com/health
```

Должно быть `ok`.

Веб-таблица:

```text
https://твой-сервис.onrender.com/
```


## Обновление: резервная копия и автоматический webhook

Добавлено:

1. Кнопка `💾 Резервная копия` и команда `/backup`.
2. Команда `/id`, чтобы узнать Telegram ID пользователя.
3. Автоматическая установка webhook при каждом запуске Render.
4. Webhook больше не удаляется при остановке Render, поэтому бот не должен “слетать” после redeploy/sleep/restart.

Для backup добавь в Render → Environment:

```text
ADMIN_ID=6269832500
```

Проверка webhook:

```text
https://api.telegram.org/botТВОЙ_ТОКЕН/getWebhookInfo
```

Должно быть:

```text
"url":"https://telegram-parts-bot.onrender.com/webhook"
```
