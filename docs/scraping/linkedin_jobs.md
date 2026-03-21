# LinkedIn Jobs — DOM/HTML report for scraping

Дата проверки: 2026-03-21
Источник данных: сохраненные Playwright HTML-снапшоты гостевых страниц LinkedIn Jobs в этом workspace, плюс локальные DOM-артефакты из браузерной сессии.

Важно: после очистки профиля встроенный Playwright MCP в этом треде перестал отвечать через `Transport closed`, поэтому я продолжил на уже снятых live HTML-страницах из той же браузерной среды. Это не синтетика, а реальные HTML/DOM артефакты гостевого доступа.

## 1) Что реально доступно без логина

Гостю доступны три основные поверхности:

1. Search/listing page с результатами jobs, фильтрами, пагинацией и infinite scroller.
2. Job detail page с полноценным `JobPosting` JSON-LD, описанием, зарплатой, критериями и блоком похожих вакансий.
3. Company overview page с описанием компании, метаданными, постами, employees, locations и CTA на jobs.

Что закрыто или частично закрыто:

1. Apply flow почти везде ведет в contextual sign-in modal.
2. Часть действий наружу идет через `session_redirect` и требует логина.
3. Персонализированные действия вроде follow, see who was hired, referral, alerts, comment/share в основном редиректят на sign-in / join.

## 2) Ключевые URL-паттерны

### Search/listing

Основные варианты:

- `/jobs/search/?keywords=software%20engineer&location=United%20States`
- canonical shortcut: `/jobs/software-engineer-jobs`

Внутри ссылок на карточках часто видны параметры:

- `position=N`
- `pageNum=0`
- `refId=...`
- `trackingId=...`

### Job detail

- `/jobs/view/{slug}-{jobId}?position=N&pageNum=0&refId=...&trackingId=...`

Пример из снапшота:

- `https://www.linkedin.com/jobs/view/software-engineer-new-grads-new-york-at-giga-4374834620?...`

### Company overview

- `/company/{companySlug}`

Пример:

- `https://www.linkedin.com/company/gigaml`

### Redirect / auth

- `/login?session_redirect=...`
- `/signup/cold-join?session_redirect=...`
- `/redir/redirect?url=...&urlhash=...`
- `/uas/login-submit`

## 3) Search page structure

### Head / meta

На guest search странице присутствуют:

- `meta name="pageKey" content="d_jobs_guest_search"`
- `meta name="robots" content="max-image-preview:large, noarchive"`
- `meta name="bingbot" content="max-image-preview:large, archive"`
- `meta property="lnkd:url"` с canonical search URL
- `meta name="clientSideIngraphs"` с endpoints для gauge/counter
- `meta id="config"` с `data-app-version`, `data-service-name="jobs-guest-frontend"`, `data-member-id="0"`

Семантически это guest SSR-страница. Она не отдает `__NEXT_DATA__`, `__APOLLO_STATE__` или подобный hydration blob. Вместо этого есть SSR DOM + несколько light JS-объектов (`window.lazyloader`, `window.tracking`, `window.ingraphTracking` и т.д.).

### Layout root

Корневой контейнер:

- `div.base-serp-page`

Полезные узлы:

- `a.skip-link[href="#main-content"]`
- `header.base-serp-page__header`
- `nav[aria-label="Primary"]`
- `section.search-bar[data-current-search-type="JOBS"]`
- `section.base-search-bar#jobs-search-panel`
- `form.base-search-bar__form[action="/jobs/search"]`
- `form.filters__form#jserp-filters[action="https://www.linkedin.com/jobs/search/"]`
- `section.two-pane-serp-page__results-list`
- `ul.jobs-search__results-list`
- `button.infinite-scroller__show-more-button`

### Search bar / switcher

Верхняя панель содержит switcher tabs:

- Jobs
- People
- Learning

Ключевые селекторы:

- `button#job-switcher-tab`
- `button#people-switcher-tab`
- `button#learning-switcher-tab`
- `button.search-bar__placeholder`
- `button.switcher-tabs__placeholder`

Для job search panel форма использует `action="/jobs/search"`.

### Filters

Фильтры живут в `form#jserp-filters`.

Стабильные filter names:

- `f_TPR` — Date posted
- `f_JT` — Job type
- `f_E` — Experience level
- `f_PP` — Location
- `f_SB2` — Salary
- `f_WT` — Remote
- `f_C` — Company

Наблюдения по DOM:

- Каждый фильтр открывается как `button.filter__dropdown-to-modal-trigger`.
- Внутри дропдауна используются `input` + `label` пары.
- Списки вариантов находятся в `div.filter-values-container`.
- Модальные typeahead-поля используют `section.dismissable-input.typeahead-input`.

Typeahead API sources:

- `data-base-api-url="/jobs-guest/api/typeaheadHits?typeaheadType=COMPANY"`
- `data-base-api-url="/jobs-guest/api/typeaheadHits?origin=jserp&typeaheadType=GEO&geoTypes=POPULATED_PLACE"`

Примеры значений:

- `f_TPR`: `r2592000`, `r604800`, `r86400`
- `f_JT`: `F`, `P`, `C`, `T`, `V`
- `f_E`: `1`..`5`
- `f_SB2`: `1`..`5`
- `f_WT`: `1`, `3`, `2`
- `f_C`: company ids
- `f_PP`: location ids

### Listing cards

Список вакансий:

- `ul.jobs-search__results-list > li`
- внутри карточка `div.base-card.base-search-card.base-search-card--link.job-search-card`

Стабильные data-*:

- `data-entity-urn="urn:li:jobPosting:..."`
- `data-impression-id="jobs-search-desktop-N"`
- `data-reference-id="..."`
- `data-tracking-id="..."`
- `data-column="1"`
- `data-row="N"`

Карточка содержит:

- full-card anchor: `a.base-card__full-link`
- title: `h3.base-search-card__title`
- company link: `h4.base-search-card__subtitle a.hidden-nested-link`
- location: `span.job-search-card__location`
- posted date: `time.job-search-card__listdate[datetime]`
- logo/image: `img.artdeco-entity-image--square-4`

Что важно:

- Большинство search cards не показывают salary.
- Company link часто ведет на public company page.
- Full-card anchor ведет на job detail page.
- `span.sr-only` внутри anchor дублирует title для accessibility.

### Search page pagination / infinite scroll

- Явный control: `button.infinite-scroller__show-more-button[aria-label="See more jobs"]`
- URL-логика строится через `position`, `pageNum`, `refId`, `trackingId`
- Для листинга это не классическая numbered pagination, а load-more/infinite-style scroller.

## 4) Job detail structure

### Head / meta

На detail page присутствуют:

- `meta name="pageKey" content="d_jobs_guest_details"`
- canonical на `https://www.linkedin.com/jobs/view/...`
- `meta property="lnkd:url"` с tracking-версией URL
- `meta name="titleId"`
- `meta name="companyId"`
- `meta name="industryIds"`
- `meta name="robots" content="max-image-preview:large, noarchive"`

### Canonical data source: JSON-LD

На job detail есть полноценный:

- `script[type="application/ld+json"]`
- `@type: "JobPosting"`

Поля, которые реально есть и полезны для парсинга:

- `title`
- `description`
- `datePosted`
- `validThrough`
- `employmentType`
- `hiringOrganization.name`
- `hiringOrganization.sameAs`
- `hiringOrganization.logo`
- `identifier.value`
- `image`
- `industry`
- `jobLocation.address.addressLocality`
- `jobLocation.address.addressRegion`
- `jobLocation.address.addressCountry`
- `jobLocation.latitude`
- `jobLocation.longitude`
- `educationRequirements.credentialCategory`
- `baseSalary.currency`
- `baseSalary.value.minValue`
- `baseSalary.value.maxValue`
- `baseSalary.value.unitText`

Для этого job detail JSON-LD — лучший primary source. DOM нужен как fallback и для дополнительных UI-only блоков.

### Top card

Главный контейнер вакансии:

- `section.top-card-layout`
- `div.top-card-layout__card`
- `h1.top-card-layout__title.topcard__title`
- `a.topcard__org-name-link`
- `span.topcard__flavor--bullet` для location
- `span.posted-time-ago__text`
- `figcaption.num-applicants__caption`

Наблюдаемые поля:

- title: `Software Engineer (New Grads) - New York`
- company: `Giga`
- location: `New York, NY`
- posted time: `2 days ago`
- applicants: `Over 200 applicants`

### Apply CTA / auth wall

Guest apply не ведет к настоящей подаче. Вместо этого:

- `button#topbar-apply.sign-up-modal__outlet`
- `button.top-card-layout__cta.top-card-layout__cta--primary`
- `data-modal="job-details-topcard-apply-modal"`

Под капотом открывается modal:

- `div#job-details-topcard-apply-modal.modal--contextual-sign-in`
- `section[role="dialog"]`
- header: `Join or sign in to find your next job`
- subtitle: `Join to apply for the ... role at ...`
- Google auth placeholder: `div.google-auth-button__placeholder[aria-label="Continue with google"]`
- sign-in form: `form[data-id="sign-in-form"]`
- login endpoint: `action="https://www.linkedin.com/uas/login-submit"`
- hidden CSRF: `input[name="loginCsrfParam"]`
- hidden redirect: `input[name="session_redirect"]`

То же самое повторяется в `job-details-subnav-apply-modal`.

### Description block

Описание живет здесь:

- `section.core-section-container.description`
- `div.description__text.description__text--rich`
- `section.show-more-less-html[data-max-lines="5"]`
- `div.show-more-less-html__markup`

Внутри markup лежит HTML с:

- `strong`
- `br`
- `ul`
- `li`
- plain text

Это означает, что при парсинге описание лучше брать как HTML-fragment, а потом рендерить/очищать локально. Не стоит полагаться только на innerText, потому что потеряются списки и структура.

### Compensation block

Если зарплата показана гостю, она находится в:

- `section.core-section-container.compensation`
- `div.compensation__salary-range`
- `div.salary.compensation__salary`

Пример значения:

- `$160,000.00/yr - $250,000.00/yr`

В JSON-LD это уже нормализовано в `baseSalary`.

### Criteria block

Критерии вакансии:

- `ul.description__job-criteria-list`
- `li.description__job-criteria-item`
- `h3.description__job-criteria-subheader`
- `span.description__job-criteria-text--criteria`

Наблюдаемые поля:

- Seniority level: `Entry level`
- Employment type: `Full-time`
- Job function: `Engineering and Information Technology`
- Industries: `Software Development`

### Referral / similar / alert / metadata blocks

На detail странице видны дополнительные секции:

- `section.find-a-referral`
- `section.job-alert-redirect-section`
- `section.similar-jobs` или блоки с `main-job-card`
- hidden `code#currentJobId`

Полезные элементы:

- `a.find-a-referral__cta`
- `a.job-alert-redirect-section__cta`
- `a.base-card__full-link[data-tracking-control-name="public_jobs_similar-jobs"]`
- `div.main-job-card[data-entity-urn^="urn:li:jobPosting:"]`

Similar jobs cards повторяют карточный паттерн:

- root `div.base-card.base-main-card.main-job-card`
- anchor `a.base-card__full-link`
- title `h3.base-main-card__title`
- company `h4.base-main-card__subtitle a.hidden-nested-link`
- location `span.main-job-card__location`
- salary `span.main-job-card__salary-info` если показана
- date `time.main-job-card__listdate[datetime]`

## 5) Company page structure

### Head / meta

На guest company page присутствуют:

- `meta name="pageKey" content="d_org_guest_company_overview"`
- canonical `/company/gigaml`
- alternates hreflang
- `meta property="og:*"`
- `meta name="clientSideIngraphs"` с `/organization-guest/api/ingraphs/gauge` и `/counter`
- `meta name="linkedin:pageTag" content="noncanonical_subdomain=control"`

### Canonical structured data

Есть `script[type="application/ld+json"]` с `@graph`, где содержатся:

- `Organization` для компании
- `DiscussionForumPosting` для свежих company feed posts

Для `Organization` полезные поля:

- `name`
- `url`
- `address.addressLocality`
- `address.addressRegion`
- `address.addressCountry`
- `description`
- `numberOfEmployees.value`
- `logo.contentUrl`
- `slogan`
- `sameAs`

### Top card

Основные узлы:

- `section.top-card-layout`
- `figure.cover-img`
- `img.cover-img__image`
- `img.top-card-layout__entity-image`
- `h1.top-card-layout__title`
- `h2.top-card-layout__headline`
- `h3.top-card-layout__first-subline`
- `h4.top-card-layout__second-subline`
- `div.top-card-layout__cta-container`

Поля на странице Giga:

- company name: `Giga`
- headline: `Software Development`
- location + followers: `San Francisco, California · 27,035 followers`
- tagline: `Reprogram each of the world’s largest companies using AI, reaching every person on Earth.`

### Primary CTAs

- `a.top-card-layout__cta--primary` -> `See jobs`
- `a.top-card-layout__cta--secondary` -> `Follow`

Useful job CTA pattern:

- `https://www.linkedin.com/jobs/giga-jobs-worldwide?f_C=87441542`

### About us block

Реальная DOM-структура:

- `section[data-test-id="about-us"]`
- `p[data-test-id="about-us__description"]`
- `div[data-test-id="about-us__website"]`
- `div[data-test-id="about-us__industry"]`
- `div[data-test-id="about-us__size"]`
- `div[data-test-id="about-us__headquarters"]`
- `div[data-test-id="about-us__organizationType"]`

Поля:

- Website: external redirect link через `/redir/redirect?url=https%3A%2F%2Fgiga.ai&urlhash=...`
- Industry: `Software Development`
- Company size: `51-200 employees`
- Headquarters: `San Francisco, California`
- Type: `Privately Held`

### Employees section

- `section[data-test-id="employees-at"]`
- `a[data-tracking-control-name="org-employees"]`
- `div.base-main-card`
- `h3.base-main-card__title`
- `img[alt="Click here to view ... profile"]`

Guest sees a limited employee preview and a CTA to see all employees, which redirects to sign-in.

### Locations section

- `section.locations`
- `ul.show-more-less__list`
- `li`
- `span.tag-sm.tag-enabled` for `Primary`
- `p` address text
- `a[href*="bing.com/maps"]` for directions

### Feed / posts area

The company page includes a feed with guest-visible posts.

Important hidden refs:

- `code#feedUpdatesBaseUrl`
- `code#paginationToken`

Example feed URL:

- `/organization-guest/api/feedUpdates/87441542?paginationToken=...`

This is a very useful hidden API pattern for paging company feed content.

## 6) Auth wall, apply gating, and legal signals

### What redirects to login / signup

Observed redirect behaviors:

- Apply button on job detail opens contextual sign-in modal.
- `See who Giga has hired for this role` redirects to login with `search/results/people` and company/title filters.
- `Follow` on company page redirects to login.
- `See all employees` redirects to signup/login.
- Some guest actions use `/login?session_redirect=...`.
- Some use `/signup/cold-join?session_redirect=...`.

### Legal / policy links in modals

Login modal explicitly links:

- `/legal/user-agreement`
- `/legal/privacy-policy`
- `/legal/cookie-policy`

### Robots / crawl signals

Search and job detail pages both expose:

- `meta name="robots" content="max-image-preview:large, noarchive"`
- `meta name="bingbot" content="max-image-preview:large, archive"`

What this means for the scraper:

- These pages are crawlable in the sense that they render HTML to guests.
- There is no `noindex` in the captured snapshots.
- `noarchive` signals are present.
- Some actions are clearly intended to stay behind a login wall.

### Hidden CSRF / session data

Login forms on job detail use:

- `input[name="loginCsrfParam"]`
- `input[name="session_redirect"]`

The CSRF token value is embedded in SSR HTML. That makes the modal itself parseable, but it does not make apply possible without auth.

## 7) Network / XHR patterns

### Guest ingraph metrics

Search page:

- `/jobs-guest/api/ingraphs/gauge`
- `/jobs-guest/api/ingraphs/counter`

Company page:

- `/organization-guest/api/ingraphs/gauge`
- `/organization-guest/api/ingraphs/counter`

### Typeahead APIs

Search page uses:

- `/jobs-guest/api/typeaheadHits?typeaheadType=COMPANY`
- `/jobs-guest/api/typeaheadHits?origin=jserp&typeaheadType=GEO&geoTypes=POPULATED_PLACE`

### Company feed API

Company page hidden refs give:

- `/organization-guest/api/feedUpdates/{companyId}?paginationToken=...`

### Login endpoint

- `/uas/login-submit`

## 8) Stable selectors and fallback selectors

### Search/listing primary selectors

- `ul.jobs-search__results-list`
- `div.base-search-card.job-search-card[data-entity-urn^="urn:li:jobPosting:"]`
- `a.base-card__full-link[href*="/jobs/view/"]`
- `h3.base-search-card__title`
- `h4.base-search-card__subtitle a.hidden-nested-link`
- `span.job-search-card__location`
- `time.job-search-card__listdate[datetime]`

### Search/listing fallback selectors

- `div.base-card.base-search-card`
- `li > div[data-entity-urn]`
- `a[data-tracking-control-name="public_jobs_jserp-result_search-card"]`
- `a[data-tracking-control-name="public_jobs_jserp-result_job-search-card-subtitle"]`

### Job detail primary selectors

- `script[type="application/ld+json"]`
- `section.top-card-layout`
- `h1.top-card-layout__title.topcard__title`
- `a.topcard__org-name-link`
- `span.topcard__flavor--bullet`
- `span.posted-time-ago__text`
- `figcaption.num-applicants__caption`
- `button#topbar-apply`
- `section.core-section-container.description`
- `div.show-more-less-html__markup`
- `ul.description__job-criteria-list`
- `section.core-section-container.compensation`
- `section.similar-jobs`
- `div.main-job-card[data-entity-urn^="urn:li:jobPosting:"]`

### Job detail fallback selectors

- `a[data-tracking-control-name="public_jobs_topcard-org-name"]`
- `a[data-tracking-control-name="public_jobs_topcard_logo"]`
- `button[data-modal="job-details-topcard-apply-modal"]`
- `button[data-modal="job-details-subnav-apply-modal"]`
- `div.description__text--rich`
- `section.show-more-less-html`
- `span.compensation__salary`
- `li.description__job-criteria-item`

### Company page primary selectors

- `section.top-card-layout`
- `h1.top-card-layout__title`
- `h2.top-card-layout__headline`
- `h3.top-card-layout__first-subline`
- `h4.top-card-layout__second-subline`
- `a.top-card-layout__cta--primary`
- `a.top-card-layout__cta--secondary`
- `section[data-test-id="about-us"]`
- `p[data-test-id="about-us__description"]`
- `div[data-test-id="about-us__website"]`
- `div[data-test-id="about-us__industry"]`
- `div[data-test-id="about-us__size"]`
- `div[data-test-id="about-us__headquarters"]`
- `div[data-test-id="about-us__organizationType"]`
- `section.locations`
- `section[data-test-id="employees-at"]`

### Company page fallback selectors

- `a[href*="/company/"][data-tracking-control-name*="top-card"]`
- `a[href*="/jobs/"][href*="f_C="]`
- `a[href*="bing.com/maps"]`
- `a[href*="/redir/redirect?url="]`
- `code#feedUpdatesBaseUrl`
- `code#paginationToken`

## 9) Mapping table

### Search/listing mapping

| Field | Primary source | Fallback |
|---|---|---|
| job title | `h3.base-search-card__title` | `span.sr-only` inside `a.base-card__full-link` |
| company | `h4.base-search-card__subtitle a.hidden-nested-link` | anchor href `/company/...` |
| location | `span.job-search-card__location` | card text / `lnkd:url` params |
| posted date | `time.job-search-card__listdate[datetime]` | visible relative text |
| job URL | `a.base-card__full-link[href*="/jobs/view/"]` | `data-entity-urn` + tracking attrs |
| job urn/id | `data-entity-urn` | job URL slug/id |

### Job detail mapping

| Field | Primary source | Fallback |
|---|---|---|
| title | `h1.top-card-layout__title.topcard__title` | JSON-LD `title` |
| company | `a.topcard__org-name-link` | JSON-LD `hiringOrganization.name` |
| location | `span.topcard__flavor--bullet` | JSON-LD `jobLocation.address.*` |
| posted time | `span.posted-time-ago__text` | JSON-LD `datePosted` |
| applicants | `figcaption.num-applicants__caption` | absent if not exposed |
| salary | `div.salary.compensation__salary` | JSON-LD `baseSalary` |
| description | `div.show-more-less-html__markup` | JSON-LD `description` |
| employment type | `span.description__job-criteria-text--criteria` under Employment type | JSON-LD `employmentType` |
| seniority | criteria list | absent in JSON-LD |
| industries | criteria list | JSON-LD `industry` |
| apply URL | modal CTA / redirect | not public without auth |
| company URL | `a.topcard__org-name-link` | JSON-LD `hiringOrganization.sameAs` |

### Company page mapping

| Field | Primary source | Fallback |
|---|---|---|
| company name | `h1.top-card-layout__title` | JSON-LD `Organization.name` |
| tagline | `h4.top-card-layout__second-subline` | JSON-LD `Organization.slogan` |
| industry | `h2.top-card-layout__headline` | about-us `Industry` |
| followers | `h3.top-card-layout__first-subline` | visible text only |
| website | `div[data-test-id="about-us__website"] a` | JSON-LD `sameAs` / redirected href |
| size | `div[data-test-id="about-us__size"] dd` | JSON-LD `numberOfEmployees.value` |
| headquarters | `div[data-test-id="about-us__headquarters"] dd` | JSON-LD `address` |
| type | `div[data-test-id="about-us__organizationType"] dd` | absent in JSON-LD |
| feed URL | `code#feedUpdatesBaseUrl` | infer from company id |

## 10) Parser strategy in 2 passes

### Pass 1: Search/listing harvest

Goal: collect the universe of candidate jobs with minimal network cost.

Steps:

1. Load search page for target keyword/location.
2. Read `ul.jobs-search__results-list`.
3. For each card, store:
   - job URL
   - job urn/id
   - title
   - company
   - location
   - posted date
   - page position / row
   - tracking ids
4. Use `button.infinite-scroller__show-more-button` to load more results.
5. Apply filters through `form#jserp-filters` if needed.
6. Persist deduped job URLs for pass 2.

Why this works well:

- Search page gives stable job URLs and enough metadata to rank candidates.
- Guest listing is SSR and easy to parse.
- Result cards are uniform across many pages.

### Pass 2: Detail enrichment

Goal: for each unique job URL, extract canonical structured data and rich text.

Steps:

1. Open job detail URL.
2. Parse `script[type="application/ld+json"]` first.
3. Parse top card DOM for title/company/location/applicants.
4. Parse description HTML fragment from `div.show-more-less-html__markup`.
5. Parse compensation and criteria list from DOM.
6. Capture auth wall state if apply is blocked.
7. Extract company URL and similar jobs links.
8. Optionally queue company overview page for enrichment.

Why this works well:

- JSON-LD is the most stable canonical source for job detail.
- DOM adds UI-only facts not always present in structured data.
- Apply and similar-jobs blocks reveal extra relational data.

### Optional company enrichment pass

If company metadata matters:

1. Open company page from job detail or search result.
2. Parse top card.
3. Parse about-us section.
4. Parse employees preview.
5. Parse locations.
6. Parse feed updates using hidden `feedUpdatesBaseUrl`.

## 11) Risks and limitations

1. Guest pages are usable, but many conversion actions redirect to sign-in.
2. Search card salaries are often absent even for senior roles.
3. Apply is offsite / gated and cannot be completed unauthenticated.
4. Company feed data is paginated via hidden token, not obvious visible pagination.
5. CSS class names are verbose but mostly stable SSR classes; still, prefer data-test-id and JSON-LD where possible.
6. LinkedIn guest pages are sensitive to anti-bot and session reuse issues; for scraping, a clean session per run is safer than a shared browser profile.

## 12) Checked URLs

- `https://www.linkedin.com/jobs/software-engineer-jobs`
- `https://www.linkedin.com/jobs/search/?keywords=software%20engineer&location=United%20States`
- `https://www.linkedin.com/jobs/view/software-engineer-new-grads-new-york-at-giga-4374834620?position=1&pageNum=0&refId=Ud9+lxnS7pHgmBj67/4CkQ==&trackingId=KrLAjwTAbur0p1vghYgwsQ==`
- `https://www.linkedin.com/company/gigaml`
- `https://www.linkedin.com/login?session_redirect=...`
- `https://www.linkedin.com/signup/cold-join?session_redirect=...`
- `https://www.linkedin.com/uas/login-submit`
- `https://www.linkedin.com/redir/redirect?url=https%3A%2F%2Fgiga.ai&urlhash=GvR3&trk=about_website`
- `https://www.linkedin.com/jobs/giga-jobs-worldwide?f_C=87441542`
- `https://www.linkedin.com/search/results/people/?facetCurrentCompany=[87441542]`
- `https://www.linkedin.com/jobs/view/software-engineer-at-flip-4328940373?refId=...`
