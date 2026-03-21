# JobsDB parser report

## Scope
Этот отчет собран по `https://www.jobsdb.com/` и рабочему региональному сайту `https://hk.jobsdb.com/`, потому что корневой домен JobsDB выступает как хаб выбора региона, а фактический job board и company/apply flow живут на `hk.jobsdb.com`.

## Executive summary
JobsDB построен на **SEEK stack**: React, React Router, Apollo, GraphQL и большой слой аналитики/маркетинговых тегов. Для парсера это хороший кейс: на listing и detail страницах есть устойчивые семантические якоря, `data-*` атрибуты и богатое embedded state. Самый важный вывод: **job data лучше брать из DOM + Apollo state + GraphQL responses**, а не пытаться опираться только на HTML.

## Site map
### Root hub
`https://www.jobsdb.com/` не показывает вакансии напрямую. Это региональный хаб с выбором:
- Hong Kong
- Singapore
- Thailand

На этой странице есть:
- ссылки на региональные сайты
- чекбокс `Remember my selection`
- ссылки `About Jobsdb`, `Privacy statement`, `Terms & conditions`

### Hong Kong app
`https://hk.jobsdb.com/` и его job/search/company pages - это основной рабочий контур.

## Page types
### Home
Домашняя страница содержит:
- search form
- quick search blocks
- employer carousel
- dashboard/login prompts
- footer с job seeker / employer / about / contact links

### Listing / search results
Listing строится по canonical URL вида:
- `/software-engineer-jobs/in-Hong-Kong-SAR`
- `/...-jobs/in-<Location>`
- `/...-jobs?page=2`

### Job detail
Detail page открывается по:
- `/job/<jobId>?type=standard&ref=search-standalone...`

### Company profile
Company profile открывается по:
- `/companies/<company-slug-id>`

### Apply / auth wall
Apply flow уходит на:
- `/job/<jobId>/apply`
- затем на `login.seek.com` OAuth screen

## Home DOM structure
### Search form
Главный `form` на home:
- `action="https://hk.jobsdb.com/jobs"`
- method `GET`

Поле `What`:
- `input#keywords-input`
- `name="keywords"`
- `role="combobox"`
- placeholder: `Describe what you’re looking for (role, industry, skills...)`

Поле `Where`:
- `input#SearchBar__Where`
- `name="where"`
- `role="combobox"`
- placeholder: `Enter suburb, city, or region`

Button:
- `button#searchButton`
- aria-label: `Submit search`

### Home content
На home также есть:
- classification shortcuts
- city shortcuts
- employer carousel
- marketing banners
- sign in / register / employer site links

## Listing DOM structure
### Canonical wrapper
Search results page uses:
- `region "Search Results"`
- `article` cards with stable attributes

### Card-level selectors
Самый полезный якорь карточки:
- `article[data-automation="normalJob"]`
- `article[data-testid="job-card"]`
- `article[data-job-id="<id>"]`
- `article[data-card-type="JobCard"]`
- `id="jobcard-<n>"`
- `aria-label="<job title>"`

### Title and company
Внутри карточки:
- title: `h3 > a[href*="/job/"]`
- company link: `a[href^="/<Company>-jobs"]`
- company avatar/profile link: `a[href^="/companies/"]`
- location chips: `a[href*="/in-"]`

### Metadata fields
Типичные поля на карточке:
- listed time: `Listed twenty four days ago`, `22h ago`, `1d ago`
- work type: `This is a Full time job`
- location text and location refinement links
- classification/subClassification text
- urgency badges: `Urgently hiring`, `Expiring soon`, `Be an early applicant`
- teaser bullets / snippets

### Example card anatomy
Первая карточка на software engineer listing содержит:
- title
- company
- urgency badge
- full time label
- location links
- three bullet snippets
- short description
- classification and subClassification
- time listed
- `More` button
- `Sign in to save this job` button

## Listing URL patterns
Основные patterns:
- `/software-engineer-jobs/in-Hong-Kong-SAR`
- `/software-engineer-jobs/in-<District>`
- `/...-jobs?page=2`

Observed pagination:
- page 1: no query param
- page 2: `?page=2`
- page 3: `?page=3`
- `Prev` and `Next` are simple links

Observed related search paths:
- `/programmer-jobs/in-Hong-Kong-SAR`
- `/python-jobs/in-Hong-Kong-SAR`
- `/embedded-jobs/in-Hong-Kong-SAR`
- `/it-support-jobs/in-Hong-Kong-SAR`

## Filters
The filter rail is semantic and stable:
- classification
- salary range
- work type
- work arrangement
- date listed

Each filter is toggled with buttons like:
- `button[aria-label="refine by classifications"]`
- `button[aria-label="refine by salary range"]`
- `button[aria-label="refine by work type"]`
- `button[aria-label="refine by work arrangement"]`
- `button[aria-label="refine by date listed"]`

Inside filters there are many checkbox/radio inputs for classifications, including:
- `Information & Communication Technology`
- `Engineering`
- `Sales`
- `Marketing & Communications`
- `Science & Technology`
- and many more

## Job detail DOM structure
### Canonical detail wrapper
Detail pages are anchored by:
- `h1` for job title
- company button/link
- `Quick apply` CTA
- `Save` button

### Top metadata
Top block contains:
- urgency badge
- job title
- company name button
- `View all jobs` company link
- location link
- classification link
- work type link
- salary insight teaser
- posted time

### Primary CTAs
Important apply/save selectors:
- `a[href^="/job/<id>/apply"]`
- button `Save`
- button `Share or report ad`

### Description sections
The description area is split into semantic sections:
- `Responsibilities:`
- `Requirements:`
- `Application Instructions:`

The content is mostly plain DOM text inside `p`, `ul`, `li` blocks.

### Employer questions
The detail page exposes pre-screen questions directly in DOM:
- right to work in Hong Kong
- expected monthly basic salary
- years of experience as software engineer
- years of experience in software development role

### Insights block
There is an `Unlock job insights` block with:
- hirer responsiveness
- salary match
- number of applicants

### Safety/reporting
There is also:
- `Report this job advert`
- security reminder
- salary teaser link

## Company profile DOM structure
### Company page wrapper
Company profile pages use:
- `h1` company profile title
- `tablist` with tabs:
  - About
  - Life and Culture
  - Jobs
  - Reviews

### About tab
The About tab exposes:
- industry
- company size
- primary location
- company overview text

### Jobs on company page
The company page has a jobs section with job cards similar to listing cards.
Useful selectors:
- `article`
- `h3 a[href*="/job/"]`
- company name text
- location text
- classification/subClassification text
- posted time
- `More`
- `Sign in to save this job`

### Reviews section
The Reviews tab exposes:
- review summary
- recent review content
- rating text
- review author / role / date
- link to full reviews

### Company profile disclaimer
The page explicitly says the profile can include:
- job postings
- company websites
- third-party databases
- AI-generated content

That matters for parser trust: treat company profile fields as **aggregated** rather than canonical.

## Apply flow
`/job/<id>/apply` does not stay on JobsDB.
Observed flow:
1. `https://hk.jobsdb.com/job/<id>/apply`
2. redirect to `https://login.seek.com/login?...`
3. page title becomes `Candidate Sign In - SEEK`
4. the sign-in page shows:
  - Continue with Google
  - Continue with Facebook
  - Continue with Apple
  - Email address
  - `Email me a sign in code`
  - `Register`

This means apply is **login-gated** and uses SEEK OAuth flow.

## Structured data
### Listing and detail
На проверенных page types не нашел полноценный `JobPosting` JSON-LD.

### Home / site-level JSON-LD
Observed JSON-LD:
- `@type: WebSite`
- `SearchAction`
- target pattern: `https://hk.jobsdb.com/{search_term_string}-jobs`

### Conclusion
For JobsDB, **structured data is not the primary job source**. The better sources are:
- DOM
- Apollo data
- GraphQL

## Embedded state
This is one of the strongest signals on the site.

Observed window globals:
- `__staticRouterHydrationData`
- `SEEK_CONFIG`
- `SEEK_APP_CONFIG`
- `SEEK_APOLLO_DATA`
- `__LOADABLE_LOADED_CHUNKS__`
- `__APOLLO_CLIENT__`
- `SEEK_INITIAL_LOAD_COMPLETE`
- `utag_data`

### What these contain
- `SEEK_CONFIG`: API endpoint names, sign-in path, analytics flags, metrics hosts
- `SEEK_APP_CONFIG`: zone, locale, brand, country, available locales, site features
- `SEEK_APOLLO_DATA`: feature flags and experiments
- `__staticRouterHydrationData`: loader/action/error state for React Router
- `utag_data`: tracking metadata, session ids, anonymous ids, region ids

### Why it matters
This makes JobsDB a very good target for parser enrichment:
- canonical job data can be extracted from DOM
- extra fields and experimental state can be inferred from Apollo/loader payloads
- query state can be replayed using route patterns

## Network / XHR
### Main data endpoint
Observed:
- `POST https://hk.jobsdb.com/graphql`

This is the primary application data transport.

### Other important requests
Observed tracking and integrations:
- Google Analytics / gtag
- Bing / Clarity
- Branch
- Segment
- LinkedIn attribution
- Qualtrics intercept
- Google Ads / DoubleClick conversions
- lcto.aips-sol.com event endpoint

### Parser implication
The useful data is likely in GraphQL responses and React/Apollo state, not in those marketing requests.

## Anti-bot / auth
### Public side
No classic Cloudflare challenge or hard CAPTCHA was observed on public pages.

### Gated operations
The real gate is auth:
- saved jobs
- saved searches
- application history
- job apply
- save job on listing and detail pages

### Login wall
The login wall is not a dead end; it is a full SEEK auth flow.

## Stable selectors
### Home
- `form[action="https://hk.jobsdb.com/jobs"]`
- `input#keywords-input`
- `input#SearchBar__Where`
- `button#searchButton`

### Listing
- `article[data-automation="normalJob"]`
- `article[data-testid="job-card"]`
- `article[data-job-id]`
- `article[data-card-type="JobCard"]`
- `h3 a[href*="/job/"]`
- `a[href^="/companies/"]`
- `a[href*="/jobs/in-"]`
- `button[aria-label="Sign in to save this job"]`
- `button[aria-label="More"]`

### Detail
- `h1`
- `a[href$="/apply"]`
- `button[aria-label*="Save"]`
- `button[aria-label*="Share or report ad"]`
- section headings like `Responsibilities:`, `Requirements:`, `Application Instructions:`

### Company
- `tablist`
- `tab[aria-selected="true"]`
- company overview headings
- `article` cards under jobs section

### Fallback strategy
If the CSS classes drift:
1. prefer semantic roles and text labels
2. prefer `data-*` attributes
3. prefer URL patterns
4. use Apollo/GraphQL payloads as backup

## Field mapping
| Field | Primary source | Fallback |
|---|---|---|
| job_id | `article[data-job-id]` / `/job/<id>` URL | GraphQL response |
| title | `h3 a` / `h1` on detail | page `<title>` |
| company_name | company link text / company button | GraphQL payload |
| company_url | `/Company-jobs` or `/companies/...` links | detail page buttons |
| location | chip text and location links | page title / breadcrumbs |
| classification | `classification:` text | GraphQL payload |
| sub_classification | `subClassification:` text | GraphQL payload |
| work_type | `This is a Full time job` | structured job metadata in GraphQL |
| posted_at | `Listed ... ago` / `Posted ... ago` | GraphQL payload |
| description | card snippet / detail body | GraphQL payload |
| responsibilities | detail section text | DOM list items |
| requirements | detail section text | DOM list items |
| application_questions | Employer questions block | login/apply flow payload |
| apply_url | `/job/<id>/apply` | button/link href on detail |
| company_profile_industry | company profile about tab | GraphQL/profile payload |
| company_size | company profile about tab | GraphQL/profile payload |
| company_primary_location | company profile about tab | GraphQL/profile payload |

## 2-pass parser strategy
### Pass 1
Collect broad job data:
- listing pages
- pagination pages
- job ids
- titles
- companies
- locations
- classification/subClassification
- posted time
- teaser descriptions

### Pass 2
Enrich selected job ids:
- open detail page
- extract responsibilities and requirements
- capture application questions
- capture company profile
- record apply/login redirects
- record GraphQL payloads for missing fields

## Notes for implementation
- JobsDB is **not** a pure HTML scraper target; it is a hybrid DOM + Apollo + GraphQL app.
- The best canonical route format is based on slugged job pages, not query-string search pages.
- Apply is always login gated through SEEK.
- Company profiles are useful, but some text is aggregated and can be stale; treat them as enrichment, not authority.

## Checked URLs
- `https://www.jobsdb.com/`
- `https://hk.jobsdb.com/`
- `https://hk.jobsdb.com/software-engineer-jobs/in-Hong-Kong-SAR`
- `https://hk.jobsdb.com/job/91071229?type=standard&ref=search-standalone&origin=jobCard#sol=ee19935a8d49d62c667666ff9c367b0ade5b5aff`
- `https://hk.jobsdb.com/job/91071229/apply`
- `https://login.seek.com/login?...`
- `https://hk.jobsdb.com/companies/sportshouse-limited-171089280579079`

## Browser shutdown
MCP browser session was closed after the scan so the next agent can start with a clean profile.
