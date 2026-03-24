from __future__ import annotations

from pathlib import Path

OUTPUT_DIR = Path("tmp/search-job-e2e")

PROFILE_LINES: dict[str, list[str]] = {
    "senior_backend_remote.pdf": [
        "Aigerim Sadykova",
        "Senior Python Backend Engineer",
        "8+ years building APIs, distributed systems, async workers, ETL, and platform tooling.",
        "Stack: Python, FastAPI, Django, PostgreSQL, Redis, RabbitMQ, Docker, Kubernetes, AWS.",
        "Recent role: led backend architecture for a SaaS product serving SMB finance teams.",
        (
            "Worked on event-driven services, billing, background jobs, "
            "search indexing, and observability."
        ),
        "Prefers remote product companies, backend/platform roles, strong engineering culture.",
        "Open to senior backend engineer, platform engineer, software engineer roles.",
        "Compensation target: 4500+ USD net monthly.",
        "Exclude: internships, Android, iOS, pure frontend, gambling, crypto-only companies.",
        "Based in Bishkek, available remote across EMEA or global async teams.",
    ],
    "latam_fullstack_product.pdf": [
        "Mariana Lopez",
        "Fullstack Product Engineer",
        "Based in Mexico City. Bilingual Spanish and English.",
        "6 years building customer-facing web apps for marketplaces and logistics products.",
        "Stack: React, TypeScript, Node.js, Python, PostgreSQL, Next.js, GraphQL.",
        "Strong collaboration with product, design, analytics, and growth teams.",
        "Prefers remote-first or hybrid roles in Mexico or LATAM-focused companies.",
        "Interested in fullstack engineer, product engineer, frontend-leaning fullstack roles.",
        "Compensation target: 70000+ MXN monthly gross.",
        "Exclude: call centers, support-only jobs, strict onsite outside Mexico City.",
    ],
    "cis_platform_backend.pdf": [
        "Nikita Ivanov",
        "Platform / Backend Engineer",
        "Based in Almaty, open to remote roles in CIS and international companies.",
        "7 years in backend and infrastructure engineering for B2B SaaS and fintech.",
        "Stack: Python, Go, PostgreSQL, ClickHouse, Kafka, Docker, Kubernetes, Terraform.",
        (
            "Built internal developer platforms, deployment tooling, "
            "CI/CD pipelines, and data services."
        ),
        (
            "Interested in backend engineer, platform engineer, "
            "infrastructure software engineer roles."
        ),
        "Prefers remote or hybrid in Almaty/Bishkek; Russian and English speaking teams are okay.",
        "Compensation target: 3500+ USD monthly.",
        "Exclude: junior roles, manual QA, sales, support, and relocation-only jobs.",
    ],
}


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf_bytes(lines: list[str]) -> bytes:
    content_lines = ["BT", "/F1 11 Tf", "72 790 Td", "14 TL"]
    for index, line in enumerate(lines):
        prefix = "" if index == 0 else "T* "
        content_lines.append(f"{prefix}({_escape_pdf_text(line)}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1", "replace")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n",
        (
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\n"
            b"endobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(content)} >>\nstream\n".encode()
            + content
            + b"\nendstream\nendobj\n"
        ),
    ]

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
        ).encode()
    )
    return bytes(pdf)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, lines in PROFILE_LINES.items():
        output_path = OUTPUT_DIR / filename
        output_path.write_bytes(_build_pdf_bytes(lines))
        print(output_path.resolve())


if __name__ == "__main__":
    main()
