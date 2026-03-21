# No Fluff Jobs parser report

Дата скана: 2026-03-21
Источник: live scan через Playwright browser tools

## Короткий вывод

`nofluffjobs.com` выглядит как **JS-heavy job board**, но при этом у него очень хорошие якоря для парсинга: стабильные `id`, полезные `data-cy`, отдельные API для поиска и зарплатного калькулятора, а также предсказуемые URL-паттерны для job detail и company page. Самый сильный слой для извлечения данных здесь не JSON-LD, а **HTML + internal API**.

## Карта страниц

Проверенные типы страниц:

| Тип | Пример URL | Что важно |
| --- | --- | --- |
| Home | `https://nofluffjobs.com/` | hero search, offers of the day, most popular, footer links |
| Search/listing | `https://nofluffjobs.com/Python` | filters, search results, salary match, pagination/load more |
| Job detail | `https://nofluffjobs.com/job/software-engineer-python-link-group-remote` | title, company, salary, requirements, apply/save/analyze CV |
| Company page | `https://nofluffjobs.com/company/link-group-ccywok00` | company profile, values, team, timeline, company jobs |

## URL patterns

Наблюдаемые паттерны:

| Паттерн | Значение |
| --- | --- |
| `/<Technology>` | тематическая выдача, например `/Python` |
| `/<category>/<technology>` | вложенная выдача, например `/backend/python` |
| `/remote?criteria=...` | выдача по локации и критерию |
| `/job/<slug>` | job detail |
| `/company/<slug>` | company page |
| `/companies` | каталог компаний |
| `/wizard` | post a job flow |

## Home page

На главной странице важны:

| Элемент | Наблюдение |
| --- | --- |
| Navbar | `nfj-navbar-menu` с `job offers`, `companies`, `salary calculator`, `for employers`, `pricing`, `post a job`, `log in` |
| Search input | `textbox "main search input"` |
| Featured offers | блок `Offers of the day` с карточками вакансий |
| Popular categories | табы `Category`, `Job location`, `Job technology` |
| Footer | ссылки на about, GDPR, privacy, terms, social links |

### Полезные селекторы home

| Поле | Primary selector | Fallback |
| --- | --- | --- |
| Main search | `textbox[aria-label="main search input"]` | `input[placeholder*="offers"]` |
| Navbar | `#navbarNav` | `nfj-navbar-menu` |
| Popular categories | `tablist` / `tabpanel` | headings `Backend`, `Frontend`, etc. |

## Search / listing page

Поиск по `Python` перевел страницу на `https://nofluffjobs.com/Python`. На этой странице был виден полноценный фильтровый слой и список вакансий.

### DOM структура listing

| Блок | Что внутри |
| --- | --- |
| Filters | `Technologies`, `Salaries (PLN)`, `Salary match`, `My applications`, `Location`, `Seniority`, `Work language`, `Benefits`, `More` |
| Results header | `Jobs (7383)`, `Save this search`, sorting control |
| Job cards | карточки вакансий с salary, tags, company, location |
| Load more | `button "See more offers"` |
| Feedback | `Rate search results` |
| Salary widget | отдельный блок с медианами и переключателями `Senior / Mid / Junior` |

### Карточка вакансии на listing

На выдаче каждая карточка обернута в anchor с id вида:

- `#nfjPostingListItem-software-engineer-python-link-group-Remote`
- `#nfjPostingListItem-ZKUM1GAW` на company page

Внутри карточки были:

- title в `h2[data-cy="title position on the job offer listing"]`
- label `NEW`
- salary range
- technology tags
- company name
- location, обычно `Remote` или город
- favorite button

### Поля карточки

| Поле | Где лежит |
| --- | --- |
| Job title | `h2[data-cy="title position on the job offer listing"]` |
| Status label | `span[data-cy="sup"]` |
| Salary | текстовый блок рядом с title |
| Tags | список technology tags |
| Company | heading `h4` внутри карточки |
| Location | `Remote`, `Warszawa`, `Kraków`, `+1` и т.п. |
| Favorite | `nfj-toggle-favorite[data-cy="job favourite btn listing"]` |

### Фильтры

Фильтры на выдаче хорошо структурированы и опираются на headings:

| Фильтр | Примеры |
| --- | --- |
| Technologies | `Java`, `Python`, `C#`, `SQL`, `React`, `TypeScript` |
| Salary | slider `ngx-slider`, min/max textboxes |
| Salary match | toggle |
| Location | `Remote`, `Hybrid`, `Field work` |
| Seniority | `Trainee`, `Junior`, `Mid`, `Senior`, `Expert` |
| Work language | `Polish`, `English` |
| Benefits | `Training budget`, `Private healthcare`, `Sport card` |
| More | `Online Recruitment`, `No travel`, `Relocation package` |

### Primary selectors для listing

| Что искать | Primary selector | Fallback |
| --- | --- | --- |
| Job cards | `a[id^="nfjPostingListItem-"]` | `a[href^="/job/"]` внутри `nfjPostingList` |
| Title | `h2[data-cy="title position on the job offer listing"]` | `h2` внутри карточки |
| Favorite | `nfj-toggle-favorite[data-cy="job favourite btn listing"]` | button/text `Save this job offer` |
| Load more | `button:has-text("See more offers")` | `scroll`-based pagination if UI changes |

## Job detail

Job detail page очень полезен для извлечения структурированного контента.

### Основные блоки detail

| Блок | Что видно |
| --- | --- |
| Breadcrumbs | `Back to search`, `Python`, `Backend`, `Remote` |
| Header | title, company link, logo |
| Meta | category, seniority, location scope, expiry date |
| Must have | список обязательных навыков |
| Requirements description | подробные требования |
| Offer description | краткое описание роли |
| Your responsibilities | список обязанностей |
| Job details | `Start ASAP`, `Fully remote` |
| Salary details | B2B / UoP, monthly / hourly values |
| Actions | `Apply`, `Save job offer`, `Analyze CV BETA` |
| Similar ads | похожие вакансии |

### Поля detail

| Поле | Где лежит |
| --- | --- |
| Title | `heading h1` |
| Company | `link[href^="/company/"]` |
| Category | breadcrumbs and category links |
| Seniority | `Senior` |
| Location | `Remote` + list of regional variants |
| Expiry date | `Offer valid until: 15.04.2026` |
| Must have | section `Must have` |
| Requirements | section `Requirements description` |
| Description | section `Offer description` |
| Responsibilities | section `Your responsibilities` |
| Job details | section `Job details` |
| Salary | salary block and salary details sub-block |

### Apply flow

На этой сессии кнопка `Apply` на job detail была **disabled**, то есть публичный apply flow не был доступен без дополнительных действий. При этом страница подгружает `recaptcha`-скрипт, а рядом доступны `Save job offer` и `Analyze CV BETA`.

Вывод для парсера:

- публичный read-only контент есть
- apply как действие может быть gated
- для автоподачи нужно отдельно проектировать auth flow

### Primary selectors для detail

| Что искать | Primary selector | Fallback |
| --- | --- | --- |
| Job title | `h1` | page title / breadcrumb text |
| Company link | `#postingCompanyUrl` | `a[href^="/company/"]` |
| Apply button | `button:has-text("Apply")` | disabled button state |
| Save button | `button:has-text("Save job offer")` | `nfj-toggle-favorite` |
| Analyze CV | `button:has-text("Analyze CV")` | `button:has-text("Analyze CV BETA")` |

## Company page

Company page у `Link Group` очень богатый и хорошо структурирован.

### Структура company page

| Блок | id / custom element | Что хранит |
| --- | --- | --- |
| Header | `#company-header` / `cp-company-details-banner` | logo, company name, socials |
| Main info | `#company-main` / `cp-view-main` | founded, location, industry, company size, sectors |
| About | `#company-about` / `nfj-read-more-html` | company description, video |
| Technologies | `#company-technologies` | in-house tech stack |
| Benefits | `#company-benefits` | perks & benefits |
| Gallery | `#company-gallery` | photos/video, show more |
| Quotes | `#company-quotes` | testimonials |
| Values | `#company-values` | company values |
| Team | `#company-team` | management/team members |
| Timeline | `#company-timeline` | historical milestones |
| Clients | `#company-clients` | client logos |
| Specialization | `#company-specialization` | service areas |
| Awards | `#company-awards` | awards and years |
| Partners | `#company-partners` | partner logos |
| Recruitment process | `#company-recruitment-process` | steps after application |
| Job offers | `#company-jobs` / `nfjPostingsList` | company vacancies |

### Поля company page

| Поле | Где лежит |
| --- | --- |
| Company name | `h1` |
| Social links | `#companySocialUrl`, `#companyFacebookUrl`, `#companyTwitterUrl`, `#companyLinkedinUrl` |
| Founded | text block in main info |
| Location | `#companyShowOnMap`, `cy="company location dropdown"` |
| Industry | main info block |
| Company size | main info block |
| Technologies | `span[id^="item-tag-"]` |
| Perks | button chips |
| Team | team cards / management list |
| Timeline | `article` cards with year + description |
| Jobs | `a[id^="nfjPostingListItem-"]` under `#company-jobs` |

### Company job cards

На company page список вакансий использует те же карточки, что и listing:

- `a[id^="nfjPostingListItem-"]`
- title в `h2`
- salary range
- tags
- company name
- location

## JSON-LD и state

В ходе проверок:

- `script[type="application/ld+json"]` не был найден ни на listing, ни на job detail, ни на company page
- `window.__NEXT_DATA__` не использовался
- `window` содержит в основном `webpackChunknfj` и служебные ключи вида `nfj_visited_pl`

Вывод:

- парсить лучше через DOM + internal API
- на JSON-LD здесь опираться не стоит
- важны custom elements `nfj-*`, `cp-*` и `data-cy`

## Network / XHR

Наблюдаемые и полезные эндпоинты:

| Endpoint | Назначение |
| --- | --- |
| `GET /assets/environments/prod.json` | environment config |
| `GET /version?salaryCurrency=...&salaryPeriod=...&region=...&language=...` | version / locale bootstrap |
| `GET /api/feature?salaryCurrency=...` | feature flags |
| `POST /api/search/posting?pageFrom=1&pageTo=1&pageSize=20&salaryCurrency=PLN&salaryPeriod=month&region=pl&language=en-GB` | main search results API |
| `GET /api/calculator/salaries?requirement=Python&seniority=...` | salary calculator API |
| `GET /api/companies/search/siblings/CCYWOK00?...` | company siblings / previous-next company flow |
| `POST /signal` | internal tracking signal |

### Что это значит для парсера

Самый ценный источник вакансий здесь - **`/api/search/posting`**.
Для enrichment можно использовать:

- `version`
- `feature`
- `calculator/salaries`
- `companies/search/siblings`

## Auth / anti-bot

Обнаруженные сигналы защиты и трекинга:

- Usercentrics consent manager
- Google Analytics
- Clarity
- LinkedIn Insight tag
- Facebook Pixel
- TikTok pixel
- Bing
- Hotjar
- HubSpot chat
- reCAPTCHA script на job detail

Что важно:

- hard-blocking captcha на публичных страницах не был основным ограничением
- cookie consent сильно влияет на сетевые шумы
- apply/action слой может быть gated
- `Log in` есть в navbar, но публичный парсинг не требует авторизации

## Рекомендуемые selectors

### Home

| Что | Selector |
| --- | --- |
| Navbar | `#navbarNav` |
| Search input | `input[aria-label="main search input"]` |
| Featured offers | `a[id^="nfjPostingListItem-"]` |

### Listing

| Что | Selector |
| --- | --- |
| Results wrapper | `#nfjPostingsList` / `nfj-postings-list` |
| Job card | `a[id^="nfjPostingListItem-"]` |
| Title | `h2[data-cy="title position on the job offer listing"]` |
| Favorite | `nfj-toggle-favorite[data-cy="job favourite btn listing"]` |
| Load more | `button:has-text("See more offers")` |

### Detail

| Что | Selector |
| --- | --- |
| Title | `h1` |
| Company link | `#postingCompanyUrl` |
| Breadcrumbs | `nav a` / top list links |
| Apply | `button:has-text("Apply")` |
| Save | `button:has-text("Save job offer")` |

### Company

| Что | Selector |
| --- | --- |
| Company header | `#company-header` |
| Company main | `#company-main` |
| Technologies | `#company-technologies span[id^="item-tag-"]` |
| Benefits | `#company-benefits button` |
| Team | `#company-team` |
| Job offers | `#company-jobs a[id^="nfjPostingListItem-"]` |

## Field mapping table

| Field | Primary source | Fallback |
| --- | --- | --- |
| `job_id` | `a[id^="nfjPostingListItem-"]` | slug from `/job/<slug>` |
| `title` | `h1` on detail, `h2` on listing | document title |
| `company_name` | `#postingCompanyUrl` / company heading | company card heading |
| `salary_min/max` | listing card / detail salary block | `/api/search/posting` |
| `location` | listing card location text | breadcrumbs / job details |
| `seniority` | detail meta `Senior` | listing filters / tags |
| `must_have` | `Must have` section | tags on listing |
| `requirements` | `Requirements description` | detail body text |
| `offer_description` | `Offer description` | detail body text |
| `responsibilities` | `Your responsibilities` | detail body text |
| `job_details` | `Job details` | detail metadata |
| `company_about` | `#company-about` | company page body text |
| `company_technologies` | `#company-technologies span[id^="item-tag-"]` | company description |
| `company_benefits` | `#company-benefits button` | text chips |
| `company_jobs` | `#company-jobs a[id^="nfjPostingListItem-"]` | `/api/companies/search/siblings/CCYWOK00` |

## 2-pass parser strategy

### Pass 1

Собирать только стабильный инвентарь:

- `job_id`
- `title`
- `company_name`
- `salary`
- `location`
- `url`
- `category`
- `seniority`

Источники:

- `/api/search/posting`
- job card DOM

### Pass 2

Для выбранных вакансий догружать:

- detail page
- `Must have`
- `Requirements description`
- `Offer description`
- `Your responsibilities`
- `Job details`
- company page
- company profile metadata

Источники:

- `/job/<slug>`
- `/company/<slug>`
- `#company-jobs`
- `#company-technologies`

## Risks / notes

- На страницах много стороннего трекинга и рекламных вызовов, поэтому для стабильного краулинга лучше игнорировать network noise и опираться на `api/search/posting`
- JSON-LD отсутствует, так что валидацию лучше строить через DOM и API
- `Apply` может быть disabled на публичной странице
- Company page очень длинный, поэтому для парсера стоит разделять основную карточку компании и дочерний job-listing

## Проверенные URL

- `https://nofluffjobs.com/`
- `https://nofluffjobs.com/Python`
- `https://nofluffjobs.com/job/software-engineer-python-link-group-remote`
- `https://nofluffjobs.com/company/link-group-ccywok00`
