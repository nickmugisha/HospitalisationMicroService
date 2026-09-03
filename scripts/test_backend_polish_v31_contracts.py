from auth.v1 import auth_pb2
from consultation.v1 import consultation_pb2
from pharmacie.v1 import pharmacie_pb2


def check_field(message, name, number):
    field = message.DESCRIPTOR.fields_by_name.get(name)
    assert field is not None, f"missing field {message.DESCRIPTOR.full_name}.{name}"
    assert field.number == number, f"field number changed: {message.DESCRIPTOR.full_name}.{name}={field.number}, expected {number}"


def main():
    # Auth is additive: legacy username/password field numbers stay frozen.
    check_field(auth_pb2.LoginRequest, "username", 1)
    check_field(auth_pb2.LoginRequest, "password", 2)
    check_field(auth_pb2.LoginRequest, "identifier", 3)
    auth_methods = {m.name for m in auth_pb2.DESCRIPTOR.services_by_name["AuthService"].methods}
    assert {"Login", "ChangeMyPassword", "UpdateMyProfile"}.issubset(auth_methods)

    # Consultation legacy prescription fields remain unchanged; source metadata is additive.
    for name, number in {"medicine_ref": 1, "dose": 2, "frequency": 3, "duration": 4, "instructions": 5}.items():
        check_field(consultation_pb2.PrescriptionItemInput, name, number)
    check_field(consultation_pb2.PrescriptionItemInput, "medicine_source", 6)
    check_field(consultation_pb2.PrescriptionItemInput, "medicine_name", 7)
    assert consultation_pb2.PRESCRIPTION_MEDICINE_SOURCE_HOSPITAL_CATALOG != consultation_pb2.PRESCRIPTION_MEDICINE_SOURCE_EXTERNAL

    # Pharmacy inbox carries the same normalized distinction.
    for name, number in {"medicine_ref": 1, "dose": 2, "frequency": 3, "duration": 4, "instructions": 5}.items():
        check_field(pharmacie_pb2.PrescriptionLine, name, number)
    check_field(pharmacie_pb2.PrescriptionLine, "medicine_source", 6)
    check_field(pharmacie_pb2.PrescriptionLine, "medicine_name", 7)

    print("PROJECTX BACKEND POLISH V3.1 CONTRACTS: PASS")


if __name__ == "__main__":
    main()
