from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from src.config import get_settings

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8001")
DEFAULT_POLL_SECONDS = 3
DEFAULT_ADMIN_EMAIL = os.getenv("E2E_ADMIN_EMAIL", "admin-e2e@example.com")
DEFAULT_ADMIN_PASSWORD = os.getenv("E2E_ADMIN_PASSWORD", "admin-pass-123")

SCENARIOS: dict[str, dict[str, object]] = {
    "senior_backend_remote": {
        "pdf_path": Path("tmp/search-job-e2e/senior_backend_remote.pdf"),
        "user": {
            "full_name": "E2E Senior Backend",
            "timezone": "Asia/Bishkek",
            "locale": "en",
        },
        "clarification_answer": (
            "I am targeting senior backend or platform engineering roles. "
            "Remote only. Preferred stack is Python, FastAPI, Go, PostgreSQL, Redis, Kafka, AWS. "
            "Open to global or EMEA remote teams. Salary target is 4500 USD net monthly or higher. "
            "Prefer product companies and strong engineering culture. "
            "Exclude internships, Android, iOS, pure frontend, gambling, and crypto-only companies."
        ),
        "prompt_answers": {
            "notice_period": "My notice period is two weeks.",
            "employment_type": "I am looking for full-time roles.",
            "location": (
                "I am based in Bishkek and want remote-only roles "
                "across EMEA or global async teams."
            ),
            "remote": "Remote only.",
            "salary": "My target is at least 4500 USD net monthly.",
            "visa": "I do not need visa sponsorship for remote roles from Bishkek.",
            "education": "I have a completed bachelor's degree in computer science.",
        },
    },
    "latam_fullstack_product": {
        "pdf_path": Path("tmp/search-job-e2e/latam_fullstack_product.pdf"),
        "user": {
            "full_name": "E2E LATAM Fullstack",
            "timezone": "America/Mexico_City",
            "locale": "es-MX",
        },
        "clarification_answer": (
            "Busco roles middle de fullstack o product engineer. "
            "Remoto o hibrido en Ciudad de Mexico. "
            "Stack principal: React, TypeScript, Node.js, PostgreSQL y Python. "
            "Compensacion minima 70000 MXN mensuales. "
            "Prefiero empresas de producto y no quiero soporte, call center "
            "ni puestos totalmente onsite fuera de CDMX."
        ),
        "prompt_answers": {
            "notice_period": "Puedo empezar en dos semanas.",
            "employment_type": "Busco empleo full-time.",
            "location": "Estoy en Ciudad de Mexico y prefiero remoto o hibrido en CDMX.",
            "remote": "Prefiero remoto o hibrido en Ciudad de Mexico.",
            "salary": "Mi expectativa minima es 70000 MXN mensuales.",
            "visa": "No necesito sponsorship para trabajar en Mexico.",
            "education": "Tengo licenciatura completa en ingenieria de software.",
        },
    },
    "cis_platform_backend": {
        "pdf_path": Path("tmp/search-job-e2e/cis_platform_backend.pdf"),
        "user": {
            "full_name": "E2E CIS Platform",
            "timezone": "Asia/Almaty",
            "locale": "ru",
        },
        "clarification_answer": (
            "Ищу middle-senior backend или platform engineering роли. "
            "Формат remote или hybrid в Алматы/Бишкеке. "
            "Стек: Python, Go, PostgreSQL, ClickHouse, Kafka, Kubernetes, Terraform. "
            "Минимум 3500 USD в месяц. "
            "Не интересуют junior, manual QA, support и sales вакансии."
        ),
        "prompt_answers": {
            "notice_period": "Мой notice period две недели.",
            "employment_type": "Ищу full-time роли.",
            "location": "Я нахожусь в Алматы и рассматриваю remote или hybrid в Алматы и Бишкеке.",
            "remote": "Предпочитаю remote или hybrid в Алматы и Бишкеке.",
            "salary": "Минимум 3500 USD в месяц.",
            "visa": "Для remote ролей sponsorship не требуется.",
            "education": "У меня оконченное высшее образование по computer science.",
        },
    },
}

CONFIRM_ANSWER = "yes"


async def _latest_search_job_run(user_id: str, onboarding_session_id: str) -> dict[str, str] | None:
    engine = create_async_engine(get_settings().connection_string)
    query = text(
        "select id::text, status from search_job_workflow_runs "
        "where user_id = :user_id and onboarding_session_id::text = :session_id "
        "order by created_at desc limit 1"
    )
    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {"user_id": user_id, "session_id": onboarding_session_id},
        )
        row = result.first()
    await engine.dispose()
    if row is None:
        return None
    return {"id": row[0], "status": row[1]}


async def _wait_for_api_ready(client: httpx.AsyncClient, *, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = await client.get("/health")
            response.raise_for_status()
            return
        except Exception as exc:  # pragma: no cover - exercised in live E2E only
            last_error = exc
            await asyncio.sleep(1)
    raise RuntimeError("API did not become ready in time.") from last_error


async def _poll_json(
    client: httpx.AsyncClient,
    *,
    path: str,
    timeout_seconds: int,
    break_on,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict[str, object] | None = None
    while time.monotonic() < deadline:
        response = await client.get(path)
        response.raise_for_status()
        payload = response.json()
        last_payload = payload
        print(f"poll {path} {payload.get('status')}")
        if break_on(payload):
            return payload
        await asyncio.sleep(DEFAULT_POLL_SECONDS)

    if last_payload is None:
        raise RuntimeError(f"Polling {path} returned no payload.")
    return last_payload


async def _admin_login(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: str,
) -> None:
    response = await client.post(
        "/auth/admin/login",
        json={"email": email, "password": password},
    )
    if response.status_code == 401:
        raise RuntimeError(
            "Admin login failed. Start the app with matching ADMINS env, for example: "
            f'ADMINS=\'{{"{email}":"{password}"}}\''
        )
    response.raise_for_status()
    session_payload = response.json()
    if not session_payload.get("authenticated"):
        raise RuntimeError("Admin session was not established.")
    print("admin_login_ok", email)


async def _create_user_via_admin(
    client: httpx.AsyncClient,
    *,
    scenario_name: str,
    scenario: dict[str, object],
) -> dict[str, object]:
    user_payload = dict(scenario["user"])
    user_payload["email"] = f"{scenario_name}-{int(time.time())}@example.com"
    response = await client.post("/admin/users", json=user_payload)
    response.raise_for_status()
    return response.json()


async def _drive_onboarding(
    client: httpx.AsyncClient,
    *,
    user_id: str,
    scenario: dict[str, object],
) -> dict[str, object]:
    response = await client.get(f"/onboarding/users/{user_id}/active")
    response.raise_for_status()
    onboarding = response.json()
    print(
        "onboarding_initial",
        onboarding["status"],
        onboarding.get("pending_user_prompt_type"),
    )

    steps = 0
    while onboarding["status"] != "completed" and steps < 12:
        steps += 1
        pending_prompt = onboarding.get("pending_user_prompt")
        if pending_prompt:
            prompt_type = onboarding.get("pending_user_prompt_type")
            answer = (
                CONFIRM_ANSWER
                if prompt_type == "confirmation_request"
                else _answer_for_prompt(prompt=str(pending_prompt), scenario=scenario)
            )
            print("prompt_type", prompt_type)
            print("prompt", pending_prompt)
            print("answer", answer)
            response = await client.post(
                f"/onboarding/users/{user_id}/respond",
                json={"answer": answer},
            )
        else:
            response = await client.post(f"/onboarding/users/{user_id}/run")
        response.raise_for_status()
        onboarding = response.json()
        print("onboarding_step", onboarding["status"], onboarding.get("pending_user_prompt_type"))
        await asyncio.sleep(2)

    return onboarding


def _print_search_summary(*, label: str, search_result: dict[str, object]) -> None:
    print(label, search_result["status"])
    print(
        "totals",
        search_result.get("total_site_results"),
        search_result.get("total_jobs_found"),
        search_result.get("total_jobs_returned"),
    )
    print("notes", json.dumps(search_result.get("notes", [])[:10], ensure_ascii=False))
    for site_result in search_result.get("site_results", []):
        print(
            "site",
            site_result["site"],
            site_result["status"],
            len(site_result.get("listings_seen", [])),
            len(site_result.get("selected_jobs", [])),
            site_result.get("reason"),
        )
    for job in search_result.get("jobs", [])[:10]:
        print(
            "job",
            json.dumps(
                {
                    "fit": job.get("fit_level"),
                    "site": job.get("site"),
                    "title": job.get("title"),
                    "company": job.get("company_name"),
                    "url": job.get("job_url"),
                },
                ensure_ascii=False,
            ),
        )


async def _run_search_job(
    client: httpx.AsyncClient,
    *,
    user_id: str,
    onboarding_session_id: str,
    monitoring_mode: bool,
) -> dict[str, object]:
    latest_run = await _latest_search_job_run(user_id, onboarding_session_id)
    active_statuses = {
        "queued",
        "planning",
        "searching",
        "deduping",
        "fetching_details",
        "unifying",
    }
    if not monitoring_mode and latest_run is not None and latest_run["status"] in active_statuses:
        search_job_run_id = latest_run["id"]
    else:
        search_response = await client.post(
            f"/admin/users/{user_id}/search-jobs/run",
            params={"monitoring_mode": str(monitoring_mode).lower()},
        )
        search_response.raise_for_status()
        search_job_run = search_response.json()
        search_job_run_id = search_job_run["workflow_run_id"]
    print("search_run_id", search_job_run_id, "monitoring", monitoring_mode)
    search_result = await _poll_json(
        client,
        path=f"/admin/search-job-runs/{search_job_run_id}",
        timeout_seconds=1200,
        break_on=lambda payload: payload.get("status") in {"completed", "failed"},
    )
    latest_run = await _latest_search_job_run(user_id, onboarding_session_id)
    print("latest_search_run", latest_run)
    return search_result


async def run_scenario(
    *,
    scenario_name: str,
    admin_email: str,
    admin_password: str,
    monitoring_repeats: int,
) -> dict[str, object]:
    scenario = SCENARIOS[scenario_name]
    pdf_path: Path = scenario["pdf_path"]

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=120,
        follow_redirects=True,
    ) as client:
        await _wait_for_api_ready(client)
        await _admin_login(client, email=admin_email, password=admin_password)

        user = await _create_user_via_admin(
            client,
            scenario_name=scenario_name,
            scenario=scenario,
        )
        user_id = user["id"]
        print("user_id", user_id)

        restart_response = await client.post(f"/admin/users/{user_id}/onboarding/restart")
        restart_response.raise_for_status()
        print("onboarding_restarted", restart_response.json()["id"])

        with pdf_path.open("rb") as pdf_file:
            extraction_response = await client.post(
                f"/admin/users/{user_id}/extraction/run",
                files={"file": (pdf_path.name, pdf_file, "application/pdf")},
            )
        extraction_response.raise_for_status()
        extraction_run = extraction_response.json()
        extraction_run_id = extraction_run["workflow_run_id"]
        print("extraction_run_id", extraction_run_id)

        extraction_result = await _poll_json(
            client,
            path=f"/admin/extraction-runs/{extraction_run_id}",
            timeout_seconds=300,
            break_on=lambda payload: payload.get("status") not in {"queued", "extracting"},
        )
        print("extraction_status", extraction_result["status"])
        print("extracted_profile", (extraction_result.get("extracted_profile") or "")[:500])
        print("missing_info", extraction_result.get("missing_info"))
        print("preference_hints", extraction_result.get("preference_hints"))

        onboarding = await _drive_onboarding(
            client,
            user_id=user_id,
            scenario=scenario,
        )
        print("onboarding_final_status", onboarding["status"])
        print("search_strategy_summary", onboarding.get("search_strategy_summary"))
        print("hard_preferences", onboarding.get("hard_preferences"))
        print("soft_preferences", onboarding.get("soft_preferences"))

        initial_search = await _run_search_job(
            client,
            user_id=user_id,
            onboarding_session_id=onboarding["id"],
            monitoring_mode=False,
        )
        _print_search_summary(label="initial_search_status", search_result=initial_search)

        monitoring_results: list[dict[str, object]] = []
        previous_job_urls = {
            str(job.get("job_url")) for job in initial_search.get("jobs", []) if job.get("job_url")
        }
        for repeat_index in range(monitoring_repeats):
            monitoring_result = await _run_search_job(
                client,
                user_id=user_id,
                onboarding_session_id=onboarding["id"],
                monitoring_mode=True,
            )
            _print_search_summary(
                label=f"monitoring_search_status_{repeat_index + 1}",
                search_result=monitoring_result,
            )
            current_urls = {
                str(job.get("job_url"))
                for job in monitoring_result.get("jobs", [])
                if job.get("job_url")
            }
            print(
                "monitoring_overlap",
                repeat_index + 1,
                len(previous_job_urls & current_urls),
                len(current_urls),
            )
            previous_job_urls = current_urls
            monitoring_results.append(monitoring_result)

        return {
            "scenario": scenario_name,
            "user_id": user_id,
            "extraction_run_id": extraction_run_id,
            "onboarding_session_id": onboarding["id"],
            "initial_search": initial_search,
            "monitoring_results": monitoring_results,
        }


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run live local search-job E2E scenarios.")
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        choices=sorted(SCENARIOS.keys()),
        help="Scenario name to run. Can be provided multiple times. Defaults to all.",
    )
    parser.add_argument(
        "--admin-email",
        default=DEFAULT_ADMIN_EMAIL,
        help="Admin email bootstrapped via ADMINS env when starting the app.",
    )
    parser.add_argument(
        "--admin-password",
        default=DEFAULT_ADMIN_PASSWORD,
        help="Admin password bootstrapped via ADMINS env when starting the app.",
    )
    parser.add_argument(
        "--monitoring-repeats",
        type=int,
        default=1,
        help="How many monitoring runs to execute after the initial search.",
    )
    args = parser.parse_args()
    scenario_names = args.scenarios or list(SCENARIOS.keys())
    for scenario_name in scenario_names:
        print(f"=== scenario:{scenario_name} ===")
        await run_scenario(
            scenario_name=scenario_name,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
            monitoring_repeats=max(0, args.monitoring_repeats),
        )


def _answer_for_prompt(*, prompt: str, scenario: dict[str, object]) -> str:
    prompt_lower = prompt.lower()
    prompt_answers = dict(scenario.get("prompt_answers", {}))
    if (
        "notice period" in prompt_lower
        or "start" in prompt_lower
        or "preaviso" in prompt_lower
        or "período de preaviso" in prompt_lower
        or "период" in prompt_lower
        or "срок" in prompt_lower
    ):
        return str(prompt_answers.get("notice_period", scenario["clarification_answer"]))
    if (
        "employment type" in prompt_lower
        or "full-time" in prompt_lower
        or "contract" in prompt_lower
        or "tipo de empleo" in prompt_lower
        or "tipo de contrato" in prompt_lower
        or "тип занятости" in prompt_lower
    ):
        return str(prompt_answers.get("employment_type", scenario["clarification_answer"]))
    if (
        "education" in prompt_lower
        or "degree" in prompt_lower
        or "educación" in prompt_lower
        or "educacion" in prompt_lower
        or "образован" in prompt_lower
        or "диплом" in prompt_lower
    ):
        return str(prompt_answers.get("education", scenario["clarification_answer"]))
    if (
        "visa" in prompt_lower
        or "work authorization" in prompt_lower
        or "visado" in prompt_lower
        or "patrocinio" in prompt_lower
        or "визов" in prompt_lower
        or "визовая поддержка" in prompt_lower
        or "разрешение на работу" in prompt_lower
    ):
        return str(prompt_answers.get("visa", scenario["clarification_answer"]))
    if (
        "salary" in prompt_lower
        or "compensation" in prompt_lower
        or "pay" in prompt_lower
        or "salario" in prompt_lower
        or "compensación" in prompt_lower
        or "compensacion" in prompt_lower
        or "зарплат" in prompt_lower
    ):
        return str(prompt_answers.get("salary", scenario["clarification_answer"]))
    if (
        "location" in prompt_lower
        or "city" in prompt_lower
        or "country" in prompt_lower
        or "ubicación" in prompt_lower
        or "ubicacion" in prompt_lower
        or "ciudad" in prompt_lower
        or "страна" in prompt_lower
        or "город" in prompt_lower
    ):
        return str(prompt_answers.get("location", scenario["clarification_answer"]))
    if (
        "remote" in prompt_lower
        or "hybrid" in prompt_lower
        or "onsite" in prompt_lower
        or "remoto" in prompt_lower
        or "híbrido" in prompt_lower
        or "hibrido" in prompt_lower
        or "удален" in prompt_lower
        or "гибрид" in prompt_lower
    ):
        return str(prompt_answers.get("remote", scenario["clarification_answer"]))
    return str(scenario["clarification_answer"])


if __name__ == "__main__":
    asyncio.run(_main())
