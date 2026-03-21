# Jobberman DOM / Parser Report

## Scope
Target site: `https://www.jobberman.com/`
Observed pages: home, jobs listing, job detail, apply/login wall, sharing widgets, related jobs, footer/company directory links.

## High-Level Architecture
Jobberman is mostly server-rendered HTML with a few client-side widgets around consent, analytics, recommendations, and login/apply flows. The listing and detail pages expose stable semantic headings and links, and the detail page exposes a strong `JobPosting` JSON-LD block that is the best canonical source for job metadata.

The site is protected by a cookie consent wall on first load, and job application is gated behind login plus reCAPTCHA.

## Home Page Structure
URL: `https://www.jobberman.com/`

### Main blocks
- Top navigation with `Job Seekers`, `Career`, `Employers`, `Help Center`, `Log In`, `Sign Up`, `Post A Job`.
- Hero text and an `Apply Now!` CTA that points to `/jobs`.
- Search module with four dropdowns:
- `Any Job Functions`
- `Any Industries`
- `Any Locations`
- `Any Experience Levels`
- Popular searches section with direct category links.
- Experience-based filtering section with experience level cards and job counts.
- Companies currently hiring carousel.
- Footer with About, Companies, Privacy, Terms, CV Services, social links, app badge, and NDPR link.

### Home page notes for parsing
- The search widgets expose accessible `button` + `combobox` pairs, which are much safer than class-based selectors.
- Popular searches are direct category links and are good seed URLs for crawling.
- The home page contains strong country branding and safety copy that can be ignored by the scraper.

## Listing Page Structure
URL: `https://www.jobberman.com/jobs`

### Key layout
- Breadcrumb: `Homepage > Search results`
- Heading: `Jobs in Nigeria`
- Total result count: `4,103 Jobs Found` on the captured run.
- Search bar reused from home.
- Promotional/advertising cards between search UI and listings.
- Job cards are rendered as stacked blocks inside the results list.
- Pagination appears at the bottom with numbered links and next/previous controls.

### Card anatomy
Each visible card uses this shape:
- Title is a link to `/listings/<slug>`.
- Company name is shown below the title.
- Metadata row includes `location`, `employment type`, and `salary`.
- Category label appears as a separate line.
- New/Popular badges are separate markers.
- Posted time is shown as relative text like `Yesterday` or `2 days ago`.
- A short description excerpt appears below the company block.
- Some cards show `Easy apply`.

### Listing card examples observed
- `Sales Representative`
- `Baker`
- `Fast Food Restaurant Manager`
- `Sales Manager - Smart City, Security, IoT Solutions`
- `Executive Assistant`
- `Shop Assistant`
- `Head of Project Management Office`
- `Chief Technical Officer`
- `Managing Director`
- `Junior TikTok Poster`
- `Extra-Low Voltage (ELV) / Smart Building Engineer`

### Listing page fields
- `title`
- `company`
- `location`
- `employment type`
- `salary`
- `category`
- `relative posted time`
- `short description`
- `badges` like `FEATURED`, `New`, `Popular`
- `easy apply` marker

### Pagination
- URL pattern: `https://www.jobberman.com/jobs?page=2`
- Numbered pages are direct links.
- Previous page is disabled on page 1.
- Pagination can go deep; the snapshot showed pages up to `257`.

## Job Detail Structure
URL observed: `https://www.jobberman.com/listings/extra-low-voltage-elv-smart-building-engineer-m0pxvg`

### Canonical page layout
- Breadcrumb chain:
- `Homepage`
- `Engineering & Technology`
- `IT & Telecoms`
- `Abuja`
- `Full Time`
- job title
- Main article with the listing content
- Side/login module `Log in to apply now`
- `Share link` block
- `Similar jobs` section
- newsletter and footer below

### Detail page blocks
#### Header block
- Company logo image.
- `h1` job title.
- `h2` company name.
- Category link.
- Relative post time like `1 week ago`.
- Badges like `Easy apply`, `New`, `Featured`.
- Linked tags for `Abuja`, `Full Time`, `IT & Telecoms`.
- Salary line.

#### Job summary block
- `Job summary` heading.
- Short paragraph description.
- Summary attributes:
- `Min Qualification`
- `Experience Level`
- `Experience Length`

#### Requirements block
- `Job descriptions & requirements` heading.
- Subsections:
- `Responsibilities`
- `Requirements`
- `What We Offer`
- Additional job metadata lines:
- `Job Type`
- `Location`
- `Remuneration`

#### Safety block
- `Important safety tips` heading.
- Warning copy about not paying without confirmation.
- `Report Job` link.

#### Apply block
- `Log in to apply now` heading.
- OAuth buttons:
- `Continue with Google`
- `Continue with Linkedin`
- Email/password form.
- `Keep me logged in` checkbox.
- `Log in` button.
- `Sign Up to Apply` link.
- reCAPTCHA iframe is present.

#### Share block
- `Share on WhatsApp`
- `Share on LinkedIn`
- `Share on Facebook`
- `Share on Twitter`

#### Similar jobs block
- Job links to related listings.

### Detail page field mapping
- `title` is the `h1`.
- `company` is the `h2`.
- `category` is the category link and breadcrumb chain.
- `location` is the location tag and detail line.
- `employment type` is the type tag and detail line.
- `salary` is shown in the tag row and again in `Remuneration`.
- `summary` is the `Job summary` paragraph.
- `responsibilities` and `requirements` are bullet lists.
- `apply status` is gated by login wall and reCAPTCHA.
- `share URLs` are generated social links with UTM parameters.

## Company / Apply
Jobberman does not expose a separate company page inside the inspected job detail flow, but it does expose enough company context in the detail page and the `companies` directory links in the footer.

### Company data visible on the detail page
- Company name: `Ujax Engineering`
- Company logo image
- Company appears in JSON-LD as `hiringOrganization`

### Apply flow
- Clicking `Apply` is not a public immediate form; the user is redirected into a login panel.
- Apply flow supports Google OAuth and LinkedIn OAuth.
- Email/password login is available.
- reCAPTCHA is embedded in the form.
- `Sign Up to Apply` is a dedicated CTA with an `apply=<listing id>` parameter.

## URL Patterns
### Listing URLs
- Base search: `/jobs`
- Pagination: `/jobs?page=2`
- Category routes exist on home and are used as crawl seeds.

### Job detail URLs
- Pattern: `/listings/<slug>`
- Example: `/listings/extra-low-voltage-elv-smart-building-engineer-m0pxvg`

### Category/filter URLs observed
- `/jobs/engineering-technology`
- `/jobs/engineering-technology?industry=it-telecoms`
- `/jobs/engineering-technology/abuja?industry=it-telecoms`
- `/jobs/engineering-technology/abuja/full-time?industry=it-telecoms`
- `/jobs/full-time`
- `/jobs/remote`
- `/jobs/it-telecoms`

### Share URL patterns
- WhatsApp share uses `wa.me` with the job URL and social UTM params.
- LinkedIn/Facebook/Twitter share endpoints are standard social share URLs with the listing URL embedded.

## JSON-LD / Embedded State
### JSON-LD presence
- `script[type="application/ld+json"]` is present on the detail page.
- `__NEXT_DATA__` is not present.
- `__NUXT__` is not present.

### JSON-LD graph contents
The structured data contains an `@graph` with:
- `WebPage`
- `Organization`
- `Person`
- `WebSite`
- `BreadcrumbList`
- `JobPosting`
- `ImageObject`
- `Place`
- `PostalAddress`

### JobPosting fields observed
- `title`: `Extra-Low Voltage (ELV) / Smart Building Engineer`
- `datePosted`: `2026-03-12T00:00:00.000000Z`
- `validThrough`: `2026-06-10T00:00:00.000000Z`
- `employmentType`: `FULL_TIME`
- `directApply`: `true`
- `baseSalary.currency`: `NGN`
- `baseSalary.value.minValue`: `70000`
- `baseSalary.value.maxValue`: `150000`
- `baseSalary.value.unitText`: `MONTH`
- `description`: HTML job description with responsibilities
- `jobLocation.addressCountry`: `NG`
- `jobLocation.addressRegion`: `Nigeria`

### Organization fields observed
- `name`: `Jobberman Nigeria`
- `url`: `https://www.jobberman.com`
- `logo`: `https://www.jobberman.com/static-assets/img/jobberman-theme/opengraph-logo.png`

### Local storage signals
Observed keys on the detail page:
- `tag_engineering-technology=1`
- `tag_abuja=1`
- `tag_entry-level=1`
- `isPushNotificationsEnabled=false`
- `isOptedOut=false`
- `os_pageViews=1`

These look like user interaction and category tags, not primary scrape data.

## Network / XHR
### Important non-tracking endpoint
- `GET /ajax/listing-recommendations/similar/1212578` returns similar listing data.

### Third-party and analytics traffic observed
- OneTrust consent assets and geo lookup.
- Google Analytics requests.
- Google ads/measurement requests.
- Microsoft Clarity collect requests.
- OneSignal icon request.
- Cloudflare RUM endpoint.

### Parsing impact
- For scraping jobs, the most useful non-tracking network signal is the similar-listings endpoint.
- The rest is mainly analytics and consent plumbing.

## Auth / Anti-Bot
### Observed constraints
- Cookie consent banner appears on first load.
- Apply flow is login-gated.
- reCAPTCHA is embedded in the login/apply form.
- No hard Cloudflare challenge was seen on the inspected pages.

### Practical implication
- Public listing and detail pages are accessible.
- Application actions are not public and need auth.
- Cookie consent should be dismissed early in automation to avoid click interception.

## Primary Selectors
### Home
- `a[href="https://www.jobberman.com/jobs"]`
- `button[aria-label="Search"]` or the visible `Search` button
- `button`/`combobox` pairs for job function, industry, location, and experience level
- `a[href="/jobs/it-telecoms"]`

### Listing
- `a[href^="https://www.jobberman.com/listings/"]`
- card title paragraphs under those links
- metadata rows directly following the title link
- pagination links under `navigation[aria-label*="Pagination"]`

### Detail
- `article`
- `h1`
- `h2`
- `heading "Job summary"`
- `heading "Job descriptions & requirements"`
- `heading "Log in to apply now"`
- `script[type="application/ld+json"]`

### Apply/login wall
- `button` with name `Log in`
- `link` with name `Continue with Google`
- `link` with name `Continue with Linkedin`
- `textbox` labeled `Email Address`
- `textbox` labeled `Password`
- `checkbox` labeled `Keep me logged in`
- `link` named `Sign Up to Apply`

## Fallback Selectors
- If title link text changes, fall back to `a[href*="/listings/"]`.
- If metadata text moves, parse the nearest sibling block under the job card.
- If headings shift, use the `Job summary` and `Job descriptions & requirements` section titles as anchors.
- If login form labels change, use the reCAPTCHA iframe plus the OAuth button texts as stable markers.

## Field Mapping Table
| Field | Primary Source | Fallback Source |
|---|---|---|
| title | `h1` on detail page | listing card title link |
| company | `h2` on detail page | JSON-LD `hiringOrganization` |
| category | breadcrumb and category link | listing card category text |
| location | tag row and detail line | breadcrumb chain |
| employment type | tag row and `Job Type` line | JSON-LD `employmentType` |
| salary | tag row and `Remuneration` line | JSON-LD `baseSalary` |
| posted time | header relative time text | none observed |
| summary | `Job summary` paragraph | JSON-LD description excerpt |
| responsibilities | bullet list under requirements section | JSON-LD description HTML |
| requirements | bullet list under requirements section | JSON-LD description HTML |
| apply state | login wall and reCAPTCHA | `Sign Up to Apply` CTA |
| similar jobs | related job links section | `/ajax/listing-recommendations/similar/<id>` |

## 2-Pass Parser Strategy
### Pass 1: Listing crawl
- Start at `/jobs` and category seed URLs from home.
- Collect listing URLs from `a[href^="https://www.jobberman.com/listings/"]`.
- Extract title, company, location, salary, category, posted time, badges, and excerpt.
- Skip promotional cards and newsletter blocks.

### Pass 2: Detail enrichment
- Fetch each listing URL.
- Prefer JSON-LD `JobPosting` for canonical fields.
- Use DOM only for presentation-only fields and login/apply state.
- Capture similar jobs if needed for expansion.

## Parser Notes
- Jobberman is a good candidate for structured scraping because the detail page has a strong JSON-LD block.
- The site is not fully open for apply automation because the login wall and reCAPTCHA sit directly on the application path.
- Cookie consent should be dismissed before any click-based navigation.
- The report is intentionally focused on live DOM and network behavior, not assumptions.

## Checked URLs
- `https://www.jobberman.com/`
- `https://www.jobberman.com/jobs`
- `https://www.jobberman.com/listings/extra-low-voltage-elv-smart-building-engineer-m0pxvg`
- `https://www.jobberman.com/jobs?page=2`
- `https://www.jobberman.com/jobs/engineering-technology`
- `https://www.jobberman.com/jobs/engineering-technology?industry=it-telecoms`
- `https://www.jobberman.com/jobs/engineering-technology/abuja?industry=it-telecoms`
- `https://www.jobberman.com/jobs/engineering-technology/abuja/full-time?industry=it-telecoms`
- `https://www.jobberman.com/jobs/it-telecoms`
- `https://www.jobberman.com/jobs/full-time`
- `https://www.jobberman.com/jobs/remote`
