# Habr Career — DOM/HTML report for scraping

Дата проверки: 2026-03-21
Источник данных: live Playwright MCP browser session на `career.habr.com`.

Цель отчета: зафиксировать **реальную DOM-структуру**, полезные **селекторы**, **URL-паттерны**, **embedded state / JSON-LD**, **network/XHR** и **ограничения доступа** так, чтобы можно было строить надежный parser без догадок.

## 1) Что доступно гостю

Без логина гостю доступны:

1. Home page.
2. Vacancies listing.
3. Vacancy detail page.
4. Company profile page.
5. Public journal / salaries / course catalog blocks.

Что ограничено или гейтится:

1. Apply flow уводит в login wall и требует профиль.
2. Отклик через форму на vacancy detail защищен `reCAPTCHA`.
3. Действия вроде favorite / response / profile features завязаны на auth.
4. Большая часть динамики не через публичный JSON-LD, а через server-rendered HTML + JS bundles.

## 2) Общая карта URL

### Home

- `https://career.habr.com/`

### Vacancies listing

- `https://career.habr.com/vacancies?type=all`
- pagination pattern: `?page=2&type=all`
- sort patterns are driven by the `combobox` on page and query params behind it
- RSS feed: `/vacancies/rss?currency=RUR&sort=relevance&type=all`

### Vacancy detail

- `https://career.habr.com/vacancies/1000164844`
- guest response anchor: `#guest-response`

### Company profile

- `https://career.habr.com/companies/navio`
- company vacancies: `/companies/navio/vacancies`
- company follow: `/companies/navio/follow`
- company employees: `/resumes?company_ids%5B%5D=1000078791`
- company followers: `/companies/navio/followers`

### Auth / signup

- `/users/auth/tmid`
- `/users/auth/tmid/register?ae=vr`

### Internal API observed

- `/api/frontend_v1/users/me`

## 3) Home page structure

### Main layout

Home is heavily server-rendered and split into several marketing/content sections:

- `banner`
- `main`
- `contentinfo`

### Header and nav

Observed stable navigational links:

- `Вакансии` -> `/vacancies`
- `Специалисты` -> `/resumes`
- `Курсы и обучение` -> `/education`
- `Эксперты` -> `/experts`
- `Компании` -> `/companies`
- `Рейтинг` -> `/companies/ratings`
- `Зарплаты` -> `/salaries`
- `Журнал` -> `/journal`

### Hero / search

Main hero block includes:

- `heading` `Помогаем найти работу в IT`
- form `Начать поиск`
- textbox placeholder `Работа мечты`
- button `Найти`

### Home metrics

The home page exposes useful aggregate counters directly in text:

- `1 137` вакансий уже тут
- `6 890` курсов для получения и развития навыков
- `206 820 ₽` средняя зарплата в IT сегменте
- `227` компаний ищут сотрудников прямо сейчас

### Home content blocks

Home has several structured content areas that can be parsed separately:

- `Найдите работу по душе` with vacancy cards by specialization
- `Подготовьтесь к собеседованиям` with course cards
- `Узнайте все о работодателе` with company cards and ratings
- `Читайте интересные статьи` with journal cards
- newsletter subscribe block
- join/login CTA block
- footer with sitemap/help/legal/social links

### Home vacancy cards

Vacancy cards on home contain:

- company name
- remote / city location
- title
- salary or salary hint
- seniority tag
- skill chips

Good examples from the live DOM:

- `Cobalt Lab` / `Удаленная работа` / `Frontend-разработчик (iGaming)` / `от 2 000 $`
- `Vide Infra` / `Удаленная работа` / `PHP разработчик (Symfony)` / `от 150 000 до 250 000 ₽`
- `Atlantis` / `Удаленная работа` / `Backend Engineer`

## 4) Vacancies listing structure

### Top-level listing layout

The listing page is also SSR-heavy and has:

- `heading "Работа и вакансии"`
- subscribe button `Подписаться на вакансии`
- RSS link
- search input `Поиск`
- sort `combobox`
- sidebar filters on the right
- infinite-ish long list with page links

### Search and sort controls

The search area contains:

- `searchbox` with placeholder `Поиск`
- sort `combobox` with options:
  - `По соответствию`
  - `По дате размещения`
  - `По убыванию зарплаты`
  - `По возрастанию зарплаты`

### Vacancy card structure

Each vacancy card is laid out as a nested block with clear fields:

- top date via `time`
- company logo link
- company name link
- vacancy title link
- salary or salary hint
- seniority badge
- location badge or remote badge
- skill chips
- reaction counters / icons
- `Откликнуться` link
- `Добавить в избранное` button

Practical selectors from the live DOM:

- `article` inside listing rows
- `time`
- `a[href^="/vacancies/"]` for vacancy detail
- `a[href^="/companies/"]` for company links
- `button[aria-label*="избранное"]` or visible `Добавить в избранное`
- `a[href$="#guest-response"]` for guest apply anchor

### Example listing fields

One real card observed:

- title: `Инженер по глубокому обучению в команду нейросетевого планировщика траектории`
- company: `Navio`
- date: `21 марта`
- location: `Москва`
- seniority: `Senior`
- skills: `Python`, `C++`, `Алгоритмы и структуры данных`, `Оптимизация кода`, `Машинное обучение`, `Нейронные сети`, `PyTorch`, `TensorFlow`, `Reinforcement learning`, `Deep Learning`

### Pagination

Pagination is standard link-based:

- `?page=1&type=all`
- `?page=2&type=all`
- `?page=3&type=all`

The page also exposes next-page arrow links.

### Sidebar filters

The right sidebar contains strong parser-friendly filters:

- qualification combobox: `Любая`, `Junior`, `Middle`, `Senior`, `Lead`
- skill textbox: `Выберите навык`
- salary textbox: `От`
- currency combobox: `₽`, `€`, `$`, `₴`, `₸`
- checkbox: `Указана`
- location textbox: `Введите город, область или страну`
- employment type combobox: `Любой`, `Полный рабочий день`, `Неполный рабочий день`
- checkbox: `Можно удалённо`
- company textbox: `Выберите компанию`
- checkbox: `Аккредитованные ИТ-компании`
- checkbox: `Исключить из поиска`

## 5) Vacancy detail structure

### Main article

The vacancy detail page is a highly structured server-rendered page. Main blocks:

- `h1` title
- publication date `time`
- section `Требования`
- section `Условия`
- `Откликнуться`
- favorite button
- `Описание вакансии`
- company sidebar
- similar vacancies

### Detail title block

Observed title on live page:

- `Инженер по глубокому обучению в команду нейросетевого планировщика траектории`
- date: `21 марта`

### Requirements block

This block is very parser-friendly. It contains:

- role type: `Бэкенд разработчик`
- seniority: `Senior`
- skill tags: `Python`, `C++`, `Алгоритмы и структуры данных`, `Оптимизация кода`, `Машинное обучение`, `Нейронные сети`, `PyTorch`, `TensorFlow`, `Reinforcement learning`, `Deep Learning`

### Conditions block

Observed fields:

- location: `Москва`

### Apply block

Guest-facing apply flow is explicit in the DOM:

- link `Откликнуться` -> `#guest-response`
- button `Добавить в избранное`
- response form asks for resume PDF or resume link
- contact fields are available
- `reCAPTCHA` iframe is present
- submit button `Откликнуться без регистрации` is disabled until requirements are met

### Description block

The description is wrapped as semantically rich paragraphs and lists.

Important subheads found in the live DOM:

- `О компании и команде`
- `О команде:`
- `Кого мы ищем:`
- `Чем предстоит заниматься:`
- `Что мы ждем от кандидата:`
- `Будет плюсом:`
- `Мы предлагаем:`

Useful extraction pattern here is simple text block collection from `p`, `ul`, `li`, `strong`, and `h3` inside the description container.

### Similar vacancies block

The detail page also exposes a `Похожие вакансии` block with cards containing:

- title
- company
- city
- salary if available

### Company summary in detail sidebar

The right sidebar includes:

- company logo link
- company name link
- short company description
- website link
- company vacancy list

### Similarity and navigation blocks

The page also exposes:

- `Смотреть ещё вакансии`
- specialization links
- city links
- seniority links
- skill links

These are useful for building crawl expansion.

## 6) Company profile structure

### Top sidebar

The company page is split into a left sidebar and a large content column.

Sidebar elements:

- company logo
- company name
- company description
- website link
- follow button `Хочу тут работать`
- vacancy count
- employee count
- follower count
- location
- company size
- contacts
- links
- contact persons list

### Top counts

Observed counts on the live page:

- vacancies: `3`
- employees: `46 / 66`
- subscribers: `112 / 141`

### Contact persons

This is an unusually rich part of the profile page and very useful for scraping. The live DOM exposes individual contact cards with:

- person name
- handle
- age when available
- city when available
- role, e.g. `IT HR`, `IT HR Manager`, `Лид команды рекрутмента`

### Main company description

The company content block includes:

- `О компании «Navio»`
- paragraphs describing the company, domain, products and hiring goals
- bullet list of working benefits
- closing call to action

### Skills block

The company profile also exposes a strong skills cloud:

- `C++`, `Python`, `Linux`, `Машинное обучение`, `Алгоритмы и структуры данных`, `Deep Learning`, `Нейронные сети`, `PyTorch`, `TensorFlow`, `Docker`, `ООП`, `CI/CD`, `Grafana`, `Компьютерное зрение`, `Базы данных`, `Git`

### Company vacancies

Company vacancy cards include:

- date
- title
- city
- employment type
- specialization link
- seniority link
- skill links

### Ratings / reviews / medals / employee flows

The page also has additional structured sections:

- employee ratings and reviews
- awards / medals
- employees currently working there
- where people come from
- where people go after

These sections are highly valuable if you want company intelligence.

## 7) Structured data / embedded state

### JSON-LD

On the checked pages, I did **not** find `script[type="application/ld+json"]`.

Observed result on the live page:

- `ldCount = 0`

### Embedded state

The site is clearly server-rendered with a large amount of JS enhancement.

Useful observed runtime signals:

- no visible JSON-LD
- no obvious `window.__NEXT_DATA__` or similar hydration blob in the sampled DOM
- many webpack packs are loaded from `/assets/packs/js/...`

### Important internal API

A useful internal endpoint exists and is callable without login:

- `GET /api/frontend_v1/users/me` -> `200 {}` for guest

This is a useful presence check for auth state.

## 8) Network / XHR / third-party scripts

### Internal / app requests observed

- `GET https://career.habr.com/api/frontend_v1/users/me` -> `200`, returns `{}` for guest

### Analytics / tracking / widgets observed

The page loads a lot of third-party and app JS, including:

- `connect.facebook.net/signals/config/...`
- `cdn.mxpnl.com/libs/mixpanel-2-latest.min.js`
- `yandex.ru/ads/system/context.js`
- `yastatic.net/safeframe-bundles/...`
- `www.googletagmanager.com/gtag/js?id=G-8ZVM81B7DF`
- `browser.sentry-cdn.com/.../bundle.min.js`
- `vk.com/js/api/openapi.js`
- `code.jivosite.com/script/widget/...`

### Network notes

- Google Analytics `g/collect` is active.
- JivoSite widget is present.
- Facebook, Mixpanel, Yandex Ads, Sentry, and GTM are loaded.

For scraping, this means the site is not a hard anti-bot wall, but it is heavily instrumented and the DOM is still the reliable source.

## 9) Auth / anti-bot / access limits

### Guest access

Guest access is good for reading vacancy pages and company pages.

### Login wall

The following actions require login or are gated:

- applying without reCAPTCHA and account creation
- saving to favorites / stronger interaction flows
- personalized user behaviors

### reCAPTCHA

The `Ваш отклик` form contains a `reCAPTCHA` iframe. That is the most obvious anti-bot / anti-abuse protection in the live DOM.

### Guest response flow

The page exposes a guest response form and disabled submit until required fields are filled, but successful submission is not available without proper completion and likely account context.

## 10) Recommended selectors

### Home

- `form[aria-label*="Начать поиск"]`
- `input[placeholder="Работа мечты"]`
- `button:has-text("Найти")`
- `a[href="/vacancies"]`
- `a[href="/companies"]`

### Vacancies listing

- `h1:has-text("Работа и вакансии")`
- `searchbox[placeholder="Поиск"]`
- `combobox`
- `a[href^="/vacancies/"]`
- `a[href^="/companies/"]`
- `time`
- `button:has-text("Добавить в избранное")`
- `a[href$="#guest-response"]`
- `a[href="/vacancies/rss?currency=RUR&sort=relevance&type=all"]`

### Vacancy detail

- `h1`
- `h2:has-text("Требования")`
- `h2:has-text("Условия")`
- `h2:has-text("Описание вакансии")`
- `a[href="#guest-response"]`
- `iframe` containing `reCAPTCHA`
- `a[href^="/companies/"]` in sidebar
- `a[href^="/vacancies/"][f="similar_vacancies"]`

### Company profile

- `h1:has-text("О компании")`
- `a[href^="/companies/navio"]`
- `a[href="/companies/navio/vacancies"]`
- `a[href="/resumes?company_ids%5B%5D=1000078791"]`
- `a[href="/companies/navio/followers"]`
- company skills links under `Востребованные в компании навыки`
- vacancy cards under `Вакансии компании`

## 11) Extraction mapping table

| Field | Primary source | Fallback source |
|---|---|---|
| vacancy_title | `h1` on detail page, listing card title link | title text inside card anchor |
| company_name | company link in listing/detail/sidebar | sidebar company block |
| published_at | `time` element | title / card context if needed |
| location | location chip / text in listing, conditions block on detail | company sidebar or page context |
| salary | listing salary text, salary hint, or absent | company / similar specialists salary hint |
| seniority | badge like `Junior/Middle/Senior/Lead` | skill / specialization chips |
| specialization | role / specialization link on listing/detail | company vacancy tags |
| skills | chip list in listing/detail/company page | description text parsing |
| apply_url | `a[href="#guest-response"]` on detail, `Откликнуться` link on listing | auth/signup redirect if needed |
| company_url | `a[href^="/companies/"]` | sidebar company block |
| description | detail page `Описание вакансии` paragraphs/lists | article text blocks |
| benefits | `Мы предлагаем` list | description text |
| company_about | company page `О компании` text | sidebar short description |
| company_vacancies | company page vacancy cards | `/companies/<slug>/vacancies` |
| company_contacts | company page contact person cards | sidebar contacts section |
| company_skills | skills cloud on company page | vacancy skill tags |
| ratings | review/ratings blocks on company page | ratings pages |

## 12) 2-pass parser strategy

### Pass 1: discovery

Collect from listing and company pages:

- vacancy URLs
- company URLs
- pagination URLs
- specialization / skill / city URLs
- sort and filter state

### Pass 2: enrichment

For each vacancy and company page:

- vacancy title
- company name
- description blocks
- skills
- location
- salary or salary hint
- apply URLs
- contact / employer intelligence
- ratings / employee flow data

### Why this order works

The listing pages already expose strong structured fields, and the company page adds employer intelligence without needing login. The detail page is best for description and apply gating.

## 13) Parser risks and notes

1. There is no JSON-LD on the pages I checked, so DOM parsing is primary.
2. The site is heavily instrumented, but the app content itself is server-rendered and stable.
3. `reCAPTCHA` makes apply automation fragile.
4. Guest interactions that appear clickable may still require account or captcha completion.
5. The internal API `/api/frontend_v1/users/me` is useful only as auth-state signal, not as the main content source.

## 14) Checked URLs

- `https://career.habr.com/`
- `https://career.habr.com/vacancies?type=all`
- `https://career.habr.com/vacancies/1000164844`
- `https://career.habr.com/companies/navio`
- `https://career.habr.com/api/frontend_v1/users/me`
