# Torre.ai DOM / Parser Report

Дата проверки: 2026-03-21

Этот отчет основан на live-сканировании сайта через Playwright MCP и проверке публичных страниц, DOM-структуры, JSON-LD, client-side state и сетевых запросов. Фокус отчета - подготовка к парсингу вакансий, company profile и apply/auth flow.

## 1. Краткий вывод

Torre.ai - это JS-heavy приложение на Nuxt-style фронтенде с большим количеством клиентских API, но при этом у него есть очень полезные публичные слои для парсинга. Самые ценные страницы для извлечения данных - это `careers/Torre`, `teams/Torre` и `post/{job_id}-{slug}`. Для вакансий Torre использует сильный `JobPosting` JSON-LD на detail page, а для company pages - `Organization` JSON-LD. При этом apply-flow и часть персонализированных блоков скрыты за login wall, поэтому публичный сбор возможен, но quick-apply требует авторизации.

## 2. Карта страниц

### 2.1 Home
URL: `https://torre.ai/?r=4v9DLRjj`

Главная страница - это маркетинговый landing с app-bar навигацией, промо-блоками и ссылками на продуктовые разделы. Основные публичные entry points:
- `Search`
- `Post a job`
- `Search jobs`
- `Preferences`
- `Messages`
- `About Torre`

Home page важна не как источник вакансий, а как карта ссылок на другие разделы и подтверждение продуктовой структуры сайта.

### 2.2 Search / Listing login wall
URL: `https://torre.ai/search/jobs`

Этот маршрут без авторизации перенаправляет на `https://accounts.torre.ai/email/...` и показывает простой login wall с email field и кнопкой `Continue`.

### 2.3 Careers listing
URL: `https://torre.ai/careers/Torre`

Это главная публичная страница для парсинга вакансий Torre. Здесь есть фильтры, карточки вакансий, ссылки на job detail, а также статистика каналов и рефереров.

### 2.4 Company / team page
URL: `https://torre.ai/teams/Torre`

Это публичный профиль компании / team genome. Здесь есть:
- team members
- former members
- admins
- psychometrics
- common skills
- reputation
- jobs
- common job benefits

### 2.5 Job detail
URL: `https://torre.ai/post/ZW5ya5pW-torreai-remote-junior-recruiter-freelancer?...`

Это самая важная страница для извлечения вакансии. На ней присутствуют:
- title
- company
- author/poster
- compensation
- location
- visa sponsorship
- published time
- requirements
- questions for applicants
- stats
- top channels / referrers
- match and rank
- comments
- apply/share CTA

### 2.6 Apply / auth flow
При нажатии `Apply` на job detail пользователя уводит на `accounts.torre.ai/email/...` с OAuth-like redirect chain, где есть `detail_id`, `intent=job-post:quick-apply` и `client_id`.

## 3. DOM / HTML структура

### 3.1 Home page

Главные элементы, которые стоит использовать как якоря:
- `h1` с текстом `The AI talent agent for millions of professionals`
- верхний app bar со ссылками и sign-in button
- промо-кнопки `FIND PEOPLE or POST A JOB` и `FIND JOBS`
- блоки продуктовых карточек `Let AI do the recruitment for you`
- нижний footer со ссылками на `For candidates`, `For companies`, `For developers`, `For communities`, `For partners`, `About Torre`

Стабильные селекторы:
- `h1`
- `a[href="https://torre.ai/search/jobs"]`
- `a[href="https://torre.ai/post/onboarding"]`
- `a[href="https://torre.ai/apiforcompanies"]`
- `a[href="https://torre.ai/apiforcandidates"]`

### 3.2 Careers listing

На careers page структура карточки вакансии очень удобна для парсинга.

Ключевые якоря листинга:
- карточка вакансии - один root `a[href*="/post/"]`
- внутри root anchor лежат title, posted by, description snippet, job type, compensation, location
- рядом отдельный `View details`, но он дублирует тот же href
- у закрытых вакансий есть badge `Closed`
- строка `Application at Torre` присутствует у карточек, но сама подача все равно уводит в auth wall

Типичные поля внутри карточки:
- title в `p`
- authors/posters в `Posted by` block, обычно несколько `a[href^="/username"]`
- short description
- `work` + тип занятости: `Freelance`, `Full-time`, `Internships`, `Flexible`
- `universal_currency_alt` + compensation
- `location_on` + location

Фильтры на careers page:
- `All locations` - `combobox`
- `All types of jobs` - `combobox`
- `All skills` - `combobox`

### 3.3 Company page

На `teams/Torre` DOM устроен как набор секций с якорями:
- `#people`
- `#behavior`
- `#common-skills`
- `#reputation`
- `#jobs`
- `#common-benefits`

Основные блоки:
- header с `Torre.ai`, share button, sign in button
- hero block с названием, rating, view count, members count
- `People` секция с team members
- `Psychometrics` секция с behavioral traits sliders
- `Reputation` секция со статистикой и AI summary
- `Jobs` секция с job cards
- `Common job benefits` list

В секции People используются повторяющиеся карточки сотрудников с:
- avatar link
- `h5` name link
- role label, например `Leader`

В секции Reputation используются метрики и AI summary. Это полезно, если нужно парсить company-level signals.

### 3.4 Job detail page

Job detail page самая богатая по структуре.

Основные элементы:
- `h1` с названием вакансии
- company link на `https://torre.ai/teams/Torre`
- `Posted by` block со ссылками на авторов
- compensation block
- location block
- visa sponsorship block
- `Published X months ago`
- top navigation with anchor links to major sections

Секции detail page:
- `Requirements and responsibilities`
- `Requirements`
- `Meet your client`
- `Match and rank`
- `Comments`
- `Questions for applicants`
- `Stats`
- `Real-time user activity`
- `Real-time AI thinking`

Внутренние блоки detail page:
- `Requirements and responsibilities` содержит основной long-form description
- `Requirements` содержит skills wanted и language requirements
- `Meet your client` содержит team member info, about text, mission, reputation, job post admins
- `Match and rank` скрывает персонализированные данные за sign-in
- `Questions for applicants` показывает pre-screening questions
- `Stats` показывает visitors, applications, pre-screenings completed, mutually matched, hired, and channel breakdowns
- `Top channels attracting candidates` показывает источники трафика и application counts
- `Top referrers attracting candidates` показывает конкретных людей-рефереров

Стабильные элементы для селекторов:
- `h1`
- `a[href^="https://torre.ai/teams/Torre"]`
- `a[href^="https://torre.ai/post/"]`
- `button:has-text("Apply")`
- `button:has-text("Share")`
- `a[href^="#responsibilities"]`
- `a[href^="#requirements"]`
- `a[href^="#yourteam"]`
- `a[href^="#matchandrank"]`
- `a[href^="#comments"]`
- `a[href^="#questions"]`
- `a[href^="#stats"]`

### 3.5 Login wall

`search/jobs` и `Apply` с detail page ведут на `accounts.torre.ai/email`.

Login wall DOM очень простой:
- banner `Your information`
- text `To continue:`
- textbox `Type your email address*`
- button `Continue`

Это не CAPTCHA wall, а email-first auth wall с OAuth-like redirect.

## 4. Structured data и embedded state

### 4.1 Home

На home page есть `script[type="application/ld+json"]` с:
- `WebSite`
- `EmploymentAgency`

Также есть `SearchAction` на `https://torre.ai/search/jobs?q={search_term_string}`.

### 4.2 Company page

На `teams/Torre` есть `Organization` JSON-LD:
- `@type`: `Organization`
- `identifier.value`: `Torre`
- `name`: `Torre.ai`
- `logo`
- `description`
- `url`
- `sameAs`

### 4.3 Job detail

На `post/ZW5ya5pW-...` есть `JobPosting` JSON-LD. Это один из самых полезных источников для парсера.

Ключевые поля JSON-LD:
- `title`
- `employmentType`
- `description`
- `identifier.value` - job id
- `datePosted`
- `validThrough`
- `baseSalary`
- `directApply`
- `experienceRequirements`
- `educationRequirements`
- `hiringOrganization`
- `jobLocation`
- `jobLocationType`
- `applicantLocationRequirements`

Вывод: для вакансий приоритетный источник - JSON-LD, затем DOM fallback.

## 5. Network / API / XHR

### 5.1 Public / semi-public endpoints observed

На Torre был зафиксирован набор полезных API:
- `GET /api/suite/opportunities/{id}` - job detail payload
- `GET /api/suite/opportunities/{id}/reputation` - reputation score for job, часто `401` без auth
- `GET /api/suite/opportunities/{id}/views` - tracking views
- `GET /api/suite/opportunities/{id}/candidates/me/summary` - personalized summary, `401`
- `GET /api/suite/app/downloaded` - apply-related state, `401`
- `GET /api/referrals/referrer-code`
- `GET /api/referrals/referrers/opportunities/{id}`
- `GET /api/suite/languages?locale=en`
- `GET /api/suite/currencies`
- `POST /api/suite/store-action`
- `POST /api/suite/shorten-url`
- `POST /api/suite/opportunities/{id}/tracking`
- `POST /api/genome/people/me/signals/targets` - `401`

### 5.2 Third-party telemetry

Observed third-party scripts / trackers:
- Google Tag Manager
- Google Analytics
- Google Ads / DoubleClick
- Meta / Facebook Pixel
- LinkedIn Insight Tag
- Clarity
- Sentry
- Snowplow
- Stripe on job detail page
- FullStory on auth wall

### 5.3 Practical consequence

For public scraping, the cleanest path is:
- HTML and JSON-LD for core job fields
- API enrichment only where endpoints are public or unauthenticated
- ignore/skip `401` personalized endpoints unless you have user session

## 6. Auth wall and access limits

### 6.1 search/jobs

`https://torre.ai/search/jobs` does not expose jobs directly without login. It redirects to:
- `https://accounts.torre.ai/email/...`

The auth flow uses parameters like:
- `scope=openid profile email`
- `response_type=code`
- `redirect_uri=https://torre.ai/callback?client_name=starrgate`
- `intent=search:sign-in`

### 6.2 Apply flow

Clicking `Apply` on a public job detail redirects to auth wall with:
- `detail_id=ZW5ya5pW`
- `intent=job-post:quick-apply`
- `client_id=541493`

This confirms that the public job can be read, but direct apply requires login.

### 6.3 What remains public

Publicly available without auth:
- home page
- careers page
- team/company page
- job detail page
- JSON-LD of job detail
- most text content and stats blocks

Gated / user-specific:
- quick apply
- match and rank numbers
- me/signals targets
- candidate summary
- some reputation calls

## 7. Stable selectors and fallback selectors

### 7.1 Home
Primary:
- `h1`
- `a[href="https://torre.ai/search/jobs"]`
- `a[href="https://torre.ai/post/onboarding"]`
- `a[href="https://torre.ai/apiforcompanies"]`
- `a[href="https://torre.ai/apiforcandidates"]`

Fallback:
- text matches `FIND JOBS`, `FIND PEOPLE or POST A JOB`

### 7.2 Careers listing
Primary:
- `a[href*="/post/"]`
- `a[href*="/post/"] p` for title
- `a[href*="/post/"] a[href^="/torre"]` or `a[href^="/username"]` for posters
- `a[href*="/post/"] [data-testid]` not observed, so avoid relying on test ids

Fallback:
- text `Application at Torre`
- text `Closed`
- tokens `work`, `location_on`, `universal_currency_alt`

### 7.3 Company page
Primary:
- `a[href="#people"]`
- `a[href="#behavior"]`
- `a[href="#reputation"]`
- `a[href="#jobs"]`
- `h1`
- `a[href^="https://torre.ai/torrenegra"]`, etc. for members/admins

Fallback:
- `People`, `Psychometrics`, `Reputation`, `Jobs`, `Common job benefits`

### 7.4 Job detail
Primary:
- `h1`
- `button:has-text("Apply")`
- `button:has-text("Share")`
- `a[href^="#responsibilities"]`
- `a[href^="#requirements"]`
- `a[href^="#yourteam"]`
- `a[href^="#matchandrank"]`
- `a[href^="#comments"]`
- `a[href^="#questions"]`
- `a[href^="#stats"]`

Fallback:
- `Questions for applicants`
- `Stats`
- `Match and rank`
- `Meet your client`

### 7.5 Login wall
Primary:
- `textbox[placeholder*="email"]`
- `button:has-text("Continue")`

Fallback:
- text `To continue:`

## 8. Extraction mapping table

| Field | Primary source | Fallback source | Notes |
|---|---|---|---|
| job_id | `JobPosting.identifier.value` | URL slug prefix, e.g. `ZW5ya5pW` | Stable across detail/apply flow |
| title | `JobPosting.title` | `h1` on detail, title in listing card | Prefer JSON-LD |
| company_name | `hiringOrganization.name` | company link text, team page title | On Torre often `Torre.ai` |
| description | `JobPosting.description` | `Requirements and responsibilities` block | HTML in JSON-LD is best |
| employment_type | `JobPosting.employmentType` | listing card `Full-time`, `Freelance`, `Internships`, `Flexible` | Can be array |
| compensation | `JobPosting.baseSalary` | listing card compensation block | Some postings use textual compensation like `Provide your expected compensation` |
| location | `jobLocation` / `jobLocationType` | listing card `location_on` block | Can be remote/global or country-specific |
| visa_sponsorship | job detail visible label | none | Observed as `Visa sponsorship: No` on some jobs |
| published_at | `datePosted` or visible `Published X months ago` | card relative time if shown | Prefer JSON-LD |
| valid_through | `validThrough` | countdown in footer if present | Good for expiration logic |
| poster_names | `Posted by` section | job post admins / team members | Multiple posters possible |
| skills | `requirements` / JSON-LD if present | `Skills wanted` block | Usually visible as chips/tags |
| languages | `Language(s) required` block | JSON-LD if present | Usually human-readable list |
| questions | `Questions for applicants` section | none | Useful for application workflow |
| stats_visits | `Stats` section | none | Public and visible on detail page |
| stats_applications | `Stats` section | none | Useful for popularity/funnel |
| reputation | `Reputation` section on company page | `reputation` API endpoint | On company page mostly public summary |
| apply_url | button click redirect | `detail page auth redirect` | Quick apply is auth-gated |

## 9. Parser strategy in 2 passes

### Pass 1 - Public crawl
Goal: collect all publicly available content without auth.

What to fetch:
- home page for site map
- company page `/teams/Torre`
- careers page `/careers/Torre`
- all visible job detail pages from careers listing

What to extract:
- JSON-LD first
- visible title / company / compensation / location
- section text from `Requirements and responsibilities`
- poster names
- questions for applicants
- stats and popularity signals

### Pass 2 - Enrichment / gated signals
Goal: collect extra metadata where available without pretending auth-free access exists.

What to try:
- public API endpoints like `/api/suite/opportunities/{id}`
- referrer and channel endpoints
- reputation endpoints only if they respond without auth, otherwise mark as gated
- apply redirect mapping only, not full apply submission

What to skip unless user auth exists:
- candidate summary
- me/signals/targets
- quick apply completion
- personalized match and rank values

## 10. Practical scraping notes

- Torre uses many repeated API calls per job card. Expect console noise from `reputation` requests during listing loads.
- The site uses large Nuxt bundles and many trackers, so don’t depend on JS chunk names for parsing.
- The job detail page is the most reliable source for canonical job text.
- The company page is the best source for organization metadata and team relationships.
- The careers page is the best source for bulk discovery.

## 11. 5 alternatives to Torre for LATAM / Global

These are not direct copies of Torre, but they are the closest practical alternatives for LATAM/Global tech hiring and job search. The selection is based on observed market positioning and official pages.

| Platform | Why it is relevant | Source |
|---|---|---|
| Get on Board | Strong LATAM tech focus, job listings and company pages tailored for developers and startups | https://www.getonbrd.com/ |
| LinkedIn Jobs | Global scale, broad tech hiring, company pages and job search ecosystem | https://www.linkedin.com/jobs/ |
| Indeed | Global aggregator with large job inventory and job search surface | https://www.indeed.com/ |
| Wellfound | Startup/tech-focused job search, especially good for remote and early-stage companies | https://wellfound.com/jobs/ |
| Computrabajo | Large LATAM job board with country-localized portals and broad job inventory | https://www.computrabajo.com/ |

## 12. Checked URLs

### Torre pages checked
- `https://torre.ai/?r=4v9DLRjj`
- `https://torre.ai/search/jobs`
- `https://torre.ai/careers/Torre`
- `https://torre.ai/teams/Torre`
- `https://torre.ai/post/ZW5ya5pW-torreai-remote-junior-recruiter-freelancer?utm_source=career&utm_medium=shr_ts`
- `https://accounts.torre.ai/email/...`

### External alternative references
- `https://www.getonbrd.com/`
- `https://www.linkedin.com/jobs/`
- `https://www.indeed.com/`
- `https://wellfound.com/jobs/`
- `https://www.computrabajo.com/`
