from sqlalchemy import select

from database.pharmacie_session import PharmacieSessionLocal
from services.pharmacie.models import Medicine, Supplier


MEDICINES = [
    ("PARACETAMOL-500MG", "Paracétamol 500 mg", "TABLET", "500 mg", "tablet", 500, 10),
    ("AMOXICILLIN-500MG", "Amoxicilline 500 mg", "CAPSULE", "500 mg", "capsule", 1000, 10),
    ("ORS-SACHET", "Sels de réhydratation orale", "SACHET", "standard", "sachet", 1500, 8),
    ("CEFTRIAXONE-1G", "Ceftriaxone 1 g", "INJECTION", "1 g", "vial", 4000, 5),
]
SUPPLIERS = [
    ("SUP-001", "MedSupply Burundi", "+25700000001", "sales@medsupply.local"),
    ("SUP-002", "PharmaLog Burundi", "+25700000002", "orders@pharmalog.local"),
]


def main():
    session = PharmacieSessionLocal()
    try:
        for code, name, form, strength, unit, price, reorder in MEDICINES:
            item = session.scalar(select(Medicine).where(Medicine.code == code))
            if item is None:
                session.add(Medicine(
                    code=code,
                    name=name,
                    form=form,
                    strength=strength,
                    unit=unit,
                    sale_price_minor=price,
                    currency="BIF",
                    reorder_level=reorder,
                    active=True,
                ))
        for code, name, phone, email in SUPPLIERS:
            item = session.scalar(select(Supplier).where(Supplier.code == code))
            if item is None:
                session.add(Supplier(code=code, name=name, phone=phone, email=email, active=True))
        session.commit()
        print("PROJECTX PHARMACIE CATALOG SEED OK")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
