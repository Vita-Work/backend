# Indeed — DOM/HTML report for scraping

Дата проверки: 2026-03-21
Источник данных: live Playwright CLI browser session на `www.indeed.com` + `jobs/search` + `viewjob` + `cmp/Morgan-Stanley`.

Цель отчета: зафиксировать **реальную DOM-структуру**, полезные **селекторы**, **URL-паттерны**, **JSON-LD**, **network/XHR** и **ограничения доступа** так, чтобы можно было строить надежный scraper без догадок.

## 1) Что доступно гостю

Без логина гостю доступны:

1. Home page.
2. Search/listing page с карточками вакансий.
3. Job detail page.
4. Company profile page.

Что ограничено или гейтится:

1. Apply flow почти всегда уводит в modal login wall.
2. Часть персонализированных действий требует Indeed account.
3. Некоторые requests/anti-bot flows дергают Cloudflare Turnstile и challenge endpoints.

## 2) Общая карта URL

### Home

- `https://www.indeed.com/`

### Search/listing

- `https://www.indeed.com/jobs?q=software+engineer&l=New+York%2C+NY`
- observed pagination pattern: `...&start=10`
- `sort=date` меняет сортировку на date

### Job detail

- `https://www.indeed.com/viewjob?jk=dbc110f85b4c9752`

### Company profile

- `https://www.indeed.com/cmp/Morgan-Stanley`

### Company jobs

- `https://www.indeed.com/cmp/Morgan-Stanley/jobs?jk=...`

### Auth / redirect

- `https://secure.indeed.com/auth?...`
- `https://onboarding.indeed.com/onboarding?...`
- `https://account.indeed.com/myaccess`

## 3) Home page structure

### Основной layout

Домашняя страница собрана как SSR page с верхним nav, поисковой формой и промо-блоками.

Ключевые ориентиры DOM:

- `banner`
- `navigation "Primary"`
- `main`
- `search`
- `contentinfo`

### Search form

На home есть две основные формы ввода:

- `input[name="q"]` с aria-label `search: Job title, keywords, or company`
- `input[name="l"]` с aria-label `Edit location`

Кнопка поиска:

- `button` с текстом `Search`

### Главный UX-контент

На home видны:

- блок `Your next job starts here`
- CTA `Get Started`
- промо приложения `Your AI career coach is on the app`
- language switcher `español`

### Footer

Footer содержит навигационные ссылки на:

- Hiring Lab
- Career advice
- Browse jobs
- Browse companies
- Salaries
- Indeed Events
- Work at Indeed
- Countries
- About
- Help
- ESG at Indeed
- Post a job

## 4) Search/listing page structure

### Основной layout

Search page — это смесь SSR и динамических job cards.

Ключевые узлы:

- `main`
- `search`
- filters bar
- results list
- cards list

### Search inputs

Поле поиска:

- `input[name="q"]`
- aria-label: `search: Job title, keywords, or company`
- value на примере: `software engineer`

Поле локации:

- `input[name="l"]`
- aria-label: `Edit location`
- placeholder: `City, state, zip code, or "remote"`
- value на примере: `New York, NY`

Кнопки очистки:

- `button` `Clear what input`
- `button` `Clear location input`

Кнопка submit:

- `button` `Search`

### Filter pills

Фильтры рендерятся как отдельные кнопки-пиллы. На странице были видны:

- `Date posted`
- `Remote`
- `Developer skill`
- `Job Type`
- `Experience level`
- `Pay`
- `Education`
- `Clearance type`
- `Developer type`
- `Compensation package`
- `Within 50 miles`

Стабильные ids и имена, которые лучше использовать как первичный таргет:

- `fromAge_filter_button`
- `remote_filter_button`
- `filter-taxo1`
- `filter-jobtype1`
- `expLvl_filter_button`
- `salaryType_filter_button`
- `education_filter_button`
- `filter-taxo2`
- `filter-taxo3`
- `filter-taxo4`
- `filter-radius`

### Filter mechanics

Из DOM видно, что:

- `Date posted` и `Remote` открываются как dropdown/button flows.
- `Developer skill`, `Job Type`, `Clearance type`, `Developer type`, `Compensation package` используют submit-style pill buttons.
- typeahead/filters у Indeed часто завязаны на hidden forms и URL query params.

### Results header

В заголовке выдачи присутствуют:

- h1 вида `software engineer jobs in New York, NY`
- сортировка `relevance - date`
- ссылка `Sort by: date`

### Job cards

Карточки вакансий на странице — это не просто текст, а набор `a` и структурированных блоков.

Наиболее важные паттерны:

- title link: `a.jcs-JobTitle`
- `data-jk` на job key
- `id="job_<jk>"` у обычных карточек
- `id="sj_<jk>"` у sponsored jobs
- `href` обычно указывает на `rc/clk`, `pagead/clk`, `viewjob`

Примеры увиденных title anchors:

- `Associate Software Engineer`
- `Software Engineer, Backend`
- `Junior Software Engineer`
- `Software Engineer II`
- `Backend Engineer, Podcast`

### Card content structure

Внутри карточки обычно есть:

- title
- company
- location
- salary or pay package
- short snippet / requirement bullets
- related links:
  - `View all`
  - `Salary Search`
  - `questions & answers about <company>`

### Practical selectors for cards

Primary:

- `a.jcs-JobTitle[data-jk]`
- `a.jcs-JobTitle[href*="/rc/clk"]`
- `a.jcs-JobTitle[href*="/pagead/clk"]`
- `a.jcs-JobTitle[href*="/viewjob"]`

Fallback:

- `[id^="job_"] a`
- `[id^="sj_"] a`
- `a[href*="jk="]`

### Pagination / infinite behavior

Observed patterns:

- `a[aria-label="Next Page"]` with `href` containing `start=10`
- `button` `Show more`

That means Indeed supports both:

- page-step navigation through `start=N`
- a load-more style control

Useful URL pattern:

- `https://www.indeed.com/jobs?q=software+engineer&nl=&l=New+York%2C+NY&radius=50&start=10`

### Other useful search-page links

- `Only show jobs with pay information`
- `Upload your resume`
- bottom CTA `Upload Your Resume`

## 5) Job detail structure

### Detail page layout

Job detail page is a clean SSR page with a strong `JobPosting` JSON-LD block and visible sections for pay, job type, and description.

### Top block

Visible fields:

- title: `Associate Software Engineer`
- company: `Morgan Stanley`
- rating: `3.8 out of 5 stars`
- location: `1585 Broadway Avenue, New York, NY 10036`
- salary: `$125,000 - $135,000 a year`
- job type: `Full-time`

### Apply gate

Before the actual company-site application flow, guest users see:

- text: `You must create an Indeed account before continuing to the company website to apply`
- button: `Apply on company site`

This is the key apply gate.

### Job details section

There is a structured `Job details` section with:

- `Pay`
- `Job type`

### Full description section

The `Full job description` area is rendered as paragraphs and lists.

Observed structure:

- one or more top-level paragraphs
- list of technologies
- `What you'll do in the role:`
- bullet list of responsibilities
- `What you'll bring to the role:`
- bullet list of requirements
- company boilerplate / benefits / EEO notice

### Job description content fields observed

The description included:

- enterprise context
- role summary
- tech stack
- responsibilities
- qualifications
- equal opportunity language

### Stable selectors for detail page

Primary:

- `h1`
- `[data-jk]` on title links from search results
- `button` with text `Apply on company site`
- `button` with text `Save job`
- `button` with text `Share Job`
- `h2` `Profile insights`
- `h2` `Job details`
- `h2` `Full job description`

Fallback:

- main content container under `main`
- text anchors by section title

## 6) Company profile structure

### Overview page

Company profile for Morgan Stanley is a rich public company page with:

- company logo
- company name
- work wellbeing score
- star rating
- follow button
- write a review link
- tabs for snapshot, why join us, reviews, salaries, jobs, Q&A, interviews

### Top metrics

Observed fields:

- Work wellbeing score: `71`
- star rating: `3.8 out of 5 stars`
- CEO approval shown inside snapshot block
- founded year: `1935`
- company size: `more than 10,000`
- revenue: `more than $10B (USD)`
- industry: `Investment & Asset Management`
- headquarters: `New York, NY`
- website link: `morganstanley.com`

### Tabs / navigation

Tabs visible on the page:

- Snapshot
- Why Join Us
- Reviews
- Salaries
- Jobs
- Q&A
- Interviews

### About the company section

Contains:

- company story paragraph
- `Show more`
- `Learn more`

### Jobs carousel

The company page includes a jobs card carousel with:

- slide count
- job title
- location
- pay
- posted age
- `View job` links

Observed examples:

- `Associate Software Engineer`
- `Senior Software Engineer`
- `Java Developer – Server Side (Associate)`
- `Front End Developer`
- `Full Stack Java/Python Developer`
- `AI Platform Engineer - Associate`

This is important because Indeed exposes company jobs through a separate canonical route:

- `/cmp/Morgan-Stanley/jobs?jk=<jobKey>`

### Company page JSON-LD

Confirmed structured data:

- `LocalBusiness`
- `BreadcrumbList`

No `JobPosting` JSON-LD on company page.

### Stable selectors for company page

Primary:

- `h1`
- tab links under `navigation "secondary"`
- `a[href$="/about"]`
- `a[href$="/reviews"]`
- `a[href$="/salaries"]`
- `a[href$="/jobs"]`
- `a[href$="/faq"]`
- `a[href$="/interviews"]`
- `a[href*="/cmp/<company>/jobs?jk="]`

Fallback:

- page title and visible company name
- snapshot card carousel text blocks

## 7) JSON-LD

### Job detail

Job detail page contains a full `script[type="application/ld+json"]` with `@type: "JobPosting"`.

Confirmed fields:

- `title`
- `description`
- `datePosted`
- `validThrough`
- `employmentType`
- `baseSalary`
- `hiringOrganization`
- `jobLocation`
- `directApply`

Important values from the observed example:

- `title`: `Associate Software Engineer`
- `employmentType`: `FULL_TIME`
- `currency`: `USD`
- `baseSalary.minValue`: `125000`
- `baseSalary.maxValue`: `135000`
- `unitText`: `YEAR`
- `directApply`: `false`
- `hiringOrganization.name`: `Morgan Stanley`

### Company page

Company page contains:

- `LocalBusiness`
- `BreadcrumbList`

This is useful for:

- company name canonicalization
- logo extraction
- category breadcrumb extraction

### Search/listing

Search page did **not** expose a useful `JobPosting` JSON-LD block in the observed session.

## 8) Network / XHR / API patterns

### Search page / autocomplete

Observed requests:

- `https://autocomplete.indeed.com/api/v0/initialLog?fetchOccupations=false`
- `https://autocomplete.indeed.com/api/v0/suggestions/cmp-what-with-top-companies?...`
- `https://autocomplete.indeed.com/api/v0/suggestions/location?...`

These are useful for autocomplete and search assist, not for the canonical job dataset.

### Detail page / related jobs

Observed request:

- `https://www.indeed.com/m/getcompetitorsjobs?jobKey=<jk>&limit=15`

This looks like a related jobs endpoint.

### Logging / telemetry

Observed requests:

- `https://www.indeed.com/m/rpc/log?...`
- `https://www.indeed.com/rpc/pageload/perf?...`
- `https://s.indeed.com/com.snowplowanalytics.snowplow/tp2`
- `https://sgtm.indeed.com/g/collect?...`

These are analytics/telemetry endpoints.

### Cloudflare / anti-bot

Observed challenge traffic:

- `https://challenges.cloudflare.com/cdn-cgi/challenge-platform/...`
- `https://challenges.cloudflare.com/.../turnstile/...`
- `https://challenges.cloudflare.com/.../pat/...`

This is an important signal that Indeed can involve Cloudflare challenge infrastructure in guest traffic.

### Response codes / notable failures

Observed:

- `401` on one Cloudflare `pat` request
- `400` on some dwell log requests
- `Not signed in with the identity provider`

## 9) Auth, captcha, anti-bot, redirect limitations

### Login wall

The most important gate is the apply flow modal:

- `Login window`
- text: `Create an account or sign in before applying on company site`
- buttons:
  - `Continue with Google`
  - `Continue with Apple`
  - `Continue`

The modal is inside an `iframe`.

### Turnstile signal

On the search page, the DOM includes a hidden field:

- `input[type="hidden"][name="cf-turnstile-response"]`

This is a strong sign of Cloudflare Turnstile integration.

### Console warnings / errors

Observed console messages included:

- Google One Tap / FedCM warning
- `Not signed in with the identity provider`
- Cloudflare challenge CSS/script warnings

### Practical implication

For a scraper:

1. Guest access is good for reading titles, descriptions, salaries, and company metadata.
2. Apply actions should be treated as gated.
3. Expect challenge/turnstile noise in some sessions and design retries/fallbacks around it.

## 10) Primary selectors

### Home

- `input[name="q"]`
- `input[name="l"]`
- `button[type="submit"]` with text `Search`

### Listing

- `input[name="q"]`
- `input[name="l"]`
- `button#fromAge_filter_button`
- `button#remote_filter_button`
- `button#filter-taxo1`
- `button#filter-jobtype1`
- `button#expLvl_filter_button`
- `button#salaryType_filter_button`
- `button#education_filter_button`
- `button#filter-taxo2`
- `button#filter-taxo3`
- `button#filter-taxo4`
- `button#filter-radius`
- `a.jcs-JobTitle[data-jk]`
- `a[aria-label="Next Page"]`
- `button` `Show more`

### Job detail

- `h1`
- `button` `Apply on company site`
- `button` `Save job`
- `button` `Share Job`
- `h2` `Profile insights`
- `h2` `Job details`
- `h2` `Full job description`

### Company page

- `h1`
- `button` `Follow`
- tab links under `navigation "secondary"`
- `a[href$="/jobs"]`
- `a[href$="/reviews"]`
- `a[href$="/salaries"]`
- `a[href$="/faq"]`
- `a[href$="/interviews"]`

## 11) Fallback selectors / heuristics

If semantic selectors shift, fallback in this order:

1. `data-jk` and `jk` query params.
2. Link text + `href` patterns (`/viewjob?jk=`, `/cmp/`, `/jobs?jk=`).
3. Accessibility labels for buttons and tabs.
4. Card text order inside the listing card.
5. Section headings on detail/company pages.

Useful job key sources:

- `a[href*="jk="]`
- `data-jk`
- `id="job_<jk>"`
- `id="sj_<jk>"`

## 12) Field -> source mapping

| Field | Primary source | Fallback |
|---|---|---|
| job key | `data-jk` on title anchor | `jk` query param in `href` |
| job title | `a.jcs-JobTitle` text | `h1` on detail page |
| company name | card company text / company link | detail page company link text |
| location | card location text | detail page location text |
| salary | card pay text or detail page pay block | `JobPosting.baseSalary` |
| posted date | card date text like `30+ days ago` | list page metadata / related links |
| job type | card pills / detail `Job type` | `JobPosting.employmentType` |
| description | detail page `Full job description` | `JobPosting.description` |
| apply URL | `Apply on company site` modal flow | `secure.indeed.com/auth` redirect chain |
| company page URL | `/cmp/<slug>` | company link in job detail |
| company rating | company profile header | review block |
| company size | company profile about section | JSON-LD `LocalBusiness` only gives name/logo, not size |
| company jobs | company page carousel / jobs tab | `/cmp/<slug>/jobs?jk=` |
| company website | company profile about section | external site link |

## 13) 2-pass parser strategy

### Pass 1: Search/listing harvest

Goal:

- collect `jobKey`
- collect title/company/location/pay/date/job type
- collect card hrefs and sponsor flags
- collect page-level filters and next-page URLs

Why:

- cheap
- can be paginated via `start=10`
- gives the set of canonical job keys

### Pass 2: Detail enrichment

For each `jk`:

- open `viewjob?jk=<jobKey>`
- parse `JobPosting` JSON-LD
- parse full description text
- parse pay and job type
- collect apply gate behavior
- collect company link and company metadata

Optional Pass 2b:

- open company profile
- parse company page JSON-LD and snapshot metadata
- collect jobs carousel if you need more jobs for the same company

### Suggested extraction order

1. Listing page
2. Job detail page
3. Company profile page
4. Apply/login modal state
5. Network log only for heuristics and anti-bot detection

## 14) Practical notes for scraper implementation

1. Do not rely on hashed classnames alone.
2. Use `data-jk` as the job canonical key.
3. Treat `rc/clk`, `pagead/clk`, and `viewjob` as different navigation wrappers over the same underlying job key.
4. Expect `Show more` and `Next Page` to coexist.
5. Expect guest access to work, but apply to be gated.
6. Preserve `start=` query param support for pagination.
7. Use JSON-LD as primary source on detail pages.
8. Use company page jobs carousel as enrichment, not primary canonical source.

## 15) Checked URLs

Observed live in this session:

- `https://www.indeed.com/`
- `https://www.indeed.com/jobs?q=software+engineer&l=New+York%2C+NY`
- `https://www.indeed.com/viewjob?jk=dbc110f85b4c9752`
- `https://www.indeed.com/cmp/Morgan-Stanley?campaignid=mobvjcmp&from=mobviewjob&tk=1jk7or0q4j56v804&fromjk=dbc110f85b4c9752`

Observed in DOM / network:

- `https://www.indeed.com/jobs?q=software+engineer&nl=&l=New+York%2C+NY&radius=50&start=10`
- `https://secure.indeed.com/auth?...`
- `https://autocomplete.indeed.com/api/v0/initialLog?fetchOccupations=false`
- `https://autocomplete.indeed.com/api/v0/suggestions/location?...`
- `https://autocomplete.indeed.com/api/v0/suggestions/cmp-what-with-top-companies?...`
- `https://www.indeed.com/m/getcompetitorsjobs?jobKey=899936460d5f938e&limit=15`
- `https://challenges.cloudflare.com/cdn-cgi/challenge-platform/...`
