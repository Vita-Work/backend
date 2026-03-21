# hh.ru parser report

Дата проверки: 21 марта 2026 года. Источник исследования: `https://hh.ru/?hhtmFrom=main` и связанные страницы внутри hh.ru, просмотренные через Playwright MCP. Ниже описана не “красота интерфейса”, а именно то, как устроены страницы для последующего парсинга: где лежит основной контент, какие есть устойчивые селекторы, где находится структурированная разметка, какие есть URL-паттерны, какие поля можно извлекать, и как лучше строить двухпроходный парсер.

## Краткий вывод

hh.ru — это **гибрид SSR + динамический фронтенд**, где большая часть полезного контента уже присутствует в DOM на сервере, а JavaScript в основном добавляет навигацию, фильтры, аналитические события, личные сценарии и динамические оверлеи. Для парсинга это хороший знак: базовые данные по вакансиям, компаниям, зарплатам, дате публикации и ссылкам на отклик можно брать из HTML и JSON-LD, а не пытаться воспроизводить сложную внутреннюю логику. Самые полезные якоря здесь — `data-qa` атрибуты на карточках, деталке и странице компании, плюс `application/ld+json` на vacancy detail.

## 1. Домашняя страница

Домашняя страница работает как входная точка, а не как источник массовых данных. В DOM видно верхнее меню, региональный переключатель, логин/регистрацию, поисковую кнопку и блоки с подсказками для соискателя и работодателя. На этой странице важно не столько собирать вакансии, сколько понимать общую навигацию и точки входа в поиск.

Из устойчивых элементов на home полезны `data-qa` якоря `mainmenu_areaSwitcher`, `mainmenu_employer`, `mainmenu_expertresume`, `mainmenu_interviewpractice`, `mainmenu_applicantServices`, `searchVacancy-button`, `login`, `signup`, а также cookie-banner `cookies-policy-informer` и кнопка согласия `cookies-policy-informer-accept`. Для региона есть модальный вопрос вида “Ваш регион — Москва?”, что означает наличие региональной персонализации, которую лучше учитывать при массовом обходе.

По структуре home лучше рассматривать как страницу с навигационным каркасом и маркетинговыми блоками. Для парсера ее можно использовать как fallback-источник ссылок на поиск, но не как основной источник вакансий.

## 2. Listing / search page

Страница поиска вакансий в формате `https://hh.ru/vacancies/programmist` уже является основным источником карточек и фильтров. Здесь видны заголовок каталога, строка поиска, блоки фильтров, список вакансий и пагинация. Именно эта страница лучше всего подходит для первичного сбора массового каталога.

### Как устроен список вакансий

Основной контейнер результатов — `vacancy-serp__results`. Карточки вакансий маркируются как `vacancy-serp__vacancy`, а кликабельный заголовок обычно лежит в `a[data-qa="serp-item__title"]`. Название вакансии дополнительно доступно через `serp-item__title-text`. Компания у карточки лежит в `a[data-qa="vacancy-serp__vacancy-employer"]`, локация — в `vacancy-serp__vacancy-address`, а CTA на отклик — в `a[data-qa="vacancy-serp__vacancy_response"]`. На карточках также встречаются блоки контактов `vacancy-serp__vacancy_contacts`, опыта `vacancy-serp__vacancy-work-experience-*` и зарплаты в тексте карточки, где часто присутствуют суммы и пометка “за месяц”, “за неделю”, “за две недели”, “на руки” или “до вычета налогов”.

Из важного: зарплата на listing-page может быть представлена как текст внутри карточки, а не отдельным универсальным DOM-атрибутом. Поэтому для надежности нужно парсить и текстовый фрагмент карточки, и дочерние элементы, если они присутствуют. Для точного извлечения salary лучше делать правило “сначала ищем salary-подблок, если он есть, иначе берем текст карточки и вырезаем regex-ом денежные паттерны”.

### Фильтры

На странице поиска hh.ru сильно опирается на фильтры с `data-qa` префиксом `serp__novafilter-*` и соседние элементы формы. Видны:
`search-input`, `search-button`, `search-period-menu`, `serp__criterias`, `serp__novafilter-group`, `serp__novafilter-group-title`, `novafilters-excluded-text-input`, `novafilters-custom-compensation`, `filter-select-trigger-compensation_frequency`.

Региональные и гео-фильтры также хорошо размечены: `serp__novafilter-area-1`, `serp__novafilter-area-2019`, разные district- и metro-элементы вроде `serp__novafilter-district-139`, `serp__novafilter-metro-135.855`. Для предметной области есть фильтры по названию, компании и описанию через `serp__novafilter-search_field-name`, `serp__novafilter-search_field-company_name`, `serp__novafilter-search_field-description`. Для режима работы и занятости есть `serp__novafilter-employment_form-FULL`, `...-PART`, `...-PROJECT`, `...-FLY_IN_FLY_OUT`, а также `serp__novafilter-work_format-ON_SITE`, `...-REMOTE`, `...-HYBRID`, `...-FIELD_WORK`.

Это очень полезно для парсера, потому что часть фильтров можно либо воспроизводить напрямую через URL, либо использовать для понимания формы поиска. Самый сильный вывод здесь такой: hh.ru уже сам размечает фильтры достаточно стабильно, поэтому не нужно цепляться за случайные CSS-классы.

### Пагинация

Пагинация на listing устроена через обычные ссылки страниц, и в URL виден важный паттерн: `?page=N&search_session_id=...&hhtmFrom=vacancy_search_list`. Это значит, что для обхода страниц можно опираться на обычный page-параметр, но лучше сохранять session id и остальные query-параметры, если нужно воспроизвести тот же список.

Практически для парсера это означает: берём первую страницу поиска, сохраняем все query-параметры, затем идём по `page=2`, `page=3` и так далее до конца пагинации. Если hh.ru меняет выдачу по сессии, то `search_session_id` лучше не отбрасывать.

### Что полезно забирать с listing

Список вакансий на этой странице можно использовать для: title, employer name, employer link, vacancy url, salary text, city/metro, experience, response CTA, contact hints, labels и отдельных служебных флагов вроде accredited IT, remote/hybrid и agency/not-from-agency. Важно, что listing page уже содержит достаточно данных для грубого ранжирования без перехода на detail.

## 3. Vacancy detail page

Страница вакансии — это главный источник полной карточки. На примере `https://hh.ru/vacancy/131430293?...` видно, что detail page содержит и структурированный JSON-LD, и человекочитаемый DOM, и блоки для отклика, вопросов, адреса, компании, похожих вакансий и отзывов.

### Что есть в DOM

На деталке есть заголовок вакансии, кнопка отклика `Откликнуться`, кнопка избранного, блок компании с названием, доверенным статусом, рейтингом и количеством отзывов, блок “Где предстоит работать”, блок вопросов работодателю, публикация вакансии, похожие вакансии и блоки с отзывами. Важные ориентиры в DOM: `company-header-title`, `company-header-title-name`, `trusted-employer-link`, `employer-review-small-widget-total-rating`, `employer-review-small-widget-review-count-action`, `accredited-it-employer-icon`, а также элементы формы отклика с телефоном и кнопкой продолжения.

Особенно полезен блок “Где предстоит работать”: там можно брать точный адрес, район, карту и текст локации. Для парсинга адреса это надежнее, чем вытаскивать его только из title или из поисковой выдачи.

### JSON-LD

На detail page hh.ru встраивает `application/ld+json` с типом `JobPosting`. Это один из самых ценных источников для парсера, потому что там уже есть нормализованные поля. На проверенной вакансии были найдены: `title`, `description`, `datePosted`, `validThrough`, `hiringOrganization.name`, `employmentType`, `identifier.value`, `jobLocation.address.addressLocality`, `jobLocation.address.addressRegion`, `jobLocation.address.addressCountry`, `jobLocation.address.streetAddress`, `applicantLocationRequirements.name`.

Это значит, что для detail page JSON-LD можно считать **первым источником истины**, а DOM использовать как fallback и для дополнительных полей. Если JSON-LD есть, он сильно упрощает парсинг: большая часть полей уже приведена к schema.org-формату.

### Apply flow

Отклик у незалогиненного пользователя идет не как простой POST на вакансию, а как отдельный сценарий с формой и/или логин-барьером. На проверенной странице видно поле для телефона `Номер телефона` и кнопку `Продолжить`, а также backurl вида `/applicant/vacancy_response/after_login?vacancyId=...`. Это означает, что apply flow у hh.ru нужно считать многошаговым: сначала инициируется отклик, затем либо идет ввод телефона, либо редирект на авторизацию, либо дальше открывается форма доп.вопросов и подтверждений.

Для автоматики это важно: парсер не должен думать, что кнопка “Откликнуться” сразу ведет к финальному submit. Скорее всего, нужно моделировать цепочку состояний: vacancy open -> response start -> auth/phone gate -> continue -> final application state. Если цель только парсинг, достаточно фиксировать наличие CTA и url/формы, а не имитировать полный отклик.

## 4. Company / employer page

Страница работодателя на примере `https://hh.ru/employer/999442?hhtmFrom=vacancy` устроена как отдельный контентный объект. Здесь есть логотип, название компании, верификация, рейтинг, отзывы, описание бизнеса, отрасль, адрес, сайт, подписка, вкладки описания и вакансий, а также блоки с преимуществами и review widgets.

### Что можно извлекать

На этой странице полезны: `company-logo-image`, `company-header-title`, `company-header-title-name`, `trusted-employer-link`, `employer-review-small-widget-total-rating`, `employer-review-small-widget-review-count-action`, `employer__search-saved`, `resumeservice-button__targetemployer`, `employer-page-tabs-desktop-go-DESCRIPTION`, `employer-page-tabs-desktop-go-VACANCIES`, `employer-page-company-info`, `company-info-address`, `company-info-industries`, `company-info-category`, `advantage-accredited-it-employer`, `sidebar-company-site`.

Ревью-блоки тоже полезны: `employer-review-big-widget-reviews-summary`, `employer-review-big-widget-dream-job-rating`, `employer-review-big-widget-reviews-recommendation`, `employer-review-big-widget-benefits`, а у отдельных отзывов — `review-card-content-title`, `review-card-content-rating-row`, `review-card-content-text`. Если нужен enrichment по компании, это хороший источник для агрегатов, а не только для вакансий.

### Как это использовать в парсере

Company page стоит считать вторым ключевым объектом после vacancy detail. Обычно workflow такой: сначала берется vacancy, из нее берется employer link, затем открывается employer page и подтягиваются поля компании. Там можно собрать логотип, отрасли, адрес, сайт, рейтинг, отзывы, число вакансий и признаки типа “аккредитованная IT-компания”.

## 5. URL patterns

На hh.ru видны стабильные шаблоны. Главная страница — `https://hh.ru/?hhtmFrom=main`. Страницы выдачи обычно идут как `/vacancies/<query>` или `/search/vacancy` с параметрами. Деталка вакансии идет как `/vacancy/<id>` и часто имеет дополнительные query-параметры типа `query`, `hhtmFrom`, `from`, `area`, `text`. Страница работодателя идет как `/employer/<id>`.

Для отклика есть отдельные маршруты с backurl в applicant-ветку, например `.../applicant/vacancy_response/after_login?vacancyId=...`. Пагинация использует `page=N` и дополнительные search-session параметры. Для сбора данных лучше сохранять исходный URL целиком, потому что часть параметров влияет на регион, сортировку и session state.

## 6. JSON-LD и embedded state

Важная особенность hh.ru в том, что нужные данные приходят не только через DOM. На listing page найден `application/ld+json`, но там только `BreadcrumbList`. На vacancy detail page есть полноценный `JobPosting`. На employer page JSON-LD не обнаружен, поэтому по компании нужно полагаться на DOM и встроенное JS-state.

В глобальном JS виден объект `globalVars`, где есть полезные вещи вроде `apiHost`, `apiXhhHost`, `staticHost`, `hhcdnHost`, `siteId`, `country`, `area`, `locale`, `userType`, `pageName`, `requestId`, `analyticsParams` и другие служебные параметры. Это не прямой контент, но очень полезная часть embedded state: она подсказывает, откуда сайт может брать данные, как он идентифицирует регион и какие базовые хосты использовать.

Вывод простой: если нужен быстрый и надежный parser, то priority такой: **JSON-LD -> DOM -> embedded state -> network fallback**. На vacancy detail это особенно хорошо работает.

## 7. Network / XHR

В сетевых запросах hh.ru много аналитики, событий просмотра, трекинга и feature/experiment инфраструктуры. Были замечены запросы к `anatskytics`, `notices/mark_as_viewed`, `api/fl`, `mc.yandex.ru`, `top-fwz1.mail.ru`, `eye.targetads.io`, `widget-api.uxfeedback.ru`, `sentry.hh.ru`, `bobid-ip.hybrid.ai`, `fpf.hybrid.ai`, `matchid.adfox.yandex.ru`, `adsrv.hh.ru`.

Это говорит о том, что реальные данные страницы, скорее всего, не зависят от тяжелого client-side API, а в основном уже лежат в HTML. Сетевой слой полезен больше для понимания логики, аналитики и возможных внутренних endpoints, чем как основной источник контента. Для парсера это хорошая новость: можно не строить сложный reverse-engineering XHR, если DOM и JSON-LD уже дают все ключевые поля.

Если позже захочется углубить парсинг, стоит отдельно изучать `apiHost` и `apiXhhHost`, но на этом этапе это не обязательно.

## 8. Auth / anti-bot / legal

На проверенных страницах не было явной CAPTCHA или hard-block антибот-экрана. Вместо этого есть мягкие барьеры: cookie banner, региональная модалка, логин/регистрация, а на отклике — телефонный или auth-gate сценарий. Это значит, что hh.ru пытается не “ломать” доступ, а постепенно подталкивать пользователя в авторизацию и верификацию.

Для парсинга это означает две вещи. Первая: anonymous browsing вполне возможен для основных страниц. Вторая: apply flow и некоторые персональные действия будут ограничены без входа. Легальные предупреждения и служебные тексты в footer тоже присутствуют, включая упоминание рекомендательных технологий.

## 9. Primary selectors и fallback selectors

Ниже — практический список, который можно прямо брать в реализацию.

| Сущность | Primary selector / anchor | Fallback / пояснение |
|---|---|---|
| Home nav | `data-qa="mainmenu_areaSwitcher"` | верхнее меню, регион |
| Home employer link | `data-qa="mainmenu_employer"` | переход к employer-части |
| Search CTA | `data-qa="searchVacancy-button"` | кнопка перехода в поиск |
| Login / signup | `data-qa="login"`, `data-qa="signup"` | вход/регистрация |
| Cookie consent | `data-qa="cookies-policy-informer-accept"` | баннер согласия |
| Listing header | `data-qa="vacancies-catalog-header"` | заголовок каталога |
| Search input | `data-qa="search-input"` | форма поиска |
| Search submit | `data-qa="search-button"` | submit формы |
| Listing container | `data-qa="vacancy-serp__results"` | список результатов |
| Vacancy card | `data-qa="vacancy-serp__vacancy"` | карточка вакансии |
| Vacancy title link | `data-qa="serp-item__title"` | href на `/vacancy/<id>` |
| Employer link | `data-qa="vacancy-serp__vacancy-employer"` | href на `/employer/<id>` |
| Apply CTA in list | `data-qa="vacancy-serp__vacancy_response"` | кнопка отклика |
| Vacancy address | `data-qa="vacancy-serp__vacancy-address"` | город, метро, адрес |
| Vacancy experience | `data-qa` с `vacancy-serp__vacancy-work-experience-*` | years of experience |
| Detail title | `h1` / `company-header-title-name` | title вакансии |
| Detail apply CTA | `button` “Откликнуться” | start response flow |
| Detail employer | `trusted-employer-link` / company block | компания на detail |
| Detail rating | `employer-review-small-widget-total-rating` | рейтинг работодателя |
| Detail publication date | текст “Вакансия опубликована ...” | parsed datePosted |
| Detail JSON-LD | `script[type="application/ld+json"]` | `JobPosting` |
| Employer page title | `company-header-title` | название компании |
| Employer tabs | `employer-page-tabs-desktop-go-DESCRIPTION`, `...-VACANCIES` | переключение разделов |
| Employer info block | `employer-page-company-info` | адрес, отрасль, сайт |
| Employer site | `sidebar-company-site` | внешний сайт компании |
| Employer reviews | `employer-review-big-widget-*` | агрегаты и карточки отзывов |

Для fallback-парсинга карточек вакансий лучше иметь правило: если `data-qa` не найден, брать ближайший `article/li/div` в results container, искать внутри первый `<a>` с href на `/vacancy/`, второй `<a>` с href на `/employer/`, текст по salary regex и адрес/опыт по текстовым подблокам.

## 10. Field mapping table

Ниже — как я бы нормализовал поля hh.ru в единую схему для дальнейшего ingestion.

| Нормализованное поле | Источник на hh.ru | Как извлекать |
|---|---|---|
| `source` | hh.ru | константа |
| `vacancy_id` | URL `/vacancy/<id>` или JSON-LD `identifier.value` | regex из URL / JSON-LD |
| `vacancy_url` | link `serp-item__title` | href |
| `title` | listing title / JSON-LD title | текст карточки или JSON-LD |
| `company_name` | employer link text / JSON-LD hiringOrganization.name | DOM / JSON-LD |
| `company_url` | `vacancy-serp__vacancy-employer` | href |
| `location` | listing address / JSON-LD jobLocation | DOM / JSON-LD |
| `salary_text` | карточка listing / detail text | текст и regex |
| `salary_from` | если salary parsed | regex / structured salary block |
| `salary_to` | если salary parsed | regex / structured salary block |
| `salary_currency` | salary text | regex/маппинг |
| `salary_period` | salary text / labels | month/week/2 weeks |
| `experience_text` | listing experience block / detail info | DOM text |
| `date_posted` | JSON-LD `datePosted` | JSON-LD |
| `valid_through` | JSON-LD `validThrough` | JSON-LD |
| `employment_type` | JSON-LD `employmentType` | JSON-LD |
| `description_html` | JSON-LD `description` / detail DOM | JSON-LD first |
| `apply_url` | CTA route / after_login backurl / vacancy response flow | href / constructed route |
| `company_rating` | employer rating widgets | DOM |
| `company_reviews_count` | employer review count widget | DOM |
| `company_site` | employer sidebar site | DOM |
| `company_industry` | employer info block | DOM |
| `accredited_it` | badge/icon/text | DOM flag |

## 11. Two-pass parser strategy

Для hh.ru я бы делал **двухпроходный парсер**. Первый проход — легкий, массовый и устойчивый. Он работает по listing page и забирает карточки вакансий: `vacancy_id`, `vacancy_url`, `title`, `company_name`, `company_url`, `location`, `salary_text`, `experience_text`, `labels`, `apply_url`, а также параметры пагинации и сессионные query-поля. Этот проход нужен для обхода больших объемов и быстрой индексации.

Второй проход — глубокий. Он открывает detail page вакансии и employer page компании, затем берет `JobPosting` JSON-LD, полное описание, точные даты, employment type, address, company metadata, rating, reviews, site, accreditation flags и дополнительный контент. Если JSON-LD отсутствует или неполный, второй проход добирает поля из DOM. Если company page недоступна, можно оставить fallback на listing employer anchor.

Такой подход очень хорошо ложится на hh.ru, потому что listing уже дает хорошие “черновые” данные, а detail и employer page закрывают хвосты. Не стоит пытаться сразу тянуть все только с детальной страницы, потому что это сильно увеличит количество запросов. Лучше сначала собрать список, потом детализировать только нужные вакансии.

## 12. Практические замечания для парсинга

hh.ru стоит парсить как сайт, где **структурированный контент уже есть**, но он размазан между несколькими уровнями: listing, vacancy detail, employer page, JSON-LD и embedded state. Поэтому устойчивый pipeline должен уметь работать и с текстом, и с атрибутами, и с JSON-LD, и с fallback-логикой. Самое надежное решение здесь — не один селектор на все случаи, а маленький слой нормализации поверх нескольких источников.

Если резюмировать в одной фразе: **listing дает поток и базовые поля, detail дает точную вакансию, employer page дает контекст компании, JSON-LD дает чистую структуру, а network нужен в основном как вспомогательный слой**.

## 13. Проверенные URL

Проверенные страницы в рамках этого отчета:

- `https://hh.ru/?hhtmFrom=main`
- `https://hh.ru/vacancies/programmist`
- `https://hh.ru/vacancy/131430293?query=%D0%BF%D1%80%D0%BE%D0%B3%D1%80%D0%B0%D0%BC%D0%BC%D0%B8%D1%81%D1%82&hhtmFrom=vacancy_search_list`
- `https://hh.ru/employer/999442?hhtmFrom=vacancy`

## 14. Примечание по сессии

После завершения сканирования Playwright MCP-браузер был закрыт, чтобы следующий агент мог открыть новый браузер без конфликта профиля или сессии.
