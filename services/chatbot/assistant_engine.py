from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

SUPPORTED_LANGUAGES = {"en", "fr"}


def _norm(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_module(value: str) -> str:
    q = _norm(value)
    aliases = {
        "home": "general", "dashboard": "general", "administration": "auth", "admin": "auth",
        "accueil": "accueil", "reception": "accueil", "receptionist": "accueil",
        "consultation": "consultation", "doctor": "consultation", "medecin": "consultation",
        "laboratoire": "laboratoire", "laboratory": "laboratoire", "lab": "laboratoire",
        "pharmacie": "pharmacie", "pharmacy": "pharmacie", "stock": "pharmacie",
        "hospitalisation": "hospitalisation", "hospitalization": "hospitalisation", "admission": "hospitalisation",
        "billing": "billing", "paiement": "billing", "payment": "billing", "facturation": "billing",
        "maternite": "maternite", "maternity": "maternite",
        "rendez-vous": "rendezvous", "rendezvous": "rendezvous", "appointment": "rendezvous", "agenda": "rendezvous",
        "bi": "bi", "statistiques": "bi", "statistics": "bi",
        "chatbot": "chatbot", "assistant": "chatbot",
        "hr": "hr", "ressources humaines": "hr", "human resources": "hr", "attendance": "hr", "presence": "hr",
        "login": "login", "connexion": "login",
    }
    if q in aliases:
        return aliases[q]
    for key, module in aliases.items():
        if key in q:
            return module
    return "general"


def detect_language(question: str = "", locale: str = "") -> str:
    q = _norm(question)
    if q:
        fr_tokens = {
            "bonjour", "salut", "merci", "comment", "pourquoi", "quel", "quelle", "quels", "quelles",
            "je", "peux", "dois", "faire", "connexion", "connecter", "patient", "paiement", "facture",
            "lit", "lits", "rendez-vous", "conge", "presence", "retard", "employe", "medicament",
            "laboratoire", "maternite", "hospitalisation", "aujourd'hui", "aujourdhui", "affiche", "trouve",
        }
        en_tokens = {
            "hello", "hi", "thanks", "thank", "how", "why", "what", "which", "where", "can", "do", "i",
            "login", "sign", "patient", "payment", "invoice", "bed", "beds", "appointment", "leave", "attendance",
            "employee", "medicine", "laboratory", "maternity", "hospitalization", "today", "show", "find",
        }
        words = set(re.findall(r"[a-z0-9'-]+", q))
        fr_score = len(words & fr_tokens)
        en_score = len(words & en_tokens)
        if any(ch in question.lower() for ch in "éèêàùçôîïûœ"):
            fr_score += 2
        if q.startswith(("bonjour", "salut", "merci", "comment", "je ")):
            fr_score += 2
        if q.startswith(("hello", "hi", "thanks", "thank", "how", "what", "where", "can i")):
            en_score += 2
        if fr_score > en_score:
            return "fr"
        if en_score > fr_score:
            return "en"
    loc = _norm(locale)
    if loc.startswith("fr"):
        return "fr"
    return "en"


def friendly_name(user) -> str:
    profile = getattr(user, "staff_profile", None)
    first = getattr(profile, "first_name", "") if profile is not None else ""
    if first and first.strip():
        return first.strip()
    display = getattr(user, "display_name", "")
    if display and display.strip():
        return display.strip().split()[0]
    username = getattr(user, "username", "")
    return username.strip() if username else ""


def is_greeting(question: str) -> bool:
    q = _norm(question)
    return q in {
        "hello", "hi", "hey", "hello there", "good morning", "good afternoon", "good evening",
        "bonjour", "salut", "coucou", "bonsoir", "bonjour projectx", "hello projectx",
    } or bool(re.fullmatch(r"(hello|hi|hey|bonjour|salut|bonsoir)[!?. ]*", q))


def is_thanks(question: str) -> bool:
    q = _norm(question)
    return any(x in q for x in ["thank you", "thanks", "thank u", "merci", "merci beaucoup"])


def is_goodbye(question: str) -> bool:
    q = _norm(question)
    return any(x == q or q.startswith(x + " ") for x in ["bye", "goodbye", "see you", "au revoir", "a bientot"])


def is_identity_question(question: str) -> bool:
    q = _norm(question)
    phrases = [
        "who am i", "what is my name", "what's my name", "what is my role", "what are my roles",
        "qui suis je", "qui suis-je", "quel est mon nom", "quel est mon role", "quels sont mes roles",
    ]
    return any(_norm(p) in q for p in phrases)


def is_context_help(question: str) -> bool:
    q = _norm(question)
    phrases = [
        "what can i do here", "what can i do on this page", "help me on this page", "what is this page",
        "que puis je faire ici", "que puis-je faire ici", "que faire ici", "aide moi sur cette page",
        "a quoi sert cette page", "à quoi sert cette page",
    ]
    return any(_norm(p) in q for p in phrases)


def looks_like_howto(question: str) -> bool:
    q = _norm(question)
    starts = (
        "how do i", "how can i", "how to", "what are the steps", "where do i", "show me how",
        "comment", "comment puis je", "comment puis-je", "quelles sont les etapes", "quelle est la procedure",
        "ou puis je", "où puis-je", "aide moi a", "aide-moi a", "je veux savoir comment",
    )
    if q.startswith(starts):
        return True
    return any(x in q for x in ["steps to", "procedure for", "procedure pour", "etapes pour", "étapes pour"])


@dataclass(frozen=True)
class Procedure:
    key: str
    module: str
    permission: str
    roles: tuple[str, ...]
    aliases_en: tuple[str, ...]
    aliases_fr: tuple[str, ...]
    title_en: str
    title_fr: str
    steps_en: tuple[str, ...]
    steps_fr: tuple[str, ...]
    public_en: str
    public_fr: str


# Canonical roles/permissions come from services/auth/rbac.py in ProjectX HR v2.2.
PROCEDURES: tuple[Procedure, ...] = (
    Procedure("login", "login", "", tuple(), ("login", "sign in", "credentials"), ("connexion", "se connecter", "identifiants"),
              "Sign in to ProjectX", "Se connecter à ProjectX",
              ("Open the ProjectX login screen.", "Enter your username and password.", "Submit the form; Auth validates the account and issues the JWT used by the rest of ProjectX."),
              ("Ouvrez l'écran de connexion ProjectX.", "Saisissez votre nom d'utilisateur et votre mot de passe.", "Validez; Auth vérifie le compte et émet le JWT utilisé par le reste de ProjectX."),
              "ProjectX supports username/password login for an approved active staff account.",
              "ProjectX permet la connexion par identifiant/mot de passe pour un compte du personnel approuvé et actif."),
    Procedure("qr_login", "login", "", tuple(), ("qr login", "scan qr", "qr code"), ("connexion qr", "scanner qr", "code qr"),
              "Sign in with QR", "Se connecter avec QR",
              ("Choose the QR login option.", "Scan the personal QR issued after account approval.", "Auth validates the QR and issues the same type of JWT as password login."),
              ("Choisissez l'option de connexion QR.", "Scannez le QR personnel délivré après l'approbation du compte.", "Auth valide le QR et émet le même type de JWT que la connexion par mot de passe."),
              "QR login is available only after HR onboarding and administrator approval. A revoked, expired, pending or disabled account cannot use it.",
              "La connexion QR n'est disponible qu'après l'enregistrement RH et l'approbation de l'administrateur. Un QR révoqué/expiré ou un compte en attente/désactivé est refusé."),
    Procedure("register_employee", "hr", "hr.employee.create", ("RESPONSABLE_RH",), ("register employee", "add employee", "create employee"), ("enregistrer employe", "ajouter employe", "creer employe", "enregistrer un employe"),
              "Register a hospital employee", "Enregistrer un employé de l'hôpital",
              ("Create the employee record in Human Resources with employee number, identity, department, job title and employment information.", "Provide the username and temporary password used for account provisioning.", "HR stores the employee and asks Auth to create a PENDING_APPROVAL account.", "The administrator later approves the account and assigns application role(s)."),
              ("Créez le dossier employé dans Ressources Humaines avec matricule, identité, département, fonction et informations d'emploi.", "Renseignez le nom d'utilisateur et le mot de passe temporaire pour le provisionnement du compte.", "RH enregistre l'employé et demande à Auth de créer un compte PENDING_APPROVAL.", "L'administrateur approuve ensuite le compte et attribue le ou les rôles applicatifs."),
              "Hospital staff are not self-registered. HR creates the employment record, then an administrator approves system access.",
              "Le personnel ne s'inscrit pas lui-même. Les RH créent le dossier d'emploi, puis un administrateur approuve l'accès au système."),
    Procedure("approve_employee", "auth", "auth.users.approve", ("ADMIN_HOPITAL",), ("approve employee", "approve account", "approve staff"), ("approuver employe", "approuver compte", "approuver personnel"),
              "Approve a staff account", "Approuver un compte du personnel",
              ("Open the pending staff access request.", "Verify the staff identity and employment information.", "Assign the required ProjectX role code(s) and approve the account.", "Auth activates the account and returns the one-time QR payload for rendering/printing."),
              ("Ouvrez la demande d'accès du personnel en attente.", "Vérifiez l'identité et les informations d'emploi.", "Attribuez le ou les rôles ProjectX requis et approuvez le compte.", "Auth active le compte et retourne le QR à usage de délivrance pour affichage/impression."),
              "Only an authorized hospital administrator can approve a pending staff account and assign application roles.",
              "Seul un administrateur hospitalier autorisé peut approuver un compte en attente et attribuer les rôles applicatifs."),
    Procedure("register_patient", "accueil", "accueil.patient.create", ("AGENT_ACCUEIL", "ADMIN_HOPITAL"), ("register patient", "create patient", "add patient"), ("enregistrer patient", "creer patient", "ajouter patient", "enregistrer un patient"),
              "Register a patient", "Enregistrer un patient",
              ("Open the Accueil patient registration workflow.", "Enter first name, last name, sex, birth date, phone and address as available.", "Submit the patient record; Accueil validates it and generates the unique patient_number.", "Use the generated patient identity for arrival/check-in and all downstream services."),
              ("Ouvrez le flux d'enregistrement patient de l'Accueil.", "Saisissez prénom, nom, sexe, date de naissance, téléphone et adresse selon les informations disponibles.", "Validez; Accueil contrôle les données et génère le patient_number unique.", "Utilisez ensuite cette identité patient pour l'arrivée/check-in et les autres services."),
              "Patient creation is a controlled Accueil operation. After authentication, an account with Accueil patient-creation permission can perform it.",
              "La création d'un patient est une opération contrôlée de l'Accueil. Après authentification, un compte disposant de la permission de création patient peut l'effectuer."),
    Procedure("search_patient", "accueil", "accueil.patient.read", ("AGENT_ACCUEIL", "MEDECIN", "LABORANTIN", "PHARMACIEN", "RESP_HOSPITALISATION", "INFIRMIER", "SAGE_FEMME", "ADMIN_HOPITAL"), ("search patient", "find patient", "lookup patient"), ("rechercher patient", "trouver patient", "chercher patient"),
              "Search for a patient", "Rechercher un patient",
              ("Use Accueil patient search.", "Search by patient number, name or phone.", "Select the correct identity before opening a clinical or administrative workflow."),
              ("Utilisez la recherche patient de l'Accueil.", "Recherchez par numéro patient, nom ou téléphone.", "Sélectionnez la bonne identité avant d'ouvrir un flux clinique ou administratif."),
              "Patient lookup requires authentication and a patient-read permission.", "La recherche patient exige une authentification et une permission de lecture patient."),
    Procedure("patient_checkin", "accueil", "accueil.arrival.create", ("AGENT_ACCUEIL", "ADMIN_HOPITAL"), ("check in patient", "register arrival", "patient arrival"), ("enregistrer arrivee", "check-in patient", "arrivee patient"),
              "Register a patient's arrival", "Enregistrer l'arrivée d'un patient",
              ("Select the existing patient identity.", "Record the reason for arrival, target service and priority.", "Submit the arrival; the patient enters the Accueil waiting/orientation workflow."),
              ("Sélectionnez l'identité patient existante.", "Renseignez le motif d'arrivée, le service cible et la priorité.", "Validez l'arrivée; le patient entre dans le flux d'attente/orientation de l'Accueil."),
              "Arrival registration requires an authorized Accueil account.", "L'enregistrement d'une arrivée exige un compte Accueil autorisé."),
    Procedure("create_consultation", "consultation", "consultation.create", ("MEDECIN", "ADMIN_HOPITAL"), ("create consultation", "start consultation", "open consultation"), ("creer consultation", "demarrer consultation", "ouvrir consultation"),
              "Open a consultation", "Ouvrir une consultation",
              ("Select an existing patient.", "Create the consultation with the reason and initial symptoms.", "During the OPEN consultation, record observations, vitals and diagnoses.", "Issue prescriptions or requests as needed, then close the consultation when complete."),
              ("Sélectionnez un patient existant.", "Créez la consultation avec le motif et les symptômes initiaux.", "Pendant que la consultation est OPEN, enregistrez observations, constantes et diagnostics.", "Émettez les ordonnances/demandes nécessaires puis clôturez la consultation lorsqu'elle est terminée."),
              "Opening a consultation requires an authenticated clinician with consultation-create permission.", "L'ouverture d'une consultation exige un clinicien authentifié disposant de la permission de création de consultation."),
    Procedure("issue_prescription", "consultation", "consultation.prescription.issue", ("MEDECIN", "ADMIN_HOPITAL"), ("issue prescription", "create prescription", "prescribe medicine"), ("emettre ordonnance", "creer ordonnance", "prescrire medicament"),
              "Issue a prescription", "Émettre une ordonnance",
              ("Open an active consultation.", "Add structured medicine items with medicine reference, dose, frequency, duration and instructions.", "Issue the prescription; it becomes available to the pharmacy workflow."),
              ("Ouvrez une consultation active.", "Ajoutez les médicaments structurés avec référence, dose, fréquence, durée et instructions.", "Émettez l'ordonnance; elle devient disponible pour le flux Pharmacie."),
              "Prescription issuance is restricted to authorized clinical accounts.", "L'émission d'ordonnance est réservée aux comptes cliniques autorisés."),
    Procedure("request_lab_test", "consultation", "consultation.lab.request", ("MEDECIN", "ADMIN_HOPITAL"), ("request lab test", "order lab test", "laboratory request"), ("demander examen labo", "demander examen laboratoire", "ordre laboratoire"),
              "Request a laboratory test", "Demander un examen de laboratoire",
              ("Open the active consultation.", "Choose/provide the laboratory test and clinical information.", "Submit the request; Consultation calls Laboratoire through gRPC and keeps the correlation reference."),
              ("Ouvrez la consultation active.", "Choisissez/renseignez l'examen de laboratoire et les informations cliniques.", "Validez; Consultation appelle Laboratoire par gRPC et conserve la référence de corrélation."),
              "Laboratory requests are created from an authorized consultation workflow.", "Les demandes de laboratoire sont créées depuis un flux de consultation autorisé."),
    Procedure("request_hospitalization", "consultation", "hospitalisation.admit", ("MEDECIN", "RESP_HOSPITALISATION", "ADMIN_HOPITAL"), ("request hospitalization", "admit from consultation", "hospital admission request"), ("demander hospitalisation", "demande admission", "hospitaliser patient"),
              "Request/admit a patient for hospitalization", "Demander/admettre un patient en hospitalisation",
              ("From the clinical workflow, identify the patient and reason for admission.", "Create the hospitalization/admission request with the preferred ward when applicable.", "Hospitalisation manages bed assignment, transfer and discharge separately."),
              ("Depuis le flux clinique, identifiez le patient et le motif d'admission.", "Créez la demande d'hospitalisation/admission avec l'unité préférée si nécessaire.", "Hospitalisation gère ensuite séparément l'affectation du lit, le transfert et la sortie."),
              "Hospital admission requires an authenticated account with hospitalization admission permission.", "L'admission en hospitalisation exige un compte authentifié disposant de la permission d'admission."),
    Procedure("collect_sample", "laboratoire", "lab.sample.collect", ("LABORANTIN", "ADMIN_HOPITAL"), ("collect sample", "record sample", "lab sample"), ("prelever echantillon", "enregistrer prelevement", "prelevement labo"),
              "Record a laboratory sample", "Enregistrer un prélèvement laboratoire",
              ("Open a pending laboratory order.", "Collect the required sample and record the collection with notes if needed.", "The order advances to the sample-collected/in-progress part of the laboratory workflow."),
              ("Ouvrez un ordre de laboratoire en attente.", "Effectuez le prélèvement requis et enregistrez-le avec des notes si nécessaire.", "L'ordre avance vers l'étape prélèvement/en cours du flux laboratoire."),
              "Sample collection requires laboratory collection permission.", "Le prélèvement exige la permission laboratoire de collecte."),
    Procedure("record_lab_result", "laboratoire", "lab.result.record", ("LABORANTIN", "ADMIN_HOPITAL"), ("record lab result", "enter lab result"), ("saisir resultat labo", "enregistrer resultat laboratoire"),
              "Record a laboratory result", "Saisir un résultat laboratoire",
              ("Open the laboratory order after the sample is collected.", "Enter structured result values and/or text result.", "Save the result; validation is a separate controlled step."),
              ("Ouvrez l'ordre laboratoire après le prélèvement.", "Saisissez les valeurs structurées et/ou le résultat texte.", "Enregistrez le résultat; la validation est une étape contrôlée séparée."),
              "Result entry requires laboratory result-record permission.", "La saisie de résultat exige la permission laboratoire correspondante."),
    Procedure("validate_lab_result", "laboratoire", "lab.result.validate", ("LABORANTIN", "ADMIN_HOPITAL"), ("validate lab result", "approve lab result"), ("valider resultat labo", "valider resultat laboratoire"),
              "Validate a laboratory result", "Valider un résultat laboratoire",
              ("Review the recorded laboratory result.", "Validate it using the laboratory validation action.", "A validated result is treated as final; later correction must be explicitly traced rather than silently overwritten."),
              ("Vérifiez le résultat laboratoire saisi.", "Validez-le avec l'action de validation du laboratoire.", "Un résultat validé est considéré final; toute correction ultérieure doit être explicitement tracée et non écrasée silencieusement."),
              "Result validation requires laboratory validation permission.", "La validation d'un résultat exige la permission de validation laboratoire."),
    Procedure("stock_entry", "pharmacie", "pharmacy.stock.manage", ("PHARMACIEN", "RESPONSABLE_LOGISTIQUE", "ADMIN_HOPITAL"), ("stock entry", "add stock", "receive stock"), ("entree stock", "ajouter stock", "reception stock"),
              "Register a pharmacy stock entry", "Enregistrer une entrée de stock pharmacie",
              ("Identify the medicine.", "Enter the batch number, expiration date, quantity and reference.", "Submit the stock entry; the server updates stock through its controlled stock transaction."),
              ("Identifiez le médicament.", "Renseignez numéro de lot, date d'expiration, quantité et référence.", "Validez l'entrée; le serveur met à jour le stock via sa transaction de stock contrôlée."),
              "Stock changes require pharmacy/logistics stock-management permission.", "Les mouvements d'entrée exigent la permission de gestion stock pharmacie/logistique."),
    Procedure("dispense_prescription", "pharmacie", "pharmacy.dispense", ("PHARMACIEN", "ADMIN_HOPITAL"), ("dispense prescription", "dispense medicine", "give medicine"), ("delivrer ordonnance", "delivrer medicament", "servir ordonnance"),
              "Dispense a prescription", "Délivrer une ordonnance",
              ("Open the prescription to be dispensed.", "Verify requested medicine quantities and available non-expired stock.", "Dispense fully or partially as allowed by the prescription and stock.", "The server records the stock movement atomically and creates the billable charge only for what was actually dispensed."),
              ("Ouvrez l'ordonnance à délivrer.", "Vérifiez les quantités prescrites et le stock disponible non expiré.", "Délivrez totalement ou partiellement selon l'ordonnance et le stock.", "Le serveur enregistre atomiquement le mouvement de stock et ne facture que la quantité réellement délivrée."),
              "Dispensing requires pharmacy dispense permission and is protected against negative/expired stock.", "La délivrance exige la permission pharmacie et est protégée contre le stock négatif ou les lots expirés."),
    Procedure("purchase_order", "pharmacie", "pharmacy.stock.manage", ("RESPONSABLE_LOGISTIQUE", "PHARMACIEN", "ADMIN_HOPITAL"), ("purchase order", "order medicines", "reorder stock"), ("bon de commande", "commander medicaments", "reapprovisionnement"),
              "Create/receive a pharmacy purchase order", "Créer/réceptionner une commande pharmacie",
              ("Create the purchase order with supplier and requested medicine quantities.", "When goods arrive, receive the purchase order with the delivered batch/quantity information.", "The server updates the procurement record and stock according to the contract."),
              ("Créez le bon de commande avec le fournisseur et les quantités de médicaments demandées.", "À la livraison, réceptionnez la commande avec les informations de lot/quantité reçues.", "Le serveur met à jour l'approvisionnement et le stock selon le contrat."),
              "Procurement operations require stock-management/logistics permission.", "Les opérations d'approvisionnement exigent la permission de gestion stock/logistique."),
    Procedure("assign_bed", "hospitalisation", "hospitalisation.bed.assign", ("RESP_HOSPITALISATION", "ADMIN_HOPITAL"), ("assign bed", "allocate bed"), ("affecter lit", "attribuer lit"),
              "Assign a bed", "Affecter un lit",
              ("Open the active/pending admission.", "Choose an AVAILABLE bed from the Hospitalisation service.", "Assign the bed; the server protects against double occupancy."),
              ("Ouvrez l'admission active/en attente.", "Choisissez un lit AVAILABLE dans Hospitalisation.", "Affectez le lit; le serveur protège contre la double occupation."),
              "Bed assignment requires hospitalization bed-assignment permission.", "L'affectation d'un lit exige la permission d'affectation de lit."),
    Procedure("transfer_bed", "hospitalisation", "hospitalisation.transfer", ("RESP_HOSPITALISATION", "ADMIN_HOPITAL"), ("transfer patient", "transfer bed", "move patient to another bed"), ("transferer patient", "changer lit", "transferer lit"),
              "Transfer a hospitalized patient", "Transférer un patient hospitalisé",
              ("Open the patient's active admission.", "Select a destination AVAILABLE bed.", "Execute the transfer; Hospitalisation preserves the previous and new bed history with timestamps."),
              ("Ouvrez l'admission active du patient.", "Sélectionnez un lit de destination AVAILABLE.", "Exécutez le transfert; Hospitalisation conserve l'historique de l'ancien et du nouveau lit avec les dates."),
              "Bed transfer requires hospitalization transfer permission.", "Le transfert de lit exige la permission de transfert hospitalisation."),
    Procedure("discharge_patient", "hospitalisation", "hospitalisation.discharge", ("RESP_HOSPITALISATION", "ADMIN_HOPITAL"), ("discharge patient", "patient discharge"), ("sortir patient", "sortie patient"),
              "Discharge a hospitalized patient", "Sortir un patient hospitalisé",
              ("Open the active admission.", "Record the discharge summary and confirm discharge.", "Hospitalisation closes the stay, releases the bed and creates the configured stay charge through Billing where applicable."),
              ("Ouvrez l'admission active.", "Renseignez le résumé de sortie et confirmez la sortie.", "Hospitalisation clôture le séjour, libère le lit et crée la charge de séjour configurée via Billing lorsque prévu."),
              "Discharge requires hospitalization discharge permission.", "La sortie exige la permission de sortie hospitalisation."),
    Procedure("record_payment", "billing", "billing.payment.record", ("CAISSIER", "ADMIN_HOPITAL"), ("record payment", "take payment", "pay invoice"), ("enregistrer paiement", "encaisser", "payer facture"),
              "Record a payment", "Enregistrer un paiement",
              ("Open the patient's invoice/balance.", "Enter the payment amount, currency, method and reference when applicable.", "Submit with an idempotency key; Billing records the payment and issues the receipt.", "A validated payment is not deleted; corrections use a reversal."),
              ("Ouvrez la facture/le solde du patient.", "Saisissez le montant, la devise, le mode et la référence si nécessaire.", "Validez avec une clé d'idempotence; Billing enregistre le paiement et émet le reçu.", "Un paiement validé n'est pas supprimé; les corrections passent par un reversal."),
              "Payment recording requires billing payment permission.", "L'encaissement exige la permission de paiement Billing."),
    Procedure("reverse_payment", "billing", "billing.payment.reverse", ("ADMIN_HOPITAL",), ("reverse payment", "cancel payment", "payment reversal"), ("annuler paiement", "reversal paiement", "contrepasser paiement"),
              "Reverse a payment", "Effectuer le reversal d'un paiement",
              ("Locate the validated payment.", "Provide the reversal reason.", "Submit the reversal with an idempotency key; Billing keeps the original transaction and records the inverse operation."),
              ("Identifiez le paiement validé.", "Renseignez le motif du reversal.", "Validez avec une clé d'idempotence; Billing conserve la transaction originale et enregistre l'opération inverse."),
              "Payment reversal is a sensitive authorized operation; the original payment is never deleted.", "Le reversal est une opération sensible autorisée; le paiement original n'est jamais supprimé."),
    Procedure("create_maternity_case", "maternite", "maternity.case.create", ("SAGE_FEMME", "MEDECIN", "ADMIN_HOPITAL"), ("create maternity case", "open maternity case", "create pregnancy case"), ("creer dossier maternite", "dossier grossesse", "ouvrir dossier maternite"),
              "Create a maternity case", "Créer un dossier maternité",
              ("Select the existing patient identity.", "Create the pregnancy/maternity record with pregnancy history, dates, risk information and referral context.", "Continue the record with prenatal visits, labor events, delivery and newborn information as the case progresses."),
              ("Sélectionnez l'identité patient existante.", "Créez le dossier grossesse/maternité avec antécédents obstétricaux, dates, risque et contexte d'orientation.", "Poursuivez le dossier avec visites prénatales, événements du travail, accouchement et nouveau-né selon l'évolution."),
              "Creating a maternity case requires maternity case-create permission.", "La création d'un dossier maternité exige la permission correspondante."),
    Procedure("record_delivery", "maternite", "maternity.manage", ("SAGE_FEMME", "ADMIN_HOPITAL"), ("record delivery", "record birth", "register delivery"), ("enregistrer accouchement", "accouchement", "enregistrer naissance"),
              "Record a delivery", "Enregistrer un accouchement",
              ("Open the active maternity case/labor record.", "Record delivery time, mode, outcome and complications as applicable.", "If the outcome is a live birth, register the newborn separately with the newborn RPC/workflow."),
              ("Ouvrez le dossier maternité/travail actif.", "Enregistrez la date/heure, la voie, l'issue et les complications éventuelles.", "En cas de naissance vivante, enregistrez ensuite le nouveau-né dans le flux dédié."),
              "Delivery recording requires maternity management permission.", "L'enregistrement de l'accouchement exige la permission de gestion maternité."),
    Procedure("create_appointment", "rendezvous", "appointment.manage", ("AGENT_ACCUEIL", "ADMIN_HOPITAL"), ("create appointment", "book appointment", "schedule appointment"), ("creer rendez-vous", "prendre rendez-vous", "planifier rendez-vous"),
              "Create an appointment", "Créer un rendez-vous",
              ("Select an existing patient.", "Choose an available provider/service slot.", "Enter the reason and create the appointment with an idempotency key.", "The server prevents double booking of the same slot."),
              ("Sélectionnez un patient existant.", "Choisissez un créneau disponible du professionnel/service.", "Renseignez le motif et créez le rendez-vous avec une clé d'idempotence.", "Le serveur empêche la double réservation du même créneau."),
              "Appointment creation requires appointment-management permission.", "La création d'un rendez-vous exige la permission de gestion des rendez-vous."),
    Procedure("reschedule_appointment", "rendezvous", "appointment.manage", ("AGENT_ACCUEIL", "ADMIN_HOPITAL"), ("reschedule appointment", "move appointment"), ("replanifier rendez-vous", "deplacer rendez-vous"),
              "Reschedule an appointment", "Replanifier un rendez-vous",
              ("Open the appointment.", "Choose a new available slot and provide the reason.", "Submit with an idempotency key; the server keeps the appointment history/state transition."),
              ("Ouvrez le rendez-vous.", "Choisissez un nouveau créneau disponible et renseignez le motif.", "Validez avec une clé d'idempotence; le serveur conserve l'historique/la transition d'état."),
              "Rescheduling requires appointment-management permission.", "La replanification exige la permission de gestion des rendez-vous."),
    Procedure("cancel_appointment", "rendezvous", "appointment.manage", ("AGENT_ACCUEIL", "ADMIN_HOPITAL"), ("cancel appointment",), ("annuler rendez-vous",),
              "Cancel an appointment", "Annuler un rendez-vous",
              ("Open the appointment.", "Provide the cancellation reason.", "Cancel it with an idempotency key; the cancellation is retained rather than deleting the appointment."),
              ("Ouvrez le rendez-vous.", "Renseignez le motif d'annulation.", "Annulez avec une clé d'idempotence; l'annulation est conservée au lieu de supprimer le rendez-vous."),
              "Cancellation requires appointment-management permission.", "L'annulation exige la permission de gestion des rendez-vous."),
    Procedure("appointment_checkin", "rendezvous", "appointment.manage", ("AGENT_ACCUEIL", "ADMIN_HOPITAL"), ("check in appointment", "appointment check in"), ("check-in rendez-vous", "arrivee rendez-vous"),
              "Check in an appointment", "Faire le check-in d'un rendez-vous",
              ("Open the booked/confirmed appointment.", "Mark it checked in.", "Rendez-vous calls Accueil so a real patient arrival is created instead of only changing a local appointment flag."),
              ("Ouvrez le rendez-vous réservé/confirmé.", "Marquez-le comme CHECKED_IN.", "Rendez-vous appelle Accueil afin de créer une vraie arrivée patient au lieu de seulement changer un indicateur local."),
              "Appointment check-in requires appointment-management permission.", "Le check-in rendez-vous exige la permission de gestion des rendez-vous."),
    Procedure("view_kpi", "bi", "bi.dashboard.read", ("RESPONSABLE_BI", "ADMIN_HOPITAL"), ("view kpi", "hospital statistics", "dashboard statistics"), ("voir kpi", "statistiques hopital", "tableau de bord statistiques"),
              "View hospital KPI", "Consulter les KPI de l'hôpital",
              ("Open the BI/statistics workflow.", "Choose the requested period/service filter if applicable.", "BI aggregates read-only data through service RPCs and marks the result partial if a source service is unavailable."),
              ("Ouvrez le flux BI/statistiques.", "Choisissez la période/le service si nécessaire.", "BI agrège les données en lecture seule via les RPC des services et marque le résultat partiel si une source est indisponible."),
              "Hospital KPI require BI read permission.", "Les KPI hospitaliers exigent la permission de lecture BI."),
    Procedure("create_shift", "hr", "hr.shift.manage", ("RESPONSABLE_RH", "ADMIN_HOPITAL"), ("create shift", "schedule employee", "work shift"), ("creer horaire", "planifier employe", "shift employe", "planning employe"),
              "Schedule an employee shift", "Planifier un horaire employé",
              ("Select the employee.", "Choose the work date, start time, end time and location.", "Submit with an idempotency key so the same request is not duplicated."),
              ("Sélectionnez l'employé.", "Choisissez la date, l'heure de début, l'heure de fin et le lieu.", "Validez avec une clé d'idempotence afin d'éviter la duplication de la même demande."),
              "Shift scheduling is controlled by Human Resources.", "La planification des horaires est contrôlée par les Ressources Humaines."),
    Procedure("clock_in", "hr", "hr.attendance.clock", ("RESPONSABLE_RH", "AGENT_ACCUEIL", "MEDECIN", "LABORANTIN", "PHARMACIEN", "CAISSIER", "RESP_HOSPITALISATION", "INFIRMIER", "SAGE_FEMME", "RESPONSABLE_LOGISTIQUE", "RESPONSABLE_BI", "ADMIN_HOPITAL"), ("clock in", "start attendance", "punch in"), ("pointer entree", "pointer arrivee", "enregistrer presence"),
              "Clock in", "Pointer l'entrée",
              ("After signing in to ProjectX, use the Clock In attendance action when you actually begin work.", "The HR service records the server timestamp; application login time is not attendance time.", "If a scheduled shift exists, the server can classify the arrival as PRESENT or LATE using the configured grace period."),
              ("Après connexion à ProjectX, utilisez l'action Pointer l'entrée lorsque vous commencez réellement le travail.", "Le service RH enregistre l'heure serveur; l'heure de connexion à l'application n'est pas l'heure de présence.", "Si un horaire existe, le serveur peut classer l'arrivée PRESENT ou LATE selon la tolérance configurée."),
              "Clock-in is available only after authentication for a linked hospital employee account.", "Le pointage d'entrée est disponible après authentification pour un compte employé hospitalier lié."),
    Procedure("clock_out", "hr", "hr.attendance.clock", ("RESPONSABLE_RH", "AGENT_ACCUEIL", "MEDECIN", "LABORANTIN", "PHARMACIEN", "CAISSIER", "RESP_HOSPITALISATION", "INFIRMIER", "SAGE_FEMME", "RESPONSABLE_LOGISTIQUE", "RESPONSABLE_BI", "ADMIN_HOPITAL"), ("clock out", "end attendance", "punch out"), ("pointer sortie", "pointer depart", "fin presence"),
              "Clock out", "Pointer la sortie",
              ("Use Clock Out when you finish work.", "The HR service records the server timestamp and calculates worked minutes from the attendance record.", "Duplicate clock-out and clock-out without a prior clock-in are rejected."),
              ("Utilisez Pointer la sortie lorsque vous terminez le travail.", "Le service RH enregistre l'heure serveur et calcule les minutes travaillées à partir de la présence.", "Un double pointage de sortie ou une sortie sans entrée préalable est refusé."),
              "Clock-out is available only after authentication for a linked employee account.", "Le pointage de sortie est disponible après authentification pour un compte employé lié."),
    Procedure("correct_attendance", "hr", "hr.attendance.correct", ("RESPONSABLE_RH", "ADMIN_HOPITAL"), ("correct attendance", "fix attendance", "edit attendance"), ("corriger presence", "corriger une presence", "corriger la presence", "comment corriger une presence", "comment les rh corrigent une presence", "rh corrigent une presence", "modifier presence", "rectifier presence", "rectifier une presence", "correction presence", "correction de presence"),
              "Correct an attendance record", "Corriger une présence",
              ("Locate the employee/date attendance record.", "Enter the corrected clock-in/clock-out/status values.", "Provide a mandatory reason.", "The server records who corrected it, when it was corrected and the audit event."),
              ("Repérez la présence de l'employé/date.", "Saisissez les heures/statut corrigés.", "Renseignez obligatoirement le motif.", "Le serveur trace qui a corrigé, quand et l'événement d'audit."),
              "Attendance correction is an HR-controlled, audited operation.", "La correction de présence est une opération RH contrôlée et auditée."),
    Procedure("finalize_attendance", "hr", "hr.attendance.close_day", ("RESPONSABLE_RH", "ADMIN_HOPITAL"), ("finalize attendance", "close attendance day", "mark absences"), ("cloturer presence", "cloturer journee", "generer absences"),
              "Finalize an attendance day", "Clôturer une journée de présence",
              ("Choose the work date and provide the closure reason.", "HR compares scheduled employees with existing attendance and approved leave.", "Scheduled staff with approved leave become EXCUSED; scheduled staff with no attendance/leave become ABSENT.", "Auto-generated records are marked SYSTEM_AUTO."),
              ("Choisissez la date de travail et renseignez le motif de clôture.", "RH compare les employés planifiés avec les présences existantes et les congés approuvés.", "Le personnel planifié avec congé approuvé devient EXCUSED; sans présence ni congé il devient ABSENT.", "Les enregistrements automatiques sont marqués SYSTEM_AUTO."),
              "Attendance-day finalization is controlled by Human Resources.", "La clôture d'une journée de présence est contrôlée par les Ressources Humaines."),
    Procedure("submit_leave", "hr", "hr.leave.submit", ("RESPONSABLE_RH", "AGENT_ACCUEIL", "MEDECIN", "LABORANTIN", "PHARMACIEN", "CAISSIER", "RESP_HOSPITALISATION", "INFIRMIER", "SAGE_FEMME", "RESPONSABLE_LOGISTIQUE", "RESPONSABLE_BI", "ADMIN_HOPITAL"), ("request leave", "submit leave", "leave request"), ("demander conge", "soumettre conge", "demande de conge"),
              "Submit a leave request", "Soumettre une demande de congé",
              ("Enter leave type, start date, end date and reason.", "Submit the request; it starts as PENDING.", "The server rejects invalid date ranges and overlapping pending/approved leave."),
              ("Renseignez le type de congé, la date de début, la date de fin et le motif.", "Soumettez la demande; elle démarre au statut PENDING.", "Le serveur refuse les dates invalides et les chevauchements avec des congés en attente/approuvés."),
              "An authenticated linked employee can submit a leave request.", "Un employé lié et authentifié peut soumettre une demande de congé."),
    Procedure("review_leave", "hr", "hr.leave.review", ("RESPONSABLE_RH", "ADMIN_HOPITAL"), ("approve leave", "reject leave", "review leave"), ("approuver conge", "refuser conge", "traiter conge"),
              "Review a leave request", "Traiter une demande de congé",
              ("Open a PENDING leave request.", "Choose APPROVED or REJECTED and add a review note when needed.", "Submit the decision; only pending requests can be reviewed."),
              ("Ouvrez une demande de congé PENDING.", "Choisissez APPROVED ou REJECTED et ajoutez une note si nécessaire.", "Validez la décision; seules les demandes en attente peuvent être traitées."),
              "Leave approval/rejection is controlled by Human Resources.", "L'approbation/refus des congés est contrôlé par les Ressources Humaines."),
)


PROCEDURE_BY_KEY = {p.key: p for p in PROCEDURES}


def _without_articles(value: str) -> str:
    words = [w for w in _norm(value).split() if w not in {"a", "an", "the", "un", "une", "le", "la", "les", "des", "du"}]
    return " ".join(words)


def _iter_aliases(value) -> tuple[str, ...]:
    # Be defensive: a one-item alias accidentally written as ("text") is a str,
    # and expanding it would otherwise iterate character-by-character.
    if isinstance(value, str):
        return (value,)
    return tuple(value or ())


def match_procedure(question: str) -> Procedure | None:
    q = _norm(question)
    q_compact = _without_articles(question)
    best: Procedure | None = None
    best_len = 0
    for proc in PROCEDURES:
        aliases = _iter_aliases(proc.aliases_en) + _iter_aliases(proc.aliases_fr)
        for alias in aliases:
            a = _norm(alias)
            a_compact = _without_articles(alias)
            matched = (a and a in q) or (a_compact and a_compact in q_compact)
            if matched and len(a_compact or a) > best_len:
                best = proc
                best_len = len(a_compact or a)
    return best


def permission_note(proc: Procedure, permissions: Iterable[str], language: str, public: bool = False) -> str:
    if not proc.permission:
        return ""
    roles = ", ".join(proc.roles) if proc.roles else ""
    if public:
        if language == "fr":
            return f"Après connexion, cette opération exige la permission `{proc.permission}`" + (f" (rôles habituels: {roles})." if roles else ".")
        return f"After sign-in, this operation requires `{proc.permission}`" + (f" (typical roles: {roles})." if roles else ".")
    allowed = proc.permission in set(permissions)
    if allowed:
        return (f"Votre compte actuel possède la permission `{proc.permission}` requise." if language == "fr"
                else f"Your current account has the required `{proc.permission}` permission.")
    return (f"Votre compte actuel ne possède pas `{proc.permission}`. Cette opération est normalement réservée à: {roles}." if language == "fr"
            else f"Your current account does not have `{proc.permission}`. This operation is normally restricted to: {roles}.")


def render_procedure(proc: Procedure, language: str, permissions: Iterable[str] = (), public: bool = False) -> tuple[str, str]:
    if public:
        base = proc.public_fr if language == "fr" else proc.public_en
        note = permission_note(proc, permissions, language, public=True)
        return (base + (" " + note if note else ""), note)
    title = proc.title_fr if language == "fr" else proc.title_en
    steps = proc.steps_fr if language == "fr" else proc.steps_en
    note = permission_note(proc, permissions, language, public=False)
    if language == "fr":
        text = title + ":\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1))
    else:
        text = title + ":\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1))
    if note:
        text += "\n\n" + note
    return text, note


MODULE_LABELS = {
    "general": ("ProjectX", "ProjectX"), "login": ("Login", "Connexion"), "auth": ("Administration/Auth", "Administration/Auth"),
    "accueil": ("Accueil", "Accueil"), "consultation": ("Consultation", "Consultation"),
    "laboratoire": ("Laboratory", "Laboratoire"), "pharmacie": ("Pharmacy", "Pharmacie"),
    "hospitalisation": ("Hospitalization", "Hospitalisation"), "billing": ("Billing", "Paiement/Facturation"),
    "maternite": ("Maternity", "Maternité"), "rendezvous": ("Appointments", "Rendez-vous"),
    "bi": ("BI & Statistics", "BI & Statistiques"), "hr": ("Human Resources", "Ressources Humaines"),
    "chatbot": ("Assistant", "Assistant"),
}


def context_help(module: str, permissions: Iterable[str], language: str) -> str:
    module = normalize_module(module)
    label = MODULE_LABELS.get(module, MODULE_LABELS["general"])[1 if language == "fr" else 0]
    permitted = [p for p in PROCEDURES if p.module == module and (not p.permission or p.permission in set(permissions))]
    if not permitted:
        if language == "fr":
            return f"Vous êtes dans {label}. Je peux expliquer ce module, mais je ne vois aucune opération de ce module autorisée par vos permissions actuelles."
        return f"You are in {label}. I can explain this module, but I do not see any operation in this module allowed by your current permissions."
    names = [(p.title_fr if language == "fr" else p.title_en) for p in permitted[:6]]
    if language == "fr":
        return f"Vous êtes dans {label}. Avec vos permissions actuelles, je peux notamment vous guider pour: " + "; ".join(names) + "."
    return f"You are in {label}. With your current permissions, I can guide you with: " + "; ".join(names) + "."


def greeting(language: str, name: str = "") -> str:
    if language == "fr":
        return (f"Bonjour {name} 👋 Je suis l'assistant ProjectX. " if name else "Bonjour 👋 Je suis l'assistant ProjectX. ") + \
               "Je peux vous guider dans l'utilisation du système et, après authentification, consulter uniquement les informations autorisées par vos permissions. Posez votre question en français ou en anglais."
    return (f"Hello {name} 👋 I’m the ProjectX assistant. " if name else "Hello 👋 I’m the ProjectX assistant. ") + \
           "I can guide you through the system and, after authentication, retrieve only information allowed by your permissions. Ask me in English or French."


def thanks_response(language: str, name: str = "") -> str:
    if language == "fr":
        return f"Avec plaisir{', ' + name if name else ''}. Je reste disponible si vous avez besoin d'aide dans ProjectX."
    return f"You’re welcome{', ' + name if name else ''}. I’m here if you need help with ProjectX."


def goodbye_response(language: str, name: str = "") -> str:
    if language == "fr":
        return f"À bientôt{', ' + name if name else ''}. Bonne continuation dans ProjectX."
    return f"See you{', ' + name if name else ''}. Have a good session in ProjectX."


def public_privacy_response(language: str) -> str:
    if language == "fr":
        return "Pour protéger les patients, le personnel et les données financières, l'assistant de la page de connexion ne peut consulter aucune donnée hospitalière. Connectez-vous avec un compte approuvé; vos permissions seront ensuite vérifiées par le serveur pour chaque demande."
    return "To protect patient, staff and financial data, the login-page assistant cannot retrieve any hospital data. Sign in with an approved account; the server will then verify your permissions for every request."


def generic_help(language: str, permissions: Iterable[str], module: str = "general") -> str:
    perms = set(permissions)
    module = normalize_module(module)
    available = [p for p in PROCEDURES if (module == "general" or p.module == module) and (not p.permission or p.permission in perms)]
    if not available:
        available = [p for p in PROCEDURES if not p.permission or p.permission in perms]
    names = [(p.title_fr if language == "fr" else p.title_en) for p in available[:8]]
    if language == "fr":
        return "Je peux répondre aux questions de procédure ProjectX et aux lectures temps réel autorisées. Exemples adaptés à vos droits: " + "; ".join(names) + "."
    return "I can answer ProjectX how-to questions and authorized live-data questions. Examples based on your permissions: " + "; ".join(names) + "."


def build_suggestions(language: str, permissions: Iterable[str], module: str = "general", public: bool = False, limit: int = 4) -> list[str]:
    module = normalize_module(module)
    if public:
        return (["Comment me connecter ?", "Comment fonctionne la connexion QR ?", "Pourquoi mon compte est-il en attente ?", "Que peut faire l'assistant ?"] if language == "fr"
                else ["How do I sign in?", "How does QR login work?", "Why is my account pending?", "What can the assistant do?"])
    perms = set(permissions)
    candidates = [p for p in PROCEDURES if p.module == module and (not p.permission or p.permission in perms)]
    if not candidates:
        candidates = [p for p in PROCEDURES if not p.permission or p.permission in perms]
    out = []
    for p in candidates:
        if language == "fr":
            out.append(f"Comment {p.title_fr[0].lower() + p.title_fr[1:]} ?")
        else:
            out.append(f"How do I {p.title_en[0].lower() + p.title_en[1:]}?")
        if len(out) >= limit:
            break
    return out


LIVE_INTENTS = (
    ("service_health", 0.99, "bi.dashboard.read", ("service health", "services online", "services offline", "status of services", "etat des services", "sante des services")),
    ("hr_dashboard", 0.98, "hr.dashboard.read", (
        "hr dashboard", "attendance today", "who is absent today", "who is late today",
        "tableau de bord rh", "presence aujourd hui", "presence aujourd'hui",
        "presences aujourd hui", "presences aujourd'hui", "presence du jour", "presences du jour",
        "qui est absent aujourd hui", "qui est absent aujourd'hui", "absent aujourd hui", "absent aujourd'hui",
        "absents aujourd hui", "absents aujourd'hui", "absences aujourd hui", "absences aujourd'hui",
        "qui est en retard aujourd hui", "qui est en retard aujourd'hui", "retard aujourd hui", "retard aujourd'hui",
        "retards aujourd hui", "retards aujourd'hui",
    )),
    ("lab_results", 0.97, "lab.orders.read", ("lab results", "laboratory results", "resultats labo", "resultats laboratoire")),
    ("consultations", 0.96, "consultation.read", ("consultation history", "consultations for", "patient consultations", "historique consultation", "consultations du patient")),
    ("maternity_record", 0.96, "maternity.read", ("maternity record", "pregnancy record", "dossier maternite", "dossier grossesse")),
    ("stock_alerts", 0.96, "pharmacy.stock.read", ("stock alerts", "low stock", "expired stock", "alertes stock", "rupture stock", "stock faible")),
    ("kpi", 0.95, "bi.dashboard.read", ("kpi", "hospital statistics", "hospital stats", "statistiques hopital", "indicateurs hopital")),
    ("beds", 0.95, "hospitalisation.read", ("available beds", "bed availability", "beds available", "lits disponibles", "disponibilite des lits")),
    ("agenda", 0.94, "appointment.read", ("agenda", "appointments", "appointment", "rendez-vous", "rdv")),
    ("payment", 0.94, "billing.read", ("patient balance", "balance", "invoice balance", "solde patient", "solde", "facture patient")),
    ("stock", 0.93, "pharmacy.stock.read", ("stock", "medicine", "medication", "pharmacy", "medicament", "pharmacie")),
    ("notifications", 0.92, "notification.read", ("notifications", "my notifications", "notification", "mes notifications")),
    ("patient", 0.91, "accueil.patient.read", ("patient", "pat-")),
)


def _intent_norm(value: str) -> str:
    q = _norm(value)
    q = re.sub(r"[^a-z0-9]+", " ", q)
    return re.sub(r"\s+", " ", q).strip()


def identify_live_intent(question: str) -> tuple[str, float, str] | None:
    q = _norm(question)
    q_loose = _intent_norm(question)
    for intent, confidence, permission, phrases in LIVE_INTENTS:
        for phrase in phrases:
            strict = _norm(phrase)
            loose = _intent_norm(phrase)
            if (strict and strict in q) or (loose and loose in q_loose):
                return intent, confidence, permission
    return None


def extract_patient_number(question: str, context_patient_number: str = "", prior_text: str = "") -> str:
    for source in [question, context_patient_number, prior_text]:
        match = re.search(r"PAT-[A-Z0-9-]+", source or "", re.I)
        if match:
            return match.group(0).upper()
    return ""


def likely_sensitive_public_question(question: str) -> bool:
    q = _norm(question)
    sensitive = [
        "pat-", "patient balance", "patient details", "patient record", "lab result", "medical record", "diagnosis",
        "who is absent", "who is late", "employee attendance", "hospital revenue", "invoice", "payment status",
        "appointment of", "maternity record", "pregnancy record", "show patient", "find patient",
        "solde patient", "dossier patient", "resultat labo", "diagnostic", "qui est absent", "presence employe",
        "revenu hopital", "facture", "dossier maternite", "trouver patient", "afficher patient",
    ]
    return any(x in q for x in sensitive) or bool(re.search(r"PAT-[A-Z0-9-]+", question or "", re.I))
