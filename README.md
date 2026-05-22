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


## Supabase / PostgreSQL

Бот хранит данные в Supabase PostgreSQL через переменную Render:

```text
DATABASE_URL=postgresql://...
```

## Ежедневная резервная копия

Бот отправляет админу JSON backup каждый день после `DAILY_BACKUP_HOUR`.

Переменные Render:

```text
ADMIN_ID=6269832500
ANDREY_ID=6553421734
AUTO_DAILY_BACKUP=true
DAILY_BACKUP_HOUR=6
```

## Неопознанная б/у запчасть от склада

В группе `б/у ТКГ регионы` можно вызвать меню командой:

```text
/start
```

После этого в группе появляется кнопка:

```text
⚠️ Неопознанная б/у запчасть
```

Склад нажимает кнопку и отправляет одним сообщением или фото с подписью:

```text
123456
Стартер
1
```

Также работает быстрый формат без кнопки:

```text
+БУ
123456
Стартер
1
```

Бот отправляет Андрею личное сообщение. Андрей отвечает в 2 строки:

```text
АА1234ВС
На б/у склад
```

Рекомендация пишется в свободной форме.

Примеры рекомендаций:

```text
В утиль
На восстановление
На б/у склад
```
