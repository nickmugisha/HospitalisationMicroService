from sqlalchemy import select
from database.hospitalisation_session import HospitalisationSessionLocal
from services.hospitalisation.models import Bed, Room, Ward

STRUCTURE = [
    ("MED", "Médecine générale", 20000, [("MED-101", "Chambre 101", ["A", "B"]), ("MED-102", "Chambre 102", ["A", "B"])]),
    ("SURG", "Chirurgie", 30000, [("SURG-201", "Chambre 201", ["A", "B"])]),
    ("ICU", "Soins intensifs", 75000, [("ICU-01", "Réanimation 1", ["1", "2"])]),
]

def main():
    s = HospitalisationSessionLocal()
    try:
        for ward_code, ward_name, rate, rooms in STRUCTURE:
            ward = s.scalar(select(Ward).where(Ward.code == ward_code))
            if ward is None:
                ward = Ward(code=ward_code, name=ward_name, active=True, daily_rate_minor=rate, currency="BIF")
                s.add(ward); s.flush()
            for room_code, room_name, beds in rooms:
                room = s.scalar(select(Room).where(Room.ward_id == ward.id, Room.code == room_code))
                if room is None:
                    room = Room(ward_id=ward.id, code=room_code, name=room_name); s.add(room); s.flush()
                for bed_code in beds:
                    bed = s.scalar(select(Bed).where(Bed.room_id == room.id, Bed.code == bed_code))
                    if bed is None:
                        s.add(Bed(room_id=room.id, code=bed_code, status="AVAILABLE"))
        s.commit()
        print("PROJECTX HOSPITALISATION STRUCTURE SEED OK")
    except Exception:
        s.rollback(); raise
    finally:
        s.close()

if __name__ == "__main__": main()
