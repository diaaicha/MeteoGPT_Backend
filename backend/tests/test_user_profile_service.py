# -*- coding: utf-8 -*-

"""
Tests du service de persistance des profils utilisateurs.

Chaque test utilise une base SQLite temporaire.

Aucune donnée réelle n'est utilisée.
Aucun appel Gemini, Retriever ou WhatsApp n'est effectué.
"""

import sqlite3

from contextlib import closing

import pytest

from backend.app.services.user_profile_service import (
    UserProfileStore,
    STATUS_NEW,
    STATUS_OFFERED,
    STATUS_ACCEPTED,
    STATUS_DECLINED,
)


# ============================================================
# 1. FIXTURE
# ============================================================

@pytest.fixture
def store(tmp_path):

    """
    Crée une base SQLite indépendante pour chaque test.
    """

    database_path = (
        tmp_path
        / "test_user_profiles.sqlite3"
    )

    return UserProfileStore(
        database_path=database_path
    )


# ============================================================
# 2. PROFIL INITIAL
# ============================================================

def test_profil_inconnu(store):

    profil = store.charger_profil(
        "user-001"
    )

    assert profil == {

        "user_id": "user-001",

        "first_name": None,

        "last_name": None,

        "personalization_status": STATUS_NEW,

        "personalization_offer_seen": False,
    }


# ============================================================
# 3. PROPOSITION DE PERSONNALISATION
# ============================================================

def test_enregistrement_proposition(store):

    store.marquer_proposition_envoyee(
        "user-001"
    )

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_OFFERED
    )

    assert (
        profil["personalization_offer_seen"]
        is True
    )

    assert profil["first_name"] is None

    assert profil["last_name"] is None

    # Un nouvel enregistrement ne doit pas
    # modifier le profil existant.

    store.marquer_proposition_envoyee(
        "user-001"
    )

    assert (
        store.charger_profil("user-001")
        == profil
    )


# ============================================================
# 4. REFUS
# ============================================================

def test_refus_personnalisation(store):

    store.marquer_proposition_envoyee(
        "user-001"
    )

    store.enregistrer_refus(
        "user-001"
    )

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_DECLINED
    )

    assert (
        profil["personalization_offer_seen"]
        is True
    )

    assert profil["first_name"] is None

    assert profil["last_name"] is None

    # Une ancienne proposition ne doit pas
    # annuler le refus.

    store.marquer_proposition_envoyee(
        "user-001"
    )

    assert (
        store.charger_profil("user-001")
        == profil
    )


def test_refus_direct_sans_proposition(store):

    store.enregistrer_refus(
        "user-001"
    )

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_DECLINED
    )

    assert (
        profil["personalization_offer_seen"]
        is True
    )


def test_refus_ne_supprime_pas_identite(store):

    profil_initial = store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    store.enregistrer_refus(
        "user-001"
    )

    assert (
        store.charger_profil("user-001")
        == profil_initial
    )


# ============================================================
# 5. ENREGISTREMENT DE L'IDENTITÉ
# ============================================================

def test_enregistrement_identite(store):

    profil = store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    assert profil["first_name"] == "Mariam"

    assert profil["last_name"] == "Ndiaye"

    assert (
        profil["personalization_status"]
        == STATUS_ACCEPTED
    )

    assert (
        profil["personalization_offer_seen"]
        is True
    )


def test_normalisation_des_noms(store):

    profil = store.enregistrer_identite(

        user_id="  user-001  ",

        first_name="  Aïssatou   Mariam  ",

        last_name="  Ndiaye  ",
    )

    assert profil["user_id"] == "user-001"

    assert (
        profil["first_name"]
        == "Aïssatou Mariam"
    )

    assert profil["last_name"] == "Ndiaye"


def test_personnalisation_apres_refus(store):

    store.enregistrer_refus(
        "user-001"
    )

    profil = store.enregistrer_identite(

        user_id="user-001",

        first_name="Aminata",

        last_name="Ba",
    )

    assert (
        profil["personalization_status"]
        == STATUS_ACCEPTED
    )

    assert profil["first_name"] == "Aminata"

    assert profil["last_name"] == "Ba"


# ============================================================
# 6. VALIDATION DES DONNÉES
# ============================================================

@pytest.mark.parametrize(
    "first_name,last_name,exception",
    [

        ("", "Ndiaye", ValueError),

        ("Mariam", "   ", ValueError),

        ("A" * 101, "Ndiaye", ValueError),

        ("Mariam", "A" * 101, ValueError),

        (None, "Ndiaye", TypeError),

        ("Mariam", 123, TypeError),
    ]
)
def test_identite_invalide(
    store,
    first_name,
    last_name,
    exception
):

    with pytest.raises(exception):

        store.enregistrer_identite(

            user_id="user-001",

            first_name=first_name,

            last_name=last_name,
        )

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_NEW
    )


@pytest.mark.parametrize(
    "user_id,exception",
    [

        ("", ValueError),

        ("   ", ValueError),

        (None, TypeError),

        (123, TypeError),
    ]
)
def test_identifiant_invalide(
    store,
    user_id,
    exception
):

    with pytest.raises(exception):

        store.charger_profil(
            user_id
        )


# ============================================================
# 7. PERSISTANCE DES PROFILS
# ============================================================

def test_persistance_profil_apres_reouverture(store):

    store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    store.enregistrer_refus(
        "user-002"
    )

    store.marquer_proposition_envoyee(
        "user-003"
    )

    nouveau_store = UserProfileStore(
        database_path=store.database_path
    )

    for user_id in (
        "user-001",
        "user-002",
        "user-003",
    ):

        assert (

            nouveau_store.charger_profil(
                user_id
            )

            == store.charger_profil(
                user_id
            )
        )


# ============================================================
# 8. INITIALISATION DE LA COLLECTE
# ============================================================

def test_absence_collecte_initiale(store):

    assert (
        store.charger_collecte("user-001")
        is None
    )


def test_demarrage_collecte(store):

    collecte = store.demarrer_collecte(
        "user-001"
    )

    assert collecte == {

        "user_id": "user-001",

        "first_name": None,

        "stage": "waiting_first_name",
    }

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_NEW
    )

    assert profil["first_name"] is None


# ============================================================
# 9. ENREGISTREMENT TEMPORAIRE DU PRÉNOM
# ============================================================

def test_enregistrement_prenom_collecte(store):

    store.demarrer_collecte(
        "user-001"
    )

    collecte = store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="  Mariam  ",
    )

    assert collecte["first_name"] == "Mariam"

    assert (
        collecte["stage"]
        == "waiting_last_name"
    )

    profil = store.charger_profil(
        "user-001"
    )

    # Le prénom reste uniquement dans le brouillon.

    assert profil["first_name"] is None

    assert (
        profil["personalization_status"]
        == STATUS_NEW
    )


def test_prenom_sans_collecte_interdit(store):

    with pytest.raises(RuntimeError):

        store.enregistrer_prenom_collecte(

            user_id="user-001",

            first_name="Mariam",
        )


def test_prenom_temporaire_non_ecrase(store):

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Mariam",
    )

    with pytest.raises(RuntimeError):

        store.enregistrer_prenom_collecte(

            user_id="user-001",

            first_name="Fatou",
        )

    collecte = store.charger_collecte(
        "user-001"
    )

    assert collecte["first_name"] == "Mariam"


# ============================================================
# 10. REPRISE DE LA COLLECTE
# ============================================================

def test_demarrage_collecte_repetee(store):

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Mariam",
    )

    collecte = store.demarrer_collecte(
        "user-001"
    )

    assert collecte["first_name"] == "Mariam"

    assert (
        collecte["stage"]
        == "waiting_last_name"
    )


def test_collecte_persistante_apres_reouverture(store):

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Aïssatou",
    )

    nouveau_store = UserProfileStore(
        database_path=store.database_path
    )

    collecte = nouveau_store.charger_collecte(
        "user-001"
    )

    assert (
        collecte["first_name"]
        == "Aïssatou"
    )

    assert (
        collecte["stage"]
        == "waiting_last_name"
    )


# ============================================================
# 11. FINALISATION
# ============================================================

def test_finalisation_collecte(store):

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Mariam",
    )

    profil = store.finaliser_collecte(

        user_id="user-001",

        last_name="Ndiaye",
    )

    assert profil["first_name"] == "Mariam"

    assert profil["last_name"] == "Ndiaye"

    assert (
        profil["personalization_status"]
        == STATUS_ACCEPTED
    )

    assert (
        profil["personalization_offer_seen"]
        is True
    )

    assert (
        store.charger_collecte("user-001")
        is None
    )


def test_finalisation_sans_collecte_interdite(store):

    with pytest.raises(RuntimeError):

        store.finaliser_collecte(

            user_id="user-001",

            last_name="Ndiaye",
        )


def test_finalisation_sans_prenom_interdite(store):

    store.demarrer_collecte(
        "user-001"
    )

    with pytest.raises(RuntimeError):

        store.finaliser_collecte(

            user_id="user-001",

            last_name="Ndiaye",
        )

    collecte = store.charger_collecte(
        "user-001"
    )

    assert (
        collecte["stage"]
        == "waiting_first_name"
    )

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_NEW
    )


def test_prenom_collecte_invalide(store):

    store.demarrer_collecte(
        "user-001"
    )

    with pytest.raises(ValueError):

        store.enregistrer_prenom_collecte(

            user_id="user-001",

            first_name="   ",
        )

    collecte = store.charger_collecte(
        "user-001"
    )

    assert collecte["first_name"] is None

    assert (
        collecte["stage"]
        == "waiting_first_name"
    )


def test_nom_invalide_preserve_brouillon(store):

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Mariam",
    )

    with pytest.raises(ValueError):

        store.finaliser_collecte(

            user_id="user-001",

            last_name="   ",
        )

    collecte = store.charger_collecte(
        "user-001"
    )

    assert collecte["first_name"] == "Mariam"

    assert (
        collecte["stage"]
        == "waiting_last_name"
    )


# ============================================================
# 12. ANNULATION
# ============================================================

def test_annulation_collecte(store):

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Mariam",
    )

    assert (
        store.annuler_collecte("user-001")
        is True
    )

    assert (
        store.charger_collecte("user-001")
        is None
    )

    profil = store.charger_profil(
        "user-001"
    )

    assert profil["first_name"] is None

    assert profil["last_name"] is None


def test_annulation_sans_collecte(store):

    assert (
        store.annuler_collecte("user-001")
        is False
    )


# ============================================================
# 13. MODIFICATION DU PROFIL
# ============================================================

def test_modification_preserve_ancienne_identite(store):

    profil_initial = store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Fatou",
    )

    assert (

        store.charger_profil(
            "user-001"
        )

        == profil_initial
    )


def test_annulation_modification_preserve_profil(store):

    profil_initial = store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Fatou",
    )

    store.annuler_collecte(
        "user-001"
    )

    assert (

        store.charger_profil(
            "user-001"
        )

        == profil_initial
    )

    assert (
        store.charger_collecte("user-001")
        is None
    )


def test_modification_complete(store):

    store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Fatou",
    )

    profil = store.finaliser_collecte(

        user_id="user-001",

        last_name="Fall",
    )

    assert profil["first_name"] == "Fatou"

    assert profil["last_name"] == "Fall"

    assert (
        profil["personalization_status"]
        == STATUS_ACCEPTED
    )

    assert (
        store.charger_collecte("user-001")
        is None
    )


def test_collecte_apres_refus(store):

    store.enregistrer_refus(
        "user-001"
    )

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Aminata",
    )

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_DECLINED
    )

    profil = store.finaliser_collecte(

        user_id="user-001",

        last_name="Ba",
    )

    assert (
        profil["personalization_status"]
        == STATUS_ACCEPTED
    )

    assert profil["first_name"] == "Aminata"

    assert profil["last_name"] == "Ba"


# ============================================================
# 14. ISOLATION DES UTILISATEURS
# ============================================================

def test_isolation_des_profils(store):

    store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    store.enregistrer_identite(

        user_id="user-002",

        first_name="Fatou",

        last_name="Fall",
    )

    profil_1 = store.charger_profil(
        "user-001"
    )

    profil_2 = store.charger_profil(
        "user-002"
    )

    assert profil_1["first_name"] == "Mariam"

    assert profil_2["first_name"] == "Fatou"

    assert profil_1["last_name"] == "Ndiaye"

    assert profil_2["last_name"] == "Fall"


def test_isolation_des_collectes(store):

    store.demarrer_collecte(
        "user-001"
    )

    store.demarrer_collecte(
        "user-002"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Mariam",
    )

    collecte_1 = store.charger_collecte(
        "user-001"
    )

    collecte_2 = store.charger_collecte(
        "user-002"
    )

    assert collecte_1["first_name"] == "Mariam"

    assert collecte_2["first_name"] is None

    assert (
        collecte_2["stage"]
        == "waiting_first_name"
    )

    store.annuler_collecte(
        "user-001"
    )

    assert (
        store.charger_collecte("user-002")
        is not None
    )


# ============================================================
# 15. COHÉRENCE TRANSACTIONNELLE
# ============================================================

def test_finalisation_atomique_en_cas_echec(store):

    """
    Vérifie que si la suppression du brouillon échoue,
    la nouvelle identité n'est pas enregistrée partiellement.
    """

    profil_initial = store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Fatou",
    )

    # Simuler un échec SQLite au moment de
    # la suppression du brouillon.

    with closing(
        sqlite3.connect(
            str(store.database_path)
        )
    ) as connexion:

        with connexion:

            connexion.execute(
                """
                CREATE TRIGGER test_block_delete

                BEFORE DELETE
                ON personalization_drafts

                BEGIN

                    SELECT RAISE(
                        ABORT,
                        'suppression interdite'
                    );

                END
                """
            )

    with pytest.raises(sqlite3.IntegrityError):

        store.finaliser_collecte(

            user_id="user-001",

            last_name="Fall",
        )

    # L'ancienne identité doit être conservée.

    assert (

        store.charger_profil(
            "user-001"
        )

        == profil_initial
    )

    # Le brouillon doit également être conservé.

    collecte = store.charger_collecte(
        "user-001"
    )

    assert collecte["first_name"] == "Fatou"

    assert (
        collecte["stage"]
        == "waiting_last_name"
    )


# ============================================================
# 16. COMPATIBILITÉ AVEC UNE BASE EXISTANTE
# ============================================================

def test_creation_table_collecte_preserve_profils(store):

    """
    Simule une ancienne base ne contenant
    que la table des profils définitifs.
    """

    profil_initial = store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    with closing(
        sqlite3.connect(
            str(store.database_path)
        )
    ) as connexion:

        with connexion:

            connexion.execute(
                """
                DROP TABLE personalization_drafts
                """
            )

    # Le service doit recréer la table manquante
    # sans modifier les profils existants.

    nouveau_store = UserProfileStore(
        database_path=store.database_path
    )

    assert (

        nouveau_store.charger_profil(
            "user-001"
        )

        == profil_initial
    )

    collecte = nouveau_store.demarrer_collecte(
        "user-001"
    )

    assert (
        collecte["stage"]
        == "waiting_first_name"
    )