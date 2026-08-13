ROLES = {
    "ADMIN_HOPITAL": {
        "name": "Administrateur Hôpital",
        "description": (
            "Administration générale, comptes, rôles, "
            "configuration, audit et supervision."
        ),
    },

    "AGENT_ACCUEIL": {
        "name": "Agent d'accueil",
        "description": (
            "Gestion administrative des patients, "
            "arrivées, orientation et rendez-vous."
        ),
    },

    "MEDECIN": {
        "name": "Médecin",
        "description": (
            "Consultations, prescriptions, demandes "
            "de laboratoire et d'hospitalisation."
        ),
    },

    "INFIRMIER": {
        "name": "Infirmier",
        "description": (
            "Suivi du séjour hospitalier selon permissions."
        ),
    },

    "RESP_HOSPITALISATION": {
        "name": "Responsable Hospitalisation",
        "description": (
            "Admissions, lits, transferts et sorties."
        ),
    },

    "LABORANTIN": {
        "name": "Laborantin",
        "description": (
            "Prélèvements, résultats et validation laboratoire."
        ),
    },

    "PHARMACIEN": {
        "name": "Pharmacien",
        "description": (
            "Médicaments, stock et délivrances."
        ),
    },

    "CAISSIER": {
        "name": "Caissier",
        "description": (
            "Facturation, paiements et reçus."
        ),
    },

    "SAGE_FEMME": {
        "name": "Sage-femme",
        "description": (
            "Suivi maternité, travail, accouchement "
            "et nouveau-né."
        ),
    },

    "RESPONSABLE_LOGISTIQUE": {
        "name": "Responsable Logistique",
        "description": (
            "Fournisseurs, achats et réapprovisionnement."
        ),
    },

    "RESPONSABLE_BI": {
        "name": "Responsable BI / Direction",
        "description": (
            "Consultation des indicateurs et rapports."
        ),
    },
}

PERMISSIONS = {
    # Authentication / administration
    "auth.users.read": "Consulter les utilisateurs",
    "auth.users.create": "Créer un utilisateur",
    "auth.users.disable": "Désactiver un utilisateur",
    "auth.roles.assign": "Attribuer les rôles",
    "auth.audit.read": "Consulter les journaux d'audit",

    # Accueil
    "accueil.patient.read": "Consulter les patients",
    "accueil.patient.create": "Créer un patient",
    "accueil.patient.update": "Modifier un patient",
    "accueil.arrival.create": "Enregistrer une arrivée",
    "accueil.queue.read": "Consulter la file d'attente",

    # Consultation
    "consultation.read": "Consulter les consultations",
    "consultation.create": "Créer une consultation",
    "consultation.update": "Modifier une consultation ouverte",
    "consultation.close": "Clôturer une consultation",
    "consultation.prescription.issue": "Émettre une ordonnance",
    "consultation.lab.request": "Demander un examen laboratoire",

    # Laboratory
    "lab.orders.read": "Consulter les ordres laboratoire",
    "lab.sample.collect": "Enregistrer un prélèvement",
    "lab.result.record": "Saisir un résultat",
    "lab.result.validate": "Valider un résultat",

    # Pharmacy
    "pharmacy.stock.read": "Consulter le stock",
    "pharmacy.stock.manage": "Gérer les entrées de stock",
    "pharmacy.dispense": "Délivrer une prescription",

    # Hospitalisation
    "hospitalisation.read": "Consulter les hospitalisations",
    "hospitalisation.admit": "Admettre un patient",
    "hospitalisation.bed.assign": "Affecter un lit",
    "hospitalisation.transfer": "Transférer un patient",
    "hospitalisation.discharge": "Sortir un patient",

    # Billing
    "billing.read": "Consulter la facturation",
    "billing.payment.record": "Enregistrer un paiement",
    "billing.payment.reverse": "Effectuer un reversal",

    # Maternity
    "maternity.read": "Consulter les dossiers maternité",
    "maternity.manage": "Gérer le parcours maternité",

    # Appointments
    "appointment.read": "Consulter les rendez-vous",
    "appointment.manage": "Gérer les rendez-vous",

    # BI
    "bi.dashboard.read": "Consulter les statistiques",

    # Notifications
    "notification.read": "Consulter les notifications",
}


ROLE_PERMISSIONS = {
    "ADMIN_HOPITAL": set(PERMISSIONS.keys()),

    "AGENT_ACCUEIL": {
        "accueil.patient.read",
        "accueil.patient.create",
        "accueil.patient.update",
        "accueil.arrival.create",
        "accueil.queue.read",
        "appointment.read",
        "appointment.manage",
        "notification.read",
    },

    "MEDECIN": {
        "accueil.patient.read",
        "consultation.read",
        "consultation.create",
        "consultation.update",
        "consultation.close",
        "consultation.prescription.issue",
        "consultation.lab.request",
        "lab.orders.read",
        "hospitalisation.read",
        "hospitalisation.admit",
        "maternity.read",
        "notification.read",
    },

    "LABORANTIN": {
        "accueil.patient.read",
        "lab.orders.read",
        "lab.sample.collect",
        "lab.result.record",
        "lab.result.validate",
        "notification.read",
    },

    "PHARMACIEN": {
        "accueil.patient.read",
        "pharmacy.stock.read",
        "pharmacy.stock.manage",
        "pharmacy.dispense",
        "notification.read",
    },

    "CAISSIER": {
        "billing.read",
        "billing.payment.record",
        "notification.read",
    },

    "RESP_HOSPITALISATION": {
        "accueil.patient.read",
        "hospitalisation.read",
        "hospitalisation.admit",
        "hospitalisation.bed.assign",
        "hospitalisation.transfer",
        "hospitalisation.discharge",
        "notification.read",
    },

    "INFIRMIER": {
        "accueil.patient.read",
        "hospitalisation.read",
        "notification.read",
    },

    "SAGE_FEMME": {
        "accueil.patient.read",
        "maternity.read",
        "maternity.manage",
        "notification.read",
    },

    "RESPONSABLE_LOGISTIQUE": {
        "pharmacy.stock.read",
        "pharmacy.stock.manage",
        "notification.read",
    },

    "RESPONSABLE_BI": {
        "bi.dashboard.read",
        "notification.read",
    },
}