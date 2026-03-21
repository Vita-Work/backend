# Bayt.com Parser Report

Bayt.com в текущем скане выглядит как **SSR-heavy job board** с большим количеством статического HTML, отдельными AJAX-вставками и сильной зависимостью от своих внутренних `B8*`-скриптов. Для парсинга это хороший кейс: основная структура вакансий и компаний лежит прямо в DOM, а не спрятана за сложным SPA-state. При этом у Bayt есть несколько слоёв, которые обязательно надо учитывать: cookie banner, login/register wall для `Easy Apply`, CSRF-токен в фильтрах и большой хвост third-party аналитики/рекламы.

## Что Я Проверил

Я посмотрел `home`, `listing/search`, `job detail`, `company profile`, `filters/pagination`, `apply/login flow`, script state, network requests и URL-паттерны. Самый важный вывод: **на listing странице Bayt уже отдаёт и карточки вакансий, и фильтры, и `ItemList` JSON-LD**, а `job detail` и `company page` строятся из обычного HTML без `JobPosting` JSON-LD.

## Карта Страниц

Bayt использует несколько устойчивых шаблонов:

| Тип | Пример URL | Что там есть |
|---|---|---|
| Home | `https://www.bayt.com/` | Поиск, страны, популярные запросы, разделы для employers, app CTA |
| Listing | `https://www.bayt.com/en/international/jobs/it-jobs/` | Список вакансий, фильтры, сортировка, пагинация, `ItemList` JSON-LD |
| Job detail | `https://www.bayt.com/en/international/jobs/it-jobs/?jobId=5444346` | Полный job content, company block, `Easy Apply`, skills, description |
| Company page | `https://www.bayt.com/en/company/wizard-solutions-sal-2260128/` | About, jobs by company, follow button, company metadata |
| Apply/login | `https://www.bayt.com/en/register-j/?jb_id=...` | Регистрация/логин перед apply |

## Home

На home главные якоря для парсинга находятся в `form#form.search-bar`. Внутри есть `input[name="keyword"]#text_search` с placeholder `Search jobs, skills, companies`, `input[name="composite_search"]` и селект `select[name="country"]#search_country` с набором стран и локальных городов. Кнопка поиска имеет id `submitButtonQuickSearchWidget`. На домашней странице также есть блоки `Popular Searches`, `Who's Hiring on Bayt.com`, `Real Stories`, `Find Jobs in the Gulf and the Middle East`, блог и app CTA.

Для home полезные стабильные элементы такие:

| Поле | Primary source | Fallback |
|---|---|---|
| Keyword search | `input#text_search[name="keyword"]` | `form.search-bar` + placeholder |
| Location select | `select#search_country[name="country"]` | `input#search_country__r` |
| Submit | `#submitButtonQuickSearchWidget` | button text `Find jobs` |
| Popular searches | links under `Popular Searches` | `a[href*="/international/jobs/"]` |

## Listing / Search

Listing страница `https://www.bayt.com/en/international/jobs/it-jobs/` рендерит **карточки вакансий прямо в DOM**. Вверху есть заголовок `IT Jobs in the Middle East`, количество найденных вакансий и сортировка `Sort by: Relevance`. Главный контейнер фильтров находится в `form#clusterFormId`, а сама выдача идет списком `li`-элементов.

Карточка вакансии в Bayt строится так: заголовок в `h2 > a[href*="/jobs/"]`, компания в `a[href*="/company/"]`, локация в `a[href*="/jobs-in-..."]`, краткое описание после маркера `Summary:`, дата публикации в тексте вроде `4 days ago`, а иногда зарплата, опыт и remote-метка идут отдельными `term/definition` блоками с иконками. На карточке также часто есть `Easy Apply`.

Пример того, что реально лежит в карточке:

| Поле | Где брать |
|---|---|
| Title | `h2 a[href*="/jobs/"]` |
| Company | `a[href*="/company/"]` |
| City | `a[href*="/jobs-in-..."]` |
| Country | `a[href*="/jobs/it-jobs/"]` внутри карточки |
| Summary | текст после `Summary:` |
| Posted time | `4 days ago`, `9 days ago` и т.д. |
| Salary | блок с иконкой `` и текстом `SAR ...` или `$...` |
| Experience | блок с иконкой `` |
| Remote | блок с иконкой `` и текстом `Remote` |
| Apply CTA | `a[href*="/en/register-j/?jb_id="]` |

### Pagination and Filters

Фильтры у Bayt сделаны через обычный HTML form, но почти все контролы помечены классами вроде `jsAjaxLoad`, `accordion-toggle` и отдельными checkbox-элементами. У формы есть `input[name="YII_CSRF_TOKEN"]`, то есть для корректного воспроизведения фильтров CSRF-токен лучше сохранять и прокидывать дальше.

В listing я зафиксировал такие фильтровые группы:

| Группа | Примеры |
|---|---|
| Sort | `options[sort][]=r`, `d`, `l` |
| Date posted | `Past 30 days`, `Past 7 days`, `Past 24 hours` |
| Country | `Egypt`, `UAE`, `Saudi Arabia`, `Morocco`, `Qatar` |
| City | `Dubai`, `Cairo`, `Doha`, `Abu Dhabi`, `Riyadh` |
| Area | `Giza`, `Nasr City`, `Al Olaya`, `New York` |
| Industry | `IT Services`, `Software Development`, `Telecommunications` и другие |
| Career level | `Student/Internship`, `Entry level`, `Mid career`, `Management`, `Director/Head` |
| Employment type | `Full time`, `Contractor`, `Internship` |
| Gender | `Gender unspecified`, `Male only` |
| Company type | `Employer (private sector)`, `Recruitment agency` |

Пагинация идет через `a[href*="page=2"]`, `a[href*="page=167"]` и кнопку `More Results`. Для парсера это очень удобно: можно просто читать ссылки из DOM и не кликать UI.

## Job Detail

Открытая вакансия на Bayt не уходит в отдельный SPA-экран с тяжёлым state. Страница остаётся в том же шаблоне, а контент подгружается в job layout. В моем скане URL выглядел как `https://www.bayt.com/en/international/jobs/it-jobs/?jobId=5444346`, а canonical job URL в ItemList и карточке был `/en/lebanon/jobs/junior-software-developer-cloud-5444346/`.

На detail странице важные блоки такие:

| Блок | Что внутри |
|---|---|
| Title | `h2` с названием вакансии |
| Company | `Wizard Solutions SAL` и ссылка на company page |
| Meta | `4 days ago`, `Easy Apply`, `Save` |
| Job type | `Full time` |
| Function area | `Software Development` |
| Description | `Job Description` + `Responsibilities` + `Required Qualifications` + `Preferred Qualifications` |
| Skills | отдельный блок `Skills` |
| Compare profile | ссылка на `applications-insight` |
| Company card | short about, follow button, location, profile link |

Для detail страницы я **не нашёл `JobPosting` JSON-LD**. Это важно: canonical job data надо брать из DOM, а не рассчитывать на structured data. Внутри страницы, однако, есть много полезных классов и повторяющихся текстовых якорей, поэтому парсинг через DOM здесь надёжный.

### Apply Flow

`Easy Apply` не ведёт сразу в форму отклика. В карточке и на detail странице он уводит в `https://www.bayt.com/en/register-j/?jb_id=...&from_job_search=...&ampBtnView=1` или вариант с `ampBtnView=2`. Это фактически **registration/login wall перед apply**. Для автоматизации это означает, что apply-flow надо отделять от публичного job scraping, а для отклика нужен отдельный auth-aware путь.

Также на detail странице есть `Save` и `Follow`, но они не являются публичными действиями без пользовательского состояния.

## Company Page

Company page для `Wizard Solutions SAL` очень удобна для скрапа. Главная шапка содержит:

| Поле | Значение |
|---|---|
| Company name | `Wizard Solutions SAL` |
| Industry | `Software Development` |
| Location | `Lebanon - Jal Al Dib` |
| Employees | `10-49 Employees` |
| CTA | `Follow` / `Following` |

Ниже идёт блок `About` с текстом в `p`-элементах, а потом блок `Jobs` со списком вакансий компании. На этой странице каждая вакансия лежит как отдельный link с заголовком, названием компании, локацией и датой публикации, плюс `Easy Apply`.

Для company page полезные якоря такие:

| Поле | Primary source | Fallback |
|---|---|---|
| Company title | `h1` | page title |
| Industry + location | `h1 + ul.list.is-basic li` | visible meta text |
| Employees | same meta list | text search `Employees` |
| About text | section `h2: About` + paragraphs | first content block under About |
| Jobs list | `h2: Jobs` + `a[href*="/jobs/"]` | `View more` URL |
| Follow button | `button:has-text("Follow")` | `button:has-text("Following")` |

## Embedded State, Scripts and JSON-LD

На listing странице Bayt **встраивает `ItemList` JSON-LD прямо в inline script**. Это очень ценно, потому что даёт canonical URL списка вакансий без необходимости угадывать по DOM. Я также увидел набор полезных глобальных объектов и конфигов:

| Global | Зачем нужен |
|---|---|
| `window.B8v` | runtime config Bayt, domain type, CDN root, adsense config, firebase config |
| `window.B8` | базовая библиотека Bayt |
| `window.BaytNavigation` | AJAX/setup helpers |
| `window.searchHistory_` | история поиска |
| `window.searchControl` | search-widget logic |
| `window.B8track` | tracking helper |
| `window.B8CvSearchGlobal` | search-specific runtime |
| `window.B8loadSection` | lazy section loading |
| `window.jobSearchWebPushNotification` | job search web push logic |
| `window.jobFollowCompany` | follow action |
| `window.jobUnFollowCompany` | unfollow action |
| `window.jobViewloginModal` | login modal hook |
| `window.dataLayer` | GTM state, page view, consent, `vpvId=job5444346` |

`B8v` особенно важен: он раскрывает `domainType: "jobs"`, `cookiesDomain: ".bayt.com"`, `jsCdnRoot`, `B8trkUrl`, adsense settings и firebase config. Для fallback-логики это один из лучших источников мета-конфигурации.

### Scripts

Страница грузит заметный набор сторонних и внутренних скриптов:

| Тип | Примеры |
|---|---|
| Bayt internal | `B8com.es6.js`, `eventsDataCollector.js`, `companyViewB8.js`, `timeUtil.js`, `JobSearchClassic.js`, `jobViewClassicV2.js` |
| Consent | `cookieyes` scripts |
| Analytics | `Clarity`, `GTM`, `Google Analytics`, `Google One Tap` |
| Ads / tracking | `LinkedIn Insight`, `Twitter ads`, `Quora`, `Reddit pixel`, `Creative CDN` |

Для парсинга важно, что Bayt не прячет контент в JS-virtual DOM, а использует JS в основном для поведения, аналитики и части AJAX.

### Network / XHR

На company page я зафиксировал внутренний AJAX:

| Endpoint | Зачем |
|---|---|
| `/ajax/company/GetSimilarsSection/?companyId=...` | похожие компании/секция similar |
| `/ngx_pagespeed_beacon` | performance beacon |
| `h.clarity.ms/collect` | telemetry |
| `analytics.google.com/g/collect` | GA4 |
| `px.ads.linkedin.com/wa` | LinkedIn ads |
| `pixel-config.reddit.com` | Reddit pixel |

Это не API вакансий в прямом смысле, но полезно для понимания того, какие динамические куски Bayt подгружает отдельно.

## Primary Selectors

Ниже короткий набор стабильных селекторов, который можно брать первым проходом:

| Сценарий | Selector |
|---|---|
| Home keyword | `form#form.search-bar input[name="keyword"]#text_search` |
| Home country | `form#form.search-bar select[name="country"]#search_country` |
| Search submit | `#submitButtonQuickSearchWidget` |
| Listing form | `form#clusterFormId` |
| Listing card title | `h2 a[href*="/jobs/"]` |
| Listing company | `a[href*="/company/"]` |
| Listing date | text like `4 days ago`, `9 days ago` |
| Listing easy apply | `a[href*="/en/register-j/?jb_id="]` |
| Detail title | `h2` in the job header |
| Detail company | `a[href*="/company/"]` in job header and company card |
| Detail description | blocks under `Job Description` |
| Detail skills | section `Skills` |
| Company title | `h1` |
| Company about | `h2:has-text("About") + *` or the following paragraph block |
| Company jobs | `h2:has-text("Jobs") + * a[href*="/jobs/"]` |

## Fallback Selectors

Если Bayt немного поменяет классы, я бы падал назад на текстовые якоря и URL-patterns:

| Поле | Fallback |
|---|---|
| Job title | link text inside `li` with `/jobs/` URL |
| Company name | nearest `a[href*="/company/"]` рядом с title |
| City / country | nearest `a[href*="/jobs-in-"]` or `a[href*="/jobs/"]` in location block |
| Salary | text regex on currency pattern `^[A-Z]{3}|\$` |
| Experience | text regex `Years of Experience|Mid career|Entry level|Management` |
| Apply | href regex `/register-j/\\?jb_id=` |
| Company jobs | any `a[href*="/jobs/"]` inside company page content after `Jobs` heading |

## Field Mapping

| Field | Primary source | Secondary source |
|---|---|---|
| `title` | job card `h2 a` / detail `h2` | ItemList URL slug |
| `company` | `a[href*="/company/"]` | company page `h1` |
| `location_city` | location links in card or header | company meta |
| `location_country` | country link in card/header | URL segment |
| `summary` | `Summary:` text in listing card | job description intro |
| `description` | detail page `Job Description` block | listing summary |
| `skills` | detail page `Skills` block | keyword text in description |
| `salary` | `term` block with currency | text scan in detail/listing |
| `experience` | `term` block `Years of Experience` or career level | job text |
| `published_at` | `4 days ago`, `9 days ago` | date sort / page metadata |
| `apply_url` | `Easy Apply` href `/register-j/?jb_id=...` | job card easy apply link |
| `company_url` | `a[href*="/company/"]` | company page `View Company Profile` |
| `detail_url` | job title URL `/en/<country>/jobs/...-<id>/` | ItemList JSON-LD |
| `listing_url` | current page URL | sort/filter URLs |

## 2-Pass Parser Strategy

**Pass 1** should crawl the listing pages and extract every `li` job card, the page-level filters, and the `ItemList` JSON-LD. На этом этапе уже можно собрать title, company, location, summary, salary, experience, posted time и `Easy Apply` URL. **Pass 2** should visit only the selected detail URLs and company URLs, then enrich records with full description, skills, company about, employee range, follow state, and related jobs. Это самый безопасный путь, потому что Bayt даёт много полезного уже на listing, а detail/company нужны в основном для обогащения.

## Notes and Risks

Bayt не выглядит как жестко защищённый бот-wall сайт, но у него есть несколько operational рисков. Во-первых, `Easy Apply` требует регистрации. Во-вторых, фильтр-форма полагается на `YII_CSRF_TOKEN`, поэтому простое дергание URL без соответствующих параметров может вести себя не так, как ожидается. В-третьих, на странице много рекламных и аналитических скриптов, так что при автоматическом скрапе лучше фильтровать выдачу по семантическим блокам, а не по всем `li` подряд.

## Проверенные URL

- `https://www.bayt.com/`
- `https://www.bayt.com/en/international/jobs/it-jobs/`
- `https://www.bayt.com/en/international/jobs/it-jobs/?jobId=5444346`
- `https://www.bayt.com/en/company/wizard-solutions-sal-2260128/`
- `https://www.bayt.com/en/lebanon/jobs/junior-software-developer-cloud-5444346/`
- `https://www.bayt.com/en/register-j/?jb_id=5444346&from_job_search=%252Fen%252Finternational%252Fjobs%252Fit-jobs%252F&ampBtnView=1`
- `https://www.bayt.com/en/international/jobs/wizard-solutions-sal-jobs/?filters%5Bgid_pid%5D%5B%5D=2260128-0`
- `https://www.bayt.com/en/international/jobs/search/`
- `https://www.bayt.com/en/jobs/locations/`
- `https://www.bayt.com/en/international/companies/`
- `https://www.bayt.com/en/international/salaries/`
- `https://www.bayt.com/en/employers/`
