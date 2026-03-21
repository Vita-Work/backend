# StepStone Parser Report

## Short Conclusion
The live site `https://www.stepstone.de/en/` is **not parseable from the current browser/network context**. Every StepStone page I tried returned **403 Access Denied** from the edge layer, so there is no usable public DOM to extract selectors from in this environment. The good news is that StepStone publishes **official integration documentation** on `api.stepstone.com` that describes their `JobFeed` schema and `ATSi Apply` integrations in detail. For parser work, that means the practical path is **not** DOM scraping of `stepstone.de/en` from this environment, but either a different allowed egress/profile or StepStone's feed/integration layer.

## Live Browser Scan
I opened these StepStone URLs in Playwright:
- `https://www.stepstone.de/en/`
- `https://www.stepstone.de/en/jobs`
- `https://www.stepstone.de/en/job`

All three returned the same denial page. The browser snapshot showed only:
- `h1` text `Access Denied`
- an explanation that access is not permitted for the requested StepStone URL
- a reference code and an `errors.edgesuite.net` link

The network requests were also blocked:
- main document request returned `403`
- StepStone shared font assets returned `403`
- favicon returned `403`

This means there is **no stable DOM tree, no listing markup, and no job detail markup** available to extract from the live site in the current context.

## What This Means For Parsing
For this site, the parser should start with a **hard access check**:
- if StepStone returns `403 Access Denied`, stop DOM parsing immediately
- do not try to infer selectors from the denial page
- switch to the official StepStone feed/integration docs instead

That is important because the denial page is not a temporary rendering issue. It is a real access gate at the edge, not a flaky frontend.

## Official StepStone Integration Model
StepStone documents its content ingestion and application flows through **JobFeed** and **ATSi Apply** style integrations on `api.stepstone.com`.

The key official sources I used are:
- `Stepstone_JobFeed_EN.pdf`
- `Stepstone_HTML_Tags_EN.pdf`
- `stepstone-xml-guide`
- partner integration pages for ATS apply flows

The practical takeaway is that StepStone is designed to accept job data through a structured feed, not just through a browsable public listing page.

## Feed Structure That Matters For Extraction
The XML guide describes the canonical feed layout as:
- root node: `jobfeed`
- main listing node: `joblisting`
- unique reference key: `@reference_id`
- optional identifiers: `@sender_id`, `@organisation_id`, `@recruiter_id`
- action on push feeds: `INSERT`, `OFFLINE`, `UPDATE`, `TRANSLATE`
- country channel node: `channel`
- mandatory `jobdetails` node

Inside `jobdetails`, the most important fields are:
- `language`
- `jobtitle`
- `introduction`
- `tasks`
- `profile`
- `offer`
- `contactInfo`
- `joblocations/location`
- `apply`
- `salary`

For location, the guide supports nested fields such as:
- `countrycode`
- `city`
- `postalcode`
- `streetname`
- `buildingnumber`

For apply, StepStone supports at least:
- `email`
- `url`
- `questionnaire`

For salary, StepStone supports:
- `minimum`
- `maximum`
- `currency`
- `period`

That is the schema a parser or feed-normalizer should target if the goal is to ingest StepStone content reliably.

## HTML Formatting Support In Ads
The HTML tags guide says StepStone can process these HTML tags in job ad content:
- `p`
- `ol`
- `ul`
- `li`
- `a`
- `em` and `i`
- `strong` and `b`
- `u`
- `br`

So if you are normalizing content from StepStone feeds, you should preserve these tags or map them to a safe rich-text representation. This is relevant for job descriptions, tasks, profile text, and offer text.

## Field Mapping Table

| Field | Live DOM source | Official fallback source |
|---|---|---|
| Job title | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/jobtitle` |
| Company name | Not available from live site in this context | `/jobfeed/joblisting/companydetails/companyname` |
| Job description / intro | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/introduction` |
| Tasks | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/tasks` |
| Candidate profile | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/profile` |
| Offer / benefits | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/offer` |
| Contact text | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/contactInfo` |
| Location country | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/joblocations/location/countrycode` |
| Location city | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/joblocations/location/city` |
| Postal code | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/joblocations/location/postalcode` |
| Salary min | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/salary/minimum` |
| Salary max | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/salary/maximum` |
| Salary currency | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/salary/currency` |
| Salary period | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/salary/period` |
| Apply email | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/apply/email` |
| Apply URL | Not available from live site in this context | `/jobfeed/joblisting/jobdetails/apply/url` |
| Reference id | Not available from live site in this context | `/jobfeed/joblisting/@reference_id` |

## Primary And Fallback Selectors
Because the live site is blocked, there are **no valid live selectors** to recommend for `stepstone.de/en` from this environment. Any selector list would be guesswork, so I am not inventing one.

Use this instead as the fallback parsing contract:
- `jobfeed/joblisting/@reference_id`
- `jobfeed/joblisting/@action`
- `jobfeed/joblisting/channel`
- `jobfeed/joblisting/jobdetails/jobtitle`
- `jobfeed/joblisting/jobdetails/introduction`
- `jobfeed/joblisting/jobdetails/tasks`
- `jobfeed/joblisting/jobdetails/profile`
- `jobfeed/joblisting/jobdetails/offer`
- `jobfeed/joblisting/jobdetails/contactInfo`
- `jobfeed/joblisting/jobdetails/joblocations/location`
- `jobfeed/joblisting/jobdetails/apply`
- `jobfeed/joblisting/jobdetails/salary`
- `jobfeed/joblisting/companydetails/companyname`

## JSON-LD And Embedded State
I could not verify any live `JSON-LD`, hydration state, or job-card state on the public site because the browser never got past the `403` wall. So the report intentionally does **not** claim any live DOM script structure for StepStone.

## Network And Anti-Bot Signals
The live browser scan clearly shows:
- `403` on the document request
- `403` on shared font assets
- `403` on favicon
- denial page served by the edge layer
- `errors.edgesuite.net` reference in the denial response

This is the main anti-bot or access control signal for the site in this context. There was no visible captcha on the page because the site never reached a meaningful frontend state.

## Company And Apply Flow
The live site does not expose a browsable company or apply flow from this environment. The official docs show the application layer is handled through partner integrations and ATS connectors such as JobFeed and ATSi Apply, with customers using StepStone-managed feed contracts and application handoff to external ATSs.

For parser purposes, that means:
- do not expect a universal public apply button structure on `stepstone.de/en`
- expect application handling to be integration-specific
- treat StepStone as a feed-backed ecosystem rather than a standard public job board

## 2-Pass Parser Strategy
**Pass 1:** probe the live site and check for `403 Access Denied`. If the page is blocked, exit DOM parsing early and classify the source as inaccessible in the current environment.

**Pass 2:** use the official StepStone feed contract as the parser target. Normalize the XML/JSON feed into your internal job schema using the fields listed above.

That is the safest strategy because it avoids building a brittle scraper around a blocked page.

## Practical Recommendation
If the goal is actual production ingestion of StepStone jobs, the right approach is:
1. negotiate or obtain access to StepStone's feed/integration layer
2. parse `JobFeed` XML or JSON according to the official schema
3. treat the public website as an optional presentation layer, not the primary ingestion source

## Verified URLs
- [https://www.stepstone.de/en/](https://www.stepstone.de/en/)
- [https://www.stepstone.de/en/jobs](https://www.stepstone.de/en/jobs)
- [https://www.stepstone.de/en/job](https://www.stepstone.de/en/job)
- [https://api.stepstone.com/stepstone-xml-guide/](https://api.stepstone.com/stepstone-xml-guide/)
- [https://api.stepstone.com/wp-content/uploads/2025/03/Stepstone_JobFeed_EN.pdf](https://api.stepstone.com/wp-content/uploads/2025/03/Stepstone_JobFeed_EN.pdf)
- [https://api.stepstone.com/wp-content/uploads/2025/03/Stepstone_HTML_Tags_EN.pdf](https://api.stepstone.com/wp-content/uploads/2025/03/Stepstone_HTML_Tags_EN.pdf)
- [https://api.stepstone.com/knowledge-base/jobadder/](https://api.stepstone.com/knowledge-base/jobadder/)
- [https://api.stepstone.com/knowledge-base/talentsoft/](https://api.stepstone.com/knowledge-base/talentsoft/)
- [https://api.stepstone.com/knowledge-base/workday/](https://api.stepstone.com/knowledge-base/workday/)
