# DevKG parser report

Источник: `https://devkg.com/ru/jobs`
Дата проверки: `2026-03-21`

## Короткий вывод
DevKG - это **SSR-сайт сообщества**, а не классический SPA job board. Для парсинга он довольно удобный: у списка вакансий есть стабильный DOM, у detail/company страниц есть `JSON-LD`, а полезные данные дополнительно лежат в `window.__NUXT__`. Главная сложность здесь не в структуре вакансий, а в **сильном рекламном шуме** и вставленных `iframe`/AdSense блоках.

## Типы страниц
### Home / hub
`https://devkg.com/ru`

Это главная страница сообщества с навигацией по разделам `Вакансии`, `Мероприятия`, `Видео`, `Организации`, `Сообщество`.

### Listing
`https://devkg.com/ru/jobs`

Страница списка вакансий. На ней показаны карточки вакансий и пагинация через `Следующая страница`.

### Detail
`https://devkg.com/ru/jobs/<slug>`

Страница конкретной вакансии. Здесь есть заголовок вакансии, компания, тип работы, зарплата, описание, Telegram-контакт и блоки похожих вакансий.

### Company
`https://devkg.com/ru/organizations/<slug>-<id>`

Страница компании с описанием, сайтом компании и списком вакансий этой компании.

## Listing page structure
### Главные контейнеры
На listing странице основная структура выглядит так:
- header/navigation
- кнопка `Добавить вакансию`
- основной список вакансий в серии `article`
- пагинация `Следующая страница`
- footer сообщества

### Карточка вакансии
Каждая карточка - это `article`, внутри которого корневой `link` ведет на detail URL.

В карточке реально доступны поля:
- компания
- должность
- оклад
- тип
- город / локация
- изображение / логотип компании

### Как хранится контент
Карточка вакансии хранит данные не через сложные data-атрибуты, а через обычный текстовый DOM внутри одной большой ссылки. Это удобно для скрапера: можно брать корневой `a`, а потом вытаскивать подписи `Компания`, `Должность`, `Оклад`, `Тип` и следующие за ними текстовые значения.

### Листинговые селекторы
Primary:
```css
article a[href^="/ru/jobs/"]
article img[alt]
article
```

Fallback:
```css
main article
main a[href*="/ru/jobs/"]
```

### Пагинация
Пагинация реализована простой ссылкой:
- `Следующая страница` -> `/ru/jobs?page=2`

Для пагинатора это очень стабильный сигнал. Никакого infinite scroll я не увидел.

## Detail page structure
### Верхний блок
На detail странице есть:
- `h1` с названием вакансии
- ссылка на компанию
- тип вакансии
- оклад

### Описание вакансии
Далее идет блок `Описание вакансии`, внутри которого контент размечен как:
- заголовки в `strong`
- списки обязанностей
- списки ожиданий
- списки преимуществ

Это обычный текстовый SSR DOM, без необходимости в дополнительной JS-гидратации для чтения текста.

### Telegram / apply flow
Вместо привычной формы отклика сайт показывает контакт:
- `Telegram`
- ссылка `@Founder_2W`

То есть apply-flow здесь фактически **не внутренняя форма**, а внешний контактный канал. Для скрапера это важно: не искать `apply button` там, где его нет. Важно различать:
- пользовательский контакт
- кнопку логина / добавления вакансии
- похожие вакансии

### Похожие вакансии
В detail есть два полезных блока:
- `Похожие вакансии`
- `Другие вакансии компании`

Оба блока дают дополнительные ссылки на другие вакансии и могут быть источником для обхода и расширения графа вакансий по компании.

### Detail selectors
Primary:
```css
h1
main a[href^="/ru/organizations/"]
main strong
main ul li
main a[href^="https://t.me/"]
```

Fallback:
```css
article, main
```

## Company page structure
### Верхний блок
На странице компании есть:
- `h1` с названием компании
- ссылка на официальный сайт
- описание компании

### Вакансии компании
Ниже расположен список вакансий компании в виде карточек `article`, по той же схеме, что и на listing странице.

### Company selectors
Primary:
```css
h1
main a[href^="http"]
main article a[href^="/ru/jobs/"]
```

Fallback:
```css
main
```

## JSON-LD
### Listing page
На listing странице найден только один `script[type="application/ld+json"]`, и это `BreadcrumbList`.

То есть на листинге JSON-LD не содержит самих вакансий, только breadcrumb-навигацию.

### Detail / company pages
На detail и company страницах есть полезный structured data:
- `Organization`
- `BreadcrumbList`

Это хороший источник для:
- названия компании
- canonical URL
- logo
- хлебных крошек

### Вывод по JSON-LD
Primary source для вакансий на DevKG - **не JSON-LD листинга**, а `window.__NUXT__` и live DOM. JSON-LD полезен как дополнительный слой на detail/company.

## Embedded state
### __NUXT__
На сайте есть `window.__NUXT__`, и это очень важный источник для парсинга.

На listing странице в `__NUXT__.data[0].jobs` лежит массив вакансий с полями вроде:
- `slug`
- `currency`
- `price_from`
- `price_to`
- `position`
- `city`
- `salary`
- `created_at`
- `updated_at`
- `organization_name`
- `organization_icon`
- `type`

Это почти готовая нормализованная схема, которую можно брать как первичный data-source для списка.

На detail и company страницах `__NUXT__` тоже есть полезные данные страницы и route state.

### Почему это важно
Для DevKG лучший порядок извлечения такой:
1. `window.__NUXT__.data`
2. live DOM
3. JSON-LD
4. API endpoints

## Network / XHR
### Замеченные API endpoints
На реальном скане были зафиксированы такие рабочие endpoints:
- `GET https://devkg.com/api/pages/job?slug=<job-slug>`
- `GET https://devkg.com/api/pages/organization?slug=<organization-slug>`

Это очень ценно, потому что эти endpoints явно возвращают данные для detail/company страниц.

### Остальная сеть
Также на страницах активно дергаются:
- Google Analytics
- AdSense
- Google ad services
- Cloudflare RUM endpoint `cdn-cgi/rum`
- funding choices / consent scripts

Для парсинга это шум, его надо игнорировать.

## Auth / anti-bot
### Auth
Есть кнопка `Войти`, но сам job board публично читается без логина.

### Anti-bot / blocks
Я не увидел классический CAPTCHA wall на job pages. Но на странице очень много рекламных iframe и Google ad traffic, из-за чего при автоматизации будет много лишних сетевых запросов и консольных предупреждений.

### Практический риск
Главный риск не в блокировке контента, а в том, что при наивном парсинге можно:
- принять рекламу за контент
- перепутать iframe-ad блок с реальным вакансийным блоком
- потерять стабильность из-за рекламных вставок между `article`

## Primary / fallback selectors
### Listing
Primary:
```css
main article a[href^="/ru/jobs/"]
main article
```
Fallback:
```css
article
```

### Detail
Primary:
```css
h1
main a[href^="/ru/organizations/"]
main a[href^="https://t.me/"]
main ul li
```
Fallback:
```css
main
```

### Company
Primary:
```css
h1
main a[href^="http"]
main article a[href^="/ru/jobs/"]
```
Fallback:
```css
main
```

## Field mapping
| Field | Primary source | Fallback |
|---|---|---|
| job title | `window.__NUXT__.data[0].jobs[].position` / listing card text / detail `h1` | DOM text from root `article a` |
| company name | `window.__NUXT__.data[0].jobs[].organization_name` / detail company link | DOM text after label `Компания` |
| salary min | `window.__NUXT__.data[0].jobs[].price_from` | listing/detail text after `Оклад` |
| salary max | `window.__NUXT__.data[0].jobs[].price_to` | listing/detail text after `Оклад` |
| currency | `window.__NUXT__.data[0].jobs[].currency` | parsed from displayed salary text |
| city | `window.__NUXT__.data[0].jobs[].city` | text after `Тип` or detail page location |
| employment type | `window.__NUXT__.data[0].jobs[].type` | detail `Тип` value |
| job slug | `window.__NUXT__.data[0].jobs[].slug` | listing/detail URL path |
| created_at | `window.__NUXT__.data[0].jobs[].created_at` | API `/api/pages/job` |
| updated_at | `window.__NUXT__.data[0].jobs[].updated_at` | API `/api/pages/job` |
| description | detail page DOM text | `/api/pages/job?slug=...` |
| company logo | `window.__NUXT__.data[0].jobs[].organization_icon` | `Organization` JSON-LD |
| company website | company page DOM `a[href^="http"]` | `Organization` JSON-LD |
| company description | company page DOM main text | `/api/pages/organization?slug=...` |
| telegram contact | detail page `a[href^="https://t.me/"]` | none |

## 2-pass parser strategy
### Pass 1
Crawl listing page and extract:
- `__NUXT__.data[0].jobs`
- listing `article` cards
- `next page` URL

Goal: получить нормализованный список вакансий с slug, company, salary, city, type.

### Pass 2
Для каждой вакансии открыть detail page и company page:
- извлечь `h1`
- описание
- Telegram contact
- похожие вакансии
- другие вакансии компании
- company description
- structured data
- API endpoint enrichment через `/api/pages/job?slug=...` и `/api/pages/organization?slug=...`

## Что важно для реализации парсера
- На DevKG надо явно фильтровать рекламу и iframe.
- Не полагаться на один JSON-LD: на listing он бедный.
- Использовать `__NUXT__` как главный источник на listing.
- Использовать API detail/company как enrichment layer.
- Пагинация простая, через `?page=2`, это удобно для перебора.

## Проверенные URL
- `https://devkg.com/ru/jobs`
- `https://devkg.com/ru/jobs/vedushchiy-specialist-otdela-po-protivodeystviyu-moshennichestvu-antifrod-zao-ekoislamikbank-21462`
- `https://devkg.com/ru/organizations/ekoislamikbank-720`
- `https://devkg.com/api/pages/job?slug=vedushchiy-specialist-otdela-po-protivodeystviyu-moshennichestvu-antifrod-zao-ekoislamikbank-21462`
- `https://devkg.com/api/pages/organization?slug=ekoislamikbank-720`
- `https://devkg.com/ru/jobs?page=2`

## Итог
DevKG хорошо парсится, если идти не от HTML-слов, а от **SSR + `window.__NUXT__` + API enrichment**. Для вакансий там уже есть почти готовая структура полей, а главные проблемы лежат в рекламных вставках и необходимости правильно отличать job-карточки от ad-iframe блоков.
