# -*- coding: utf-8 -*-

"""
XamMeteo — Service de persistance des profils utilisateurs.

Responsabilités :
- charger les informations personnelles ;
- enregistrer la proposition de personnalisation ;
- enregistrer le refus ;
- enregistrer ou modifier le prénom et le nom ;
- gérer les collectes de personnalisation en cours.

Ce module ne réalise aucun traitement météorologique.
"""

import sqlite3

from contextlib import closing
from pathlib import Path


# ============================================================
# 1. CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

DEFAULT_DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "user_profiles.sqlite3"
)


# ============================================================
# 2. ÉTATS DE PERSONNALISATION
# ============================================================

STATUS_NEW = "new"

STATUS_OFFERED = "offered"

STATUS_ACCEPTED = "accepted"

STATUS_DECLINED = "declined"


# ============================================================
# 3. SERVICE DE PERSISTANCE
# ============================================================

class UserProfileStore:

    """
    Gestion du stockage persistant des profils utilisateurs.

    Une connexion SQLite est ouverte pour chaque opération
    puis automatiquement fermée.
    """

    def __init__(
        self,
        database_path=DEFAULT_DATABASE_PATH
    ):

        self.database_path = Path(
            database_path
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.initialiser_base()


    # ========================================================
    # 4. CONNEXION À LA BASE
    # ========================================================

    def _connect(self):

        connexion = sqlite3.connect(
            str(self.database_path),
            timeout=10
        )

        connexion.row_factory = sqlite3.Row

        return connexion


    # ========================================================
    # 5. INITIALISATION
    # ========================================================

    def initialiser_base(self):

        """
        Crée les tables nécessaires à la persistance
        des profils et des collectes de personnalisation.

        Ne supprime aucune information existante.
        """

        with closing(self._connect()) as connexion:

            with connexion:

                # ============================================
                # TABLE DES PROFILS DÉFINITIFS
                # ============================================

                connexion.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_profiles (

                        user_id TEXT PRIMARY KEY,

                        first_name TEXT,

                        last_name TEXT,

                        personalization_status TEXT NOT NULL,

                        CHECK (
                            personalization_status IN (
                                'offered',
                                'accepted',
                                'declined'
                            )
                        ),

                        CHECK (
                            (
                                personalization_status = 'accepted'
                                AND first_name IS NOT NULL
                                AND last_name IS NOT NULL
                            )
                            OR
                            (
                                personalization_status IN (
                                    'offered',
                                    'declined'
                                )
                                AND first_name IS NULL
                                AND last_name IS NULL
                            )
                        )
                    )
                    """
                )

                # ============================================
                # TABLE DES COLLECTES EN COURS
                # ============================================

                connexion.execute(
                    """
                    CREATE TABLE IF NOT EXISTS personalization_drafts (

                        user_id TEXT PRIMARY KEY,

                        first_name TEXT,

                        CHECK (
                            first_name IS NULL
                            OR length(trim(first_name)) > 0
                        )
                    )
                    """
                )


    # ========================================================
    # 6. VALIDATION DE L'IDENTIFIANT
    # ========================================================

    @staticmethod
    def _normaliser_user_id(user_id):

        if not isinstance(user_id, str):

            raise TypeError(
                "user_id doit être une chaîne de caractères."
            )

        user_id = user_id.strip()

        if not user_id:

            raise ValueError(
                "user_id ne peut pas être vide."
            )

        return user_id


    # ========================================================
    # 7. VALIDATION DES INFORMATIONS PERSONNELLES
    # ========================================================

    @staticmethod
    def _normaliser_nom(valeur, champ):

        if not isinstance(valeur, str):

            raise TypeError(
                f"{champ} doit être une chaîne de caractères."
            )

        valeur = " ".join(
            valeur.split()
        )

        if not valeur:

            raise ValueError(
                f"{champ} ne peut pas être vide."
            )

        if len(valeur) > 100:

            raise ValueError(
                f"{champ} ne peut pas dépasser 100 caractères."
            )

        return valeur


    # ========================================================
    # 8. CHARGEMENT DU PROFIL
    # ========================================================

    def charger_profil(
        self,
        user_id
    ):

        """
        Charge le profil enregistré.

        Un utilisateur inconnu possède par défaut
        le statut 'new'.
        """

        user_id = self._normaliser_user_id(
            user_id
        )

        with closing(self._connect()) as connexion:

            ligne = connexion.execute(
                """
                SELECT
                    user_id,
                    first_name,
                    last_name,
                    personalization_status

                FROM user_profiles

                WHERE user_id = ?
                """,
                (user_id,)
            ).fetchone()

        if ligne is None:

            return {

                "user_id":
                    user_id,

                "first_name":
                    None,

                "last_name":
                    None,

                "personalization_status":
                    STATUS_NEW,

                "personalization_offer_seen":
                    False,
            }

        profil = dict(ligne)

        profil[
            "personalization_offer_seen"
        ] = True

        return profil


    # ========================================================
    # 9. PROPOSITION EFFECTIVEMENT ENVOYÉE
    # ========================================================

    def marquer_proposition_envoyee(
        self,
        user_id
    ):

        """
        Enregistre l'envoi effectif de la proposition.

        Cette opération ne remplace jamais un profil
        déjà existant.
        """

        user_id = self._normaliser_user_id(
            user_id
        )

        with closing(self._connect()) as connexion:

            with connexion:

                connexion.execute(
                    """
                    INSERT INTO user_profiles (
                        user_id,
                        first_name,
                        last_name,
                        personalization_status
                    )

                    VALUES (?, NULL, NULL, ?)

                    ON CONFLICT(user_id) DO NOTHING
                    """,
                    (
                        user_id,
                        STATUS_OFFERED
                    )
                )


    # ========================================================
    # 10. REFUS DE LA PERSONNALISATION
    # ========================================================

    def enregistrer_refus(
        self,
        user_id
    ):

        """
        Enregistre le refus de personnalisation.

        Un ancien bouton de refus ne doit pas supprimer
        une identité déjà enregistrée.
        """

        user_id = self._normaliser_user_id(
            user_id
        )

        with closing(self._connect()) as connexion:

            with connexion:

                connexion.execute(
                    """
                    INSERT INTO user_profiles (
                        user_id,
                        first_name,
                        last_name,
                        personalization_status
                    )

                    VALUES (?, NULL, NULL, ?)

                    ON CONFLICT(user_id)

                    DO UPDATE SET

                        personalization_status =
                            excluded.personalization_status

                    WHERE
                        user_profiles.personalization_status
                        != 'accepted'
                    """,
                    (
                        user_id,
                        STATUS_DECLINED
                    )
                )


    # ========================================================
    # 11. ENREGISTREMENT OU MODIFICATION DE L'IDENTITÉ
    # ========================================================

    def enregistrer_identite(
        self,
        user_id,
        first_name,
        last_name
    ):

        """
        Enregistre ou remplace le prénom et le nom.

        L'identité est considérée comme acceptée uniquement
        lorsque les deux informations sont renseignées.
        """

        user_id = self._normaliser_user_id(
            user_id
        )

        first_name = self._normaliser_nom(
            first_name,
            "first_name"
        )

        last_name = self._normaliser_nom(
            last_name,
            "last_name"
        )

        with closing(self._connect()) as connexion:

            with connexion:

                connexion.execute(
                    """
                    INSERT INTO user_profiles (
                        user_id,
                        first_name,
                        last_name,
                        personalization_status
                    )

                    VALUES (?, ?, ?, ?)

                    ON CONFLICT(user_id)

                    DO UPDATE SET

                        first_name =
                            excluded.first_name,

                        last_name =
                            excluded.last_name,

                        personalization_status =
                            excluded.personalization_status
                    """,
                    (
                        user_id,
                        first_name,
                        last_name,
                        STATUS_ACCEPTED
                    )
                )

        return self.charger_profil(
            user_id
        )


    # ========================================================
    # 12. CHARGEMENT DE LA COLLECTE EN COURS
    # ========================================================

    def charger_collecte(
        self,
        user_id
    ):

        """
        Retourne l'état de la collecte en cours.

        Retourne None si aucune collecte n'est active.
        """

        user_id = self._normaliser_user_id(
            user_id
        )

        with closing(self._connect()) as connexion:

            ligne = connexion.execute(
                """
                SELECT
                    user_id,
                    first_name

                FROM personalization_drafts

                WHERE user_id = ?
                """,
                (user_id,)
            ).fetchone()

        if ligne is None:

            return None

        collecte = dict(ligne)

        collecte["stage"] = (

            "waiting_last_name"

            if collecte["first_name"] is not None

            else "waiting_first_name"
        )

        return collecte


    # ========================================================
    # 13. DÉMARRAGE DE LA COLLECTE
    # ========================================================

    def demarrer_collecte(
        self,
        user_id
    ):

        """
        Démarre une collecte du prénom et du nom.

        Si une collecte existe déjà, elle est conservée
        afin de ne pas perdre les informations saisies.

        Le profil définitif n'est pas modifié.
        """

        user_id = self._normaliser_user_id(
            user_id
        )

        with closing(self._connect()) as connexion:

            with connexion:

                connexion.execute(
                    """
                    INSERT INTO personalization_drafts (
                        user_id,
                        first_name
                    )

                    VALUES (?, NULL)

                    ON CONFLICT(user_id) DO NOTHING
                    """,
                    (user_id,)
                )

        return self.charger_collecte(
            user_id
        )


    # ========================================================
    # 14. ENREGISTREMENT TEMPORAIRE DU PRÉNOM
    # ========================================================

    def enregistrer_prenom_collecte(
        self,
        user_id,
        first_name
    ):

        """
        Enregistre le prénom dans le brouillon.

        Cette opération ne modifie pas le profil définitif.
        """

        user_id = self._normaliser_user_id(
            user_id
        )

        first_name = self._normaliser_nom(
            first_name,
            "first_name"
        )

        with closing(self._connect()) as connexion:

            with connexion:

                resultat = connexion.execute(
                    """
                    UPDATE personalization_drafts

                    SET first_name = ?

                    WHERE user_id = ?

                    AND first_name IS NULL
                    """,
                    (
                        first_name,
                        user_id
                    )
                )

                if resultat.rowcount != 1:

                    raise RuntimeError(
                        "Aucune collecte de prénom active."
                    )

        return self.charger_collecte(
            user_id
        )


    # ========================================================
    # 15. FINALISATION DE LA COLLECTE
    # ========================================================

    def finaliser_collecte(
        self,
        user_id,
        last_name
    ):

        """
        Enregistre définitivement le prénom et le nom.

        L'enregistrement du profil et la suppression
        du brouillon sont réalisés dans une même
        transaction SQLite.
        """

        user_id = self._normaliser_user_id(
            user_id
        )

        last_name = self._normaliser_nom(
            last_name,
            "last_name"
        )

        with closing(self._connect()) as connexion:

            with connexion:

                # Empêcher une autre écriture concurrente
                # de modifier la collecte pendant sa validation.

                connexion.execute(
                    "BEGIN IMMEDIATE"
                )

                # --------------------------------------------
                # Récupération du prénom temporaire
                # --------------------------------------------

                ligne = connexion.execute(
                    """
                    SELECT first_name

                    FROM personalization_drafts

                    WHERE user_id = ?
                    """,
                    (user_id,)
                ).fetchone()

                if (
                    ligne is None
                    or ligne["first_name"] is None
                ):

                    raise RuntimeError(
                        "La collecte du prénom "
                        "doit être terminée avant "
                        "la validation du nom."
                    )

                first_name = ligne[
                    "first_name"
                ]

                # --------------------------------------------
                # Enregistrement définitif de l'identité
                # --------------------------------------------

                connexion.execute(
                    """
                    INSERT INTO user_profiles (
                        user_id,
                        first_name,
                        last_name,
                        personalization_status
                    )

                    VALUES (?, ?, ?, ?)

                    ON CONFLICT(user_id)

                    DO UPDATE SET

                        first_name =
                            excluded.first_name,

                        last_name =
                            excluded.last_name,

                        personalization_status =
                            excluded.personalization_status
                    """,
                    (
                        user_id,
                        first_name,
                        last_name,
                        STATUS_ACCEPTED
                    )
                )

                # --------------------------------------------
                # Suppression du brouillon
                # --------------------------------------------

                connexion.execute(
                    """
                    DELETE FROM personalization_drafts

                    WHERE user_id = ?
                    """,
                    (user_id,)
                )

        return self.charger_profil(
            user_id
        )


    # ========================================================
    # 16. ANNULATION DE LA COLLECTE
    # ========================================================

    def annuler_collecte(
        self,
        user_id
    ) -> bool:

        """
        Annule la collecte en cours.

        Le profil définitif, s'il existe,
        reste intégralement conservé.

        Retourne True si un brouillon a été supprimé.
        """

        user_id = self._normaliser_user_id(
            user_id
        )

        with closing(self._connect()) as connexion:

            with connexion:

                resultat = connexion.execute(
                    """
                    DELETE FROM personalization_drafts

                    WHERE user_id = ?
                    """,
                    (user_id,)
                )

                collecte_supprimee = (
                    resultat.rowcount > 0
                )

        return collecte_supprimee