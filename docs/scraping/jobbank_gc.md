# Job Bank Canada - DOM / parsing report

Дата скана: 2026-03-21
Источник: live Playwright scan `https://www.jobbank.gc.ca/home`, `https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=software+engineer&locationstring=`, `https://www.jobbank.gc.ca/jobsearch/jobposting/49050568?source=searchresults`

## 1. Короткий вывод

Job Bank - это в первую очередь **серверно-рендеренный job board** с очень понятной семантической структурой. Для парсинга он удобен тем, что:

1. Главная страница уже содержит полноценную поисковую форму и трендовые ссылки.
2. Listing-страница отдает карточки вакансий как отдельные `article`, внутри которых почти все поля лежат текстом и в отдельных `listitem`.
3. Detail-страница имеет стабильные секции `Job details`, `Job market information`, `Similar job postings` и внешнюю ссылку на исходную публикацию.
4. У части вакансий Job Bank является только агрегатором и показывает партнерский источник, а полная вакансия открывается на внешнем сайте.

Для скрапера это значит: **основной источник истины - DOM**, а не сложный JS hydration state. На странице я не увидел богатых JSON-LD-блоков, зато увидел много стабильных URL-паттернов и семантических блоков.

## 2. Карта страниц

### Home

`https://www.jobbank.gc.ca/home`

Это маркетинговый и навигационный хаб:

- search box для keyword/location
- trending keywords
- featured tools
- resource links
- guide tabs
- usage stats
- page details

### Search / listing

`https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=software+engineer&locationstring=`

Это основная страница для сбора вакансий:

- заголовок поиска и число результатов
- сортировка `Best match` / `Date posted`
- кнопка `Create alert`
- список карточек вакансий
- фильтры слева и снизу
- RSS feed
- `Show more results`

### Job detail

`https://www.jobbank.gc.ca/jobsearch/jobposting/49050568?source=searchresults`

Это детальная карточка вакансии с:

- title
- employer
- job details
- external source link
- expiry date
- similar postings
- market info

### Company / apply

Отдельной внутренней company page в духе "company profile" здесь нет.
Для многих вакансий Job Bank показывает:

- внутреннюю карточку с названием работодателя
- внешнюю ссылку `View the full job posting on ...`
- уведомление, что это партнерский сайт

То есть apply flow часто уходит **наружу**, на исходную платформу-партнер.

## 3. Home DOM

### Верхняя часть

На главной есть стандартная gov shell:

- skip links
- language switch
- sign in
- Job Bank menu

Меню сверху устроено как `menubar` с пунктами:

- Job search
- Training and careers
- Labour market information
- Hiring
- Help
- About

### Поиск

Главный поисковый блок лежит в обычных form-like контейнерах:

- `Keywords` input с placeholder `Job title, employer`
- `Location` input с placeholder `City, province or territory`
- кнопка `Advanced`
- ссылка `Browse`
- кнопка `Search`

Это хороший базовый якорь для авто-поиска.

### Trending keywords

На главной есть блок трендовых ссылок:

- `Part time`
- `Remote`
- `IT`
- `Student`
- `LMIA`

Каждая ссылка уже содержит готовый query URL.

### Featured tools / resources

Есть сетка ссылок:

- Job search
- Training and careers
- Labour market information
- Hiring

И набор ресурсных страниц для разных аудиторий:

- Young Canadians
- Indigenous people
- Newcomers
- Foreign candidates from outside Canada
- Temporary foreign workers
- Persons with disabilities
- Veterans

### Page details

На главной есть `Date modified: 2026-01-28`.
Это полезно для контроля свежести страницы.

## 4. Listing DOM

### Search header

На search page структура уже более операционная:

- `h1` с текстом запроса
- блок с interactive map
- `Filters` panel
- `Create alert`
- число результатов
- сортировка

Для нашего примера страница показала:

- `103 results`
- `Best match`
- `Date posted`

### Карточка вакансии

Каждая вакансия рендерится как `article`.
Внутри карточки root clickable area - это ссылка на job posting.

Самый важный паттерн:

`/jobsearch/jobposting/<jobId>?source=searchresults`

Внутри карточки я увидел такую структуру:

- title / source / employer / location / salary
- дата публикации
- иногда badge-метки
- отдельная кнопка `Save to favourites`

Примеры observed badges:

- `New`
- `Hybrid`
- `On site`
- `Direct Apply`
- `Posted on Job Bank`

Источник карточки может быть разным:

- CareerBeacon
- indeed.com
- Talent.com
- Job Bank

### Как хранится контент в карточке

Поля лежат очень просто:

- title и source внутри heading
- дата и employer внутри list items
- location в отдельном `listitem` с label `Location`
- salary в отдельном `listitem` с label `Salary`
- action button для favourites отдельно от ссылки на вакансию

Это удобно для селектора по `article` + вложенные `listitem`.

### Load more

Внизу списка есть:

- `Show more results`

Это значит, что парсер должен уметь:

- читать текущий список
- нажимать load-more
- дочитывать новые карточки

Не стоит рассчитывать только на классическую numbered pagination.

## 5. Listing filters

Фильтры на Job Bank очень семантичные.
Я видел такие блоки:

- `Location` input
- `Interactive map`
- `Provinces and territories`
- `Related job titles`
- `Date posted`
- `Type of job`
- `Hours of work`
- `Language at work`
- `Salary`
- `Period of employment`
- `Employment groups`
- `Work location`
- `Job source`
- `Intended applicants`
- `Top related job categories`
- `Labour Market Impact Assessment (LMIA)`

### Структура фильтров

Некоторые фильтры раскрываются как `heading`, часть как `radiogroup`, часть как набор `checkbox`.

Самая полезная часть для скрапера:

- `Provinces and territories` - набор checkbox-ов с count
- `Date posted` - отдельная группа
- `View more filters` - переход в advanced search

### Пример структуры provinces

Каждый регион идет как checkbox с подсказкой вида:

- `Ontario 62 jobs found`
- `Québec 13 jobs found`
- `British Columbia 9 jobs found`

Это уже готовые агрегированные counts, которые можно использовать как faceted search data.

### URL patterns фильтров

На странице и в ссылках встречаются такие паттерны:

- `?fn21=21231&page=1&sort=M&term=software+engineer`
- `?fn21=21231&page=1&sort=D&term=software+engineer`
- `/jobsearch/advancedsearch?fn21=21231&term=software+engineer&page=1&sort=M`
- `/jobsearch/jobalert/indregister/fn21=21231&term=software+engineer&page=1&sort=M`
- `/jobsearch/feed/jobSearchRSSfeed?...`

## 6. Job detail DOM

### Top warning dialog

На detail page первым делом показывается warning dialog:

- сайт видит, что пользователь outside Canada
- предупреждает, что не на все вакансии можно податься
- есть ссылка на `foreign candidates`

Это важный access signal для скрапера и для UX.

### Main title block

В detail page я увидел:

- `h1` с названием вакансии
- subtitle `Title posted on <source>`
- строка `Posted on <date> by`
- `Employer details`
- имя работодателя жирным текстом

### Action buttons

Есть блок действий:

- `Add to favourites`
- `Actions`

Здесь нет внутреннего company profile.
Это именно job posting page с внешним происхождением.

### Job details section

Самая полезная секция.

Внутри `Job details` я видел такие поля:

- `Location`
- `Work location`
- `Salary`
- `Terms of employment`
- `Starts as soon as possible`
- `Source`

Пример текста:

- `Vancouver, BC`
- `On site`
- `31.00 to 82.00 hourly`
- `Permanent employment`
- `Full time`
- `CareerBeacon #2867905`

### External source link

Есть link:

- `View the full job posting on CareerBeacon`

Это ключевой apply/outbound path:

- Job Bank показывает агрегированную запись
- полная вакансия открывается на партнерском сайте

### Expiry

Есть блок:

- `Advertised until`
- дата, например `2026-04-05`

### Notice

Есть важное уведомление:

- `This job posting has been provided by a partner site. Job Bank is not responsible for this content.`

Это надо учитывать при сборе и дедупликации.

### Report a problem

Есть action:

- `Report a problem with this job posting`

### Plus account upsell

Есть upsell блок:

- `Sign up for a Plus account`

Это не часть вакансии, но это часть DOM и может мешать наивному парсингу.

### Job market information

Очень ценная секция с дополнительными данными:

- occupation link `software engineer`
- `NOC 21231`
- region link, например `Lower Mainland–Southwest Region`
- `Median wage`
- link `Explore this career`

Для tech-аналитики это полезный enrichment слой.

### Similar job postings

Есть блок похожих вакансий:

- список ссылок на другие jobposting IDs
- link `Similar job postings`

Это хороший источник для обхода соседних вакансий.

## 7. URL patterns

### Main patterns

- Home: `/home`
- Search: `/jobsearch/jobsearch?searchstring=...&locationstring=...`
- Detail: `/jobsearch/jobposting/<id>?source=searchresults`
- RSS: `/jobsearch/feed/jobSearchRSSfeed?...`
- Advanced search: `/jobsearch/advancedsearch?...`
- Jobalert registration: `/jobsearch/jobalert/indregister/...`
- Market reports: `/marketreport/...`
- Foreign candidates: `/findajob/foreign-candidates`

### Important parameters

- `searchstring`
- `locationstring`
- `page`
- `sort`
- `fn21`
- `term`
- `mid`
- `source`
- `jsessionid`

`fn21=21231` выглядит как внутренний occupation/NOC code для software engineer search.

## 8. JSON-LD / embedded data / network

### JSON-LD

В живом DOM snapshot я не увидел богатой `application/ld+json` разметки на этих страницах.
Для Job Bank основной слой данных - **HTML DOM**, а не structured data.

### Embedded data

По наблюдениям:

- страница довольно SSR-friendly
- много данных сразу лежит в тексте и списках
- отдельные блоки строятся без тяжелого client-side state

### Network / endpoint signals

На странице есть много route-level endpoints, которые полезны как data source:

- `/jobsearch/feed/jobSearchRSSfeed`
- `/jobsearch/advancedsearch`
- `/marketreport/jobs/...`
- `/marketreport/wages-occupation/...`
- `/marketreport/summary-occupation/...`

Для текущего скана я не увидел отдельного GraphQL слоя или крупного JSON API, как на более JS-heavy job boards.
Модель здесь ближе к classic server-rendered portal.

### Console issue

В listing snapshot в console был зафиксирован JS error:

- `TypeError: Cannot read properties of null (reading 'appendChild')`
- источник: `addCurrentLocationLink`

Это стоит учитывать как потенциальный stability signal для браузерной автоматизации.

## 9. Auth / ограничения

### Sign in

На home и search page есть `Sign in`, но базовый поиск доступен без логина.

### Outside Canada warning

На detail page открывается предупреждение о доступе из-за пределов Канады.
Смысл:

- не все вакансии подходят международным кандидатам
- Job Bank явно ведет фильтрацию по eligibility

### Basic HTML

Есть `Switch to basic HTML version`.
Это полезный fallback, если нужен максимально простой DOM.

### Partner content

Большая часть detail pages может быть партнерским листингом.
Тогда:

- Job Bank показывает агрегат
- полная вакансия уходит на внешний сайт
- apply делается на source site, не внутри Job Bank

## 10. Primary selectors

### Home

- Search keywords input: `input[placeholder="Job title, employer"]`
- Search location input: `input[placeholder="City, province or territory"]`
- Search button: button with text `Search`
- Advanced button: button with text `Advanced`

### Listing

- Results container: main search results block under `article`
- Job card root: `article`
- Job card link: `a[href^="/jobsearch/jobposting/"]`
- Save favourite: button with text `Save to favourites`
- Load more: button with text `Show more results`

### Detail

- Title: `h1`
- Job details heading: `h2` with text `Job details`
- External source link: `a[href*="careerbeacon"]` or generic `View the full job posting on ...`
- Similar job postings: section with heading `Similar job postings`

### Filters

- Filters heading: `h2` with text `Filters`
- Provinces and territories: heading text `Provinces and territories`
- Date posted: heading text `Date posted`
- View more filters: link `View more filters`

## 11. Fallback selectors

Если primary role/text selectors изменятся, я бы падал назад на:

- `article` for job cards
- `listitem` within job card for date/employer/location/salary
- text match on `Location`, `Salary`, `Terms of employment`, `Source`
- `a[href*="/jobsearch/jobposting/"]`
- `a[href*="/marketreport/"]`
- `a[href*="/jobsearch/feed/jobSearchRSSfeed"]`

## 12. Field mapping

| Field | Primary source | Fallback |
|---|---|---|
| `job_id` | `a[href*="/jobsearch/jobposting/<id>"]` | any detail URL / similar postings URL |
| `title` | `h1` on detail, card heading on listing | anchor text inside card |
| `source` | card heading prefix / detail subtitle | `Source` row on detail page |
| `employer` | card `listitem` and detail employer bold text | partner source name |
| `posted_at` | card date row / `Posted on March ...` | detail top paragraph |
| `location` | card location row / detail `Location` row | market report region link |
| `work_location` | detail `Work location` row | badge text on card (`On site`, `Hybrid`) |
| `salary` | card salary row / detail salary row | market wage page |
| `employment_terms` | detail `Terms of employment` | card badges / related text |
| `start_date` | detail `Starts as soon as possible` | none |
| `expiry_date` | detail `Advertised until` | partner source page if available |
| `noc` | `Job market information` block | market report pages |
| `median_wage` | `Job market information` block | wage report link |
| `apply_url` | external `View the full job posting on ...` | partner source page |
| `similar_jobs` | `Similar job postings` section | listing result cards |

## 13. 2-pass parser strategy

### Pass 1: listing harvest

Собираем:

- job card URL
- title
- source
- employer
- posted_at
- location
- salary
- badges
- whether it is `Direct Apply`
- whether it is partner content

Идем через:

- initial results
- `Show more results`
- optional filter expansion

### Pass 2: detail enrichment

Для каждой карточки открываем detail page и добираем:

- exact employer
- work location
- employment terms
- start date
- expiry date
- NOC
- regional market info
- median wage
- similar jobs
- external apply/source link

### Why this order

Такой порядок минимизирует лишние переходы:

- сначала дешево и быстро собираем список
- потом только нужные записи добираем на detail
- partner content и apply path уже обрабатываем отдельным шагом

## 14. Practical notes for scraper

1. Job Bank очень хорошо подходит для **structured crawling**.
2. Самая большая сложность здесь не DOM, а **партнерские внешние источники**.
3. Для международных кандидатов обязательно проверять warning / eligibility signals.
4. Для bulk-загрузки полезно сохранять `jobposting/<id>` как canonical key.
5. RSS feed может быть дополнительным источником, если нужен быстрый refresh.

## 15. Проверенные URL

- `https://www.jobbank.gc.ca/home`
- `https://www.jobbank.gc.ca/jobsearch/jobsearch?searchstring=software+engineer&locationstring=`
- `https://www.jobbank.gc.ca/jobsearch/jobposting/49050568?source=searchresults`
