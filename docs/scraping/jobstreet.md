# JobStreet ID Parser Report

Дата скана: 2026-03-21
Источник: `https://id.jobstreet.com/en`

## Короткий вывод

JobStreet для Индонезии выглядит как **React/Apollo/GraphQL**-приложение поверх SEEK-экосистемы. Публичная часть хорошо парсится по устойчивым DOM-якорям, но **apply flow почти всегда уводит в SEEK login wall**, а персонализированные данные и некоторые действия завязаны на авторизацию.

Для парсинга здесь лучше строить схему из трех слоев: **DOM**, **GraphQL/Apollo cache**, **SEO/structured data**. Важно не полагаться только на HTML, потому что карточки, фильтры и детали вакансий частично живут в GraphQL и в React hydration state.

## Типы страниц

### Home

Главная страница `https://id.jobstreet.com/en` содержит:

- верхнюю навигацию JobStreet
- поисковую форму `What / Where`
- блоки quick search
- блок dashboard для гостя с предложением войти
- блок компаний с каруселью работодателей
- footer с job seeker / employer / about / contact links

### Listing / Search

Рабочий listing после поиска выглядит так:

- `https://id.jobstreet.com/software-engineer-jobs/in-Jakarta`

На listing есть:

- заголовок с количеством вакансий
- панель refinements
- блок related searches
- список job cards
- пагинация
- email alert form
- правый panel для selected job, который по умолчанию пустой

### Detail

Детальная вакансия открывается на том же маршруте listing через `jobId`, например:

- `https://id.jobstreet.com/software-engineer-jobs/in-Jakarta?jobId=90589797&type=standard`

На detail-режиме видны:

- заголовок вакансии
- компания
- location / work arrangement
- classification
- salary
- posted time
- quick apply
- save
- длинное описание
- employer questions
- featured jobs

### Company / employer jobs

Company page в доступной части выглядит как jobs listing для компании:

- `https://id.jobstreet.com/Cavalry-Collective-jobs/at-this-company`

Это не отдельный rich profile page с полноценным about/culture блоком, а скорее **company-specific job listing**.

### Apply / Auth

Quick apply и некоторые действия уходят на SEEK auth:

- `https://id.jobstreet.com/job/90589797/apply?sol=...`
- редирект на `https://login.seek.com/login?...`

Без логина открывается **Candidate Sign In - SEEK** с social login и email-code flow.

## DOM Структура

### Home

Ключевые якоря:

- `button#searchButton` для submit search
- `combobox[aria-label="What"]`
- `combobox[aria-label="Where"]`
- навигация в header: `Job search`, `People search`, `Career advice`, `Companies`, `Community`

По home хорошо видно, что искать стоит по `aria`-ролям и стабильным `id`, а не по сгенерированным CSS-классам.

### Listing

Ключевые контейнеры:

- `navigation[aria-label="Refine your search"]`
- `region[aria-label="Search Results"]`
- `navigation[aria-label="Pagination of results"]`
- `article[aria-label="..."]` для каждой вакансии

Что лежит в карточке:

- title в `h3` с внутренним `a`
- company link
- listing age: `Listed four days ago`
- work type: `This is a Full time job`
- location
- remote/hybrid marker
- salary
- one-line summary
- subClassification / classification
- actions: `More`, `Sign in to save this job`

В карточках устойчиво повторяются следующие формы:

- `a[href^="/job/"]`
- `a[href*="origin=cardTitle"]`
- `a[href*="/<Company>-jobs"]`

### Detail

Ключевые якоря:

- `h1` для job title
- company button / company link
- `a[href^="/job/<id>/apply"]` для quick apply
- `button` save
- section headings: `About the Role`, `Responsibilities`, `Required Qualifications`, `Nice to Have`, `Company information`, `Employer questions`, `Report this job advert`, `Featured jobs`

На detail-странице описание и требования хранятся обычным текстом и списками:

- paragraph blocks
- `ul/li` lists

Это удобно для extraction, потому что структура довольно стабильна и не размазана по спанам.

### Company jobs page

На company page структура похожа на listing:

- header count: `2 Cavalry Collective jobs in Indonesia`
- search inputs сверху остаются теми же
- listing карточки идут в `article`
- справа также есть пустой details panel

## Фильтры и пагинация

### Search form

В home и listing форма поиска строится вокруг:

- `What` keyword combobox
- `Where` location combobox
- submit button

URL-паттерн после поиска:

- `/{keyword}-jobs/in-{Location}`

Пример:

- `software-engineer-jobs/in-Jakarta`

### Refinements

На listing видны фильтры:

- work type
- work arrangement
- minimum salary
- maximum salary
- date listed

На текущем снимке фильтры выглядели как раскрываемые кнопки с короткой текущей сводкой, например:

- `All work types`
- `All remote options`
- `paying Rp 0`
- `to Rp 100M+`
- `listed any time`

### Pagination

Пагинация строится обычным query param:

- `?page=2`
- `?page=3`

На listing есть:

- `Prev`
- page numbers
- `Next`

Это хороший сигнал: страницы можно краулить без JS-инференса только по URL.

## URL Patterns

Проверенные паттерны:

- `https://id.jobstreet.com/en`
- `https://id.jobstreet.com/{keyword}-jobs/in-{Location}`
- `https://id.jobstreet.com/{keyword}-jobs/in-{Location}?page=2`
- `https://id.jobstreet.com/{keyword}-jobs/in-{Location}?jobId=90589797&type=standard`
- `https://id.jobstreet.com/job/90589797/apply?sol=...`
- `https://id.jobstreet.com/{Company}-jobs/at-this-company`
- `https://id.jobstreet.com/oauth/login?returnUrl=...`

Для парсера это удобно тем, что:

- listing и detail живут на одном route, меняется только `jobId`
- company jobs page отдельный route
- apply всегда уводит на login seek

## JSON-LD и embedded state

### Structured data

На проверенных страницах я увидел только один `application/ld+json`, и он содержал:

- `WebSite`
- `SearchAction`

То есть на этой выборке **JobPosting JSON-LD не был виден как основной source**. Для извлечения вакансий надо опираться на DOM и GraphQL, а не ждать job schema в HTML.

### Hydration / runtime state

В `window` есть важные объекты:

- `__staticRouterHydrationData`
- `__LOADABLE_LOADED_CHUNKS__`
- `__reactRouterVersion`
- `__APOLLO_CLIENT__`
- `__tealium_twc_switch`
- `seekTiq`
- `__G_ID_CLIENT__`
- `__googleSignInScript__`
- `__SEGMENT_INSPECTOR__`

Для JobStreet это сильный сигнал, что parser должен учитывать:

- SSR shell
- React Router
- Apollo cache
- analytics side effects

### Apollo cache

`window.__APOLLO_CLIENT__.cache.extract()` содержит ключи:

- `ROOT_QUERY`
- `JobSearchV6ClassificationDetail:...`
- `JobSearchV6Data:{id:...}`

Это важный скрытый слой данных. Для bulk extraction здесь полезно смотреть не только DOM, но и Apollo cache, если нужно строить более надёжный scraper.

## Network / XHR

Ключевой endpoint:

- `POST https://id.jobstreet.com/graphql`

Сетевая активность показывает, что JobStreet активно тянет данные через GraphQL, а не через статические HTML endpoints.

Дополнительные трекеры и аналитика:

- Branch
- Segment
- Tealium
- Clarity
- Google Analytics
- DoubleClick / Google Ads
- TikTok Pixel
- Hotjar
- Qualtrics
- Facebook Pixel
- Bing
- Google conversion endpoints

Для парсера это шум, но полезно для понимания, что:

- сеть тяжёлая
- DOM строится не только из HTML
- часть контента может обновляться client-side

## Auth / Anti-bot

### Apply gate

Quick apply ведёт в:

- `id.jobstreet.com/job/.../apply`
- затем редирект на `login.seek.com/login`

На логине доступны:

- `Continue with Google`
- `Continue with Facebook`
- `Continue with Apple`
- email sign-in code

### Guest ограничения

Без логина видны:

- вакансии
- поиск
- company jobs
- карьерные советы

Но скрыты или ограничены:

- saved searches
- saved jobs
- job applications
- application flow
- save actions
- detail insights

### Anti-bot / warnings

Во время скана были консольные ошибки от рекламных и трекинговых скриптов, но явного CAPTCHA wall на публичных страницах не было. Главный барьер здесь именно **auth wall**, а не жесткий bot challenge.

## Primary Selectors

### Home

- `button#searchButton`
- `combobox[aria-label="What"]`
- `combobox[aria-label="Where"]`
- `link[href="/en"]`
- `link[href="/companies"]`

### Listing

- `navigation[aria-label="Refine your search"]`
- `region[aria-label="Search Results"]`
- `navigation[aria-label="Pagination of results"]`
- `article[aria-label]`
- `a[href^="/job/"]`
- `a[href*="origin=cardTitle"]`
- `a[href*="/-jobs"]`

### Detail

- `h1`
- `a[href^="/job/90589797/apply"]`
- `button[aria-label*="Save"]`
- section headings `About the Role`, `Responsibilities`, `Required Qualifications`, `Nice to Have`

### Company

- `article[aria-label]`
- `a[href^="/job/"]`
- `a[href="/Cavalry-Collective-jobs"]`

### Apply / Login

- `button[aria-label="Continue with Google"]`
- `button[aria-label="Continue with Facebook"]`
- `button[aria-label="Continue with Apple"]`
- `textbox[aria-label="Email address"]`
- `button:has-text("Email me a sign in code")`

## Fallback Selectors

Если `aria-label` меняется, fallback лучше строить по:

- href patterns
- visible headings
- text fragments
- route params

Например:

- job card title by `article` + inner `h3 a`
- company by `article` + `a[href*="-jobs"]`
- apply by `/apply?sol=`

## Field Mapping Table

| Field | Primary source | Fallback |
| --- | --- | --- |
| `title` | `h1` on detail, `h3 a` in listing card | article `aria-label` |
| `company_name` | company button/link on detail, company link in card | route slug from `/...-jobs` |
| `location` | detail location chip, listing location block | URL slug `/in-{Location}` |
| `work_arrangement` | `(Remote)`, `(Hybrid)` chips | listing text |
| `work_type` | `Full time job` text | filter state |
| `salary_min/max` | salary chip text | listing salary label |
| `posted_at` | `Posted 4d ago`, `Listed four days ago` | listing age on card |
| `description` | `About the Role` section | listing summary |
| `responsibilities` | `Responsibilities` list | none |
| `requirements` | `Required Qualifications` list | none |
| `nice_to_have` | `Nice to Have` list | none |
| `apply_url` | `a[href^="/job/<id>/apply"]` | login redirect returnUrl |
| `company_jobs_url` | `a[href="/<Company>-jobs"]` | derived company slug |
| `job_id` | `jobId=90589797` in URL | `JobSearchV6Data` Apollo cache |
| `classification` | chips / text in detail and card | Apollo cache / GraphQL |

## 2-Pass Parser Strategy

### Pass 1: URL and card harvest

Сначала собирать:

- listing URLs
- job IDs
- company routes
- title/company/location/salary/age from cards

Это даёт массовый, дешёвый проход.

### Pass 2: Detail enrichment

Потом для выбранных вакансий добирать:

- full description
- responsibilities
- required qualifications
- nice to have
- employer questions
- apply/auth gate
- company jobs context

Если нужен максимально надёжный парсер, второй проход стоит дополнить чтением Apollo cache и GraphQL response, а не только DOM.

## Проверенные URL

- `https://id.jobstreet.com/en`
- `https://id.jobstreet.com/software-engineer-jobs/in-Jakarta`
- `https://id.jobstreet.com/software-engineer-jobs/in-Jakarta?jobId=90589797&type=standard`
- `https://id.jobstreet.com/job/90589797/apply?sol=731e455c2319e32d6f069f9b335474e0af72c851`
- `https://login.seek.com/login?...`
- `https://id.jobstreet.com/Cavalry-Collective-jobs/at-this-company`
