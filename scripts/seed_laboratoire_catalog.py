from __future__ import annotations

from sqlalchemy import select

from database.laboratoire_session import LaboratoireSessionLocal
from services.laboratoire.models import LabTest


CATALOG = [
    ("CBC", "Numération formule sanguine", "Sang total EDTA", 12000),
    ("CRP", "Protéine C-réactive", "Sérum", 10000),
    ("GLU", "Glycémie", "Sang / plasma", 5000),
    ("MALARIA", "Test paludisme", "Sang", 7000),
]


def main():
    session = LaboratoireSessionLocal()
    try:
        created = 0
        for code, name, sample_type, price_minor in CATALOG:
            item = session.scalar(select(LabTest).where(LabTest.code == code))
            if item is None:
                session.add(LabTest(
                    code=code,
                    name=name,
                    sample_type=sample_type,
                    price_minor=price_minor,
                    currency="BIF",
                    active=True,
                ))
                created += 1
            else:
                item.name = name
                item.sample_type = sample_type
                item.price_minor = price_minor
                item.currency = "BIF"
                item.active = True
        session.commit()
        print(f"LAB CATALOG READY: {len(CATALOG)} tests ({created} created)")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
