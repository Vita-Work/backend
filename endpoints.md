# Backend Endpoints for Frontend

**Base URL:** `{base_url}`
Локально обычно: `http://127.0.0.1:8000`

**Важно для фронта:** после логина все запросы к ` /me/* ` и ` /me/job-tracker/* ` нужно слать с **cookie auth** (`credentials: "include"`).

**Общие состояния, которые нужно уметь мокать почти везде:**
- `200 OK` - успешное чтение или обновление
- `201 Created` - создан новый ресурс
- `202 Accepted` - long-running workflow принят в очередь
- `400 Bad Request` - неверный OTP / невалидное действие по бизнес-правилам
- `401 Unauthorized` - нет auth cookie
- `404 Not Found` - сущность не найдена
- `409 Conflict` - текущий шаг пока недоступен по состоянию flow
- `413 Payload Too Large` - CV слишком большой
- `415 Unsupported Media Type` - неподдерживаемый формат CV
- `422 Unprocessable Entity` - невалидный body/query/path по схеме FastAPI
- `503 Service Unavailable` - временная проблема внешней интеграции, БД, очереди, S3, Gemini, email

---

## 1. Auth

### `POST {base_url}/auth/email/request-code`
**Зачем нужен:** первый шаг signup/login по email OTP.

**Принимает JSON:**
```json
{
  "email": "user@example.com"
}
```

**Возвращает:** `202 Accepted`
```json
{
  "detail": "If the email is allowed, a verification code has been sent."
}
```

**Состояния:**
- `202` - код запрошен или запрос специально замаскирован generic-ответом
- `503` - email provider не смог отправить письмо
- `422` - невалидный body

---

### `POST {base_url}/auth/email/verify-code`
**Зачем нужен:** подтверждение OTP. Это и регистрация нового user, и вход существующего user.

**Принимает JSON:**
```json
{
  "email": "user@example.com",
  "code": "123456",
  "timezone": "Asia/Bishkek",
  "locale": "ru",
  "full_name": "Nikita Nosov"
}
```

**Возвращает:** `200 OK` + ставит user auth cookie
```json
{
  "authenticated": true,
  "role": "user",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "Nikita Nosov",
    "timezone": "Asia/Bishkek",
    "locale": "ru",
    "role": "user",
    "status": "active",
    "email_verified_at": "2026-03-27T12:00:00Z"
  },
  "is_new_user": true,
  "next_route": "/onboarding",
  "needs_onboarding": true,
  "has_active_onboarding_session": false,
  "has_completed_onboarding": false,
  "has_search_results": false,
  "has_tracker_jobs": false
}
```

**Состояния:**
- `200` - OTP подтверждён, юзер залогинен
- `400` - `Invalid or expired code.` или `Code is no longer valid.`
- `403` - `User is disabled.` или `Use admin login for this account.`
- `422` - невалидный body

---

### `GET {base_url}/auth/session`
**Зачем нужен:** восстановление сессии после reload/app start. Это главный способ понять, залогинен ли пользователь.

**Принимает:** ничего

**Возвращает без сессии:**
```json
{
  "authenticated": false,
  "role": null,
  "user": null
}
```

**Возвращает с сессией:** тот же `AuthSessionResponse`, что и `verify-code`.

**Состояния:**
- `200` - всегда, просто либо сессия есть, либо нет

---

### `POST {base_url}/auth/logout`
**Зачем нужен:** logout user.

**Принимает:** ничего

**Возвращает:** `200 OK`
```json
{
  "detail": "Logged out."
}
```

**Состояния:**
- `200` - logout выполнен, даже если сессии уже не было

---

## 2. App bootstrap

### `GET {base_url}/me`
**Зачем нужен:** получить профиль текущего юзера.

**Принимает:** ничего

**Возвращает:** `UserResponse`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Nikita Nosov",
  "timezone": "Asia/Bishkek",
  "locale": "ru",
  "role": "user",
  "email_verified_at": "2026-03-27T12:00:00Z",
  "status": "active",
  "created_at": "2026-03-27T12:00:00Z",
  "updated_at": "2026-03-27T12:00:00Z"
}
```

**Состояния:**
- `200`
- `401` - `Authentication required.`

---

### `GET {base_url}/me/app-state`
**Зачем нужен:** главный frontend bootstrap endpoint после login и после refresh. По нему фронт решает, куда вести пользователя.

**Принимает:** ничего

**Возвращает:** `MeAppStateResponse`
```json
{
  "phase": "new_user",
  "next_route": "/onboarding",
  "needs_onboarding": true,
  "has_active_onboarding_session": false,
  "has_completed_onboarding": false,
  "has_search_results": false,
  "has_tracker_jobs": false,
  "onboarding_session_id": null,
  "extraction_workflow_run_id": null,
  "search_job_workflow_run_id": null,
  "is_new_user": true
}
```

**Возможные `phase`:**
- `new_user`
- `upload_cv`
- `processing_cv`
- `onboarding_chat`
- `awaiting_confirmation`
- `searching_jobs`
- `results_ready`

**Состояния:**
- `200`
- `401`

---

## 3. Onboarding

### `GET {base_url}/me/onboarding/active`
**Зачем нужен:** получить активную onboarding session и её текущее состояние.

**Принимает:** ничего

**Возвращает:** `OnboardingSessionResponse`
```json
{
  "id": "uuid",
  "user_id": "user-uuid",
  "status": "awaiting_clarification",
  "current_step": "clarifying",
  "latest_workflow_run_id": "uuid",
  "extracted_profile": "...",
  "missing_info": [],
  "preference_hints": [],
  "clarification_turns": [],
  "pending_user_prompt": "What kind of role are you targeting?",
  "pending_user_prompt_type": "clarification",
  "verification_score": null,
  "verification_summary": null,
  "search_strategy_summary": null,
  "hard_preferences": [],
  "soft_preferences": [],
  "extraction_model": "gemini-...",
  "last_error_message": null,
  "superseded_by_session_id": null,
  "created_at": "2026-03-27T12:00:00Z",
  "updated_at": "2026-03-27T12:00:00Z"
}
```

**Типичные `status`:**
- `draft`
- `extracting`
- `awaiting_clarification`
- `clarifying`
- `verifying`
- `planning`
- `awaiting_confirmation`
- `completed`
- `failed`
- `superseded`

**Состояния:**
- `200`
- `401`
- `404` - `Active onboarding session not found.`

---

### `POST {base_url}/me/onboarding/restart`
**Зачем нужен:** начать onboarding заново.

**Принимает:** ничего

**Возвращает:** `201 Created` + новый `OnboardingSessionResponse`

**Состояния:**
- `201`
- `401`

---

### `POST {base_url}/me/onboarding/run`
**Зачем нужен:** двинуть onboarding pipeline дальше без ответа пользователя.

**Принимает:** ничего

**Возвращает:** `OnboardingSessionResponse`

**Состояния:**
- `200`
- `401`
- `404` - нет активной onboarding session
- `409` - flow пока не готов, например ещё нет `extracted_profile`

---

### `GET {base_url}/me/onboarding/thread`
**Зачем нужен:** основной endpoint для чатового UI onboarding.

**Принимает:** ничего

**Возвращает:** `OnboardingThreadResponse`
```json
{
  "onboarding_session_id": "uuid",
  "conversation_status": "awaiting_clarification",
  "input_mode": "free_text",
  "confirmation_mode": null,
  "messages": [
    {
      "id": "session:intro",
      "role": "agent",
      "message_type": "status_note",
      "text": "I reviewed your CV and I'm putting together your job search profile.",
      "state": "sent",
      "created_at": "2026-03-27T12:00:00Z"
    }
  ],
  "search_job_workflow_run_id": null
}
```

**Типичные `role`:**
- `agent`
- `user`

**Типичные `message_type`:**
- `status_note`
- `clarification_question`
- `user_answer`
- `confirmation_request`
- `confirmation_answer`

**Типичные `input_mode`:**
- `free_text`
- `confirmation`

**Типичные `confirmation_mode`:**
- `yes_no_with_optional_reason`

**Состояния:**
- `200`
- `401`
- `404` - нет активной onboarding session

---

### `POST {base_url}/me/onboarding/respond`
**Зачем нужен:** отправить ответ пользователя в onboarding chat, включая финальный confirmation.

**Принимает JSON:**
```json
{
  "answer": "Yes"
}
```

**Возвращает:** `OnboardingRespondResponse`
```json
{
  "session": { "...OnboardingSessionResponse..." },
  "thread": { "...OnboardingThreadResponse..." },
  "onboarding_completed": true,
  "search_job_enqueued": true,
  "search_job_workflow_run_id": "uuid"
}
```

**Состояния:**
- `200`
- `401`
- `404` - нет активной onboarding session
- `409` - текущий шаг flow не готов к ответу
- `503` - не удалось поставить поиск вакансий в очередь после завершения onboarding

---

## 4. CV upload and extraction

### `POST {base_url}/me/extraction/cv/run`
**Зачем нужен:** загрузить CV и запустить extraction workflow.

**Принимает:** `multipart/form-data`
- `file` - PDF/DOCX/TXT/MD файл

**Возвращает:** `202 Accepted` + `CvExtractionWorkflowRunResponse`
```json
{
  "workflow_run_id": "uuid",
  "file": {
    "bucket": "bucket",
    "key": "key",
    "uri": "s3://...",
    "filename": "resume.pdf",
    "content_type": "application/pdf",
    "extension": ".pdf",
    "size_bytes": 12345,
    "sha256": "..."
  },
  "extraction": {
    "strategy": "model_file",
    "inline_text_characters": null
  },
  "status": "queued",
  "extracted_profile": null,
  "missing_info": [],
  "preference_hints": [],
  "extraction_model": null,
  "error_message": null,
  "ui_phase": "upload_received",
  "ui_label": "CV uploaded",
  "ui_description": "Your file is safely uploaded and queued.",
  "progress_percent": 5,
  "progress_stage_index": 1,
  "progress_stage_total": 6,
  "started_at": null,
  "finished_at": null,
  "last_progress_at": "2026-03-27T12:00:00Z",
  "created_at": "2026-03-27T12:00:00Z",
  "updated_at": "2026-03-27T12:00:00Z"
}
```

**Типичные `status`:**
- `queued`
- `extracting`
- `awaiting_clarification`
- `awaiting_confirmation`
- `completed`
- `failed`

**Типичные `ui_phase`:**
- `upload_received`
- `file_stored`
- `text_extraction`
- `cv_analysis`
- `building_profile`
- `ready_for_questions`

**Состояния:**
- `202`
- `400` - файл битый или невалидный
- `401`
- `413` - файл слишком большой
- `415` - неподдерживаемый формат
- `422`
- `503` - S3 / Gemini / ARQ / БД временно недоступны

---

### `GET {base_url}/me/extraction/runs/{workflow_run_id}`
**Зачем нужен:** polling fallback для extraction.

**Принимает:** path param `workflow_run_id`

**Возвращает:** тот же `CvExtractionWorkflowRunResponse`

**Состояния:**
- `200`
- `401`
- `404` - `Workflow run not found.`

---

### `GET {base_url}/me/extraction/runs/{workflow_run_id}/events`
**Зачем нужен:** live progress stream для красивой анимации обработки CV.

**Принимает:** path param `workflow_run_id`

**Возвращает:** `text/event-stream`
Каждое событие содержит `ExtractionProgressEventResponse`:
```json
{
  "workflow_run_id": "uuid",
  "event_type": "phase_changed",
  "ui_phase": "text_extraction",
  "ui_label": "Reading your CV",
  "ui_description": "We are extracting the important details from your resume.",
  "progress_percent": 35,
  "progress_stage_index": 3,
  "progress_stage_total": 6,
  "payload": {},
  "created_at": "2026-03-27T12:00:00Z"
}
```

**Типичные SSE event names:**
- `phase_changed`
- `step_started`
- `step_completed`
- `error`
- `terminal`

**Состояния:**
- `200`
- `401`
- `404`

---

## 5. Search jobs

### `POST {base_url}/me/search-jobs/run`
**Зачем нужен:** вручную запустить поиск вакансий после завершённого onboarding.

**Query params:**
- `monitoring_mode=true|false` - optional, по умолчанию `false`

**Возвращает:** `202 Accepted` + `SearchJobWorkflowRunResponse`

**Состояния:**
- `202`
- `401`
- `409` - onboarding ещё не готов для поиска
- `503` - очередь или модель временно недоступны

---

### `GET {base_url}/me/search-jobs/runs/{workflow_run_id}`
**Зачем нужен:** polling fallback для поиска вакансий и результатов.

**Принимает:** path param `workflow_run_id`

**Возвращает:** `SearchJobWorkflowRunResponse`
```json
{
  "workflow_run_id": "uuid",
  "onboarding_session_id": "uuid",
  "user_id": "user-uuid",
  "status": "searching",
  "search_strategy_summary": "...",
  "hard_preferences": [],
  "soft_preferences": [],
  "source_sites": ["hh", "indeed"],
  "monitoring_mode": false,
  "total_site_results": 20,
  "total_jobs_found": 10,
  "total_jobs_returned": 10,
  "summary_markdown": null,
  "jobs": [
    {
      "site": "hh",
      "job_url": "https://...",
      "title": "ML Engineer",
      "company_name": "Acme",
      "location": "Remote",
      "salary_text": null,
      "salary_min": null,
      "salary_max": null,
      "currency": null,
      "employment_type": null,
      "published_at": null,
      "description": null,
      "skills": [],
      "apply_url": null,
      "company_url": null,
      "company_about": null,
      "company_contacts": [],
      "why_apply": "Good fit",
      "risks": [],
      "fit_level": "high",
      "source_queries": [],
      "is_saved_to_tracker": false,
      "tracked_job_id": null,
      "company_logo_url": null,
      "site_display_name": "HH",
      "site_logo_key": "hh",
      "display_badge_label": "High"
    }
  ],
  "site_results": [],
  "notes": [],
  "search_model": null,
  "unification_model": null,
  "error_message": null,
  "current_internal_stage": "searching",
  "current_display_stage": "searching",
  "current_display_label": "Scanning job boards",
  "current_display_description": "We are checking the best sources for matching roles.",
  "progress_percent": 33,
  "progress_stage_index": 2,
  "progress_stage_total": 6,
  "started_at": "2026-03-27T12:00:00Z",
  "finished_at": null,
  "last_progress_at": "2026-03-27T12:00:00Z",
  "created_at": "2026-03-27T12:00:00Z",
  "updated_at": "2026-03-27T12:00:00Z"
}
```

**Типичные `status`:**
- `queued`
- `planning`
- `searching`
- `deduping`
- `fetching_details`
- `unifying`
- `completed`
- `failed`

**Состояния:**
- `200`
- `401`
- `404`

---

### `GET {base_url}/me/search-jobs/runs/{workflow_run_id}/progress`
**Зачем нужен:** получить полную историю progress events поискового workflow списком.

**Принимает:** path param `workflow_run_id`

**Возвращает:** массив `SearchJobProgressEventResponse`
```json
[
  {
    "workflow_run_id": "uuid",
    "event_type": "phase_changed",
    "internal_stage": "planning",
    "display_stage": "planning",
    "display_label": "Understanding your preferences",
    "display_description": "We are turning your profile into a search plan.",
    "site": null,
    "progress_order": 1,
    "display_icon_key": "sparkles",
    "display_color_key": "sky",
    "site_display_name": null,
    "payload": {},
    "created_at": "2026-03-27T12:00:00Z"
  }
]
```

**Типичные `event_type`:**
- `phase_changed`
- `step_completed`
- `site_activity`
- `jobs_ready`
- `error`

**Состояния:**
- `200`
- `401`
- `404`

---

### `GET {base_url}/me/search-jobs/runs/{workflow_run_id}/events`
**Зачем нужен:** live SSE stream для красивого экрана поиска вакансий.

**Принимает:** path param `workflow_run_id`

**Возвращает:** `text/event-stream`
Каждое событие содержит `SearchJobProgressEventResponse`. В конце приходит `terminal` с финальным `SearchJobWorkflowRunResponse`.

**Типичные SSE event names:**
- `phase_changed`
- `step_completed`
- `site_activity`
- `jobs_ready`
- `error`
- `terminal`

**Состояния:**
- `200`
- `401`
- `404`

---

## 6. Save search results to tracker

### `POST {base_url}/me/job-tracker/jobs/from-search-run`
**Зачем нужен:** кнопка "Сохранить" на карточке вакансии из search results.

**Принимает JSON:**
```json
{
  "workflow_run_id": "uuid",
  "job_index": 0
}
```

или

```json
{
  "workflow_run_id": "uuid",
  "job_url": "https://..."
}
```

**Возвращает при новом сохранении:** `201 Created`

**Возвращает при повторном сохранении той же вакансии:** `200 OK`
```json
{
  "tracked_job": { "...TrackedJobResponse..." },
  "already_saved": false,
  "tracked_job_id": "uuid",
  "tracker_status": "saved"
}
```

**Состояния:**
- `201` - сохранено впервые
- `200` - уже было сохранено ранее
- `401`
- `404` - workflow run / job не найдены или в run нет jobs
- `422` - не передан ни `job_url`, ни `job_index`

---

## 7. Job tracker list and detail

### `GET {base_url}/me/job-tracker/jobs`
**Зачем нужен:** основная таблица вакансий в tracker.

**Query params:**
- `status`
- `site`
- `priority`
- `has_follow_up`
- `archived`
- `search`
- `sort`

**Допустимые `sort`:**
- `updated_at`
- `deadline_at`
- `next_follow_up_at`
- `applied_at`

**Допустимые `priority`:**
- `low`
- `medium`
- `high`

**Допустимые `status`:**
- `saved`
- `to_apply`
- `applied`
- `screening`
- `interview`
- `take_home`
- `final_round`
- `offer`
- `rejected`
- `withdrawn`
- `archived`

**Возвращает:** массив `TrackedJobResponse`

**Состояния:**
- `200`
- `401`
- `422` - невалидный `sort/status/priority`

---

### `POST {base_url}/me/job-tracker/jobs`
**Зачем нужен:** вручную создать запись в tracker.

**Принимает JSON:**
```json
{
  "title": "Senior ML Engineer",
  "company_name": "Acme",
  "source_job_url": "https://...",
  "site": "manual",
  "location": "Remote",
  "salary_text": "$5k",
  "employment_type": "full-time",
  "apply_url": "https://...",
  "description_snapshot": "...",
  "skills_snapshot": ["python", "llm"],
  "fit_level": "high",
  "why_apply_snapshot": "...",
  "priority": "medium",
  "deadline_at": null,
  "notes_summary": "Strong match"
}
```

**Возвращает:** `201 Created` + `TrackedJobResponse`

**Состояния:**
- `201`
- `401`
- `409` - `Tracked job with this URL already exists.`
- `422` - невалидный body или `priority`

---

### `GET {base_url}/me/job-tracker/jobs/{tracked_job_id}`
**Зачем нужен:** получить одну карточку вакансии с activities и contacts.

**Возвращает:** `TrackedJobDetailResponse`
```json
{
  "...TrackedJobResponse fields...": "...",
  "activities": [],
  "contacts": []
}
```

**Состояния:**
- `200`
- `401`
- `404` - `Tracked job not found.`

---

### `PATCH {base_url}/me/job-tracker/jobs/{tracked_job_id}`
**Зачем нужен:** редактировать поля tracker job.

**Принимает JSON:** любой поднабор полей:
```json
{
  "title": "Updated title",
  "company_name": "Updated company",
  "priority": "high",
  "deadline_at": "2026-04-01T12:00:00Z",
  "next_follow_up_at": "2026-03-29T12:00:00Z",
  "notes_summary": "Updated note",
  "applied_at": "2026-03-27T12:00:00Z"
}
```

**Возвращает:** `TrackedJobResponse`

**Состояния:**
- `200`
- `401`
- `404`
- `422`

---

### `DELETE {base_url}/me/job-tracker/jobs/{tracked_job_id}`
**Зачем нужен:** архивировать вакансию.

**Принимает:** ничего

**Возвращает:** `TrackedJobResponse` со статусом `archived`

**Состояния:**
- `200`
- `401`
- `404`

---

### `POST {base_url}/me/job-tracker/jobs/{tracked_job_id}/status`
**Зачем нужен:** поменять stage вакансии.

**Принимает JSON:**
```json
{
  "status": "applied"
}
```

**Возвращает:** `TrackedJobResponse`

**Состояния:**
- `200`
- `401`
- `404`
- `422` - невалидный `status`

---

## 8. Job tracker activities

### `GET {base_url}/me/job-tracker/jobs/{tracked_job_id}/activities`
**Зачем нужен:** таймлайн активности по вакансии.

**Возвращает:** массив `TrackedJobActivityResponse`

**Типичные `activity_type`:**
- `note`
- `status_change`
- `follow_up`
- `interview`

**Состояния:**
- `200`
- `401`
- `404`

---

### `POST {base_url}/me/job-tracker/jobs/{tracked_job_id}/activities`
**Зачем нужен:** добавить note, follow-up или interview.

**Принимает JSON:**
```json
{
  "activity_type": "follow_up",
  "title": "Follow up after application",
  "body": "Ping recruiter",
  "due_at": "2026-03-30T12:00:00Z",
  "event_at": null,
  "interview_format": null,
  "outcome": null,
  "details": {}
}
```

**Для `note`:**
- нужен `body`

**Для `follow_up`:**
- нужен `due_at`

**Для `interview`:**
- нужен `event_at`
- `interview_format` может быть:
  - `phone`
  - `zoom`
  - `onsite`
  - `async`

**Возвращает:** `201 Created` + `TrackedJobActivityResponse`

**Состояния:**
- `201`
- `401`
- `404`
- `422` - невалидный `activity_type` или обязательные поля не переданы

---

### `POST {base_url}/me/job-tracker/jobs/{tracked_job_id}/activities/{activity_id}/complete`
**Зачем нужен:** отметить follow-up как выполненный.

**Принимает:** ничего

**Возвращает:** `TrackedJobActivityResponse`

**Состояния:**
- `200`
- `401`
- `404` - `Activity not found.` или job not found
- `409` - `Only follow-up activities can be completed.`

---

## 9. Job tracker contacts

### `GET {base_url}/me/job-tracker/jobs/{tracked_job_id}/contacts`
**Зачем нужен:** список контактов по вакансии.

**Возвращает:** массив `TrackedJobContactResponse`

**Состояния:**
- `200`
- `401`
- `404`

---

### `POST {base_url}/me/job-tracker/jobs/{tracked_job_id}/contacts`
**Зачем нужен:** добавить recruiter / hiring manager / referral / interviewer.

**Принимает JSON:**
```json
{
  "name": "Jane Recruiter",
  "role": "Recruiter",
  "company": "Acme",
  "email": "jane@acme.com",
  "linkedin_url": "https://linkedin.com/in/jane",
  "relation_type": "recruiter",
  "last_contact_at": "2026-03-27T12:00:00Z",
  "next_follow_up_at": "2026-03-30T12:00:00Z",
  "notes": "Friendly intro call"
}
```

**Допустимые `relation_type`:**
- `recruiter`
- `hiring_manager`
- `referral`
- `interviewer`
- `other`

**Возвращает:** `201 Created` + `TrackedJobContactResponse`

**Состояния:**
- `201`
- `401`
- `404`
- `422` - невалидный `relation_type`

---

## 10. Job tracker metrics, dashboard, feed, bulk and export

### `GET {base_url}/me/job-tracker/metrics`
**Зачем нужен:** получить сводные метрики tracker-а.

**Возвращает:** `JobTrackerMetricsResponse`
```json
{
  "total_jobs": 10,
  "saved_jobs_count": 3,
  "applications_submitted": 4,
  "interviews_count": 2,
  "offers_count": 1,
  "rejections_count": 1,
  "conversion_saved_to_applied": 0.4,
  "conversion_applied_to_interview": 0.5,
  "conversion_interview_to_offer": 0.5,
  "jobs_by_status": {
    "saved": 3,
    "applied": 4
  },
  "kanban_group_counts": {
    "saved": 3,
    "applied": 4
  },
  "overdue_followups_count": 1,
  "average_days_in_stage": 2.5
}
```

**Состояния:**
- `200`
- `401`

---

### `GET {base_url}/me/job-tracker/dashboard`
**Зачем нужен:** агрегированный payload для домашнего экрана tracker-а.

**Возвращает:** `JobTrackerDashboardResponse`
```json
{
  "tracker_totals": { "...JobTrackerMetricsResponse..." },
  "upcoming_followups": [],
  "overdue_followups": [],
  "upcoming_interviews": [],
  "recently_updated_jobs": []
}
```

**Состояния:**
- `200`
- `401`

---

### `GET {base_url}/me/job-tracker/activity-feed`
**Зачем нужен:** общая лента последних действий по tracker-у.

**Возвращает:** массив `JobTrackerActivityFeedItemResponse`
```json
[
  {
    "activity": { "...TrackedJobActivityResponse..." },
    "tracked_job": { "...TrackedJobResponse..." }
  }
]
```

**Состояния:**
- `200`
- `401`

---

### `POST {base_url}/me/job-tracker/jobs/bulk/status`
**Зачем нужен:** массово поменять статус нескольких вакансий.

**Принимает JSON:**
```json
{
  "tracked_job_ids": ["uuid1", "uuid2"],
  "status": "archived"
}
```

**Возвращает:** массив `TrackedJobResponse`

**Состояния:**
- `200`
- `401`
- `404` - один из jobs не найден
- `422` - пустой список или невалидный `status`

---

### `POST {base_url}/me/job-tracker/jobs/bulk/archive`
**Зачем нужен:** массово архивировать вакансии.

**Принимает JSON:**
```json
{
  "tracked_job_ids": ["uuid1", "uuid2"]
}
```

**Возвращает:** массив `TrackedJobResponse`

**Состояния:**
- `200`
- `401`
- `404` - один из jobs не найден
- `422` - пустой список

---

### `GET {base_url}/me/job-tracker/export.csv`
**Зачем нужен:** экспорт tracker-а в CSV.

**Query params:** те же, что у `GET /me/job-tracker/jobs`
- `status`
- `site`
- `priority`
- `has_follow_up`
- `archived`
- `search`
- `sort`

**Возвращает:** `text/csv` + `Content-Disposition: attachment; filename="job-tracker.csv"`

**Состояния:**
- `200`
- `401`
- `422`

---

## 11. Минимальный реальный flow для frontend

### Auth
1. `POST /auth/email/request-code`
2. `POST /auth/email/verify-code`
3. `GET /auth/session`
4. `GET /me/app-state`

### Новый пользователь
1. `POST /me/onboarding/restart`
2. `POST /me/extraction/cv/run`
3. `GET /me/extraction/runs/{id}/events`
4. `GET /me/onboarding/thread`
5. `POST /me/onboarding/respond` до завершения onboarding
6. взять `search_job_workflow_run_id`
7. `GET /me/search-jobs/runs/{id}/events`

### После получения вакансий
1. показать `jobs[]` из search run
2. по кнопке save: `POST /me/job-tracker/jobs/from-search-run`
3. для tracker home: `GET /me/job-tracker/dashboard`
4. для таблицы: `GET /me/job-tracker/jobs`

---

## 12. Что в этот файл не включено

Здесь перечислены только **user-facing frontend endpoints**.
**Admin endpoints** сюда не включал специально, чтобы файл оставался чистым и не смешивал пользовательский продукт с админкой.
