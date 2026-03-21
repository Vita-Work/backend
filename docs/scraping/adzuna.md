# Adzuna DOM / HTML report

Источник проверки: `https://www.adzuna.com/`

Цель отчета: описать **реальную DOM-структуру** Adzuna так, чтобы по ней можно было собрать надежный парсер вакансий, company pages, detail pages и базовые apply-сигналы.

## Краткий вывод

Adzuna хорошо подходит для парсинга, потому что основные страницы **server-side rendered**, у карточек есть устойчивые semantic blocks, а на detail page присутствует **`JobPosting` JSON-LD** с богатым набором полей. При этом сайт очень сильно насыщен рекламой и трекингом, поэтому для парсера важно жестко отделять **job content** от **ads / trackers / cookie UI**.

Самое важное для извлечения данных:
- на listing page искать `article`-карточки вакансий
- на detail page читать `script[type="application/ld+json"]` с `JobPosting`
- company pages использовать как отдельный listing layer по employer
- pagination и фильтры брать по `href`-паттернам, а не по визуальному тексту

## Карта страниц

| Тип страницы | Пример URL | Что брать |
|---|---|---|
| Home | `https://www.adzuna.com/` | Search form, country selector, product CTAs, recruiter API link |
| Search / listing | `https://www.adzuna.com/search?q=software%20engineer&w=New%20York%2C%20NY` | Job cards, filters, pagination, search state, related searches |
| Detail | `https://www.adzuna.com/details/5616455592?...` | Title, employer, location, JSON-LD `JobPosting`, description, similar jobs |
| Company page | `https://www.adzuna.com/company/robert-half` | Company-scoped listing, average salary, pagination, salary page link |
| Company salary page | `https://www.adzuna.com/robert-half/salary` | Salary landing page for the employer |
| Employer / recruiter entry | `https://www.adzuna.com/hire/` | Recruiter funnel, not job data |
| API entry | `https://developer.adzuna.com` | Public recruiter API docs |

## Home page

### Верхняя панель
На главной странице есть:
- логотип Adzuna
- ссылки `Login`, `Register`, `Employers`
- форма поиска
- блоки маркетинга и product CTAs
- footer с `Browse jobs`, `Blog`, `ValueMyResume`, `ApplyIQ`, `AI Tools`, `Post a job`, `API`

### Search form
На главной видна простая форма поиска:
- поле `What?` с placeholder `job, company, title`
- поле `Where?` с placeholder `city, state or ZIP code`
- кнопка `Search`
- ссылка `Advanced`

Для парсера это удобно, потому что поля имеют стабильные **role / placeholder** признаки.

### Product blocks
На home также есть маркетинговые блоки:
- `ValueMyResume`
- `ApplyIQ`
- `Find jobs on the go`
- app store / google play badges

Это не job data, но важно понимать, что Adzuna продает рядом несколько смежных продуктов. Для скрапера эти блоки нужно игнорировать.

## Search / listing page

Проверенный URL:
`https://www.adzuna.com/search?q=software%20engineer&w=New%20York%2C%20NY`

### Общая структура
Listing page рендерится как:
- верхняя search bar
- заголовок результата
- блок average salary
- email alert form
- фильтры
- main results list
- related searches
- pagination
- footer

### Search state
На странице присутствуют глобальные объекты:
- `window.az_search_data`
- `window.az_wj_data`
- `PATH`
- `afs_data`

Это полезно как backup-источник состояния запроса. В частности:
- `az_search_data.count` содержит число результатов
- `az_search_data.what` и `az_search_data.where` содержат query и location
- `az_search_data.acq_where` содержит SEO slug локации
- `az_search_data.location_level` помогает понять гранулярность location
- `az_search_data.serialised` хранит сериализованный command payload
- `az_wj_data.search.where` и `az_wj_data.search.what` дублируют query
- `PATH` содержит `host`, `host_sans_jobs`, `asset_version`, `country`, `stage`

### Filters
Видимые фильтры на listing page:
- `Sort by`
- `Date posted`
- `Salary`
- `Remote`
- `Location`
- `Category`
- `Company`
- `Employment type`
- `Hours`

В интерфейсе они выглядят как сворачиваемые sections с `a[href="#"]` и заголовками второго уровня. Для устойчивого парсинга лучше не опираться на классы, а брать:
- текст секции
- role / heading
- параметры URL после открытия фильтра

### Search radius combobox
Рядом с заголовком и average salary есть combobox с радиусом поиска:
- `only in`
- `within 5 miles`
- `within 10 miles`
- `within 15 miles`
- `within 25 miles`
- `within 50 miles`
- `within 100 miles`

Это хороший сигнал, что location filter меняется через controlled UI, а не через просто статический HTML.

### Job cards
Карточки вакансий на listing page рендерятся через `article`.

У каждой карточки обычно есть:
- title link
- company link
- location text
- salary text или estimate
- tags / badges
- description snippet
- `More details ❯`
- favorite button

Пример наблюдаемой структуры:
- `article`
- `h2 > a[href*="/land/ad/"]` или `a[href*="/details/"]`
- `a[href*="/company/<slug>"]`
- location text node
- salary / estimate block
- badge block
- description snippet block
- `More details ❯` link

### Badges
На карточках встречаются:
- `TOP MATCH`
- `CLOSING SOON`
- `NEW`
- `REMOTE`
- `ABOVE AVERAGE SALARY`

Эти badges удобны как отдельные structured flags, но не надо парсить их как часть title.

### Salary on cards
Salary может отображаться в нескольких форматах:
- `ESTIMATED: $131,201 per year`
- `$200,000-$250000`
- `120000-180000 per year`
- `$150k - $200k`
- `20USD - 22USD PER HOUR`
- `15USD PER HOUR`

То есть salary нужно нормализовать отдельно, а не пытаться брать одной regex-строкой. На listing page это часто **estimate** или **hourly rate**, а не финальный годовой salary.

### Related searches
Под listing появляется блок `Related searches` с дополнительными поисковыми ссылками. Для парсера это вторичный источник, но он полезен как генератор похожих query seeds.

### Pagination
На listing page pagination строится ссылками вида:
- `https://www.adzuna.com/search?loc=153871&q=software%20engineer&p=2`
- `https://www.adzuna.com/search?loc=153871&q=software%20engineer&page=2`

Наблюдение: у Adzuna встречаются **два паттерна** pagination:
- numbered pages используют `p=2`, `p=3`, ...
- `next ❯` может использовать `page=2`

Это важно: для краулера не надо жестко завязываться только на один параметр.

### Listing selectors
Primary selectors:
- `main article`
- `h2 a[href*="/details/"]`
- `a[href*="/company/"]`
- `button[aria-label*="favorite"]` или кнопка с текстом `Add to favorite jobs`
- text nodes containing salary / badges

Fallback selectors:
- `article`
- link text containing `More details ❯`
- link text containing `ESTIMATED:`
- text text with company name and location grouped под одной карточкой

## Detail page

Проверенный URL:
`https://www.adzuna.com/details/5616455592?se=uvhWgQIl8RG9qIDBX2ocxA&title=Software_Engineer&v=AF30EFC71BCC6E404F780AB8C7C04D06EF15FF3B`

### Структура detail page
На detail page видны:
- `h1` с названием вакансии
- company link
- location text
- region availability message
- description text
- `Show full description`
- ad iframe
- `Similar jobs`
- email alert form

### Region gating
На проверенном detail page отображается сообщение:
- `Sorry, this job is not available in your region`

Это важный сигнал. Даже если job detail доступен визуально и JSON-LD присутствует, пользователь может видеть региональное ограничение. Для парсера это значит:
- контент вакансии можно извлечь
- но apply flow может быть ограничен или отсутствовать
- для production нужно отдельно обрабатывать региональные блокировки

### Detail page fields in visible DOM
На detail page видны:
- `title`
- `company`
- `location`
- long `description`
- employer/company informational text
- legal notice
- link to Robert Half app
- statement about work authorization

### JSON-LD on detail page
На detail page присутствуют два JSON-LD блока:
- `BreadcrumbList`
- `JobPosting`

`JobPosting` содержит следующие полезные поля:
- `title`
- `@type`
- `directApply`
- `jobLocation`
- `hiringOrganization`
- `jobLocationType`
- `jobImmediateStart`
- `employmentType`
- `datePosted`
- `description`
- `validThrough`
- `industry`
- `@context`

### Important detail from JSON-LD
В наблюдаемом примере:
- `directApply` = `False`
- `jobLocation.addressLocality` = `Grand Central, NY`
- `jobLocation.addressRegion` = `NY`
- `jobLocation.addressCountry` = `US`
- `hiringOrganization.name` = `Robert Half`
- `hiringOrganization.sameAs` = company page URL
- `employmentType` = `FULL_TIME`
- `datePosted` and `validThrough` are present

### Description source of truth
Описание вакансии лучше брать из `JobPosting.description`, потому что там уже есть full HTML-ish text with `<br />` markers. В DOM текст виден как long plain text paragraphs. На detail page это самый надежный источник описания.

### Similar jobs block
Внизу есть блок `Similar jobs`, где каждая похожая вакансия имеет:
- title link
- salary / estimate text
- company name
- location

Это полезный fallback для загрузки дополнительных вакансий по теме, но не нужно путать его с основной выдачей.

### Ads / sponsored content on detail
На detail page есть рекламный iframe с Google Ads и несколько sponsored blocks. Их нужно исключать из job parsing.

### Detail selectors
Primary selectors:
- `h1`
- `script[type="application/ld+json"]` и поиск объекта `@type: JobPosting`
- `a[href*="/company/"]`
- `main` / `body` text blocks for description
- `h2:has-text("Similar jobs")`

Fallback selectors:
- body text sections around `Description`
- link text `Show full description`
- `similar jobs` block as a separate data source

## Company page

Проверенный URL:
`https://www.adzuna.com/company/robert-half`

### Что это за page type
Adzuna company page выглядит не как profile card, а как **company-scoped listing**:
- заголовок `Robert Half Jobs`
- email alert form
- same top search bar
- average salary
- filters
- results list scoped to this employer
- link to company salary page

### Company page fields
На page видны:
- employer name
- total jobs count for that employer
- average salary for employer-scope results
- pagination
- company salary page link
- result cards with the same structure as search page

### Company-specific links
Видны дополнительные ссылки:
- `Robert Half salaries`
- `https://www.adzuna.com/robert-half/salary`

### Company page selectors
Primary selectors:
- `h1` or `h2` with text `Robert Half Jobs`
- `main article`
- `a[href*="/details/"]`
- `a[href*="/salary"]`

Fallback selectors:
- body text `Jobs in US at Robert Half`
- pagination links under the employer scope

### Company/apply interpretation
На Adzuna company page нет отдельного rich employer profile, как в LinkedIn. Это скорее **filtered search view**. Поэтому для company extraction надо считать company page частью listing layer, а не отдельной profile schema.

## Apply flow

### Что есть вместо обычного apply button
На наблюдаемом Adzuna job detail нет стандартной кнопки `Apply` внутри самой вакансии. Вместо этого видны:
- `More details ❯` на listing
- `Show full description` на detail
- `ApplyIQ` как product CTA по всему сайту
- `Create alert` email alert form

### directApply
В `JobPosting` JSON-LD для наблюдаемой вакансии:
- `directApply = False`

Это означает, что Adzuna здесь выступает как **job aggregator**, а не как direct-apply destination. Для скрапера это важный сигнал: поле `apply_url` может отсутствовать, и нужно использовать внешний employer link only if present elsewhere.

### Practical apply handling
Для нормализации job data можно использовать такие правила:
- если есть external employer apply URL, сохранять его отдельно
- если `directApply` = `False`, помечать `apply_mode = external_or_missing`
- если на странице нет применимого CTA, не пытаться синтезировать apply URL из `details` URL

## Embedded state and scripts

### Search page state
На listing page найдено:
- `window.az_search_data`
- `window.az_wj_data`
- `PATH`
- `afs_data`
- `window.uetq`
- ad / tracking initialization blocks

### Detail page state
На detail page найдено:
- `window.az_details`
- `afs_data`
- `PATH`
- search/ad tracking initialization blocks
- two JSON-LD blobs

### What useful fields live in `window.az_details`
На detail page `window.az_details` содержит:
- `reply_to_ad_details`
- `location_name`
- `query_info`
- additional serialised search / ad info

Это можно использовать как fallback для восстановления query context или для debug, но не как primary job source.

### What useful fields live in `window.az_search_data`
На search page `window.az_search_data` содержит:
- `count`
- `what`
- `where`
- `acq_where`
- `location_level`
- `serialised`

Это полезно для валидации запроса и для canonical SEO slugs.

### Scripts and tech stack signals
Видны скрипты и внешние зависимости:
- Google Tag Manager / gtag
- Google Ads / Adsense search
- Bing tracking
- LinkedIn Insight
- Facebook Pixel
- TikTok Pixel
- FullStory
- `unpkg.com/react@18.3.1/umd/react.production.min.js`

Это говорит о том, что сайт гибридный: SSR + client-side enhancement + ad/search modules.

## Network calls and external services

На страницах Adzuna в сети заметны в основном trackers, ad feeds и analytics, а не job API.

### Observed external calls
- Google `ccm/collect`
- Google `g/collect`
- Google Ads conversion endpoints
- Google `pagead/form-data`
- LinkedIn pixel attribution
- Facebook signals / fbevents
- Bing `bat.js`
- TikTok pixel
- Creative CDN tags
- FullStory script

### Scraper relevance
Эти вызовы не являются job data source. Их лучше игнорировать в scraper pipeline, кроме случаев отладки load issues.

### No public job API observed on the public pages
На проверенных публичных pages не было видно открытого jobs API, который бы удобно отдавал vacancy feed напрямую в браузерном DOM. Основной data source — это HTML + JSON-LD + embedded JS state.

## Auth and anti-bot

### Auth wall
На публичных страницах Adzuna login/register links присутствуют, но без обязательного входа для просмотра вакансий.

### Cookie consent
При работе с page всплывает cookie dialog:
- `Accept all`
- `Decline all`
- category checkboxes
- `Show details`
- `Close`

Для автоматизации это значит, что первый шаг краулера должен либо принимать, либо отклонять cookies, чтобы не мешать работе селекторов.

### Region gating
Главный ограничитель здесь не CAPTCHA, а **region availability**.

На наблюдаемой detail page вакансия показывала message:
- `Sorry, this job is not available in your region`

### Anti-bot signals
Я не увидел явного Cloudflare challenge в публичном DOM. Вместо этого есть:
- cookie consent flow
- heavy tracker stack
- ad iframes
- region-based availability messages

Для scraper-resilience это значит, что главная проблема не бот-защита, а **нестабильный рекламный шум и regional availability**.

## What to ignore

При парсинге игнорировать:
- cookie dialog
- ad iframe blocks
- Google Ads sponsored blocks
- Tracker script tags
- marketing CTAs
- app store badges
- footer legal navigation
- login/register buttons

## Primary selectors

### Home
- `input[placeholder="job, company, title"]`
- `input[placeholder="city, state or ZIP code"]`
- `button:has-text("Search")`
- `a[href="https://www.adzuna.com/advanced-search"]`

### Search / listing
- `main article`
- `h2 a[href*="/details/"]`
- `a[href*="/company/"]`
- `a[href*="/land/ad/"]`
- text nodes containing salary
- badges in card text
- `a:has-text("More details ❯")`

### Detail
- `h1`
- `script[type="application/ld+json"]`
- `a[href*="/company/"]`
- `a:has-text("Show full description")`
- `h2:has-text("Similar jobs")`

### Company
- `h1:has-text("Jobs")`
- `main article`
- `a[href*="/details/"]`
- `a[href*="/salary"]`

## Fallback selectors

### Home
- text `What?`
- text `Where?`
- footer link `API`

### Search / listing
- `article`
- `a[href*="/details/"]`
- `a[href*="/company/"]`
- text `ESTIMATED:`
- text `TOP MATCH`
- text `CLOSING SOON`
- text `NEW`
- text `REMOTE`

### Detail
- body text around `Description`
- body text around `Sorry, this job is not available in your region`
- `window.az_details`
- JSON-LD `JobPosting`

### Company
- body text `Jobs in US at <company>`
- body text with company job count
- pagination links under company scope

## Field mapping table

| Field | Primary source | Fallback source | Notes |
|---|---|---|---|
| `title` | `h1` on detail / `h2 a` on listing | body text / breadcrumb | Detail title is the canonical one |
| `company_name` | company link text / `hiringOrganization.name` | card company text | Company page slug also helps |
| `company_url` | `/company/<slug>` / `hiringOrganization.sameAs` | card company link | Strongly stable |
| `location_text` | listing card location text | `jobLocation.addressLocality` | Normalize separately |
| `location_city` | `jobLocation.addressLocality` | listing card location text | May include metro-style location |
| `location_region` | `jobLocation.addressRegion` | listing card location text | `NY`, `TX`, etc. |
| `postal_code` | `jobLocation.address.postalCode` | none | Only where present |
| `salary_text` | listing card salary text | similar jobs block / company page cards | Often estimate/hourly, not structured salary |
| `salary_amount` | parsed from salary text | none | Needs normalization per format |
| `salary_type` | parsed from salary text | none | `annual`, `hourly`, `estimate` |
| `date_posted` | `JobPosting.datePosted` | none | Detail page JSON-LD |
| `valid_through` | `JobPosting.validThrough` | none | Detail page JSON-LD |
| `description` | `JobPosting.description` | visible detail body text | Use JSON-LD as primary |
| `industry` | `JobPosting.industry` | none | Present in example |
| `employment_type` | `JobPosting.employmentType` | listing card text if exposed | Example: `FULL_TIME` |
| `direct_apply` | `JobPosting.directApply` | none | Example: `False` |
| `job_url` | detail URL | listing link URL | Canonical job URL |
| `apply_url` | external employer link if exposed | none / missing | Often absent on Adzuna detail |
| `is_region_available` | region message on detail | none | Important gating flag |
| `badges` | listing card badges text | none | `TOP MATCH`, `CLOSING SOON`, etc. |
| `result_count` | listing heading / `az_search_data.count` | body heading | Useful for crawl stats |

## 2-pass parser strategy

### Pass 1: Fast discovery
Use search/listing pages to collect:
- job URLs
- title
- company
- short location
- salary text or estimate
- badges
- pagination URLs
- search query state

Recommended primary source order:
1. `article` cards
2. `a[href*="/details/"]`
3. `a[href*="/company/"]`
4. `window.az_search_data`

### Pass 2: Enrichment
Open detail pages and enrich every item with:
- canonical title
- JSON-LD `JobPosting`
- full description
- structured location fields
- employer metadata
- `directApply`
- `validThrough`
- region availability message

Recommended primary source order:
1. `script[type="application/ld+json"]`
2. `window.az_details`
3. visible `h1` and description body
4. related company page if needed

### Why this order
Adzuna detail pages are reliable for canonical vacancy metadata because the `JobPosting` block already contains most of the fields you want. The listing page is better for discovery and high-volume crawl. The company page is useful for scope expansion under one employer.

## Parser risks and notes

- Search results and detail pages are heavily decorated with ads and tracking.
- A few query paths show region-gated content.
- Pagination uses mixed params (`p` and `page`).
- Salary data is not guaranteed to be structured, often only visible as text.
- Some detail pages may not have direct apply links at all.
- `ApplyIQ` is a separate product CTA, not a universal job apply endpoint.
- Cookie dialog may cover the page on first load.

## Recommended extraction flow

1. Load search page.
2. Dismiss or accept cookies once.
3. Extract `window.az_search_data` and all `article` cards.
4. Store job URLs, company links, salary text, badges, snippets.
5. For each job URL, open detail page.
6. Extract `JobPosting` JSON-LD.
7. Store `directApply`, `validThrough`, `industry`, `description`, `jobLocation`.
8. If needed, open company page from `sameAs` or company link.
9. Optionally enrich with company-scope search and salary page.

## Tested URLs

- `https://www.adzuna.com/`
- `https://www.adzuna.com/search?q=software%20engineer&w=New%20York%2C%20NY`
- `https://www.adzuna.com/details/5616455592?se=uvhWgQIl8RG9qIDBX2ocxA&title=Software_Engineer&v=AF30EFC71BCC6E404F780AB8C7C04D06EF15FF3B`
- `https://www.adzuna.com/company/robert-half`
- `https://www.adzuna.com/robert-half/salary`
- `https://www.adzuna.com/hire/`
- `https://developer.adzuna.com`
