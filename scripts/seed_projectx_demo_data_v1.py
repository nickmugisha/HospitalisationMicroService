from __future__ import annotations

r"""
ProjectX demo seeder v1
----------------------
Seeds realistic SYNTHETIC demo data through ProjectX gRPC APIs.
It does not write directly to MySQL.

Run from the Windows ProjectX root with all 12 services online:
    $env:PYTHONPATH="$PWD;$PWD\\generated"
    .\.venv\Scripts\python.exe <path>\seed_projectx_demo_data_v1.py

Optional environment variables:
    PROJECTX_GRPC_HOST=127.0.0.1
    PROJECTX_DEMO_PASSWORD=ProjectX-Demo-2026!
"""

import getpass
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

try:
    from auth.v1 import auth_pb2, auth_pb2_grpc
    from accueil.v1 import accueil_pb2, accueil_pb2_grpc
    from hr.v1 import hr_pb2, hr_pb2_grpc
    from consultation.v1 import consultation_pb2, consultation_pb2_grpc
    from laboratoire.v1 import laboratoire_pb2, laboratoire_pb2_grpc
    from pharmacie.v1 import pharmacie_pb2, pharmacie_pb2_grpc
    from hospitalisation.v1 import hospitalisation_pb2, hospitalisation_pb2_grpc
    from billing.v1 import billing_pb2, billing_pb2_grpc
    from rendezvous.v1 import rendezvous_pb2, rendezvous_pb2_grpc
    from maternite.v1 import maternite_pb2, maternite_pb2_grpc
except ImportError as exc:
    print("[ERROR] Generated ProjectX gRPC modules are not importable.")
    print('Run from the project root after: $env:PYTHONPATH="$PWD;$PWD\\generated"')
    raise

HOST = os.getenv("PROJECTX_GRPC_HOST", "127.0.0.1")
DEMO_PASSWORD = os.getenv("PROJECTX_DEMO_PASSWORD", "ProjectX-Demo-2026!")
TIMEOUT = 6

PORTS = {
    "auth": 50051,
    "accueil": 50052,
    "hospitalisation": 50053,
    "billing": 50054,
    "consultation": 50055,
    "laboratoire": 50056,
    "pharmacie": 50057,
    "maternite": 50058,
    "rendezvous": 50059,
    "hr": 50062,
}


def md(token: str):
    return (("authorization", f"Bearer {token}"),)


def ts(dt: datetime) -> Timestamp:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    t = Timestamp()
    t.FromDatetime(dt.astimezone(timezone.utc))
    return t


def ch(port: int):
    return grpc.insecure_channel(f"{HOST}:{port}")


def rpc_error(label: str, exc: grpc.RpcError):
    print(f"[WARN] {label}: {exc.code().name}: {exc.details()}")


def is_skip_error(exc: grpc.RpcError) -> bool:
    return exc.code() in {
        grpc.StatusCode.ALREADY_EXISTS,
        grpc.StatusCode.FAILED_PRECONDITION,
    }


# Football-inspired but synthetic names are used deliberately. We avoid creating
# fake medical records under exact real-player identities.
STAFF = [
    dict(emp="DEMO-RCP-001", first="Emma", last="Dubois", email="emma.dubois@projectx.demo", phone="+257796100001", dept="Accueil", title="Agent d'accueil", username="reception.demo", role="AGENT_ACCUEIL"),
    dict(emp="DEMO-MED-001", first="Carlo", last="Moretti", email="carlo.moretti@projectx.demo", phone="+257796100002", dept="Consultation", title="Médecin généraliste", username="doctor.carlo", role="MEDECIN"),
    dict(emp="DEMO-MED-002", first="Mikel", last="Navarro", email="mikel.navarro@projectx.demo", phone="+257796100003", dept="Consultation", title="Médecin interniste", username="doctor.mikel", role="MEDECIN"),
    dict(emp="DEMO-NUR-001", first="Elena", last="Martin", email="elena.martin@projectx.demo", phone="+257796100004", dept="Hospitalisation", title="Infirmière", username="nurse.elena", role="INFIRMIER"),
    dict(emp="DEMO-HSP-001", first="Roberto", last="Silva", email="roberto.silva@projectx.demo", phone="+257796100005", dept="Hospitalisation", title="Responsable hospitalisation", username="hosp.roberto", role="RESP_HOSPITALISATION"),
    dict(emp="DEMO-LAB-001", first="Luka", last="Petrovic", email="luka.petrovic@projectx.demo", phone="+257796100006", dept="Laboratoire", title="Technicien de laboratoire", username="lab.luka", role="LABORANTIN"),
    dict(emp="DEMO-PHA-001", first="Andrea", last="Bianchi", email="andrea.bianchi@projectx.demo", phone="+257796100007", dept="Pharmacie", title="Pharmacien", username="pharmacy.andrea", role="PHARMACIEN"),
    dict(emp="DEMO-CAS-001", first="Sofia", last="Garcia", email="sofia.garcia@projectx.demo", phone="+257796100008", dept="Finance", title="Caissière", username="cashier.sofia", role="CAISSIER"),
    dict(emp="DEMO-MAT-001", first="Lucia", last="Romano", email="lucia.romano@projectx.demo", phone="+257796100009", dept="Maternité", title="Sage-femme", username="maternity.lucia", role="SAGE_FEMME"),
    dict(emp="DEMO-HR-001", first="Isabelle", last="Laurent", email="isabelle.laurent@projectx.demo", phone="+257796100010", dept="Ressources Humaines", title="Responsable RH", username="hr.isabelle", role="RESPONSABLE_RH"),
    dict(emp="DEMO-LOG-001", first="Marco", last="Rossi", email="marco.rossi@projectx.demo", phone="+257796100011", dept="Logistique", title="Responsable logistique", username="logistics.marco", role="RESPONSABLE_LOGISTIQUE"),
    dict(emp="DEMO-BI-001", first="Thomas", last="Meyer", email="thomas.meyer@projectx.demo", phone="+257796100012", dept="Direction", title="Analyste BI", username="bi.thomas", role="RESPONSABLE_BI"),
]

PATIENTS = [
    ("Kylian", "Dubois", "M", "1998-12-20", "+257796200101", "Rohero, Bujumbura"),
    ("Jude", "Carter", "M", "2003-06-29", "+257796200102", "Gihosha, Bujumbura"),
    ("Erling", "Hansen", "M", "2000-07-21", "+257796200103", "Kinindo, Bujumbura"),
    ("Vinicius", "Rocha", "M", "2001-03-18", "+257796200104", "Kinanira, Bujumbura"),
    ("Lamine", "Ndiaye", "M", "2004-08-13", "+257796200105", "Ngagara, Bujumbura"),
    ("Pedri", "Morales", "M", "2002-11-25", "+257796200106", "Musaga, Bujumbura"),
    ("Bukayo", "Campbell", "M", "2001-09-05", "+257796200107", "Kamenge, Bujumbura"),
    ("Declan", "Walker", "M", "1997-01-14", "+257796200108", "Cibitoke, Bujumbura"),
    ("Rodri", "Navarro", "M", "1996-06-22", "+257796200109", "Mutanga Nord, Bujumbura"),
    ("Kevin", "Janssen", "M", "1992-04-11", "+257796200110", "Kiriri, Bujumbura"),
    ("Jamal", "Becker", "M", "2003-02-26", "+257796200111", "Nyakabiga, Bujumbura"),
    ("Florian", "Keller", "M", "1999-05-03", "+257796200112", "Bwiza, Bujumbura"),
    ("Antoine", "Moreau", "M", "1991-10-09", "+257796200113", "Jabe, Bujumbura"),
    ("Ousmane", "Diallo", "M", "1997-05-15", "+257796200114", "Kanyosha, Bujumbura"),
    ("Lautaro", "Romano", "M", "1998-08-22", "+257796200115", "Kajaga, Bujumbura"),
    ("Lucia", "Martin", "F", "1995-09-17", "+257796200116", "Kinindo, Bujumbura"),
    ("Alexia", "Moreno", "F", "1994-02-04", "+257796200117", "Rohero, Bujumbura"),
    ("Aitana", "Garcia", "F", "1996-01-18", "+257796200118", "Gihosha, Bujumbura"),
    ("Chloe", "Laurent", "F", "1998-07-02", "+257796200119", "Kinanira, Bujumbura"),
    ("Lena", "Hoffmann", "F", "2000-12-19", "+257796200120", "Mutanga Sud, Bujumbura"),
]

MEDICINES = [
    ("DEMO-PARA500", "Paracétamol", "Comprimé", "500 mg", "comprimé", 500, 100),
    ("DEMO-IBU400", "Ibuprofène", "Comprimé", "400 mg", "comprimé", 800, 80),
    ("DEMO-AMOX500", "Amoxicilline", "Gélule", "500 mg", "gélule", 1200, 80),
    ("DEMO-ORS", "Sels de réhydratation orale", "Sachet", "20.5 g", "sachet", 1500, 50),
    ("DEMO-OMEP20", "Oméprazole", "Gélule", "20 mg", "gélule", 1000, 60),
    ("DEMO-CET10", "Cétirizine", "Comprimé", "10 mg", "comprimé", 700, 50),
    ("DEMO-MET500", "Metformine", "Comprimé", "500 mg", "comprimé", 900, 100),
    ("DEMO-AZI500", "Azithromycine", "Comprimé", "500 mg", "comprimé", 2500, 40),
    ("DEMO-SALB", "Salbutamol", "Inhalateur", "100 mcg/dose", "inhalateur", 18000, 15),
    ("DEMO-CEF1G", "Ceftriaxone", "Flacon injectable", "1 g", "flacon", 5500, 30),
]

WARDS = [
    ("DEMO-MED", "Médecine générale", 35000),
    ("DEMO-SURG", "Chirurgie", 45000),
    ("DEMO-PED", "Pédiatrie", 30000),
]

CONSULT_SCENARIOS = [
    (0, "Fatigue et soif excessive", "Fatigue, soif, urines fréquentes", "Suspicion de trouble glycémique", "R73.9"),
    (1, "Fièvre et toux", "Fièvre, toux sèche, courbatures", "Infection respiratoire probable", "J06.9"),
    (2, "Douleur lombaire", "Douleur lombaire après effort", "Lombalgie mécanique", "M54.5"),
    (3, "Céphalées", "Maux de tête intermittents", "Céphalée sans signe d'alarme", "R51"),
    (4, "Douleur abdominale", "Douleur abdominale et nausée", "Gastro-entérite probable", "K52.9"),
    (5, "Contrôle tensionnel", "Vertiges légers", "Surveillance tensionnelle", "R03.0"),
    (15, "Suivi prénatal", "Grossesse, contrôle de routine", "Grossesse en suivi", "Z34.8"),
    (16, "Suivi grossesse à terme", "Contractions irrégulières", "Grossesse proche du terme", "Z34.9"),
    (6, "Douleur au genou", "Douleur après activité sportive", "Entorse légère probable", "S83.9"),
    (17, "Fatigue générale", "Fatigue sans fièvre", "Bilan clinique", "R53"),
]


def main():
    print("PROJECTX DEMO DATA SEED v1")
    print(f"Target gRPC host: {HOST}")
    print("No direct MySQL writes; all data is created through ProjectX gRPC APIs.\n")

    admin_username = input("Admin username [admin]: ").strip() or "admin"
    admin_password = getpass.getpass("Admin password: ")

    channels = {name: ch(port) for name, port in PORTS.items()}
    auth = auth_pb2_grpc.AuthServiceStub(channels["auth"])
    accueil = accueil_pb2_grpc.AccueilServiceStub(channels["accueil"])
    hr = hr_pb2_grpc.HRServiceStub(channels["hr"])
    consultation = consultation_pb2_grpc.ConsultationServiceStub(channels["consultation"])
    lab = laboratoire_pb2_grpc.LaboratoireServiceStub(channels["laboratoire"])
    pharmacy = pharmacie_pb2_grpc.PharmacieServiceStub(channels["pharmacie"])
    hosp = hospitalisation_pb2_grpc.HospitalisationServiceStub(channels["hospitalisation"])
    billing = billing_pb2_grpc.BillingServiceStub(channels["billing"])
    rdv = rendezvous_pb2_grpc.RendezvousServiceStub(channels["rendezvous"])
    maternity = maternite_pb2_grpc.MaterniteServiceStub(channels["maternite"])

    try:
        admin_login = auth.Login(auth_pb2.LoginRequest(identifier=admin_username, password=admin_password), timeout=TIMEOUT)
    except grpc.RpcError:
        admin_login = auth.Login(auth_pb2.LoginRequest(username=admin_username, password=admin_password), timeout=TIMEOUT)
    admin_token = admin_login.access_token
    AMD = md(admin_token)
    print(f"[OK] Admin login: {admin_login.user.display_name or admin_login.user.username}")

    # ------------------------------------------------------------------ staff
    staff_by_user: dict[str, dict[str, Any]] = {}
    for s in STAFF:
        employee = None
        try:
            existing = hr.ListEmployees(hr_pb2.ListEmployeesRequest(limit=100, offset=0, search=s["emp"]), metadata=AMD, timeout=TIMEOUT)
            for e in existing.employees:
                if e.employee_number == s["emp"]:
                    employee = e
                    break
        except grpc.RpcError as exc:
            rpc_error(f"Search employee {s['emp']}", exc)

        if employee is None:
            try:
                r = hr.RegisterEmployee(
                    hr_pb2.RegisterEmployeeRequest(
                        employee_number=s["emp"], first_name=s["first"], last_name=s["last"],
                        email=s["email"], phone=s["phone"], department=s["dept"], job_title=s["title"],
                        hire_date="2026-01-15", employment_type="PERMANENT",
                        username=s["username"], temporary_password=DEMO_PASSWORD,
                    ), metadata=AMD, timeout=TIMEOUT,
                )
                employee = r.employee
                print(f"[OK] Staff created: {s['username']} ({s['role']})")
            except grpc.RpcError as exc:
                rpc_error(f"Create staff {s['username']}", exc)
                continue
        else:
            print(f"[SKIP] Staff exists: {s['username']}")

        user_id = employee.auth_user_id
        if user_id:
            try:
                auth.ApproveUser(auth_pb2.ApproveUserRequest(user_id=user_id, role_codes=[s["role"]]), metadata=AMD, timeout=TIMEOUT)
                print(f"[OK] Approved: {s['username']} -> {s['role']}")
            except grpc.RpcError as exc:
                if not is_skip_error(exc):
                    rpc_error(f"Approve {s['username']}", exc)

        token = ""
        try:
            lr = auth.Login(auth_pb2.LoginRequest(identifier=s["username"], password=DEMO_PASSWORD), timeout=TIMEOUT)
            token = lr.access_token
            user_id = lr.user.id
        except grpc.RpcError as exc:
            rpc_error(f"Login demo staff {s['username']}", exc)
        staff_by_user[s["username"]] = {"employee": employee, "user_id": user_id, "token": token, **s}

    # ---------------------------------------------------------------- patients
    patients = []
    for first, last, sex, birth, phone, address in PATIENTS:
        patient = None
        try:
            sr = accueil.SearchPatients(accueil_pb2.SearchPatientsRequest(query=phone, limit=20, offset=0), metadata=AMD, timeout=TIMEOUT)
            patient = next((p for p in sr.patients if p.phone == phone), None)
        except grpc.RpcError as exc:
            rpc_error(f"Search patient {phone}", exc)
        if patient is None:
            try:
                patient = accueil.CreatePatient(
                    accueil_pb2.CreatePatientRequest(
                        first_name=first, last_name=last,
                        sex=accueil_pb2.SEX_MALE if sex == "M" else accueil_pb2.SEX_FEMALE,
                        birth_date=birth, phone=phone, address=address,
                    ), metadata=AMD, timeout=TIMEOUT,
                ).patient
                print(f"[OK] Patient: {patient.patient_number} {first} {last}")
            except grpc.RpcError as exc:
                rpc_error(f"Create patient {first} {last}", exc)
                continue
        else:
            print(f"[SKIP] Patient exists: {patient.patient_number} {first} {last}")
        patients.append(patient)

    # Add some waiting-queue data without duplicating current waiting entries.
    try:
        waiting = accueil.ListWaitingQueue(accueil_pb2.ListWaitingQueueRequest(target_service="Consultation", limit=100, offset=0), metadata=AMD, timeout=TIMEOUT)
        waiting_patient_ids = {x.patient.id for x in waiting.entries}
    except grpc.RpcError:
        waiting_patient_ids = set()
    for i, p in enumerate(patients[10:14]):
        if p.id in waiting_patient_ids:
            continue
        try:
            accueil.RegisterArrival(
                accueil_pb2.RegisterArrivalRequest(
                    patient_id=p.id,
                    reason=["Fièvre", "Contrôle clinique", "Douleur", "Suivi"][i],
                    target_service="Consultation",
                    priority=accueil_pb2.ARRIVAL_PRIORITY_URGENT if i == 0 else accueil_pb2.ARRIVAL_PRIORITY_ROUTINE,
                ), metadata=AMD, timeout=TIMEOUT,
            )
            print(f"[OK] Waiting queue: {p.patient_number}")
        except grpc.RpcError as exc:
            rpc_error(f"Arrival {p.patient_number}", exc)

    # -------------------------------------------------------------- pharmacy
    pharm_token = staff_by_user.get("pharmacy.andrea", {}).get("token") or admin_token
    PMD = md(pharm_token)
    medicine_by_code = {}
    for code, name, form, strength, unit, price, reorder in MEDICINES:
        med_obj = None
        try:
            sr = pharmacy.SearchMedicines(pharmacie_pb2.SearchMedicinesRequest(query=code, active_only=False, limit=50, offset=0), metadata=PMD, timeout=TIMEOUT)
            med_obj = next((m for m in sr.medicines if m.code == code), None)
        except grpc.RpcError as exc:
            rpc_error(f"Search medicine {code}", exc)
        if med_obj is None:
            try:
                med_obj = pharmacy.CreateMedicine(
                    pharmacie_pb2.CreateMedicineRequest(
                        code=code, name=name, form=form, strength=strength, unit=unit,
                        sale_price_minor=price, currency="BIF", reorder_level=reorder, active=True,
                    ), metadata=PMD, timeout=TIMEOUT,
                ).medicine
                print(f"[OK] Medicine: {code} {name}")
            except grpc.RpcError as exc:
                rpc_error(f"Create medicine {code}", exc)
                continue
        medicine_by_code[code] = med_obj

        batch = f"DEMO-{code}-AUG26"
        try:
            stock = pharmacy.GetStock(pharmacie_pb2.GetStockRequest(medicine_ref=code), metadata=PMD, timeout=TIMEOUT).stock
            if any(b.batch_number == batch for b in stock.batches):
                continue
            pharmacy.RegisterStockEntry(
                pharmacie_pb2.RegisterStockEntryRequest(
                    medicine_code=code, batch_number=batch, expiry_date="2027-12-31",
                    quantity=max(reorder * 4, 100), reference="DEMO-SEED-2026",
                ), metadata=PMD, timeout=TIMEOUT,
            )
            print(f"[OK] Stock: {code} batch {batch}")
        except grpc.RpcError as exc:
            rpc_error(f"Stock {code}", exc)

    suppliers = [
        ("DEMO-SUP-01", "Bujumbura Medical Supply", "+25722245001", "orders@bms.projectx.demo"),
        ("DEMO-SUP-02", "Great Lakes Pharma Distribution", "+25722245002", "sales@glpd.projectx.demo"),
        ("DEMO-SUP-03", "East Africa Health Logistics", "+25722245003", "supply@eahl.projectx.demo"),
    ]
    for code, name, phone, email in suppliers:
        try:
            existing = pharmacy.ListSuppliers(pharmacie_pb2.ListSuppliersRequest(query=code, active_only=False, limit=20, offset=0), metadata=PMD, timeout=TIMEOUT)
            if any(s.code == code for s in existing.suppliers):
                continue
            pharmacy.CreateSupplier(pharmacie_pb2.CreateSupplierRequest(code=code, name=name, phone=phone, email=email), metadata=PMD, timeout=TIMEOUT)
            print(f"[OK] Supplier: {code}")
        except grpc.RpcError as exc:
            rpc_error(f"Supplier {code}", exc)

    # ------------------------------------------------------ wards/rooms/beds
    hosp_token = staff_by_user.get("hosp.roberto", {}).get("token") or admin_token
    HMD = md(hosp_token)
    ward_map = {}
    bed_pool = []
    try:
        ward_list = hosp.ListWards(hospitalisation_pb2.ListWardsRequest(active_only=False), metadata=HMD, timeout=TIMEOUT)
    except grpc.RpcError:
        ward_list = None
    existing_wards = {w.code: w for w in (ward_list.wards if ward_list else [])}
    for code, name, rate in WARDS:
        ward = existing_wards.get(code)
        if ward is None:
            try:
                ward = hosp.CreateWard(hospitalisation_pb2.CreateWardRequest(code=code, name=name, daily_rate_minor=rate, currency="BIF"), metadata=HMD, timeout=TIMEOUT).ward
                print(f"[OK] Ward: {code}")
            except grpc.RpcError as exc:
                rpc_error(f"Ward {code}", exc)
                continue
        ward_map[code] = ward
        try:
            rooms_resp = hosp.ListRooms(hospitalisation_pb2.ListRoomsRequest(ward_id=ward.id), metadata=HMD, timeout=TIMEOUT)
            rooms = {r.code: r for r in rooms_resp.rooms}
        except grpc.RpcError:
            rooms = {}
        for rn in (1, 2):
            room_code = f"{code}-R{rn:02d}"
            room = rooms.get(room_code)
            if room is None:
                try:
                    room = hosp.CreateRoom(hospitalisation_pb2.CreateRoomRequest(ward_id=ward.id, code=room_code, name=f"Chambre {rn:02d}"), metadata=HMD, timeout=TIMEOUT).room
                    print(f"[OK] Room: {room_code}")
                except grpc.RpcError as exc:
                    rpc_error(f"Room {room_code}", exc)
                    continue
            try:
                avail = hosp.GetBedAvailability(hospitalisation_pb2.GetBedAvailabilityRequest(ward_code=code, available_only=False), metadata=HMD, timeout=TIMEOUT)
                existing_beds = {b.code: b for b in avail.beds}
            except grpc.RpcError:
                existing_beds = {}
            for bn in (1, 2, 3):
                bed_code = f"{room_code}-B{bn}"
                bed = existing_beds.get(bed_code)
                if bed is None:
                    try:
                        bed = hosp.CreateBed(hospitalisation_pb2.CreateBedRequest(room_id=room.id, code=bed_code), metadata=HMD, timeout=TIMEOUT).bed
                        print(f"[OK] Bed: {bed_code}")
                    except grpc.RpcError as exc:
                        rpc_error(f"Bed {bed_code}", exc)
                        continue
                if bed.status == hospitalisation_pb2.BED_STATUS_AVAILABLE:
                    bed_pool.append(bed)

    # --------------------------------------------------------------- HR data
    hr_token = staff_by_user.get("hr.isabelle", {}).get("token") or admin_token
    HRMD = md(hr_token)
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    for idx, s in enumerate(STAFF[:10]):
        entry = staff_by_user.get(s["username"])
        if not entry or not entry.get("employee"):
            continue
        emp_id = entry["employee"].id
        for d, label in ((yesterday, "Y"), (tomorrow, "T")):
            try:
                hr.CreateShift(
                    hr_pb2.CreateShiftRequest(
                        employee_id=emp_id, shift_date=d.isoformat(), start_time="08:00", end_time="16:00",
                        location=s["dept"], idempotency_key=f"DEMO-SHIFT-{s['emp']}-{d.isoformat()}",
                    ), metadata=HRMD, timeout=TIMEOUT,
                )
            except grpc.RpcError as exc:
                if not is_skip_error(exc):
                    rpc_error(f"Shift {s['username']} {d}", exc)
        if idx < 8:
            ci = datetime(yesterday.year, yesterday.month, yesterday.day, 8, 5 + idx, tzinfo=timezone.utc)
            co = datetime(yesterday.year, yesterday.month, yesterday.day, 16, 0, tzinfo=timezone.utc)
            try:
                hr.RecordAttendanceByHR(
                    hr_pb2.RecordAttendanceByHRRequest(
                        employee_id=emp_id, work_date=yesterday.isoformat(), clock_in_at=ts(ci), clock_out_at=ts(co),
                        status=hr_pb2.ATTENDANCE_STATUS_LATE if idx in (2, 5) else hr_pb2.ATTENDANCE_STATUS_PRESENT,
                        reason="Données de démonstration ProjectX",
                    ), metadata=HRMD, timeout=TIMEOUT,
                )
            except grpc.RpcError as exc:
                if not is_skip_error(exc):
                    rpc_error(f"Attendance {s['username']}", exc)
    print("[OK] HR shifts/attendance seeded")

    # -------------------------------------------------------- consultations
    doctor_entries = [staff_by_user.get("doctor.carlo"), staff_by_user.get("doctor.mikel")]
    doctor_entries = [d for d in doctor_entries if d and d.get("token")]
    lab_token = staff_by_user.get("lab.luka", {}).get("token") or admin_token
    LMD = md(lab_token)
    try:
        lab_tests = list(lab.ListLabTests(laboratoire_pb2.ListLabTestsRequest(query="", active_only=True, limit=20, offset=0), metadata=LMD, timeout=TIMEOUT).tests)
    except grpc.RpcError as exc:
        rpc_error("List lab tests", exc)
        lab_tests = []

    consult_by_patient = {}
    prescription_ids = []
    if doctor_entries:
        for n, (patient_index, reason, symptoms, diagnosis, diag_code) in enumerate(CONSULT_SCENARIOS):
            if patient_index >= len(patients):
                continue
            p = patients[patient_index]
            doc = doctor_entries[n % len(doctor_entries)]
            DMD = md(doc["token"])
            existing_consult = None
            try:
                lr = consultation.ListPatientConsultations(consultation_pb2.ListPatientConsultationsRequest(patient_id=p.id, limit=50, offset=0), metadata=DMD, timeout=TIMEOUT)
                existing_consult = next((c for c in lr.consultations if c.reason.startswith("DEMO - ")), None)
            except grpc.RpcError:
                pass
            created_now = existing_consult is None
            if created_now:
                try:
                    c = consultation.CreateConsultation(
                        consultation_pb2.CreateConsultationRequest(patient_id=p.id, reason=f"DEMO - {reason}", symptoms=symptoms),
                        metadata=DMD, timeout=TIMEOUT,
                    ).consultation
                    consultation.UpdateClinicalNotes(
                        consultation_pb2.UpdateClinicalNotesRequest(
                            consultation_id=c.id,
                            observations="Examen clinique stable. Données synthétiques de démonstration.",
                            notes="Dossier de démonstration pour validation du client ProjectX.",
                            vitals=consultation_pb2.Vitals(
                                temperature_c=36.7 + (n % 3) * 0.4,
                                systolic_bp=118 + n,
                                diastolic_bp=76 + (n % 4),
                                pulse_bpm=70 + n,
                                respiratory_rate=16 + (n % 2),
                                spo2_percent=97 + (n % 3),
                                weight_kg=64.0 + n * 2,
                                height_cm=170.0 + (n % 5),
                            ),
                            diagnoses=[consultation_pb2.DiagnosisInput(text=diagnosis, code=diag_code, is_primary=True)],
                            replace_diagnoses=True,
                        ), metadata=DMD, timeout=TIMEOUT,
                    )
                    print(f"[OK] Consultation: {p.patient_number} / {doc['username']}")
                except grpc.RpcError as exc:
                    rpc_error(f"Consultation {p.patient_number}", exc)
                    continue
            else:
                c = existing_consult
            consult_by_patient[p.id] = (c, doc)

            if not created_now:
                continue

            # prescriptions for selected scenarios
            if n in (0, 1, 2, 4, 5, 8):
                code = ["DEMO-MET500", "DEMO-PARA500", "DEMO-IBU400", "DEMO-ORS", "DEMO-OMEP20", "DEMO-PARA500"][ (0,1,2,4,5,8).index(n) ]
                items = [
                    consultation_pb2.PrescriptionItemInput(
                        medicine_ref=code, medicine_source=consultation_pb2.PRESCRIPTION_MEDICINE_SOURCE_HOSPITAL_CATALOG,
                        dose="1 unité", frequency="2 fois par jour", duration="5 jours", instructions="Après le repas",
                    )
                ]
                if n in (1, 8):
                    items.append(consultation_pb2.PrescriptionItemInput(
                        medicine_source=consultation_pb2.PRESCRIPTION_MEDICINE_SOURCE_EXTERNAL,
                        medicine_name="SportFlex Gel", medicine_form="Gel topique", medicine_strength="2%",
                        dose="Application locale", frequency="2 fois par jour", duration="7 jours",
                        instructions="Médicament externe: à obtenir hors pharmacie hospitalière",
                    ))
                try:
                    pr = consultation.IssuePrescription(consultation_pb2.IssuePrescriptionRequest(consultation_id=c.id, items=items), metadata=DMD, timeout=TIMEOUT).prescription
                    prescription_ids.append((pr.id, code))
                    print(f"[OK] Prescription: {pr.prescription_number}")
                except grpc.RpcError as exc:
                    rpc_error(f"Prescription {p.patient_number}", exc)

            # lab workflow for selected scenarios
            if lab_tests and n in (0, 1, 4, 9):
                test = next((x for x in lab_tests if x.code == ("GLU" if n == 0 else "CBC")), lab_tests[n % len(lab_tests)])
                try:
                    consultation.RequestLabTest(
                        consultation_pb2.RequestLabTestRequest(
                            consultation_id=c.id, test_code=test.code, test_name=test.name,
                            clinical_information=f"{reason}: {symptoms}",
                        ), metadata=DMD, timeout=TIMEOUT,
                    )
                    pending = lab.ListPendingOrders(laboratoire_pb2.ListPendingOrdersRequest(limit=100, offset=0), metadata=LMD, timeout=TIMEOUT)
                    order = next((o for o in reversed(list(pending.orders)) if o.consultation_id == c.id and o.status == laboratoire_pb2.LAB_ORDER_STATUS_ORDERED), None)
                    if order:
                        lab.CollectSample(laboratoire_pb2.CollectSampleRequest(order_id=order.id, notes="Prélèvement de démonstration"), metadata=LMD, timeout=TIMEOUT)
                        if test.code == "GLU":
                            vals = [laboratoire_pb2.ResultValue(name="Glucose", value="104", unit="mg/dL", reference_range="70-99", flag="HIGH")]
                            text = "Glycémie légèrement au-dessus de la plage de référence de démonstration."
                        elif test.code == "CBC":
                            vals = [
                                laboratoire_pb2.ResultValue(name="Hemoglobin", value="14.2", unit="g/dL", reference_range="12.0-17.0", flag="NORMAL"),
                                laboratoire_pb2.ResultValue(name="WBC", value="7.4", unit="10^9/L", reference_range="4.0-11.0", flag="NORMAL"),
                            ]
                            text = "Numération dans les limites de référence de démonstration."
                        else:
                            vals = [laboratoire_pb2.ResultValue(name=test.name, value="Normal", unit="", reference_range="", flag="NORMAL")]
                            text = "Résultat de démonstration sans anomalie significative."
                        lab.RecordResult(laboratoire_pb2.RecordResultRequest(order_id=order.id, values=vals, text_result=text), metadata=LMD, timeout=TIMEOUT)
                        lab.ValidateResult(laboratoire_pb2.ValidateResultRequest(order_id=order.id), metadata=LMD, timeout=TIMEOUT)
                        print(f"[OK] Lab validated: {test.code} for {p.patient_number}")
                except grpc.RpcError as exc:
                    rpc_error(f"Lab workflow {p.patient_number}", exc)

            # close some, keep some open for client UI
            if n in (2, 3, 5, 9):
                try:
                    consultation.CloseConsultation(consultation_pb2.CloseConsultationRequest(consultation_id=c.id, closing_notes="Consultation terminée - données de démonstration."), metadata=DMD, timeout=TIMEOUT)
                except grpc.RpcError as exc:
                    rpc_error(f"Close consultation {p.patient_number}", exc)

    # --------------------------------------------------- pharmacy dispensing
    for k, (prescription_id, med_code) in enumerate(prescription_ids[:4]):
        try:
            pharmacy.DispensePrescription(
                pharmacie_pb2.DispensePrescriptionRequest(
                    prescription_id=prescription_id,
                    items=[pharmacie_pb2.DispenseItemInput(medicine_ref=med_code, quantity=2)],
                    idempotency_key=f"DEMO-DISP-{prescription_id}",
                ), metadata=PMD, timeout=TIMEOUT,
            )
            print(f"[OK] Dispensed hospital item for prescription {prescription_id[:8]}")
        except grpc.RpcError as exc:
            if not is_skip_error(exc):
                rpc_error(f"Dispense {prescription_id}", exc)

    # ----------------------------------------------------------- admissions
    available_beds = []
    try:
        av = hosp.GetBedAvailability(hospitalisation_pb2.GetBedAvailabilityRequest(ward_code="DEMO-MED", available_only=True), metadata=HMD, timeout=TIMEOUT)
        available_beds = list(av.beds)
    except grpc.RpcError as exc:
        rpc_error("Load demo beds", exc)
    admission_patient_indexes = (1, 4, 6)
    for ix, pidx in enumerate(admission_patient_indexes):
        if pidx >= len(patients):
            continue
        p = patients[pidx]
        pair = consult_by_patient.get(p.id)
        if not pair:
            continue
        c, doc = pair
        try:
            existing = hosp.ListAdmissions(hospitalisation_pb2.ListAdmissionsRequest(patient_id=p.id, limit=20, offset=0), metadata=HMD, timeout=TIMEOUT)
            adm = next((a for a in existing.admissions if a.consultation_id == c.id), None)
        except grpc.RpcError:
            adm = None
        if adm is None:
            try:
                consultation.RequestHospitalization(
                    consultation_pb2.RequestHospitalizationRequest(
                        consultation_id=c.id, reason="Observation clinique de démonstration", preferred_ward="DEMO-MED",
                        target=consultation_pb2.HOSPITALIZATION_TARGET_HOSPITALISATION,
                    ), metadata=md(doc["token"]), timeout=TIMEOUT,
                )
                existing = hosp.ListAdmissions(hospitalisation_pb2.ListAdmissionsRequest(patient_id=p.id, limit=20, offset=0), metadata=HMD, timeout=TIMEOUT)
                adm = next((a for a in reversed(list(existing.admissions)) if a.consultation_id == c.id), None)
            except grpc.RpcError as exc:
                rpc_error(f"Hospitalization request {p.patient_number}", exc)
                continue
        if not adm:
            continue
        try:
            if adm.status == hospitalisation_pb2.ADMISSION_STATUS_PENDING:
                adm = hosp.ApproveAdmission(hospitalisation_pb2.ApproveAdmissionRequest(admission_id=adm.id, reason="Admission validée pour démonstration"), metadata=HMD, timeout=TIMEOUT).admission
            if not adm.current_bed.id and available_beds:
                bed = available_beds.pop(0)
                adm = hosp.AssignBed(hospitalisation_pb2.AssignBedRequest(admission_id=adm.id, bed_id=bed.id, idempotency_key=f"DEMO-BED-{adm.id}"), metadata=HMD, timeout=TIMEOUT).admission
            if doc.get("user_id"):
                try:
                    hosp.AssignDoctor(hospitalisation_pb2.AssignDoctorRequest(admission_id=adm.id, doctor_user_id=doc["user_id"], idempotency_key=f"DEMO-DOC-{adm.id}"), metadata=HMD, timeout=TIMEOUT)
                except grpc.RpcError as exc:
                    if not is_skip_error(exc):
                        rpc_error(f"Assign doctor {adm.admission_number}", exc)
            if ix == 0 and adm.status == hospitalisation_pb2.ADMISSION_STATUS_ADMITTED:
                hosp.DischargePatient(hospitalisation_pb2.DischargePatientRequest(admission_id=adm.id, discharge_summary="État stable. Sortie de démonstration.", idempotency_key=f"DEMO-DISCH-{adm.id}"), metadata=HMD, timeout=TIMEOUT)
            print(f"[OK] Admission seeded: {adm.admission_number}")
        except grpc.RpcError as exc:
            rpc_error(f"Admission workflow {p.patient_number}", exc)

    # --------------------------------------------------------- appointments
    now = datetime.now(timezone.utc)
    providers = [d for d in doctor_entries if d.get("user_id")]
    if providers:
        for i, p in enumerate(patients[:8]):
            provider = providers[i % len(providers)]
            day = (now + timedelta(days=1 + i // 2)).date()
            hour = 9 + (i % 2) * 2
            start = datetime(day.year, day.month, day.day, hour, 0, tzinfo=timezone.utc)
            end = start + timedelta(minutes=45)
            try:
                slot = rdv.CreateScheduleSlot(
                    rendezvous_pb2.CreateScheduleSlotRequest(
                        provider_id=provider["user_id"], service="Consultation générale",
                        start_at=ts(start), end_at=ts(end), idempotency_key=f"DEMO-SLOT-{provider['user_id']}-{start.date()}-{hour}",
                    ), metadata=AMD, timeout=TIMEOUT,
                ).slot
                appt = rdv.CreateAppointment(
                    rendezvous_pb2.CreateAppointmentRequest(
                        patient_id=p.id, slot_id=slot.id, reason="Rendez-vous de suivi - démonstration",
                        idempotency_key=f"DEMO-RDV-{p.id}-{start.date()}-{hour}",
                        correlation_id=f"demo-{uuid.uuid4()}", request_reminder=False,
                    ), metadata=AMD, timeout=TIMEOUT,
                ).appointment
                if i < 5 and appt.status == rendezvous_pb2.APPOINTMENT_STATUS_BOOKED:
                    rdv.ConfirmAppointment(rendezvous_pb2.ConfirmAppointmentRequest(appointment_id=appt.id), metadata=AMD, timeout=TIMEOUT)
                print(f"[OK] Appointment: {appt.appointment_number}")
            except grpc.RpcError as exc:
                if not is_skip_error(exc):
                    rpc_error(f"Appointment {p.patient_number}", exc)

    # ------------------------------------------------------------- maternity
    mat_token = staff_by_user.get("maternity.lucia", {}).get("token") or admin_token
    MMD = md(mat_token)
    for j, pidx in enumerate((15, 16)):
        if pidx >= len(patients):
            continue
        p = patients[pidx]
        pair = consult_by_patient.get(p.id)
        if not pair:
            continue
        c, _doc = pair
        try:
            rec = maternity.CreateMaternityCase(
                maternite_pb2.CreateMaternityCaseRequest(
                    patient_id=p.id, consultation_id=c.id,
                    gravida=2 if j == 0 else 1, para=1 if j == 0 else 0,
                    lmp_date="2026-02-15" if j == 0 else "2025-12-10",
                    edd="2026-11-22" if j == 0 else "2026-09-16",
                    risk_level=maternite_pb2.RISK_LEVEL_LOW if j == 0 else maternite_pb2.RISK_LEVEL_MODERATE,
                    risk_factors="Aucun facteur majeur" if j == 0 else "Surveillance rapprochée de démonstration",
                    referral_reason="Suivi obstétrical de démonstration",
                    idempotency_key=f"DEMO-MAT-{p.id}", correlation_id=f"demo-mat-{p.id}",
                ), metadata=MMD, timeout=TIMEOUT,
            ).record
            preg_id = rec.pregnancy.id
            maternity.AddPrenatalVisit(
                maternite_pb2.AddPrenatalVisitRequest(
                    pregnancy_id=preg_id, visit_at=ts(now - timedelta(days=7)), gestational_age_weeks=28 if j == 0 else 36,
                    observations="Suivi prénatal satisfaisant - données synthétiques.", systolic_bp=118, diastolic_bp=74,
                    weight_kg=68.5 if j == 0 else 72.0, fetal_heart_bpm=142,
                    idempotency_key=f"DEMO-PRENATAL-{preg_id}",
                ), metadata=MMD, timeout=TIMEOUT,
            )
            if j == 1 and rec.pregnancy.status not in (maternite_pb2.PREGNANCY_STATUS_DELIVERED, maternite_pb2.PREGNANCY_STATUS_CLOSED):
                maternity.AdmitForLabor(maternite_pb2.AdmitForLaborRequest(pregnancy_id=preg_id, admitted_at=ts(now - timedelta(hours=8)), reason="Travail spontané - démonstration", idempotency_key=f"DEMO-LABOR-{preg_id}"), metadata=MMD, timeout=TIMEOUT)
                delivery = maternity.RecordDelivery(
                    maternite_pb2.RecordDeliveryRequest(
                        pregnancy_id=preg_id, delivered_at=ts(now - timedelta(hours=3)), mode=maternite_pb2.DELIVERY_MODE_VAGINAL,
                        outcome=maternite_pb2.DELIVERY_OUTCOME_LIVE_BIRTH, complications="Aucune complication",
                        idempotency_key=f"DEMO-DELIVERY-{preg_id}",
                    ), metadata=MMD, timeout=TIMEOUT,
                ).delivery
                maternity.RegisterNewborn(
                    maternite_pb2.RegisterNewbornRequest(
                        delivery_id=delivery.id, sex=maternite_pb2.NEWBORN_SEX_FEMALE, weight_g=3250, apgar_1=8, apgar_5=9,
                        status=maternite_pb2.NEWBORN_STATUS_STABLE, idempotency_key=f"DEMO-NEWBORN-{delivery.id}",
                    ), metadata=MMD, timeout=TIMEOUT,
                )
                maternity.CloseMaternityCase(maternite_pb2.CloseMaternityCaseRequest(pregnancy_id=preg_id, reason="Mère et nouveau-né stables - démonstration"), metadata=MMD, timeout=TIMEOUT)
            print(f"[OK] Maternity case: {p.patient_number}")
        except grpc.RpcError as exc:
            if not is_skip_error(exc):
                rpc_error(f"Maternity {p.patient_number}", exc)

    # --------------------------------------------------------------- billing
    cashier_token = staff_by_user.get("cashier.sofia", {}).get("token") or admin_token
    BMD = md(cashier_token)
    for i, p in enumerate(patients[:10]):
        try:
            charge = billing.CreateCharge(
                billing_pb2.CreateChargeRequest(
                    source_type="DEMO_SERVICE", source_id=f"DEMO-SVC-{i+1:03d}", patient_id=p.id,
                    amount_minor=15000 + i * 5000, currency_code="BIF",
                    description=["Consultation générale", "Examens de laboratoire", "Soins ambulatoires", "Frais de dossier"][i % 4],
                    idempotency_key=f"DEMO-CHARGE-{p.id}-{i}", correlation_id=f"demo-bill-{p.id}",
                ), metadata=BMD, timeout=TIMEOUT,
            )
            inv = charge.invoice
            if i < 6 and inv.balance.amount_minor > 0:
                pay_amount = inv.balance.amount_minor if i < 3 else max(1000, inv.balance.amount_minor // 2)
                billing.RecordPayment(
                    billing_pb2.RecordPaymentRequest(
                        invoice_id=inv.id, amount_minor=pay_amount, currency_code="BIF",
                        method=billing_pb2.PAYMENT_METHOD_MOBILE_MONEY if i % 2 else billing_pb2.PAYMENT_METHOD_CASH,
                        reference=f"DEMO-PAY-{i+1:03d}", idempotency_key=f"DEMO-PAY-{p.id}-{i}",
                    ), metadata=BMD, timeout=TIMEOUT,
                )
            print(f"[OK] Billing: {p.patient_number}")
        except grpc.RpcError as exc:
            if not is_skip_error(exc):
                rpc_error(f"Billing {p.patient_number}", exc)

    print("\n" + "=" * 72)
    print("PROJECTX DEMO SEED COMPLETE")
    print("=" * 72)
    print(f"Synthetic patients available: {len(patients)}")
    print(f"Demo staff configured: {len(staff_by_user)}")
    print(f"Demo medicine codes: {len(medicine_by_code)}")
    print("\nDemo login accounts (local/demo use only):")
    for s in STAFF:
        print(f"  {s['role']:<26} {s['username']}")
    print(f"  Shared demo password: {DEMO_PASSWORD}")
    print("\nIMPORTANT: these are synthetic demo credentials/data. Do not reuse the password for real accounts.")
    print("The seeder never prints QR credentials or JWT values.")

    for channel in channels.values():
        channel.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
