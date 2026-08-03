# Telegram Invoice Bot 🤖📄

Telegram-бот для автоматизации подачи заявок на оплату счетов сотрудниками с записью данных в Google Таблицу и сохранением файлов в Google Drive.

## 📋 Функциональность

1. **Пошаговый сбор данных** — бот последовательно запрашивает все поля заявки
2. **Валидация ввода** — проверка формата дат, сумм, обязательных полей
3. **Загрузка файла счёта** — PDF, изображения, документы (с проверкой MIME-типа и размера)
4. **Запись в Google Sheets** — данные автоматически попадают в таблицу
5. **Сохранение в Google Drive** — файл счёта загружается с restricted-доступом
6. **Срочные уведомления** — при отметке «срочно» бот уведомляет указанного сотрудника

## 🏗 Архитектура

```
tg-invoice-bot/
├── bot.py                      # Точка входа, настройка Application
├── config.py                   # Конфигурация через pydantic-settings (.env)
├── handlers/
│   └── application.py          # ConversationHandler — пошаговый диалог
├── services/
│   ├── google_sheets.py        # Google Sheets API (service account)
│   └── google_drive.py         # Google Drive API (upload + permissions)
├── models/
│   └── invoice.py              # Pydantic-модели с валидаторами
├── validators/
│   └── fields.py               # Пошаговые валидаторы для ConversationHandler
├── middleware/
│   └── security.py             # Проверка доступа (чат + пользователь)
├── pyproject.toml              # Зависимости и настройки инструментов
└── .env.example                # Шаблон переменных окружения
```

### Стек технологий

| Компонент | Инструмент | Обоснование |
|-----------|-----------|-------------|
| **Язык** | Python 3.12+ | Лучшая экосистема для TG-ботов + Google API |
| **Telegram Bot API** | `python-telegram-bot` v21 | Async-native, ConversationHandler для пошаговых форм |
| **Валидация** | Pydantic v2 | Строгая типизация, кастомные валидаторы на каждое поле |
| **Google Sheets** | `google-api-python-client` | Официальный SDK, service account аутентификация |
| **Google Drive** | `google-api-python-client` | Тот же SDK, permissions API |
| **Конфигурация** | `pydantic-settings` | Загрузка из `.env` с автоматической валидацией |
| **Асинхронность** | `asyncio` | PTB v21 работает на asyncio |
| **Логирование** | `logging` | Стандартная библиотека Python |
| **Bitrix24** | `httpx` + REST API | Поиск сотрудника по Telegram ID через UF-поле |
| **Деплой** | Docker + docker-compose | Контейнеризация, auto-restart, ротация логов |

### Поток данных

```
Пользователь (TG)
       │
       ▼
┌─────────────────┐
│ Security         │──▶ Проверка chat_id и user_id
│ Middleware       │
└─────────────────┘
       │
       ▼
┌─────────────────┐
│ Conversation     │──▶ 9 шагов: дата → контрагент → сумма → статья
│ Handler          │    → комментарий → статус → файл → срочность → ✓
└─────────────────┘
       │
       ├──────────────────────┐
       ▼                      ▼
┌──────────────┐    ┌──────────────────┐
│ Google Sheets │    │ Google Drive      │
│ append_row()  │    │ upload + restrict │
└──────────────┘    └──────────────────┘
       │                      │
       └──────────┬───────────┘
                  ▼
          Уведомление (если срочно)
```

## 🔒 Безопасность

### Идентификация пользователей
- **Telegram user_id** — неизменяемый идентификатор, проверяемый серверами Telegram
- Пользователь аутентифицирован на уровне Telegram, подмена невозможна
- Белый список (`ALLOWED_USER_IDS`) — только указанные сотрудники могут подавать заявки

### Разграничение доступа
- **Chat restriction** — бот принимает команды только в указанном групповом чате (`ALLOWED_CHAT_ID`)
- **Middleware-level проверка** — каждый update проходит через `security_middleware` до попадания в обработчики
- Неавторизованные пользователи получают понятное сообщение об ошибке

### Защита файлов и данных
- **Google Drive permissions** — после загрузки файла удаляются все default-разрешения, остаётся только owner (сервисный аккаунт)
- **MIME-type фильтрация** — принимаются только PDF, изображения, документы
- **Размер файла** — ограничение через `MAX_INVOICE_FILE_SIZE_MB` (по умолчанию 10 МБ)
- **Credentials вне репозитория** — `credentials.json` и `.env` в `.gitignore`
- **Текст заявки виден в чате** — это требование задачи, файл счёта при этом недоступен посторонним

### Защита от подмены пользователя
- Telegram API гарантирует, что `effective_user.id` нельзя подделать
- Имя сотрудника (`full_name`) берётся из профиля Telegram автоматически
- Ручной ввод имени сотрудника не предусмотрен — это исключает impersonation

## 🚀 Инструкция по запуску

### 1. Предварительные требования

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (менеджер пакетов)
- Google Cloud проект с включёнными API: Sheets API, Drive API
- Сервисный аккаунт Google Cloud с ключом в формате JSON

### 2. Создание бота в Telegram

1. Напишите [@BotFather](https://t.me/BotFather) и создайте нового бота: `/newbot`
2. Получите токен бота
3. Добавьте бота в групповой чат и сделайте администратором
4. Узнайте `chat_id` чата (через [@RawDataBot](https://t.me/RawDataBot) или через `getUpdates`)

### 3. Настройка Google Cloud

1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com/)
2. Включите API: **Google Sheets API**, **Google Drive API**
3. Создайте сервисный аккаунт: IAM & Admin → Service Accounts
4. Скачайте JSON-ключ и сохраните как `credentials.json` в корне проекта
5. Предоставьте доступ сервисному аккаунту к Google Таблице и папке Google Drive (email сервисного аккаунта как редактор)

### 4. Установка и запуск

#### Вариант А: Интерактивный мастер (рекомендуется)

```bash
git clone https://github.com/Ivan-Baidyk/tg-invoice-bot.git
cd tg-invoice-bot
python setup.py       # ответить на вопросы — сгенерирует .env
uv sync               # установить зависимости
uv run python bot.py  # запустить
```

#### Вариант Б: Docker Compose

```bash
git clone https://github.com/Ivan-Baidyk/tg-invoice-bot.git
cd tg-invoice-bot
cp .env.example .env
nano .env              # заполнить переменные
# Положить credentials.json в корень проекта
docker compose up -d   # запустить в фоне
docker compose logs -f # смотреть логи
```

#### Вариант В: Ручная настройка

```bash
git clone https://github.com/Ivan-Baidyk/tg-invoice-bot.git
cd tg-invoice-bot
cp .env.example .env
nano .env              # заполнить переменные
uv sync
uv run python bot.py
```

### 5. Развёртывание на сервере (production)

Бот работает как **polling-клиент** — ему не нужен публичный URL или вебхук.
Достаточно запустить Docker-контейнер на любом сервере с доступом в интернет.

```bash
# На сервере:
git clone https://github.com/Ivan-Baidyk/tg-invoice-bot.git /opt/invoice-bot
cd /opt/invoice-bot
python setup.py
# Копируем credentials.json в /opt/invoice-bot/
docker compose up -d
```

Контейнер настроен на `restart: unless-stopped` — переживает перезагрузки сервера.
Логи ротируются: максимум 3 файла по 10 МБ.

### 5. Переменные окружения (`.env`)

| Переменная | Описание | Пример |
|-----------|----------|--------|
| `BOT_TOKEN` | Токен Telegram бота | `7583...:AAH...` |
| `ALLOWED_CHAT_ID` | ID группового чата | `-1001234567890` |
| `ALLOWED_USER_IDS` | ID сотрудников (JSON-список) | `[123456789, 987654321]` |
| `URGENT_NOTIFY_USER_ID` | ID для срочных уведомлений | `123456789` |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Путь к JSON-ключу | `credentials.json` |
| `GOOGLE_SHEET_ID` | ID Google Таблицы | `1ABC...789` |
| `GOOGLE_DRIVE_FOLDER_ID` | ID папки Google Drive | `1XYZ...765` |
| `MAX_INVOICE_FILE_SIZE_MB` | Макс. размер файла (МБ) | `10` |

### 6. Структура Google Таблицы

Таблица должна содержать лист «Заявки» со столбцами:

| A | B | C | D | E | F | G | H | I |
|---|---|---|---|---|---|---|---|---|
| Дата внесения | Плановая дата оплаты | Сотрудник | Контрагент | Сумма | Статья | Статус оплаты | Комментарий | Ссылка на счёт |

## 🧪 Тестирование

```bash
uv run pytest
```

## 📝 Использование

1. В групповом чате сотрудник пишет команду: `/new_invoice`
2. Бот последовательно запрашивает:
   - Плановую дату оплаты (ДД.ММ.ГГГГ)
   - Наименование контрагента
   - Сумму в рублях
   - Статью расхода (из списка)
   - Комментарий (опционально)
   - Статус оплаты (из списка)
   - Файл счёта (опционально)
   - Срочность (да/нет)
3. Бот показывает сводку и ждёт подтверждения `/confirm`
4. Данные записываются в Google Таблицу, файл — в Google Drive
5. Если заявка срочная — отправляется уведомление указанному сотруднику

## ⚙️ Статьи расхода

1. Канцелярия
2. Оборудование
3. ПО и лицензии
4. Аренда
5. Коммунальные услуги
6. Маркетинг и реклама
7. Командировки
8. Обучение
9. Услуги подрядчиков
10. Прочее

## ⚙️ Статусы оплаты

1. Ожидает оплаты
2. Оплачено
3. Отклонено
4. На уточнении

## 📄 Лицензия

MIT
