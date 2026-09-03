from services.chatbot.assistant_engine import (
    detect_language,
    extract_patient_number,
    greeting,
    identify_live_intent,
    is_greeting,
    likely_sensitive_public_question,
    match_procedure,
    render_procedure,
)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"[OK] {message}")


check(detect_language("Hello, how do I register a patient?") == "en", "English detection")
check(detect_language("Bonjour, comment enregistrer un patient ?") == "fr", "French detection")
check(is_greeting("hello"), "English greeting recognized")
check(is_greeting("Bonjour !"), "French greeting recognized")
check("Alice" in greeting("en", "Alice"), "Authenticated greeting contains first name")

proc = match_procedure("How do I register a patient?")
check(proc is not None and proc.key == "register_patient", "Patient-registration procedure detected")
text, note = render_procedure(proc, "en", {"accueil.patient.create"})
check("patient_number" in text and "has the required" in note, "Authorized patient-registration guidance")

text, note = render_procedure(proc, "fr", {"consultation.read"})
check("ne possède pas" in note, "Unauthorized procedure is explained without granting permission")

live = identify_live_intent("Show me the available beds")
check(live is not None and live[0] == "beds", "Bed live-data intent detected")
check(extract_patient_number("What is the balance for PAT-ABC-123?") == "PAT-ABC-123", "Patient number extraction")

# Regression: public patient-data queries must never be misclassified as an unrelated procedure.
check(match_procedure("Show patient PAT-PRIVATE-001") is None, "Sensitive patient lookup is not misclassified as a procedure")
check(likely_sensitive_public_question("Show patient PAT-PRIVATE-001"), "Sensitive public patient lookup is detected")
cancel_proc = match_procedure("How do I cancel an appointment?")
check(cancel_proc is not None and cancel_proc.key == "cancel_appointment", "Single-alias procedure matching remains correct")

# Regression: natural French HR wording must route correctly.
fr_attendance_proc = match_procedure("Comment les RH corrigent une présence ?")
check(fr_attendance_proc is not None and fr_attendance_proc.key == "correct_attendance", "Natural French attendance-correction how-to detected")
fr_hr_live = identify_live_intent("Qui est absent aujourd'hui ?")
check(fr_hr_live is not None and fr_hr_live[0] == "hr_dashboard", "French HR attendance live-data intent detected")
fr_hr_late = identify_live_intent("Qui est en retard aujourd’hui ?")
check(fr_hr_late is not None and fr_hr_late[0] == "hr_dashboard", "French curly-apostrophe HR wording detected")

print("\nPROJECTX CHATBOT V2 ENGINE TEST: PASS")
