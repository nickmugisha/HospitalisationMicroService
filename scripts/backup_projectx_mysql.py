from __future__ import annotations

import argparse
import glob
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from shutil import which

from dotenv import load_dotenv

DATABASE_KEYS = [
    ("auth", "MYSQL_AUTH_DATABASE", "hospital_auth"),
    ("accueil", "MYSQL_ACCUEIL_DATABASE", "hospital_accueil"),
    ("hospitalisation", "MYSQL_HOSPITALISATION_DATABASE", "hospital_hospitalisation"),
    ("billing", "MYSQL_BILLING_DATABASE", "hospital_billing"),
    ("consultation", "MYSQL_CONSULTATION_DATABASE", "hospital_consultation"),
    ("laboratoire", "MYSQL_LABORATOIRE_DATABASE", "hospital_laboratoire"),
    ("pharmacie", "MYSQL_PHARMACIE_DATABASE", "hospital_pharmacie"),
    ("maternite", "MYSQL_MATERNITE_DATABASE", "hospital_maternite"),
    ("rendezvous", "MYSQL_RENDEZVOUS_DATABASE", "hospital_rendezvous"),
    ("bi", "MYSQL_BI_DATABASE", "hospital_bi"),
    ("chatbot", "MYSQL_CHATBOT_DATABASE", "hospital_chatbot"),
    ("hr", "MYSQL_HR_DATABASE", "hospital_hr"),
]


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing {name} in .env")
    return value


def locate(exe: str) -> str:
    candidates: list[str] = []
    configured = os.getenv("MYSQL_BIN_DIR", "").strip()
    if configured:
        candidates.append(str(Path(configured) / exe))
    for root in (r"C:\wamp64\bin\mysql", r"C:\wamp\bin\mysql"):
        candidates.extend(glob.glob(str(Path(root) / "mysql*" / "bin" / exe)))
    candidates.extend(glob.glob(str(Path(r"C:\Program Files\MySQL") / "MySQL Server *" / "bin" / exe)))
    for candidate in sorted(set(candidates), reverse=True):
        if Path(candidate).is_file():
            return candidate
    found = which(exe) or which(Path(exe).stem)
    if found:
        return found
    raise RuntimeError(
        f"{exe} not found. Set MYSQL_BIN_DIR in .env, install MySQL client tools, or add them to PATH."
    )


def client_file() -> Path:
    fd, raw = tempfile.mkstemp(prefix="projectx_mysql_", suffix=".cnf", text=True)
    os.close(fd)
    path = Path(raw)
    path.write_text(
        "[client]\n"
        f"host={required('MYSQL_HOST')}\n"
        f"port={os.getenv('MYSQL_PORT', '3306').strip() or '3306'}\n"
        f"user={required('MYSQL_USER')}\n"
        f"password={required('MYSQL_PASSWORD')}\n"
        "default-character-set=utf8mb4\n",
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a private SQL backup of all ProjectX logical databases.")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-root", type=Path, default=None)
    args = parser.parse_args()
    root = args.project_root.resolve()
    env_file = root / ".env"
    if not env_file.is_file():
        raise SystemExit(f"Project .env not found: {env_file}")
    load_dotenv(env_file, override=True)

    dump_exe = locate("mysqldump.exe")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_root = (args.output_root.resolve() if args.output_root else root / "backups")
    target = output_root / f"projectx-{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    cfg = client_file()
    manifest: list[str] = []
    try:
        for service, env_key, default in DATABASE_KEYS:
            db = os.getenv(env_key, default).strip() or default
            out = target / f"{db}.sql"
            cmd = [
                dump_exe,
                f"--defaults-extra-file={cfg}",
                "--single-transaction",
                "--skip-lock-tables",
                "--routines",
                "--triggers",
                "--events",
                "--hex-blob",
                "--default-character-set=utf8mb4",
                db,
            ]
            with out.open("wb") as handle:
                result = subprocess.run(cmd, stdout=handle, stderr=subprocess.PIPE)
            if result.returncode != 0:
                out.unlink(missing_ok=True)
                raise RuntimeError(f"Backup failed for {db}: {result.stderr.decode(errors='replace')}")
            if out.stat().st_size == 0:
                raise RuntimeError(f"Backup produced an empty dump for {db}.")
            manifest.append(f"{service}\t{db}\t{out.name}\t{out.stat().st_size}")
            print(f"[OK] {db} -> {out.name}")
        (target / "MANIFEST.tsv").write_text(
            "service\tdatabase\tfile\tbytes\n" + "\n".join(manifest) + "\n", encoding="utf-8"
        )
        print(f"\nPROJECTX MYSQL BACKUP COMPLETE: {target}")
        print("Sensitive hospital data: keep this folder private and never commit it.")
    finally:
        try:
            cfg.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
