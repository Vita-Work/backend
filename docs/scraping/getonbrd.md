# Get on Board DOM / API Report

Дата проверки: 2026-03-21
Цель: подготовить базу для будущего парсера вакансий, company profiles и API-интеграции.

## Короткий вывод

Get on Board хорошо структурирован для парсинга через сочетание **публичного `search/jobs` API**, **DOM карточек вакансий**, **детальной страницы вакансии** и **страницы компании**. На живых страницах я **не увидел JSON-LD** на home, listing, job detail и company profile, поэтому для веб-парсинга основными источниками будут DOM и публичный API.

Есть важная оговорка: документация API описывает public API как доступный без логина, но в live-проверке `GET /api/v0/jobs?page=1&per_page=1&lang=en` вернул `401 Unauthorized`, а `GET /api/v0/search/jobs?query=node&page=1&per_page=1&lang=en` вернул `200` и полезные данные. Это значит, что **парсер нельзя строить на предположении, будто все API-эндпоинты открыты одинаково**.

## Проверенные страницы

| Тип | URL | Что подтверждено |
|---|---|---|
| Home | `https://www.getonbrd.com/` | Hero, search box, featured jobs, category blocks, country/city/tag blocks, events, insights, footer API link |
| Listing | `https://www.getonbrd.com/jobs/programming` | Большая SSR-страница со списком карточек вакансий по категории |
| Job detail | `https://www.getonbrd.com/jobs/programming/backend-developer-node-js-aws-bc-tecnologia-remote` | Полная детальная страница вакансии, apply flow, tags, company teaser, share links |
| Company profile | `https://www.getonbrd.com/companies/bctecnologia` | About section, follower count, jobs list, follow link, website link |
| Apply/login wall | `https://www.getonbrd.com/jobs/backend-developer-node-js-aws-bc-tecnologia-remote/applications/new` | Редирект на `https://www.getonbrd.com/webpros/login` |
| API docs | `https://www.getonbrd.com/api-doc.html` | Scalar OpenAPI docs с public/private API, sandbox, auth, pagination, expand |
| OpenAPI YAML | `https://www.getonbrd.com/doc/openapi.yaml` | Полный OpenAPI документ |

## Home page

### Основная структура

Home-страница состоит из верхнего бара, hero-блока, набора быстрых ссылок и длинной нижней части с подборками.

### Что видно в DOM

| Блок | Наблюдение |
|---|---|
| Cookie banner | Есть overlay с кнопкой `Accept all cookies` |
| Header | Лого, поиск, `Superpower AI`, `💰 Salaries`, `Pricing`, `ATS`, `Help`, `Sign in`, `Sign up`, theme switch |
| Search | `input#search_term` с placeholder вида `Search jobs: MySQL, Service Designer, Vue...` |
| Hero | Заголовок `Jobs in awesome tech companies` и подзаголовок о LATAM tech jobs |
| Quick links | Категории: `Design / UX`, `Programming`, `Data Science / Analytics`, `Mobile Development`, `Customer Support`, `Digital Marketing`, `SysAdmin / DevOps / QA`, `Operations / Admin`, `Sales`, `Product, Innovation & Agile` |
| Featured jobs | Карточки вакансий в виде больших ссылок с title, company, location, perks icons, salary, date |
| Events | Upcoming events block с датой, title и city link |
| Category sections | `Programming jobs`, `SysAdmin / DevOps / QA`, `Data Science / Analytics`, `Sales`, `Product, Innovation & Agile`, `Design / UX`, `Operations / Management`, `Mobile Developer`, `Customer Support`, `Digital Marketing`, etc. |
| Bottom blocks | `Jobs by category`, `Remote companies`, `Tests and assessments`, `Jobs by country`, `Jobs by city`, `Jobs by tags`, blogs, podcasts, Events, Insights, social links |
| Footer | Есть явный линк `API` на `/api-doc.html` |

### Теги и контент

Home page не использует JSON-LD в проверенных снэпшотах. Данные лежат прямо в DOM: заголовки, ссылки, числа, названия компаний, города, иконки-перки и даты.

### Полезные селекторы

| Что искать | Селектор / паттерн |
|---|---|
| Search input | `input#search_term` |
| Hero title | `h1` |
| Featured/job card root | `a[href*="/jobs/"], a[href*="/empleos/"], a[href*="/jobs/programacion/"]` |
| Job title inside card | `h3, h4` внутри root anchor |
| Company name inside card | `strong` внутри root anchor |
| Location inside card | текст рядом с иконкой `` |
| Salary inside card | текст рядом с иконкой `` |
| Date inside card | последний текстовый блок в карточке |

## Listing page

### Проверенная страница

`https://www.getonbrd.com/jobs/programming`

### Структура листинга

Это SSR-страница с breadcrumb `All jobs > Programming`, H1/H2, и длинным списком карточек.

### Как устроена карточка вакансии

Каждая карточка в живом DOM обернута в один большой `a[href]`, который ведет на detail page. Внутри карточки обычно есть:

| Поле | Где лежит |
|---|---|
| Company logo | `img` с alt названием компании |
| Title | `h3` или `h4` внутри карточки, часто внутри `strong` |
| Company | `strong` рядом с title |
| Location | текст с иконкой `` |
| Modality | `Remote`, `Hybrid`, `In-office` и локализованные варианты |
| Salary | текст рядом с иконкой `` |
| Date | `Mar 20`, `March 20, 2026`, `ago 07` и т.д. |
| Badges | `New`, `🚀 Responds quickly`, дополнительные иконки/перки |

### Важные наблюдения

На `Programming jobs` я **не увидел**:

| Признак | Статус |
|---|---|
| Pagination links `?page=` | Не наблюдались в DOM |
| `load more` button | Не наблюдался |
| Infinite scroll hints | Не наблюдались (`data-infinite-scroll`, `data-controller*="scroll"`) |

То есть текущий листинг выглядит как **длинная SSR-страница без явной пагинации в видимой области**. При этом страницы фильтров и категории существуют как обычные URL.

### Полезные URL-паттерны

| Тип | Пример |
|---|---|
| Category page | `/jobs/programming` |
| Job detail | `/jobs/programming/backend-developer-node-js-aws-bc-tecnologia-remote` |
| Localized slug | `/empleos/programacion/...` |
| City/category/tag filters | `/jobs/city/santiago`, `/jobs/tag/aws`, `/jobs/tag/python` |

## Job detail page

### Проверенная страница

`https://www.getonbrd.com/jobs/programming/backend-developer-node-js-aws-bc-tecnologia-remote`

### Верхний блок

| Элемент | Наблюдение |
|---|---|
| Company header | `BC Tecnología` с link на company page и `Follow` |
| Publish time | `March 20, 2026` |
| Title | `Back-end Developer (Node.js / AWS)` в `h1` |
| Secondary line | `Remote | Semi Senior | Freelance | Programming` в `h2` |
| Applications count | `96 applications` |
| Response time | `Responde entre 3 y 11 días` |
| Freshness | `Last checked today` |
| Apply CTA | `Apply now` ведет на `/applications/new` |

### Основной контент

Ниже идут текстовые блоки, каждый со своим H3:

| Секция | Содержание |
|---|---|
| Company teaser | Описание компании и короткая фраза `Apply without intermediaries through Get on Board.` |
| `Funciones` | Список задач в `ul > li` |
| `Requisitos` | Список требований |
| `Deseables` | Один текстовый абзац |
| `Beneficios` | Несколько абзацев |
| Job ID | `GETONBRD Job ID: 59837` |
| Remote work policy | `Fully remote` и пояснение `Candidates can reside anywhere in the world.` |

### Apply flow внутри detail page

В блоке `Apply now` присутствуют:

| Действие | URL |
|---|---|
| Apply with your email | `#magic-link` |
| Apply with Google | `/auth/google_oauth2` |
| Apply with LinkedIn | `/auth/linkedin` |
| Apply with Twitter | `/auth/twitter` |
| Apply with GitHub | `/auth/github` |
| Forgot account | `#magic-link` |

### Share / utility actions

Есть отдельный блок со ссылками:

| Action | URL pattern |
|---|---|
| Copy link | `javascript:void(0);` |
| Email share | `mailto:?subject=...&body=...` |
| LinkedIn share | `javascript:(function(){...})()` |
| WhatsApp share | `whatsapp://send?text=...` |
| Image preview | `/og_previews/job/...jpg?variant=square` |
| Report job | `/complaints/new?job_slug=...` |

### Tags и хлебные крошки

Внизу detail page есть набор `a[href^="/jobs/tag/"]`:

`Node.js`, `Microservices`, `GraphQL`, `TypeScript`, `NestJS`, `AWS`, `REST`, `Testing`, `Event-Driven Architecture`.

Breadcrumbs:

`Jobs > Programming > BC Tecnología > Back-end Developer (Node.js / AWS)`

### About company teaser

Внизу detail page есть блок:

| Элемент | Наблюдение |
|---|---|
| Heading | `About BC Tecnología` |
| Company link | `/companies/bctecnologia` |
| Short description | `Somos una consultora de TI con personal experto en diferentes áreas de tecnología.` |
| Follow link | `/companies/bctecnologia/follow_unfollow` |

### Previous / next navigation

Есть links:

| Action | URL |
|---|---|
| Previous job | `/jobs/backend-developer-node-js-aws-bc-tecnologia-remote/previous` |
| Next job | `/jobs/backend-developer-node-js-aws-bc-tecnologia-remote/next` |

### JSON-LD / structured data

На detail page в живой проверке **не было найдено** `script[type="application/ld+json"]`.
Это важно: парсер не должен рассчитывать на JSON-LD как на primary source.

### Полезные селекторы

| Что искать | Селектор / паттерн |
|---|---|
| Job title | `h1` |
| Company name | `a[href^="/companies/"]` в верхнем блоке |
| Apply CTA | `a[href$="/applications/new"]` |
| Section headings | `h3` с текстами `Funciones`, `Requisitos`, `Deseables`, `Beneficios` |
| Tag chips | `a[href^="/jobs/tag/"]` |
| Job ID | текст `GETONBRD Job ID:` |
| About company block | `h3` + `a[href^="/companies/"]` нижнего teaser-блока |
| Share links | `a[href^="mailto:"], a[href^="whatsapp://"], a[href*="linkedin"], a[href*="/og_previews/job/"]` |

## Company profile page

### Проверенная страница

`https://www.getonbrd.com/companies/bctecnologia`

### Верхняя структура

| Элемент | Наблюдение |
|---|---|
| Followers count | `1753 Followers` |
| Follow button | `Follow` |
| Company title | `BC Tecnología` в `h1` |
| Anchor nav | `About us`, `Open jobs` |
| Subtitle | `Somos una consultora de TI con personal experto en diferentes áreas de tecnología.` |
| CTA | `See jobs` ведет к `#jobs` |

### About us section

Это набор `p`-абзацев без JSON-LD:

| Наблюдение |
|---|
| Компания — consultora de Servicios IT |
| Есть описание портфеля услуг, outsourcing, selección de profesionales |
| Упоминаются agile teams, infrastructure technology, software development, business units |
| Есть список основных направлений бизнеса |

### Jobs section

На company page есть большой список открытых вакансий, сгруппированный по категориям:

| Категория | Наблюдение |
|---|---|
| Programming jobs | `Programming jobs (57)` |
| SysAdmin / DevOps / QA | `SysAdmin / DevOps / QA (...)` |
| Data Science / Analytics | `Data Science / Analytics (...)` |
| Product / Innovation / Agile | `Innovation & Agile jobs (...)` |
| Operations / Management | `Operations / Management jobs (6)` |
| Mobile Developer | `Mobile Developer jobs (3)` |
| Sales | `Sales jobs (4)` |
| Customer Support | `Customer Support jobs (4)` |
| Digital Marketing | `Digital Marketing jobs (1)` |

### Jobs card structure on company page

Карточки компактнее, чем на listing page:

| Поле | Наблюдение |
|---|---|
| Title | Сокращенный title |
| Modality | `Remote`, `Santiago (Hybrid)`, `Remoto`, `In-office` |
| Date | `March 20, 2026`, `13 de marzo de 2026`, etc. |
| CTA | `Apply` / `Postula` |

### Learn more

Есть блок `Learn more` с link на website:

`/companies/bctecnologia/website/bctecnologia`

### JSON-LD / structured data

На проверенной company page **не было найдено** JSON-LD.

### Полезные селекторы

| Что искать | Селектор / паттерн |
|---|---|
| Company title | `h1` |
| Followers count | top bar text рядом с `Followers` |
| Follow link | `a[href$="/follow_unfollow"]` |
| About anchor | `a[href="#about"]` |
| Jobs anchor | `a[href="#jobs"]` |
| Company website | `a[href*="/website/"]` |
| Job cards inside company | `a[href*="/jobs/"], a[href*="/empleos/"]` внутри секции jobs |

## Auth wall / apply flow / anti-bot

### Что доступно без логина

| Раздел | Доступ |
|---|---|
| Home | Да |
| Category listing | Да |
| Public job detail | Да |
| Company profile | Да |
| Public API `categories` | Да |
| Public API `companies` | Да |
| Public API `search/jobs` | Да, если передан query/remote/country_code/board_host и т.п. |

### Где стоит auth wall

| Путь | Поведение |
|---|---|
| `/jobs/.../applications/new` | Редирект на `/webpros/login` |
| `/companies/bctecnologia/api_settings` | Редирект на `/members/auth/login` |

### Экран `webpros/login`

| Поле / button | Наблюдение |
|---|---|
| Email sign in | `Sign in with email` |
| Google | `Sign in with Google` |
| LinkedIn | `Sign in with LinkedIn` |
| Twitter | `Sign in with Twitter` |
| GitHub | `Sign in with GitHub` |
| Privacy notice | `We protect your data` |

### Экран company login

| Поле | Наблюдение |
|---|---|
| Email | `textbox "Email"` |
| Password | `textbox "Password"` |
| Remember me | checkbox |
| Log in | button |

### Anti-bot / CSRF

| Факт | Наблюдение |
|---|---|
| CSRF meta | На страницах есть `meta[name="csrf-token"]` |
| Cookie banner | Есть обязательный cookie overlay |
| CAPTCHA | Не наблюдалась |
| Cloudflare challenge | Не наблюдался |
| Security headers | Не исследовались глубоко, но есть `cdn-cgi/rum` и telemetry scripts |

## API surface

### Документация

API docs живут в Scalar/OpenAPI на `/api-doc.html`, а полный YAML доступен по `/doc/openapi.yaml`.

### Базовые факты из docs

| Факт | Значение |
|---|---|
| API version | `0.1.0` |
| OpenAPI | `3.0.3` |
| Base URL | `https://www.getonbrd.com/api/v0/` |
| Sandbox | `https://sandbox.getonbrd.dev/api/v0/` |
| Locales | `en`, `es`, `pt` |
| Pagination | `page`, `per_page` |
| Expand | `expand[]`, nested expansion via dot notation |
| Date filtering | `from`, `to` as Unix epoch on some private endpoints |

### Public API endpoints, confirmed from OpenAPI

| Endpoint | Status / note |
|---|---|
| `GET /api/v0/categories` | 200, public |
| `GET /api/v0/categories/{category_id}/jobs` | public according to docs |
| `GET /api/v0/companies` | 200, public |
| `GET /api/v0/companies/{company_id}/jobs` | public according to docs |
| `GET /api/v0/companies/{id}` | public according to docs |
| `GET /api/v0/countries` | public |
| `GET /api/v0/headcounts` | public |
| `GET /api/v0/industries` | public |
| `GET /api/v0/insights/{id}` | public |
| `GET /api/v0/jobs` | live `401` in this session |
| `GET /api/v0/search/jobs` | public search, requires at least one filter |
| `GET /api/v0/modalities` | public |
| `GET /api/v0/perks` | public |
| `GET /api/v0/regions` | public |
| `GET /api/v0/seniorities` | public |
| `GET /api/v0/tags` | public |
| `GET /api/v0/tags/{tag_id}/jobs` | public |
| `GET /api/v0/webhook_events` | private, Bearer auth |
| `GET /api/v0/webhook_endpoints` | private, Bearer auth |

### Private API endpoints, confirmed from OpenAPI

| Endpoint | Purpose |
|---|---|
| `POST /api/v0/auth_tokens` | Issue professional JWT token |
| `GET /api/v0/applications` | List applications |
| `GET /api/v0/applications/{id}` | Retrieve application |
| `POST /api/v0/applications` | Create application |
| `PUT /api/v0/applications/{id}` | Update application |
| `GET /api/v0/jobs` | Job CRUD collection, but live unauth call returned `401` |
| `POST /api/v0/jobs/{job_id}/submit` | Submit job for moderation |
| `GET /api/v0/processes` | Hiring processes |
| `GET /api/v0/professionals` | Professional profiles in process |
| `GET /api/v0/matching_jobs` | Matching jobs for professionals |
| `DELETE/GET/POST /api/v0/board/professionals` | Board+ integration |

### Live API response samples

`GET /api/v0/search/jobs?query=node&page=1&per_page=1&lang=en` returned `200` and a job object with:

| Field | Example / note |
|---|---|
| `id` | `backend-developer-node-js-aws-bc-tecnologia-remote` |
| `type` | `job` |
| `title` | `Back-end Developer (Node.js / AWS)` |
| `description_headline` | `Requisitos` |
| `description` | HTML string |
| `projects` | HTML string |
| `functions_headline` / `functions` | HTML string |
| `benefits_headline` / `benefits` | HTML string |
| `desirable_headline` / `desirable` | HTML string |
| `remote` | `true` |
| `remote_modality` | `fully_remote` |
| `countries` | `["Remote"]` |
| `lang` | `lang_not_specified` |
| `category_name` | `Programming` |
| `perks` | `["remote_full", "computer_provided"]` |
| `min_salary` / `max_salary` | `null` in this sample |
| `published_at` | Unix timestamp |
| `applications_count` | `96` |
| `location_regions`, `location_tenants`, `location_cities` | arrays / objects |
| `modality`, `seniority` | references |
| `tags` | tag id list |
| `company` | company reference |
| `links.public_url` | public job URL |

`GET /api/v0/companies?page=1&per_page=1&lang=en` returned `200` and a company object with:

| Field | Example / note |
|---|---|
| `id` | `lifestyle-and-wellness` |
| `type` | `company` |
| `name` | company name |
| `description` | nullable |
| `long_description` | string |
| `web` | company website |
| `country` | ISO country code |
| `response_time_in_days` | `{min,max}` |
| `logo` | nullable object |

### Important inconsistency

OpenAPI docs talk about public jobs, but live unauthenticated `GET /api/v0/jobs?page=1&per_page=1&lang=en` returned:

```json
{"message":"(Status 401) Unauthorized access.","code":"unauthorized"}
```

So for automation we should use:

1. `search/jobs` for public search and discovery.
2. `categories`, `companies`, `tags`, `countries`, `seniorities`, etc. for metadata.
3. Job detail DOM for final rendered content.
4. Private API only after authentication.

## Stable selectors and fallback selectors

### Home

| Purpose | Primary selector | Fallback |
|---|---|---|
| Search box | `input#search_term` | `input[type="search"]` |
| Hero title | `h1` | first `h1` on page |
| Featured / category links | `a[href^="/jobs/"], a[href^="/empleos/"]` | text-based link matching |

### Listing

| Purpose | Primary selector | Fallback |
|---|---|---|
| Job card root | `a[href*="/jobs/"], a[href*="/empleos/"]` under main list | link text + child heading |
| Title | `h3, h4` inside card | first strong text in card |
| Company | `strong` inside card | adjacent text block before location |
| Location | text around `` | aria/text match for `Remote`, `Hybrid`, `In-office` |
| Salary | text around `` | regex on currency / month / `USD` / `$/mes` |
| Date | last text node in card | date regex |

### Job detail

| Purpose | Primary selector | Fallback |
|---|---|---|
| Job title | `h1` | `meta[property="og:title"]` |
| Company name | `a[href^="/companies/"]` in header | `h3` header link |
| Apply now | `a[href$="/applications/new"]` | `a[href*="/applications/new"]` |
| Functions / Requirements / Benefits | `h3` headings `Funciones`, `Requisitos`, `Deseables`, `Beneficios` | text anchors |
| Tags | `a[href^="/jobs/tag/"]` | tag chips by text |
| Job ID | text `GETONBRD Job ID:` | none |

### Company profile

| Purpose | Primary selector | Fallback |
|---|---|---|
| Company title | `h1` | top heading |
| Followers count | top count near `Followers` | none |
| Follow button | `a[href$="/follow_unfollow"]` | button text `Follow` |
| About section | `#about` anchor + paragraphs | `h4` `About us` |
| Jobs list | `#jobs` anchor + `a[href*="/jobs/"]` | category headings + link groups |
| Website link | `a[href*="/website/"]` | text `Website` |

### Apply/login

| Purpose | Primary selector | Fallback |
|---|---|---|
| Email sign-in | `a[href="#magic-link"]` or `input` on auth screen | text match `Sign in with email` |
| Social sign-in | `a[href*="/auth/google_oauth2"], a[href*="/auth/linkedin"], a[href*="/auth/twitter"], a[href*="/auth/github"]` | visible button text |
| Company login email/password | `textbox "Email"`, `textbox "Password"` | `input[type="email"]`, `input[type="password"]` |

## Extraction mapping table

| Field | Primary source | Fallback |
|---|---|---|
| `job_id` | `search/jobs` API `id` | detail page URL slug |
| `job_url` | API `links.public_url` | detail page root link href |
| `title` | `search/jobs` API `attributes.title` | detail page `h1` |
| `company_name` | `search/jobs` API `company.data.id` + `companies` API `name` | detail page header/company teaser |
| `company_url` | `companies` API or detail page company link | company teaser link |
| `location` | `search/jobs` API `countries`, `location_cities`, `remote_modality` | detail page `h2` line |
| `salary_min/max` | `search/jobs` API `min_salary`, `max_salary` | listing card salary text |
| `published_at` | `search/jobs` API `published_at` | listing card date text |
| `applications_count` | `search/jobs` API `applications_count` | detail page `95 applications` |
| `description_headline` | `search/jobs` API `description_headline` | detail page first section title |
| `description_html` | `search/jobs` API `description` | detail page `Funciones`, `Requisitos`, `Deseables`, `Beneficios` HTML/text |
| `functions_html` | `search/jobs` API `functions` | detail page `Funciones` section |
| `benefits_html` | `search/jobs` API `benefits` | detail page `Beneficios` section |
| `desirable_html` | `search/jobs` API `desirable` | detail page `Deseables` section |
| `tags` | `search/jobs` API `tags` + `tags/{tag_id}` if needed | detail page tag chips |
| `perks` | `search/jobs` API `perks` | icons / perk labels in listing and detail |
| `apply_url` | detail page `a[href$="/applications/new"]` | auth screen action links |
| `company_about` | company profile page `About us` paragraphs | detail page company teaser |
| `company_followers` | company profile top bar | none |
| `company_web` | `companies` API `web` | company profile learn more link |

## Parser strategy

### Pass 1

Use `search/jobs` as the **main discovery API**. It gives public job data with the exact fields we need for indexing, filtering and quick sync.

### Pass 2

For every job found in pass 1, visit the **detail page** and extract:

1. Title and exact wording.
2. Full description blocks.
3. Apply URL and auth behavior.
4. Tag chips.
5. Company teaser / company page link.

### Pass 3

For every company encountered, call the **company profile page** and/or the `companies` API for:

1. About text.
2. Web / social links.
3. Follower count.
4. Company-specific job listings.

### Pass 4

Use API docs only as a **schema reference**, not as a guarantee that every endpoint is open. The live test clearly showed that some endpoints advertised in docs still answer `401` without auth.

## Verified URLs

`https://www.getonbrd.com/`
`https://www.getonbrd.com/jobs/programming`
`https://www.getonbrd.com/jobs/programming/backend-developer-node-js-aws-bc-tecnologia-remote`
`https://www.getonbrd.com/jobs/programming/backend-developer-node-js-aws-bc-tecnologia-remote/applications/new`
`https://www.getonbrd.com/companies/bctecnologia`
`https://www.getonbrd.com/companies/bctecnologia/api_settings`
`https://www.getonbrd.com/webpros/login`
`https://www.getonbrd.com/members/auth/login`
`https://www.getonbrd.com/api-doc.html`
`https://www.getonbrd.com/doc/openapi.yaml`
`https://www.getonbrd.com/api/v0/search/jobs?query=node&page=1&per_page=1&lang=en`
`https://www.getonbrd.com/api/v0/categories?page=1&per_page=1&lang=en`
`https://www.getonbrd.com/api/v0/companies?page=1&per_page=1&lang=en`
`https://www.getonbrd.com/api/v0/jobs?page=1&per_page=1&lang=en`
