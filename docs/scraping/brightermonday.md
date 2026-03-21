# BrighterMonday Kenya - DOM/HTML report for scraping

Дата проверки: 2026-03-21
Источник данных: live Playwright MCP scan на `www.brightermonday.co.ke` с проходом по `home`, `jobs`, `listings/software-developer-4ne2vm` и `company/brightermonday-consulting`.

Цель отчета: зафиксировать **реальную DOM-структуру**, полезные **селекторы**, **URL-паттерны**, **JSON-LD**, **network/XHR** и **ограничения доступа**, чтобы можно было строить надежный scraper без догадок.

## 1) Короткий вывод

BrighterMonday Kenya выглядит как **SSR-heavy job board** с очень читаемой DOM-структурой. Для парсинга это хороший источник, потому что ключевые данные лежат прямо в HTML: title, company, location, employment type, salary, category, date, summary и detail text. При этом сайт активно использует аналитические и рекламные пиксели, cookie consent и personalization endpoints, но сами вакансии не скрыты в сложном SPA-state.

Главные ограничения такие:

1. Просмотр вакансий и company page доступны без логина.
2. Apply flow жестко уходит в `login to apply now`.
3. На apply wall есть `reCAPTCHA`.
4. На страницах есть cookie consent overlay, который может мешать automation click actions.
5. Я не увидел `__NEXT_DATA__` или `__NUXT__`; structured data есть, но сайт не выглядит как SPA с hydration state.

## 2) Карта страниц

### Home

`https://www.brightermonday.co.ke/`

На главной есть:

1. Верхняя навигация `Job Seekers`, `Career`, `Employers`, `Help Center`.
2. Кнопки `Log In`, `Sign Up`, `Post A Job`.
3. Hero-блок с CTA `Apply Now!`.
4. Быстрый поиск вакансий.
5. Популярные поиски по категориям.
6. Блоки с компаниями, карьерными инструментами и employer CTA.

### Listing / search

`https://www.brightermonday.co.ke/jobs`

Это основная выдача, где есть:

1. Search bar с фильтрами по job function, industry, location и experience level.
2. Список вакансий с title, company, location, work type, salary, category, age of post.
3. Badges `FEATURED`, `New`, `Popular`, `Easy apply`.
4. Pagination по `page=2`, `page=3` и далее.
5. Панель `Filters Applied` и sidebar `Filter Results`.

### Job detail

`https://www.brightermonday.co.ke/listings/software-developer-4ne2vm`

Детальная страница содержит:

1. Название вакансии.
2. Company name.
3. Category / function.
4. Time since posting.
5. Summary block.
6. Full description and requirements.
7. Apply/login wall.
8. Share links.
9. Similar jobs.
10. Safety tips.

### Company page

`https://www.brightermonday.co.ke/company/brightermonday-consulting`

Company page содержит:

1. Company heading and verification badge.
2. Address and website.
3. Industry, type, founded, employees.
4. About section.
5. Benefits section.
6. Open jobs list.
7. Awards.
8. Company gallery.
9. Similar companies.
10. Pagination for company jobs.

## 3) Home page structure

### Top navigation

Навигация собрана как обычный banner/nav layout. Полезные ссылки:

- `Job Seekers` -> `/job-seeker`
- `Career` -> `/discover`
- `Employers` -> `/employer`
- `Help Center` -> external help portal
- `Log In` -> `/account/login`
- `Sign Up` -> `/account/sign-up`
- `Post A Job` -> employer flow

### Main search entry

На главной есть четыре search controls, каждый в виде button + combobox pair:

- `Any Job Functions`
- `Any Industries`
- `Any Locations`
- `Any Experience Levels`

Кнопка запуска поиска:

- `Find a Job`

### Popular searches

Это отдельный блок с готовыми category URL:

- `IT & Telecoms`
- `Remote (Work From Home)`
- `Contract`
- `Nairobi`
- `Outside Kenya`
- `Rest of Kenya`

### Experience cards

На home есть карточки по уровню опыта:

- `Executive level`
- `No Experience`
- `Mid level`
- `Internship & Graduate`
- `Entry level`
- `Senior level`

Это удобно для парсера как отдельный индексный слой по сегментам рынка.

### Company carousel

Есть отдельный блок `Companies currently hiring in Kenya` со слайдером и ссылкой `View All Companies Hiring`.

### Career tools and employer blocks

На home также есть:

- блок `Advance your career with BrighterMonday`
- CTA на `AI Career Tool`
- employer block `Searching for the right talent?`

## 4) Search / listing structure

### Search header

На `/jobs` я увидел полноценный page shell:

- breadcrumb `Homepage > Search results`
- `Jobs in Kenya`
- счетчик результатов
- horizontal ad slot
- CV-services promo

### Filtering UI

Основные фильтры на странице:

- `Any Job Functions`
- `Any Industries`
- `Any Locations`
- `Any Experience Levels`
- `Order By`

В `Order By` есть:

- `Latest`
- `Featured`
- `Popular`

Есть также `Reset Filter`.

### URL patterns

Наблюдаемые паттерны:

- `/jobs`
- `/jobs?page=2`
- `/jobs?page=3`
- `/jobs?sort=featured`
- `/jobs?sort=popular`
- `/jobs/engineering-technology`
- `/jobs/engineering-technology?industry=it-telecoms`
- `/jobs/engineering-technology/nairobi?industry=it-telecoms`
- `/jobs/engineering-technology/nairobi/full-time?industry=it-telecoms`

### Job cards

Карточки вакансий на listing состоят из nested blocks, но важные поля читаются напрямую из DOM:

- title link
- company name
- location
- work type
- salary
- category
- status badge
- posting age
- short preview / teaser

### Stable listing selector

Самый полезный anchor для title:

- `a[data-cy="listing-title-link"]`

На карточке также встречаются:

- title attribute с названием вакансии
- `FEATURED` badge
- `Easy apply`
- `New`
- `Popular`

### Listing card field examples

Примеры данных, которые были видны прямо в карточке:

- `Software developer`
- `Anonymous Employer`
- `Nairobi`
- `Full Time`
- `IT & Telecoms`
- `Confidential`
- `3 days ago`

## 5) Job detail structure

### Top block

В деталке поля лежат прямо в DOM:

- `h1` job title
- `h2` company name
- category link
- posting age
- badges `Easy apply`, `New`, `Featured`
- location / work type / category chips
- salary chip when present

### Job summary

Структура summary-блока:

- `Job summary`
- short description
- `Min Qualification`
- `Experience Level`
- `Experience Length`

На проверенной вакансии было:

- `Bachelors`
- `Mid level`
- `2 years`

### Job descriptions & requirements

Большой текстовый блок содержит:

- location line
- industry line
- `JOB PURPOSE`
- responsibilities
- education requirements
- experience requirements
- certifications
- technical competencies
- submission deadline
- shortlist note

Это чистый SSR-текст, который можно брать как primary content source.

### Safety tips

Есть отдельный блок:

- `Important safety tips`
- предупреждение не платить заранее
- ссылка `Report Job`

### Apply wall

Apply секция спрятана внутри блока `Log in to apply now`. Внутри есть:

- `Continue with Google`
- `Continue with Linkedin`
- `Email Address`
- `Password`
- `Keep me logged in`
- `Log in`
- `Sign Up to Apply`
- Google reCAPTCHA iframe

### Share block

Есть шаринг:

- WhatsApp
- LinkedIn
- Facebook
- Twitter
- SMS

Это полезно для диагностики canonical share URLs и UTM patterns.

### Similar jobs

На detail page есть отдельный блок `Similar jobs` с такими же карточками, как на listing:

- title
- company
- location
- type
- salary
- age of post

Есть ссылка `View More` обратно на `/jobs`.

## 6) Company page structure

### Breadcrumb and header

Company page использует breadcrumb:

- `Homepage`
- `Companies Hiring`
- company name

Вверху есть:

- company heading
- verified badge
- banner image
- logo block

### Company facts

В company sidebar я увидел structured facts:

- address
- website
- industry: `Recruitment`
- type: `Recruitment Agency`
- founded: `2006`
- employees: `51 - 100`

### About and benefits

Основной content area содержит:

- `About BrighterMonday Consulting`
- short about paragraph
- `see more`
- `Company benefits`
- benefit list

### Job opportunities

Блок `Job opportunities` показывает:

- company name
- open positions count
- average years of experience
- typical level range
- minimum qualification signal

Дальше идет список вакансий компании, где каждая карточка содержит:

- title link
- location
- work type
- salary if present
- category
- posting age

### Company pagination

У company jobs есть отдельная пагинация:

- `?page=2`
- `?page=3`
- `?page=4`

### Awards / gallery / similar companies

Есть отдельные блоки:

- `Awards`
- `Company gallery`
- `Similar companies`

Для скрапера это полезно, потому что company page дает не только вакансии, но и метаданные о бренде.

## 7) JSON-LD and embedded state

### JSON-LD

На detail page и company page я подтвердил `script[type="application/ld+json"]`.

На detail page в structured data есть:

- `WebPage`
- `Organization`
- `JobPosting`

В preview JSON-LD на detail page видно:

- canonical URL
- job name
- description
- datePublished

Это хороший сигнал, что для detail page можно строить **двухслойный парсер**:

1. сначала JSON-LD,
2. потом DOM fallback.

### Embedded state

На проверенных страницах:

- `window.__NEXT_DATA__` = false
- `window.__NUXT__` = false

То есть сайт не выглядит как Next/Nuxt SPA, и hydration state не является основным источником данных.

## 8) Network / XHR

### Что реально полезно для парсинга

Самый важный non-HTML endpoint, который я подтвердил:

- `GET /ajax/listing-recommendations/similar/1167309`

Он возвращает similar jobs для detail page.

### Personalization / analytics

На странице также активно дергаются:

- `api.sail-personalize.com/v1/personalize/simple?pageviews=...`
- `h.clarity.ms/collect`
- `www.google-analytics.com/g/collect`
- `pagead2.googlesyndication.com`
- `www.google.com/measurement/...`
- `cdn-cgi/rum`
- `OneTrust` consent requests
- `ingest.webvitalize.io/api/log`

Большая часть этого шума не нужна для job scraping, но полезна как признак того, что страница реально живая и не статический mock.

### What I did not see

Я не увидел отдельного публичного JSON jobs API в этом скане. Основной источник вакансий здесь - **SSR HTML** плюс один endpoint для похожих вакансий и персонализация/аналитика.

## 9) Auth / anti-bot / consent

### Cookie consent

На входе есть OneTrust consent banner. Он может перекрывать клики и ломать automation, пока не нажать `Accept All Cookies`.

### Apply wall

Apply flow требует логин:

- Google OAuth
- LinkedIn OAuth
- email/password login
- `Forgot Password?`
- `Keep me logged in`

### reCAPTCHA

На login-to-apply block есть reCAPTCHA iframe, поэтому автоматическая подача без авторизации не проходит.

### Security and warnings

Есть safety tips и `Report Job`. Это не антибот, но важно как UX gating и trust signal.

## 10) Primary selectors

### Home

- `a[href="/account/login"]`
- `a[href="/account/sign-up"]`
- `button:has-text("Find a Job")`
- `button:has-text("Any Job Functions")`
- `button:has-text("Any Industries")`
- `button:has-text("Any Locations")`
- `button:has-text("Any Experience Levels")`

### Listing

- `a[data-cy="listing-title-link"]`
- `a[href*="/listings/"]`
- `button:has-text("Search")`
- `button:has-text("Order By")`
- `a[href*="?page=2"]`
- `a[href*="?sort=featured"]`
- `a[href*="?sort=popular"]`

### Detail

- `h1`
- `h2`
- `h3:has-text("Job summary")`
- `h3:has-text("Job descriptions & requirements")`
- `h3:has-text("Important safety tips")`
- `h3:has-text("Log in to apply now")`
- `iframe[title*="reCAPTCHA"]`

### Company

- `h1`
- `h2:has-text("About")`
- `h3:has-text("Job opportunities")`
- `h3:has-text("Awards")`
- `h2:has-text("Company gallery")`
- `h3:has-text("Similar companies")`
- `a[href*="/company/"]`
- `a[href*="/listings/"]`

## 11) Fallback selectors

Если primary selectors сломаются, я бы падал назад на:

- text anchors `Apply`, `Search`, `Featured`, `Easy apply`
- `link[title]`
- first `article` or major `main` subsection
- breadcrumb links
- direct `href` patterns like `/listings/`, `/company/`, `/jobs?page=`
- structured text blocks under headings

## 12) Field mapping table

| Field | Primary source | Fallback source |
|---|---|---|
| job title | `h1` / `a[data-cy="listing-title-link"]` | JSON-LD `WebPage.name` |
| company name | `h2` on detail / company card text | JSON-LD `Organization.name` |
| location | card chips / detail chips | description text line |
| work type | card chips | detail chips |
| salary | card chip if present | detail page text |
| category / function | card text / breadcrumb | JSON-LD / page title |
| posted age | card text like `3 days ago` | similar jobs card or page metadata |
| summary | `Job summary` block | JSON-LD `description` |
| description | `Job descriptions & requirements` block | JSON-LD `JobPosting.description` |
| qualifications | summary/description paragraphs | bullet text in description |
| apply URL | login wall links, OAuth links | explicit `account/customer/sign-up?apply=...` |
| company facts | company sidebar | JSON-LD `Organization` |
| similar jobs | `Similar jobs` section | `/ajax/listing-recommendations/similar/{id}` |

## 13) 2-pass parser strategy

### Pass 1: fast indexer

Сначала парсим:

1. Home categories and quick-search links.
2. Listing cards.
3. Pagination URLs.
4. Company cards on company page.
5. Detail page canonical fields.

Цель первого прохода - быстро собрать много вакансий и company anchors.

### Pass 2: enrichment

Потом добираем:

1. Detail page body text.
2. JSON-LD metadata.
3. Similar jobs endpoint.
4. Company facts and awards.
5. Apply/login gating information.

Это удобно, потому что первый проход дает объем, а второй - качество и нормализацию.

## 14) Practical scraper notes

1. Нажимай `Accept All Cookies` сразу, иначе overlay может перекрывать клики.
2. Для listings используй `a[data-cy="listing-title-link"]` как главный anchor.
3. Для detail page бери не только заголовок, но и полный `Job descriptions & requirements`.
4. Apply flow не считать публичным - он gated через login + reCAPTCHA.
5. Company page полезен не меньше detail page, потому что там есть open jobs, факты о компании и company-specific pagination.

## 15) Проверенные URL

- `https://www.brightermonday.co.ke/`
- `https://www.brightermonday.co.ke/jobs`
- `https://www.brightermonday.co.ke/listings/software-developer-4ne2vm`
- `https://www.brightermonday.co.ke/company/brightermonday-consulting`
- `https://www.brightermonday.co.ke/jobs?page=2`
- `https://www.brightermonday.co.ke/jobs?sort=featured`
- `https://www.brightermonday.co.ke/jobs?sort=popular`
- `https://www.brightermonday.co.ke/jobs/engineering-technology?industry=it-telecoms`
- `https://www.brightermonday.co.ke/jobs/engineering-technology/nairobi/full-time?industry=it-telecoms`
- `https://www.brightermonday.co.ke/ajax/listing-recommendations/similar/1167309`
