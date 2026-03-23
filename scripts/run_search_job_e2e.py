from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from src.config import get_settings

BASE_URL = "http://127.0.0.1:8001"
DEFAULT_POLL_SECONDS = 3

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
    while onboarding["status"] != "completed" and steps < 10:
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


async def run_scenario(*, scenario_name: str) -> dict[str, object]:
    scenario = SCENARIOS[scenario_name]
    user_payload = dict(scenario["user"])
    user_payload["email"] = f"{scenario_name}-{int(time.time())}@example.com"
    pdf_path: Path = scenario["pdf_path"]

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120) as client:
        user_response = await client.post("/users", json=user_payload)
        user_response.raise_for_status()
        user = user_response.json()
        user_id = user["id"]
        print("user_id", user_id)

        with pdf_path.open("rb") as pdf_file:
            extraction_response = await client.post(
                "/extraction/cv/run",
                files={"file": (pdf_path.name, pdf_file, "application/pdf")},
                data={"user_id": user_id},
            )
        extraction_response.raise_for_status()
        extraction_run = extraction_response.json()
        extraction_run_id = extraction_run["workflow_run_id"]
        print("extraction_run_id", extraction_run_id)

        extraction_result = await _poll_json(
            client,
            path=f"/extraction/cv/run/{extraction_run_id}",
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

        search_run = None
        for _ in range(10):
            search_run = await _latest_search_job_run(user_id, onboarding["id"])
            if search_run is not None:
                break
            await asyncio.sleep(2)

        if search_run is None:
            search_response = await client.post("/search-jobs/run", json={"user_id": user_id})
            search_response.raise_for_status()
            search_job_run = search_response.json()
            search_job_run_id = search_job_run["workflow_run_id"]
        else:
            search_job_run_id = search_run["id"]

        print("search_run_id", search_job_run_id)
        search_result = await _poll_json(
            client,
            path=f"/search-jobs/run/{search_job_run_id}",
            timeout_seconds=1200,
            break_on=lambda payload: payload.get("status") in {"completed", "failed"},
        )
        print("search_status", search_result["status"])
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

        return {
            "scenario": scenario_name,
            "user_id": user_id,
            "extraction_run_id": extraction_run_id,
            "onboarding_session_id": onboarding["id"],
            "search_job_run_id": search_job_run_id,
            "search_status": search_result["status"],
            "search_result": search_result,
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
    args = parser.parse_args()
    scenario_names = args.scenarios or list(SCENARIOS.keys())
    for scenario_name in scenario_names:
        print(f"=== scenario:{scenario_name} ===")
        await run_scenario(scenario_name=scenario_name)


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
