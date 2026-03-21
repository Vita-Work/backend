# Computrabajo DOM/HTML report

## Scope and note
Этот отчет собран из live-скана в Playwright на `Computrabajo` с опорой на два уровня: глобальный хаб `https://www.computrabajo.com/` и рабочий страновой портал `https://mx.computrabajo.com/`. В этом браузерном профиле прямые заходы на `co.computrabajo.com` давали `403`, поэтому стабильные DOM-структуры и сетевые паттерны я зафиксировал на мексиканском портале, который показывает тот же продуктовый шаблон: home, listing, detail, company и login/apply flow.

Главная практическая мысль: **Computrabajo парсится не только по DOM, но и через очень полезные `JSON-LD`, `window.*` конфиги и несколько внутренних XHR-эндпоинтов**. Для надежного парсера лучше строить трехслойный подход: structured data -> DOM -> XHR fallback.

## 1) Карта страниц и URL-паттерны

### Home
Глобальная главная страница `https://www.computrabajo.com/` — это country gateway и поисковой хаб. Она показывает ссылки на страновые порталы LATAM и два searchbox-поля.

### Country portal
Рабочий страновой домен имеет формат `https://<cc>.computrabajo.com/`. На живом примере:
- `https://mx.computrabajo.com/` — страновой home/portal
- `https://mx.computrabajo.com/trabajo-de-desarrollador-en-ciudad-de-mexico` — listing
- `https://mx.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-...-<id>` — job detail
- `https://mx.computrabajo.com/empresas/ofertas-de-trabajo-de-...-<id>` — company page
- `https://secure.computrabajo.com/Account/Login?...` — login/apply wall

### URL patterns, которые реально видны
- `trabajo-de-<slug>`
- `trabajo-de-<slug>-en-<city>`
- `empleos-en-<city>`
- `empleos-en-<state>`
- `empleos-de-<category>`
- `salarios/<slug>`
- `ofertas-de-trabajo/oferta-de-trabajo-de-<slug>-en-<city>-<jobId>`
- `empresas/ofertas-de-trabajo-de-<company-slug>-<companyId>`

## 2) Home page structure

### Global home `www.computrabajo.com`
Главная страница устроена как крупный country selector и поисковой вход. В DOM есть:
- логотип/ссылка `Computrabajo Colombia` или аналогично по root
- `h1` с заголовком `Bolsa de trabajo`
- два searchbox-поля
- CTA `Buscar empleos`
- блок стран LATAM с прямыми ссылками на локали

### Структура DOM
- `banner` с логотипом и заголовком
- `main` с описанием и метриками
- блок выбора страны через ссылки `https://ar.computrabajo.com`, `https://mx.computrabajo.com`, `https://co.computrabajo.com` и т.д.
- footer с copyright

### Поля поиска
На global home searchboxы подписаны как:
- `Cargo o área`
- `Lugar`
- button `Buscar empleos`

### Что важно для парсера
Главная — это не вакансионный листинг, а **navigational hub**. Для краулера здесь ценны:
- список страновых доменов
- доступные searchbox labels
- возможность перейти на локальный портал

## 3) Country portal structure

На `mx.computrabajo.com` шапка уже локализована и полезна для робота-парсера.

### Header
- логотип `Computrabajo México`
- ссылки `Buscar ofertas`, `Evaluaciones de empresa`, `Salarios`, `Desarrollo profesional`
- recruiter entry `Reclutadores`
- login entry `Login`
- `Crear CV`

### Main portal blocks
- hero with `Encuentra el empleo que encaja contigo`
- search form с двумя полями:
  - `Cargo o categoría`
  - `Lugar`
- CTA `Buscar empleos`
- company promo strip: плитки компаний/брендов
- CTA для работодателей `¿Eres empresa? Recluta gratis al mejor talento hoy mismo`
- content block `Bolsa de empleo según:` с localities и professional categories
- app promo/footer links

### Структура ссылок на локальные страницы
На home/portal есть прямые ссылки типа:
- `Empleos en Ciudad de México`
- `Empleos en Jalisco`
- `Empleos en Nuevo León`
- `Empleos de Informática / Telecomunicaciones`
- `Empleos de desarrollador`
- `Salarios de desarrollador`

Эти ссылки полезны для seed crawl, потому что они ведут к тем же шаблонным страницам, только с другим слагом.

## 4) Listing page structure

### URL
Пример живого listing:
`https://mx.computrabajo.com/trabajo-de-desarrollador-en-ciudad-de-mexico`

### Верхняя часть listing
На странице списка есть:
- searchbox input с уже заполненными значениями
- уведомление/permission prompt для web push
- набор фильтров

### Фильтры
Семантически листинг держит такие фильтры:
- `Ordenar`
- `Fecha`
- `Lugar de trabajo`
- `Experiencia`
- `Salario`
- `Jornada`
- `Contrato`
- `Discapacidad`

Это видно как кликабельные контролы с текстовыми лейблами. Для парсера лучше использовать именно эти тексты или связанные атрибуты, а не хрупкие иконки.

### Карточка вакансии
На листинге каждая вакансия рендерится отдельным `article`. Внутри стабильно встречаются:
- `h2` с названием вакансии
- `a` на detail page внутри заголовка
- `a` на company page внутри строки компании
- location paragraph
- salary block, если зарплата указана
- date paragraph `Hace X horas`
- badges `Vista`, `Empleo destacado`, `Se precisa Urgente`
- action icons/favorite/report/share

### Что лежит где
- title: `article h2 a`
- company: `article p a` или plain text, если компания не ссылкой
- location: `article p` сразу после компании
- salary: отдельный `generic`/`span` блок рядом с location, если есть
- date: последний paragraph в карточке
- featured/urgent labels: верхние generic-лейблы в карточке

### Реальный DOM-паттерн карточек
На живом listing карточки выглядели так:
- `article` с `heading` + `link` на detail URL
- company link ведет на `https://mx.computrabajo.com/empresas/ofertas-de-trabajo-de-...`
- salary может быть строкой вида `$ 35,000.00 (Mensual)` или отсутствовать
- modality может быть в отдельном блоке, например `Presencial y remoto`

### Pagination
Пагинация присутствует как span/button-like элемент, а не всегда как обычная `<a>`:
- текст `Siguiente`
- класс `b_primary w48 buildLink cp`
- атрибут `data-path="https://mx.computrabajo.com/trabajo-de-desarrollador-en-ciudad-de-mexico?p=2"`

Это очень важно: **next-page переход лучше брать из `data-path`, а не из `href`**.

### Related jobs
Внизу есть блок `Empleos similares` или `Búsquedas relacionadas` со связанными ссылками. Это хороший seed для дополнительного crawl.

## 5) Detail page structure

### URL
Пример:
`https://mx.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-desarrolladora-jr-en-miguel-hidalgo-D08E8945F3347C0861373E686DCF3405`

### Верхний блок
- `h1` с названием вакансии
- company line `Cipre Holding - Miguel Hidalgo, Ciudad de México DF`
- back link `Volver al listado`
- быстрые действия:
  - `Postularme`
  - `Add favorite`

### Tabs / sections
На detail page есть навигация:
- `Oferta`
- `Empresa`
- `Ofertas similares`

### Offer section DOM
В основном блоке `Oferta` видно:
- heading `Descripción de la oferta`
- salary/status row: `A convenir`, `Contrato por tiempo indeterminado`, `Tiempo Completo`
- основной текст вакансии в одном длинном paragraph/text block
- section `Requerimientos`
- list items с требованиями
- `Palabras clave`
- timestamp `Hace 15 horas (actualizada)`
- CTA `Postularme`
- `Avísame con ofertas similares`
- `Denunciar empleo`
- `Imprimir`

### Что лежит в описании
На реальной вакансии описание было уже структурировано как plain text с подзаголовками:
- `Descripción del puesto`
- `Responsabilidades`
- `Requisitos`
- `Deseable`
- `Ofrecemos`
- `Interesadas`

Это полезно для парсинга, потому что можно восстановить смысловые секции даже без отдельных HTML tags.

### Company panel on detail page
Справа/ниже есть блок `Acerca de Cipre Holding`:
- company name
- короткое описание компании
- follow button
- company logo/link

### Similar jobs on detail page
Есть большой блок `Ofertas similares` с карточками конкурирующих вакансий. Каждая карточка содержит:
- title
- company
- location
- short description snippet
- age of posting
- image/logo

### Related search block
Ниже есть `Búsquedas relacionadas`:
- `Ver todos los avisos en Ciudad de México DF`
- `Empleos en Miguel Hidalgo`
- `Empleos de Informática / Telecomunicaciones`
- `Empleos de programador web`
- `Empleos de desarrollador`
- `Salarios de programador`

Этот блок очень полезен для расширения crawl по кластерам.

## 6) Company page structure

### URL
Пример:
`https://mx.computrabajo.com/empresas/ofertas-de-trabajo-de-cipre-holding-F2A9F2EFD06CFF5B`

### Header
- `h1` с названием компании
- follower count `0 seguidores`
- button `+ Seguir`

### Tabs
- `La empresa`
- `Ofertas 1`
- `Entrevistas`
- `Fotos`

### Filter bar
На company page сохраняются те же фильтры, что и на listing:
- `Ordenar`
- `Fecha`
- `Categoría`
- `Lugar de trabajo`
- `Experiencia`
- `Salario`
- `Jornada`
- `Contrato`
- `Discapacidad`

### Company offers list
Есть карточка оффера компании с тем же паттерном, что на листинге:
- title `Desarrolladora Jr.`
- status badge `Vista`
- company link
- location
- date
- preview action icons

### Inline preview drawer
На company page после выбора оффера снизу/в правой области появляется preview с:
- job title
- short keywords/role label
- company name
- location
- `Postularme`
- `Add favorite`
- `Share button`
- `Ocultar`
- more options
- salary/status icons
- full description
- `Acerca de <company>` block

### About block
На живом примере:
- `Cipre Holding es una empresa mexicana enfocada en inteligencia artificial y desarrollo de infraestructura tecnológica...`

### Why company page matters
Компания часто дает второй источник данных:
- title/location/company consistency
- posting freshness
- company description
- company-specific job list
- follow/alerts semantics

## 7) Apply / access / auth flow

### Что происходит при `Postularme`
На detail page кнопка `Postularme` **не ведет на публичный apply form**. Она редиректит на:
`https://secure.computrabajo.com/Account/Login?ReturnUrl=...`

### Auth wall details
Login page title:
- `Alta de currículum - Computrabajo México`

На странице логина есть:
- CTA `Continúa con Google`
- CTA `Continúa con Apple`
- email input `Continúa con tu correo`
- button `Continuar`
- password field на втором шаге
- `¿No recuerdas tu contraseña?`
- `Iniciar sesión`
- link `Ingresa como empresa`

### Hidden / security fields
В форме есть:
- `ReturnUrl`
- `Email`
- `Password`
- `__RequestVerificationToken`
- вспомогательные hidden/config inputs `IOS`, `CG`, `Lang`, `IdSitePiano`, `UrlPortal`, `Client`, `EnabledGA4`, `EnabledGTM`, `EnabledPIANO`, `Gac`, `GTMAccount`, `PianoDebugMode`

### Что это значит
- **apply flow gated behind auth**
- visible CAPTCHA нет на первом экране
- CSRF token есть
- auth построен как OIDC/OpenID Connect callback flow
- redirect_uri ведет на `https://candidato.mx.computrabajo.com`

### Practical implication
Для автоматизации парсер должен считать apply как **protected action**, а не как публичный URL. Если цель только извлекать вакансии, login wall нужен только как сигнальный endpoint для обхода при клике `Postularme`.

## 8) JSON-LD and structured data

### Home / portal
На home/portal присутствует `JSON-LD` блока `Organization` и `WebPage`.

### Listing
На listing page JSON-LD особенно полезен. В одном `script[type="application/ld+json"]` лежит `@graph`, где есть:
- `Organization` для Computrabajo México
- `WebPage` с description страницы поиска
- `ItemList` с `itemListElement` на первые вакансии и их URL

Это очень сильный источник для краулера, потому что он дает:
- canonical page title
- page description
- ordered list of job URLs

### Detail
На detail page `JSON-LD` еще полезнее. В одном `@graph` есть:
- `Organization`
- `WebPage`
- `JobPosting`
- `ItemList` со связанными вакансиями

В `JobPosting` на живом примере есть:
- `title`
- `description`
- `industry`
- `datePosted`
- `employmentType`
- `salaryCurrency`
- `url`
- `directApply`
- `validThrough`
- `jobLocation`
- `baseSalary`
- `hiringOrganization`
- `identifier`

### Почему JSON-LD важнее DOM
Для detail page structured data почти всегда лучше, чем парсить большой текстовый блок. DOM нужен как fallback, но primary source тут именно JSON-LD.

## 9) `window.*` objects and runtime config

На живых страницах есть полезные runtime-конфиги.

### Listing page
- `window.searchData`
- `window.collectorData`
- `window.latestSearchData`
- `window.alertData`
- `window.shortcutsOffers`
- `window.searchBox`

### Detail page
- `window.searchData`
- `window.collectorData`
- `window.latestSearchData`
- `window.alertData`
- `window.shortcutsOffers`
- `window.searchBox`
- `window.lateralMenuData`
- `window.menuItemsResponsive`
- `window.urlac`, `window.ub`, `window.ubf`

### Что хранится в этих объектах
- `searchData`: base/final URL, page number, country code, semantic URL settings
- `collectorData`: search/result metadata, query, result count, offer id, taxonomy hashes
- `latestSearchData`: query param names for pagination/salary/location
- `alertData`: alert UI strings and limits
- `shortcutsOffers`: analytics labels for quick actions
- `searchBox`: search origin, device type, lite text, offers-grid flag

### Why it matters
Эти объекты хороши как fallback, если DOM поменяют. Особенно полезны:
- `searchData.finalUrl`
- `collectorData.q`
- `collectorData.totRes`
- `collectorData.oi` на detail

## 10) Network / XHR endpoints

На листинге и detail page реально всплывали следующие endpoints:

### Search and suggestions
- `POST https://mx.computrabajo.com/ajax/geticonquerysuggest`
- `POST https://mx.computrabajo.com/ajax/geticonplacessuggest`
- `POST https://mx.computrabajo.com/offersgrid/getcitiesbylocation`

### Detail / offer payload
- `GET https://oferta.computrabajo.com/offer/<jobId>/d/j?ipo=2&iapo=1`
- `POST https://collector.dgnet.ltd.uk/offer/search`
- `POST https://collector.dgnet.ltd.uk/offer/detail`
- `POST https://mx.computrabajo.com/ajax/basicinfo`

### Company / follow / menu
- `GET https://candidato.mx.computrabajo.com/menu/_menuitems?responsive=true`
- `GET https://candidato.mx.computrabajo.com/Follower/IsLoginAndFollowCompany?ice=<companyId>`

### Analytics / third-party
- `POST https://h.clarity.ms/collect`
- `POST https://accounts.google.com/gsi/log...`
- `POST https://www.google.com/ccm/collect...`
- `POST https://us.creativecdn.com/tags/v2?type=json`

### Interpretation
Из этого набора для парсинга особенно важны:
- `ajax/geticonquerysuggest`
- `ajax/geticonplacessuggest`
- `offersgrid/getcitiesbylocation`
- `oferta.computrabajo.com/offer/<id>/d/j`
- `ajax/basicinfo`

Остальное в основном аналитика или UI sugar.

## 11) Auth / captcha / CSRF / limits

### Auth
- apply flow gated by `secure.computrabajo.com`
- OIDC/OpenID Connect style redirect
- Google/Apple/email login options

### CSRF
- `__RequestVerificationToken` присутствует в login form

### CAPTCHA
- на первом экране явной CAPTCHA не видно

### Click interception / overlay
- на detail page мне мешал `div#pop-up-webpush-background`, он перехватывал pointer events
- это не антибот, но важно как UI-ограничение для автоматизации

### Console hints
На странице логина/портала были ошибки и предупреждения типа:
- `ga is not defined`
- `Provider's accounts list is empty`
- `FedCM get() rejects with NetworkError`

Это не ломает структуру страниц, но показывает, что ancillary scripts могут шуметь в консоли.

## 12) Primary selectors and fallbacks

### Home / portal
Primary:
- `searchbox[aria-label="Cargo o categoría"]`
- `searchbox[aria-label="Lugar"]`
- `button:has-text("Buscar empleos")`

Fallback:
- любые `input`/`textbox` с этими label-ами
- ссылки на country portals через `a[href*="computrabajo.com"]`

### Listing
Primary:
- `article`
- `article h2 a[href*="/ofertas-de-trabajo/oferta-de-trabajo-"]`
- `article p a[href*="computrabajo.com/empresas/"]`
- `span.buildLink[data-path*="?p="]` for pagination

Fallback:
- `article` blocks with `heading` + `company paragraph` + `location paragraph` + `date paragraph`
- role/text based search for `Siguiente`

### Detail
Primary:
- `h1`
- `heading "Descripción de la oferta"`
- `paragraph "Requerimientos"`
- `button`/text `Postularme`
- `a[href*="/empresas/ofertas-de-trabajo-de-"]`

Fallback:
- main `article`-like content block with long text paragraphs
- `Ofertas similares` section cards

### Company
Primary:
- `h1`
- `navigation` tabs text `La empresa`, `Ofertas`, `Entrevistas`, `Fotos`
- `article` offer cards within company offers list
- `button "+ Seguir"`

Fallback:
- company about paragraph
- company name link in offer preview

### Login / apply
Primary:
- `input#Email`
- `input#password`
- `button:has-text("Continuar")`
- `a:has-text("Continúa con Google")`
- `a:has-text("Continúa con Apple")`

Fallback:
- form action `secure.computrabajo.com/Account/Login`
- hidden `__RequestVerificationToken`

## 13) Field mapping table

| Field | Primary source | Fallback source |
|---|---|---|
| `title` | `JobPosting.title` in JSON-LD | `h1` on detail, `article h2 a` on listing |
| `company` | `JobPosting.hiringOrganization.name` | company link text in listing/detail |
| `salary` | `JobPosting.baseSalary.value.value` + `salaryCurrency` | listing salary span, detail top row `A convenir` |
| `location` | `JobPosting.jobLocation.address.*` | listing company/location paragraph, detail `Ubicación: ...` |
| `datePosted` | `JobPosting.datePosted` | detail timestamp `Hace X horas (actualizada)`, listing timestamp |
| `validThrough` | `JobPosting.validThrough` | none, keep JSON-LD as source of truth |
| `description` | `JobPosting.description` | detail text block under `Descripción de la oferta` |
| `requirements` | parse from `JobPosting.description` or detail `Requerimientos` block | list items under `Requerimientos` and detail text headings |
| `applyUrl` | action flow from `Postularme` to `secure.computrabajo.com/Account/Login` | candidate auth redirect, not a public public apply URL |
| `companyUrl` | company link in listing/detail | company tab/offer card link |
| `similarJobs` | `ItemList` on detail JSON-LD + `Ofertas similares` | detail related jobs cards |
| `filters` | listing UI labels + `searchData` / `latestSearchData` | URL query params (`p`, `by`, city/category slugs) |

## 14) Two-pass parser strategy

### Pass 1: discovery and list harvest
- Start from global home and choose a working country portal
- Fill searchboxes or follow semantic URLs like `trabajo-de-...-en-...`
- Extract `ItemList` URLs from listing JSON-LD
- Extract `article` cards from DOM as a fallback and to get salary/location/date previews
- Capture pagination from `span.buildLink[data-path]`
- Record `collectorData`, `searchData`, and query state

### Pass 2: detail enrichment
- Visit each detail URL from `ItemList`
- Prefer `JobPosting` JSON-LD for structured fields
- Use DOM text to recover section headers and bullet-like requirements
- Extract company panel and similar jobs
- On `Postularme`, stop at auth wall and record login URL instead of trying to bypass it
- If available, follow company page for company description and company-specific offer list

### Why this order works
Computrabajo gives you a layered page model:
- listing = discovery
- detail = canonical job payload
- company = organization context
- login wall = protected action boundary

If you respect those layers, scraping becomes stable and easier to maintain.

## 15) Practical notes / quirks

- Direct access to some country roots can return `403` in a headless-ish profile; entering through the global home and then clicking the country link worked reliably for `mx.computrabajo.com`.
- `Postularme` is not a public application URL. It is a protected auth flow.
- A webpush overlay can block pointer events. For automation, close/dismiss it or navigate by direct `href` when needed.
- `JSON-LD` on listing/detail is much more reliable than trying to scrape every visible text fragment.
- Salary can be missing on some cards and present on others; do not assume it exists.

## 16) Verified URLs

- `https://www.computrabajo.com/`
- `https://mx.computrabajo.com/`
- `https://mx.computrabajo.com/trabajo-de-desarrollador-en-ciudad-de-mexico`
- `https://mx.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-desarrolladora-jr-en-miguel-hidalgo-D08E8945F3347C0861373E686DCF3405`
- `https://mx.computrabajo.com/empresas/ofertas-de-trabajo-de-cipre-holding-F2A9F2EFD06CFF5B`
- `https://secure.computrabajo.com/Account/Login?ReturnUrl=...`
- `https://candidato.mx.computrabajo.com/acceso/`
- `https://mx.computrabajo.com/empleos-en-ciudad-de-mexico`
- `https://mx.computrabajo.com/empleos-de-informatica-telecomunicaciones`
- `https://mx.computrabajo.com/trabajo-de-desarrollador`
- `https://mx.computrabajo.com/salarios/desarrollador`
