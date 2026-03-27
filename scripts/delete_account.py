import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.db.engine import session_factory
from src.extensions.s3 import S3StorageError, get_s3_storage

DELETE_ORDER = [
    "tracked_job_contacts",
    "tracked_job_activities",
    "tracked_jobs",
    "search_job_progress_events",
    "search_job_seen_jobs",
    "search_job_workflow_runs",
    "extraction_progress_events",
    "extraction_workflow_runs",
    "onboarding_sessions",
    "auth_sessions",
    "auth_email_challenges",
    "users",
]

DELETE_SQL = {
    "tracked_job_contacts": "delete from tracked_job_contacts where user_id = :user_id",
    "tracked_job_activities": "delete from tracked_job_activities where user_id = :user_id",
    "tracked_jobs": "delete from tracked_jobs where user_id = :user_id",
    "search_job_progress_events": "delete from search_job_progress_events where user_id = :user_id",
    "search_job_seen_jobs": "delete from search_job_seen_jobs where user_id = :user_id",
    "search_job_workflow_runs": "delete from search_job_workflow_runs where user_id = :user_id",
    "extraction_progress_events": "delete from extraction_progress_events where user_id = :user_id",
    "extraction_workflow_runs": "delete from extraction_workflow_runs where user_id = :user_id",
    "onboarding_sessions": "delete from onboarding_sessions where user_id = :user_id",
    "auth_sessions": "delete from auth_sessions where user_id = :user_id",
    "auth_email_challenges": "delete from auth_email_challenges where email = :email",
    "users": "delete from users where id::text = :user_id",
}


async def _table_exists(session, table_name: str) -> bool:
    result = await session.execute(
        text(
            "select exists ("
            "select 1 from information_schema.tables "
            "where table_schema = 'public' and table_name = :table_name)"
        ),
        {"table_name": table_name},
    )
    return bool(result.scalar())


async def _delete_account(email: str) -> None:
    async with session_factory() as session:
        user_id = await session.scalar(
            text("select id::text from users where email = :email"),
            {"email": email},
        )
        if not user_id:
            print(f"User not found for email: {email}")
            return

        extraction_keys = [
            row[0]
            for row in (
                await session.execute(
                    text(
                        "select storage_key from extraction_workflow_runs "
                        "where user_id = :user_id and storage_key is not null"
                    ),
                    {"user_id": user_id},
                )
            ).all()
        ]

        if extraction_keys:
            storage = get_s3_storage()
            for key in extraction_keys:
                try:
                    await storage.delete_object(key=key)
                    print(f"deleted_s3 {key}")
                except S3StorageError as exc:
                    print(f"s3_delete_failed {key}: {exc}")

        for table_name in DELETE_ORDER:
            if not await _table_exists(session, table_name):
                print(f"skip_missing_table {table_name}")
                continue

            result = await session.execute(
                text(DELETE_SQL[table_name]),
                {"user_id": user_id, "email": email},
            )
            print(f"deleted_rows {table_name} {result.rowcount}")

        await session.commit()
        print(f"delete_complete {email}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Delete all dev test data for an account email.")
    parser.add_argument("email", help="Account email to delete.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    asyncio.run(_delete_account(args.email.strip().lower()))


if __name__ == "__main__":
    main()
