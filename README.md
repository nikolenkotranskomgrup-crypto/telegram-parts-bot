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
