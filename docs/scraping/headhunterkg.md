# bishkek.headhunter.kg parser report

Дата проверки: 2026-03-21

## Краткий вывод
`bishkek.headhunter.kg` хорошо парсится как **SSR job board с сильной семантикой**. У сайта есть стабильные `data-qa` якоря, понятные URL-паттерны, отдельные API/shards для related vacancies, counters и interactions, а на detail page присутствует полноценный `JobPosting` JSON-LD. Для company page structured data не найдено, поэтому там лучше опираться на DOM.

## Карта страниц
Сайт удобно делится на несколько типов страниц.

- `home` и общий вход на региональный хост
- `listing/search` на `/vacancies`
- `detail` на `/vacancy/<id>`
- `company` на `/employer/<id>`
- `apply flow` внутри detail page через response/signup/login блоки

## Home / entry
На домашнем уровне видны базовые навигационные элементы, но для парсинга важнее не лендинг, а список вакансий.

Что полезно для scraper:
- выбор региона в шапке, например `Бишкек`
- ссылка на смену типа пользователя `Соискателям` / `Работодателям`
- вход в аккаунт `Войти`
- создание резюме `Создать резюме`
- общий search entry в шапке

Стабильный смысловой вывод: домашняя страница ведет к поиску вакансий, но сама по себе не несет основного контента.

## Listing / Search
Рабочая страница списка: `https://bishkek.headhunter.kg/vacancies`

### Видимые поля и структура
Главные элементы страницы списка:
- H1: `Работа в Бишкеке`
- счетчик вакансий: `3 125 вакансий`
- блок сортировки: `По соответствию`, `За всё время`
- search input: `Профессия, должность или компания`
- advanced search button: `Расширенный поиск`
- save search button: `Сохранить поиск`
- кнопка `Найти`

Фильтры в левой колонке представлены семантическими группами и чекбоксами:
- `Регион`
- `Соседние города`
- `Специализации`
- `Указан доход`
- `Частота выплат`
- `Исключить слова`
- `Уровень дохода`

### Стабильные селекторы
На этой странице особенно полезны:

```css
input[placeholder="Профессия, должность или компания"]
button:has-text("Расширенный поиск")
button:has-text("Сохранить поиск")
button:has-text("Найти")
button[data-qa="vacancy-serp__vacancy"]
a[href^="https://bishkek.headhunter.kg/vacancy/"]
a[href^="/employer/"]
a[data-qa="vacancy-serp__vacancy_response"]
nav a[href*="/vacancies?page="]
```

### Карточка вакансии
Карточки вакансий на listing page устроены очень удобно для парсинга.

У одной карточки внутри обычно есть:
- title link внутри `heading h2`
- salary block
- experience block
- payment frequency block
- company link
- location text
- status text вроде `Отклик без резюме`
- apply button `Откликнуться`
- contacts button `Контакты`

Наиболее устойчивые якоря:
- корень карточки: `button[data-qa="vacancy-serp__vacancy"]`
- title link: `a[href^="https://bishkek.headhunter.kg/vacancy/"]`
- employer link: `a[href^="/employer/"]`
- response link: `a[data-qa="vacancy-serp__vacancy_response"]`

### URL patterns
На listing page используются такие паттерны:
- `/vacancies`
- `/vacancies?page=1&search_session_id=...`
- `search_session_id` стабилизирует сессию выдачи
- `hhtmFrom=vacancy_search_list` помогает понять источник перехода

Внизу есть обычная пагинация с номерами страниц, например `1`, `2`, `3`, `40`.

### Полезные наблюдения
- список SSR-рендерится, так что карточки доступны без сложного hydration
- в выдаче есть промо/служебные блоки вроде подписки на новые вакансии
- URL карточки вакансии всегда нормализован и ведет на детальную страницу

## Detail / Vacancy
Пример detail page: `https://bishkek.headhunter.kg/vacancy/131367287?hhtmFrom=vacancy_search_list`

### Верхний блок
На detail page видны:
- title: `Водитель-экспедитор`
- salary: `от 63 000 сом за месяц, на руки`
- experience: `Опыт работы: 1–3 года`
- work type: `Полная занятость`
- schedule: `График: 6/1 или 5/2`
- working hours: `Рабочие часы: 8`
- view counter: `Сейчас эту вакансию смотрят 4 человека`

### Apply / action buttons
Верхние action buttons:
- `Откликнуться`
- `Контакты`
- `Добавить в избранное`

Стабильный якорь для apply flow:
- `a[data-qa="vacancy-response-link-top"]`

### Описание вакансии
Описание структурировано очень семантично:
- `Обязанности`
- `Требования`
- `Условия`
- `Ключевые навыки`
- `Контакты`
- `Задайте вопрос работодателю`
- `Где предстоит работать`
- `Похожие вакансии`

Это дает простой DOM mapping: заголовок секции -> содержимое следующего блока.

### Локация и карта
На detail page есть:
- адрес работы: `Бишкек, улица Тимура Фрунзе, 2`
- link на карту: `Показать на большой карте`
- отдельный map route: `/search/vacancy/map?vacancy_id=131367287&hhtmFrom=vacancy`

### Similar vacancies
Ниже есть блок `Похожие вакансии` с такими же повторяющимися карточками, но уже в detail-context. Их полезно парсить отдельно, если нужен graph recommendations.

## Company / Employer
Пример company page: `https://bishkek.headhunter.kg/employer/2457065?hhtmFrom=vacancy`

### Верхний блок
Здесь видны:
- company title: `ОсОО РУСТЭЛЬ`
- logo
- button `Подписаться`
- tabs `О компании` и `Вакансии 6`

### Company content
Внутри `О компании` присутствуют:
- company description paragraphs
- списки `Что мы делаем`
- `Кто мы`
- `Наши ценности`
- `Почему к нам`
- `Кому у нас будет интересно`

### Company info fields
Семантический блок company info содержит:
- `Город` -> `Бишкек`
- `Сферы деятельности` -> `Продукты питания`
- `Тип регистрации` -> `Организация`
- `Сайт` -> `http://www.rustel.kg/`

### Стабильные селекторы
```css
h1
button:has-text("Подписаться")
role=tab[name="О компании"]
role=tab[name="Вакансии 6"]
a[href^="/employer/"]
a[href^="http://www.rustel.kg/"]
```

## Apply flow
Apply flow у hh KG не уходит на отдельный отдельный “чистый” apply page, а раскрывается как встроенный response/signup flow внутри detail page.

Что видно у неавторизованного пользователя:
- top apply link ведет на `/applicant/vacancy_response?vacancyId=131367287&employerId=2457065&hhtmFrom=vacancy`
- login link сохраняет `backurl` на `after_login`
- signup form просит `Номер телефона`
- кнопка продолжения: `Продолжить`
- присутствует текст оферты и link на соглашение

Ключевой login/backurl pattern:
- `/account/login?role=applicant&backurl=%2Fapplicant%2Fvacancy_response%2Fafter_login%3FvacancyId%3D131367287&hhtmFrom=vacancy`

Вывод для парсера: отклик здесь лучше считать **двухшаговым flow**.

## JSON-LD / embedded state
### JSON-LD
На vacancy detail page найден полноценный `script[type="application/ld+json"]` с `JobPosting`.

Поля из JSON-LD:
- `@type: JobPosting`
- `title`
- `description`
- `datePosted`
- `validThrough`
- `hiringOrganization.name`
- `jobLocation.address.addressLocality`
- `jobLocation.address.addressCountry`
- `jobLocation.address.streetAddress`
- `applicantLocationRequirements.name`
- `employmentType`
- `identifier.value`

Важно: **salary в JSON-LD на этом примере нет**, salary берется из DOM.

На employer page JSON-LD не найден.

### Embedded state
На сайте не найдено типичных globals вроде:
- `window.__INITIAL_STATE__`
- `window.__NEXT_DATA__`
- `window.__NUXT__`
- `window.__APOLLO_STATE__`

Но есть `window.qaState` с очень маленьким набором ключей:
- `errors`
- `axiosRequests`
- `scrollTopProcessing`
- `autotestsComponentsInitEnd`

Это скорее runtime instrumentation, чем полезный state для контента.

## Network / XHR
На странице используются несколько полезных внутренних endpoints.

### Vacancy detail
- `GET /shards/vacancy/related_vacancies?vacancyId=...&page=0&search_session_id=...`
- `GET /shards/vacancy_view_count?vacancyId=...`
- `GET /shards/banners/targeting_params?currencyCode=KGS&salary=...&area=...&roles=...&vacancyTitle=...`
- `POST /shards/vacancy/register_interaction`
- `GET /tracking/response?vacancy_id=...&employer_id=...`
- `POST /notices/mark_as_viewed`
- `POST /anatskytics` для analytics/view-duration

### Third-party / tracking noise
- Google Analytics
- Yandex Metrika
- AdFox
- Sentry
- UXFeedback widget
- google.com ads audiences

### Что это значит для scraper-а
- контент можно брать из SSR HTML и JSON-LD
- network полезен как supplemental source, особенно для related vacancies и счетчиков
- `anatskytics` и analytics лучше игнорировать, это telemetry

## Auth / Anti-bot
Классического CAPTCHA/Turnstile/Cloudflare challenge на проверенных страницах не было видно.

Что есть вместо этого:
- login gate для apply flow
- `backurl` и `after_login` маршруты
- много аналитических и tracking запросов
- `blocked_by_client` ошибки в консоли из-за расширения браузера, а не из-за сайта

Для неавторизованного пользователя apply и контакты частично доступны как UI-слой, но продолжение требует user flow.

## Primary selectors
### Listing
- `button[data-qa="vacancy-serp__vacancy"]`
- `a[href^="https://bishkek.headhunter.kg/vacancy/"]`
- `a[href^="/employer/"]`
- `a[data-qa="vacancy-serp__vacancy_response"]`
- `input[placeholder="Профессия, должность или компания"]`
- `nav a[href*="/vacancies?page="]`

### Vacancy detail
- `h1`
- `a[data-qa="vacancy-response-link-top"]`
- `button:has-text("Показать контакты")`
- `button:has-text("Контакты")`
- `button:has-text("Добавить в избранное")`
- `a[href*="/search/vacancy/map?vacancy_id="]`

### Company page
- `h1`
- `role=tab[name="О компании"]`
- `role=tab[name="Вакансии 6"]`
- `a[href^="http://www.rustel.kg/"]`
- `button:has-text("Подписаться")`

## Fallback selectors
Если `data-qa` или role selectors поменяются, fallback лучше строить так:
- title links через `h2 a`
- employer links через `/employer/`
- vacancy cards через `button[role="button"]` внутри списка выдачи
- apply button через текст `Откликнуться` в верхнем блоке страницы
- company info через текстовые labels `Город`, `Сферы деятельности`, `Тип регистрации`, `Сайт`

## Field mapping table
| Field | Primary source | Fallback | Notes |
|---|---|---|---|
| vacancy_id | URL `/vacancy/<id>` | JSON-LD `identifier.value` | Stable anchor |
| title | `h1` on detail, title link on listing | JSON-LD `title` | Use detail as source of truth |
| salary | visible DOM on detail/list card | none | Not present in JSON-LD on sample |
| experience | detail DOM | listing card summary | Often duplicated |
| employment_type | detail DOM and JSON-LD | card summary | Example: `FULL_TIME` |
| schedule | detail DOM | none | Human-readable block |
| location | detail DOM + employer page | JSON-LD `jobLocation.address` | City and street are useful |
| employer_name | employer link text | JSON-LD `hiringOrganization.name` | Consistent across pages |
| employer_id | `/employer/<id>` | page source / link href | Stable numeric id |
| description | detail DOM sections | JSON-LD `description` | JSON-LD contains HTML markup |
| posted_at | detail footer `Вакансия опубликована ...` | JSON-LD `datePosted` | JSON-LD preferred |
| valid_through | none visible | JSON-LD `validThrough` | Great for expiry |
| apply_url | `a[data-qa="vacancy-response-link-top"]` | login `backurl` pattern | Two-step flow |
| company_site | employer page `a[href^="http"]` | none | Domain-level trust signal |

## 2-pass parser strategy
### Pass 1: listing crawl
- crawl `/vacancies`
- collect vacancy URLs
- collect employer URLs and employer ids
- capture salary, location, experience, quick status flags
- store `search_session_id` and page number for reproducibility

### Pass 2: detail + company enrichment
- open each vacancy detail URL
- parse JSON-LD first
- parse visible DOM sections second
- extract apply/login flow URLs
- open employer page to enrich company description and company metadata
- store related vacancies if needed

This split is important because listing gives breadth, while detail/company pages give high-quality structured content.

## Checked URLs
- `https://bishkek.headhunter.kg/`
- `https://bishkek.headhunter.kg/vacancies`
- `https://bishkek.headhunter.kg/vacancy/131367287?hhtmFrom=vacancy_search_list`
- `https://bishkek.headhunter.kg/employer/2457065?hhtmFrom=vacancy`
- `https://bishkek.headhunter.kg/search/vacancy/map?vacancy_id=131367287&hhtmFrom=vacancy`
- `https://bishkek.headhunter.kg/applicant/vacancy_response?vacancyId=131367287&employerId=2457065&hhtmFrom=vacancy`
- `https://bishkek.headhunter.kg/account/login?role=applicant&backurl=%2Fapplicant%2Fvacancy_response%2Fafter_login%3FvacancyId%3D131367287&hhtmFrom=vacancy`
- `https://bishkek.headhunter.kg/notices/mark_as_viewed`
- `https://bishkek.headhunter.kg/shards/vacancy/related_vacancies?vacancyId=131367287&page=0&search_session_id=8c0a0443-ed74-4ca5-a557-6e4cfc464a51`
- `https://bishkek.headhunter.kg/shards/vacancy_view_count?vacancyId=131367287`
- `https://bishkek.headhunter.kg/shards/banners/targeting_params?currencyCode=KGS&salary=63000&area=2760&roles=21&vacancyTitle=%D0%92%D0%BE%D0%B4%D0%B8%D1%82%D0%B5%D0%BB%D1%8C-%D1%8D%D0%BA%D1%81%D0%BF%D0%B5%D0%B4%D0%B8%D1%82%D0%BE%D1%80`
