from __future__ import annotations

import argparse
import glob
import os
import subprocess
import tempfile
from pathlib import Path
from shutil import which

from dotenv import load_dotenv

DATABASE_KEYS = [
    ("MYSQL_AUTH_DATABASE", "hospital_auth"), ("MYSQL_ACCUEIL_DATABASE", "hospital_accueil"),
    ("MYSQL_HOSPITALISATION_DATABASE", "hospital_hospitalisation"), ("MYSQL_BILLING_DATABASE", "hospital_billing"),
    ("MYSQL_CONSULTATION_DATABASE", "hospital_consultation"), ("MYSQL_LABORATOIRE_DATABASE", "hospital_laboratoire"),
    ("MYSQL_PHARMACIE_DATABASE", "hospital_pharmacie"), ("MYSQL_MATERNITE_DATABASE", "hospital_maternite"),
    ("MYSQL_RENDEZVOUS_DATABASE", "hospital_rendezvous"), ("MYSQL_BI_DATABASE", "hospital_bi"),
    ("MYSQL_CHATBOT_DATABASE", "hospital_chatbot"), ("MYSQL_HR_DATABASE", "hospital_hr"),
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
    raise RuntimeError(f"{exe} not found. Set MYSQL_BIN_DIR in .env or add the MySQL client tools to PATH.")


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
    parser = argparse.ArgumentParser(description="Restore all ProjectX logical databases from a verified backup folder.")
    parser.add_argument("backup_folder", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--confirm",
        metavar="PHRASE",
        help="Required destructive confirmation. Exact value: RESTORE_PROJECTX",
    )
    args = parser.parse_args()
    if args.confirm != "RESTORE_PROJECTX":
        raise SystemExit("Refusing destructive restore. Re-run with --confirm RESTORE_PROJECTX after stopping all ProjectX services.")

    root = args.project_root.resolve()
    env_file = root / ".env"
    if not env_file.is_file():
        raise SystemExit(f"Project .env not found: {env_file}")
    load_dotenv(env_file, override=True)
    folder = args.backup_folder.resolve()
    if not folder.is_dir():
        raise SystemExit(f"Backup folder not found: {folder}")

    # Preflight every dump BEFORE dropping a single database.
    plan: list[tuple[str, Path]] = []
    for env_key, default in DATABASE_KEYS:
        db = os.getenv(env_key, default).strip() or default
        sql = folder / f"{db}.sql"
        if not sql.is_file() or sql.stat().st_size == 0:
            raise SystemExit(f"Backup preflight failed: missing or empty dump {sql.name}")
        plan.append((db, sql))
    manifest = folder / "MANIFEST.tsv"
    if not manifest.is_file():
        raise SystemExit("Backup preflight failed: MANIFEST.tsv is missing.")

    mysql = locate("mysql.exe")
    cfg = client_file()
    try:
        for db, sql in plan:
            create = (
                f"DROP DATABASE IF EXISTS `{db}`; "
                f"CREATE DATABASE `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            result = subprocess.run([mysql, f"--defaults-extra-file={cfg}", "--execute", create], stderr=subprocess.PIPE)
            if result.returncode:
                raise RuntimeError(f"Could not recreate {db}: {result.stderr.decode(errors='replace')}")
            with sql.open("rb") as handle:
                result = subprocess.run([mysql, f"--defaults-extra-file={cfg}", db], stdin=handle, stderr=subprocess.PIPE)
            if result.returncode:
                raise RuntimeError(f"Restore failed for {db}: {result.stderr.decode(errors='replace')}")
            print(f"[OK] restored {db}")
        print("\nPROJECTX MYSQL RESTORE COMPLETE")
    finally:
        try:
            cfg.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
