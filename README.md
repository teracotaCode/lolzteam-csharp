# lolzteam-csharp

[![CI](https://github.com/teracotaCode/lolzteam-csharp/actions/workflows/ci.yml/badge.svg)](https://github.com/teracotaCode/lolzteam-csharp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

C# .NET 8.0 обёртка для API **Lolzteam Forum** и **Market**.

Автоматически сгенерирована из OpenAPI 3.1 схем с полной типизацией, nullable-полями, повторными запросами, ограничением частоты запросов и поддержкой прокси.

## Возможности

- ✅ **100% покрытие API** — автогенерация из официальных OpenAPI-схем
- ✅ **Полная типизация** — 117 моделей Forum + 75 моделей Market, все поля nullable
- ✅ **20 сервисов Forum** + **14 сервисов Market**
- ✅ **Автоматические повторы** — экспоненциальная отсрочка с настраиваемой политикой
- ✅ **Rate limiting** — встроенное ограничение частоты запросов
- ✅ **Поддержка прокси** — HTTP и SOCKS5
- ✅ **async/await** — полностью асинхронный API
- ✅ **.NET 8.0** — C# 12, nullable reference types, System.Text.Json

## Требования

- .NET 8.0+
- C# 12

## Установка
```bash
git clone https://github.com/teracotaCode/lolzteam-csharp.git
cd lolzteam-csharp
dotnet build
```


## Быстрый старт

### Forum API
```csharp
using Lolzteam.Runtime;
using Lolzteam.Generated.Forum;

// Создание клиента
var config = new LolzteamClientConfig
{
    BaseUrl = LolzteamClientConfig.DefaultForumBaseUrl,
    Token = "your-forum-token",
};

using var httpClient = new LolzteamHttpClient(config);
var forum = new ForumClient(httpClient);

// Получить список категорий
var categories = await forum.Categories.ListAsync();

// Получить профиль пользователя
var user = await forum.Users.GetAsync(userId: 1);

// Создать пост
var post = await forum.Posts.CreateAsync(threadId: 123, postBody: "Привет!");

// Получить темы форума
var threads = await forum.Threads.ListAsync(forumId: 1, limit: 10);

// Поиск
var results = await forum.Searching.ThreadsAsync(q: "ключевое слово");
```

### Market API
```csharp
using Lolzteam.Runtime;
using Lolzteam.Generated.Market;

// Создание клиента
var config = new LolzteamClientConfig
{
    BaseUrl = LolzteamClientConfig.DefaultMarketBaseUrl,
    Token = "your-market-token",
};

using var httpClient = new LolzteamHttpClient(config);
var market = new MarketClient(httpClient);

// Поиск Steam-аккаунтов
var items = await market.CategorySearch.SteamAsync(pmin: 10, pmax: 100);

// Получить детали аккаунта
var item = await market.AccountsManaging.GetAsync(itemId: 123456);

// Получить профиль
var profile = await market.Profile.GetAsync();

// Баланс и платежи
var history = await market.Payments.HistoryAsync();
```

## Конфигурация

### Повторные запросы
```csharp
var config = new LolzteamClientConfig
{
    BaseUrl = LolzteamClientConfig.DefaultForumBaseUrl,
    Token = "your-token",
    RetryConfig = new RetryConfig
    {
        MaxRetries = 5,
        InitialDelay = TimeSpan.FromMilliseconds(500),
        MaxDelay = TimeSpan.FromSeconds(30),
        BackoffMultiplier = 2.0,
    },
};
```

### Ограничение частоты запросов
```csharp
var config = new LolzteamClientConfig
{
    BaseUrl = LolzteamClientConfig.DefaultForumBaseUrl,
    Token = "your-token",
    RateLimitConfig = new RateLimitConfig
    {
        MaxRequests = 3,                          // Максимум запросов
        Period = TimeSpan.FromSeconds(1),         // За период
    },
};
```

### Поддержка прокси
```csharp
// HTTP-прокси
var config = new LolzteamClientConfig
{
    BaseUrl = LolzteamClientConfig.DefaultForumBaseUrl,
    Token = "your-token",
    ProxyConfig = ProxyConfig.Parse("http://user:pass@proxy.example.com:8080"),
};

// SOCKS5-прокси
var config = new LolzteamClientConfig
{
    BaseUrl = LolzteamClientConfig.DefaultForumBaseUrl,
    Token = "your-token",
    ProxyConfig = ProxyConfig.Parse("socks5://proxy.example.com:1080"),
};
```

### Таймаут
```csharp
var config = new LolzteamClientConfig
{
    BaseUrl = LolzteamClientConfig.DefaultForumBaseUrl,
    Token = "your-token",
    Timeout = TimeSpan.FromSeconds(60), // По умолчанию 30 секунд
};
```

## Обработка ошибок

```csharp
using Lolzteam.Runtime.Errors;

try
{
    var user = await forum.Users.GetAsync(userId: 123);
}
catch (RateLimitException e)
{
    // 429 — превышен лимит запросов
    Console.WriteLine($"Превышен лимит, повтор через: {e.RetryAfter}");
}
catch (AuthException e)
{
    // 401/403 — ошибка аутентификации
    Console.WriteLine("Проверьте ваш API-токен");
}
catch (NotFoundException e)
{
    // 404 — ресурс не найден
    Console.WriteLine("Не найдено");
}
catch (ValidationException e)
{
    // 400/422 — ошибка валидации
    Console.WriteLine($"Ошибка валидации: {e.Message}");
}
catch (ServerException e)
{
    // 500+ — ошибка сервера
    Console.WriteLine($"Ошибка сервера: {e.StatusCode}");
}
catch (HttpException e)
{
    // Прочие HTTP-ошибки
    Console.WriteLine($"HTTP {e.StatusCode}: {e.Message}");
}
catch (LolzteamException e)
{
    // Базовое исключение для всех ошибок
    Console.WriteLine($"Ошибка: {e.Message}");
}
```

## Покрытие API

### Forum API — сервисы (20)
| Сервис | Описание |
|---|---|
| `Assets` | CSS-ассеты |
| `Authentication` | OAuth-токены |
| `BatchRequests` | Пакетные запросы |
| `Categories` | Категории форума |
| `Chatbox` | Чат в реальном времени |
| `ContentTagging` | Управление тегами |
| `Conversations` | Личные сообщения |
| `Forms` | Управление формами |
| `Forums` | Список форумов и управление |
| `LinkForums` | Форумы-ссылки |
| `Navigation` | Элементы навигации |
| `Notifications` | Уведомления |
| `Pages` | Статические страницы |
| `PostComments` | Комментарии к постам |
| `Posts` | CRUD постов, лайки, жалобы |
| `ProfilePostComments` | Комментарии к постам профиля |
| `ProfilePosts` | Посты в профиле |
| `Searching` | Поиск тем, постов, пользователей |
| `Threads` | CRUD тем, опросы, подписки |
| `Users` | Профили, аватары, подписчики |

### Market API — сервисы (14)
| Сервис | Описание |
|---|---|
| `AccountPublishing` | Публикация/продажа аккаунтов |
| `AccountPurchasing` | Покупка аккаунтов, скидки |
| `AccountsList` | Аккаунты пользователя, заказы, избранное |
| `AccountsManaging` | CRUD аккаунтов, бамп, инвентарь |
| `BatchRequests` | Пакетные запросы |
| `Cart` | Корзина |
| `Categories` | Список категорий |
| `CategorySearch` | Поиск по категориям (Steam, Fortnite и др.) |
| `CustomDiscounts` | Управление скидками |
| `IMAP` | Настройка IMAP-почты |
| `Invoices` | Управление счетами |
| `Payments` | Платежи, переводы, баланс |
| `Profile` | Профиль пользователя |
| `Proxy` | Управление прокси |

## Генерация кода

Перегенерация клиентов из обновлённых схем:

```bash
python3 codegen/generate.py \
  --schema schemas/forum.json \
  --output-dir src/Lolzteam/Generated/Forum \
  --namespace Lolzteam.Generated.Forum

python3 codegen/generate.py \
  --schema schemas/market.json \
  --output-dir src/Lolzteam/Generated/Market \
  --namespace Lolzteam.Generated.Market
```

## Структура проекта

```
src/Lolzteam/
├── Runtime/                         # HTTP-клиент, повторы, лимиты, прокси
│   ├── ILolzteamHttpClient.cs       # Интерфейс HTTP-клиента
│   ├── LolzteamHttpClient.cs        # Реализация HTTP-клиента
│   ├── RetryConfig.cs               # Конфигурация повторов
│   ├── RetryHandler.cs              # Логика повторных запросов
│   ├── RateLimitConfig.cs           # Конфигурация лимитов
│   ├── RateLimiter.cs               # Ограничение частоты запросов
│   ├── ProxyConfig.cs               # Конфигурация прокси
│   └── Errors/                      # Иерархия исключений
│       ├── LolzteamException.cs     # Базовое исключение
│       ├── AuthException.cs         # 401/403
│       ├── RateLimitException.cs    # 429
│       ├── NotFoundException.cs     # 404
│       ├── ValidationException.cs   # 400/422
│       ├── ServerException.cs       # 500+
│       └── HttpException.cs         # Прочие HTTP-ошибки
└── Generated/
    ├── Forum/
    │   ├── ForumClient.cs           # Главный клиент Forum API
    │   ├── *Service.cs              # 20 сервисов
    │   ├── Enums/                   # Перечисления
    │   └── Models/                  # 117 моделей ответов
    └── Market/
        ├── MarketClient.cs          # Главный клиент Market API
        ├── *Service.cs              # 14 сервисов
        ├── Enums/                   # Перечисления
        └── Models/                  # 75 моделей ответов
```

## Сборка и тестирование

```bash
# Сборка
dotnet build

```

## Лицензия

MIT © 2026 Lolzteam
