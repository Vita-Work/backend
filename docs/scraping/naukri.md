# Naukri Parser Report

Дата скана: 2026-03-21
Источник: `https://www.naukri.com/` через Playwright MCP

## Краткий вывод

В текущем окружении Naukri не отдаёт живой HTML для публичных страниц. Все проверенные URL возвращают одну и ту же страницу **`Access Denied`** с HTTP `403`, поэтому в этом отчёте нет реальной DOM-карты вакансий, карточек, компаний, фильтров или JSON-LD. Это важно зафиксировать прямо: **для парсинга в этой среде сайт недоступен на уровне edge/security gate, а не на уровне отдельных шаблонов страниц**.

## Что удалось подтвердить в браузере

На всех проверках виден один и тот же denial page:

- `h1`: `Access Denied`
- основной текст: `You don't have permission to access ... on this server.`
- `p`: reference id в формате `Reference #...`
- `p`: ссылка на `https://errors.edgesuite.net/...`

Это выглядит как защита уровня CDN / edge, а не как обычный login wall или anti-bot challenge в DOM.

## Проверенные URL

- `https://www.naukri.com/`
- `https://m.naukri.com/`
- `https://www.naukri.com/jobs-in-bangalore`
- `https://www.naukri.com/job-listings-software-engineer-example`
- `https://www.naukri.com/robots.txt`
- `https://www.naukri.com/sitemap.xml`
- `https://www.naukri.com/companies`

## DOM / HTML

Фактически доступен только denial shell:

- `generic` root container
- `heading` уровня 1 с текстом `Access Denied`
- `text` с причиной отказа
- `paragraph` с reference id
- `paragraph` со ссылкой на error page

Ниже ничего полезного для вакансий нет. Это значит, что:

- нет списка вакансий в DOM
- нет `job detail`
- нет `company/apply` элементов
- нет фильтров, пагинации или search form
- нет structured data
- нет embedded app state

## Сеть / XHR

На проверенных запросах браузер показал только 403-ответы:

- `GET https://www.naukri.com/companies => 403`
- `GET https://www.naukri.com/robots.txt => 403`
- `GET https://www.naukri.com/sitemap.xml => 403`
- favicon-запросы также возвращают `403`

Ни одного полезного XHR/API endpoint из самой страницы извлечь не удалось, потому что контент до них не доходит.

## Auth / Anti-bot

Признаки такие:

- блокировка происходит до рендера полезного контента
- это не reCAPTCHA-экран и не human verification flow
- это серверный edge denial
- сайт не раскрывает даже `robots.txt` и `sitemap.xml`

Для скрапера это означает, что обычный Playwright flow здесь не помогает: проблема не в селекторах, а в доступе.

## Селекторы

Для текущего состояния страницы селекторы почти бесполезны, но как минимальный сигнал можно отметить:

- `h1` -> `Access Denied`
- `paragraph` -> текст ошибки и reference id

Никаких стабильных job selectors, company selectors или filter selectors подтвердить нельзя.

## Таблица маппинга

| Field | Primary source | Fallback | Status |
|---|---|---|---|
| title | no access | none | not available |
| company | no access | none | not available |
| location | no access | none | not available |
| salary | no access | none | not available |
| description | no access | none | not available |
| apply url | no access | none | not available |
| posted date | no access | none | not available |
| filters | no access | none | not available |
| pagination | no access | none | not available |

## 2-pass parser strategy

### Pass 1: access detection

Первым делом парсер должен проверять, не попал ли он на denial page. Для Naukri это сейчас обязательный шаг.

Сигналы отказа:

- `document.title === 'Access Denied'`
- `h1` содержит `Access Denied`
- текст `You don't have permission to access`
- URL страницы содержит `errors.edgesuite.net` в референсе
- сетевой статус главного запроса `403`

### Pass 2: fallback path

Если публичный фронт Naukri снова станет доступен в другой среде, тогда можно переключаться на обычный parser flow:

- home -> search/listing -> detail -> company/apply
- JSON-LD -> DOM -> XHR enrichment

Но в текущем окружении этот второй шаг не активируется, потому что доступ к сайту блокируется раньше.

## Практический вывод

Для этого окружения Naukri сейчас нужно считать **недоступным для HTML-парсинга**. Если нужен дальнейший сбор данных по Naukri, логичный следующий путь — не Playwright на публичном домене, а поиск официальных recruiter-side / partner-side каналов доступа.

## Дополнительный официальный контекст

В открытых официальных материалах Naukri, которые доступны вне этой заблокированной страницы, видны recruiter-side продукты и demo-led hiring suite, например `recruit.naukri.com/hiringsuite/*` и `login.recruit.naukri.com`. Это не часть браузерного скана публичного job board, но это полезный сигнал, что платформа строит отдельный employer/recruiting контур вместо открытого public API.

Проверенные страницы по этому контексту:
- `https://recruit.naukri.com/hiringsuite/naukri-career-site.html`
- `https://recruit.naukri.com/hiringsuite/naukri-resdex.html`
- `https://recruit.naukri.com/hiringsuite/naukri-e-hire.html`
- `https://recruit.naukri.com/hiringsuite/naukri-premium.html`
- `https://login.recruit.naukri.com/Login/RPAuthenticate`
