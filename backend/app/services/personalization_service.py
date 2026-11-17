
# -*- coding: utf-8 -*-

"""
XamMeteo — Service de personnalisation par formulaire web.

Responsabilités :
- générer des tokens sécurisés ;
- vérifier leur validité ;
- charger le profil associé ;
- enregistrer ou modifier une identité ;
- invalider les tokens après validation ou annulation.

Ce module ne réalise aucun traitement météorologique.
"""

import hashlib
import re
import secrets
import time
import unicodedata

from contextlib import closing

from backend.app.services.user_profile_service import (
    UserProfileStore,
    STATUS_ACCEPTED,
)


# ============================================================
# 1. CONFIGURATION
# ============================================================

DEFAULT_TOKEN_TTL_SECONDS = 15 * 60

TOKEN_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{43}$"
)


# ============================================================
# 2. EXCEPTION MÉTIER
# ============================================================

class PersonalizationTokenError(ValueError):

    """
    Token inexistant, expiré, annulé ou déjà utilisé.
    """

    pass


# ============================================================
# 3. SERVICE DE PERSONNALISATION
# ============================================================

class PersonalizationService:

    def __init__(
        self,
        profile_store=None,
        ttl_seconds=DEFAULT_TOKEN_TTL_SECONDS,
        clock=None,
    ):

        if (
            not isinstance(ttl_seconds, int)
            or isinstance(ttl_seconds, bool)
            or ttl_seconds <= 0
        ):

            raise ValueError(
                "La durée de validité doit être positive."
            )

        self.profile_store = (
            profile_store
            if profile_store is not None
            else UserProfileStore()
        )

        self.ttl_seconds = ttl_seconds

        self.clock = (
            clock
            if clock is not None
            else time.time
        )

        self.initialiser_base()


    # ========================================================
    # 4. INITIALISATION DE LA TABLE
    # ========================================================

    def initialiser_base(self):

        """
        Ajoute la table des tokens dans la base existante.

        Les profils et les brouillons ne sont pas modifiés.
        """

        with closing(
            self.profile_store._connect()
        ) as connexion:

            with connexion:

                connexion.execute(
                    """
                    CREATE TABLE IF NOT EXISTS
                    personalization_tokens (

                        user_id TEXT PRIMARY KEY,

                        token_hash TEXT NOT NULL UNIQUE,

                        created_at REAL NOT NULL,

                        expires_at REAL NOT NULL,

                        CHECK (
                            length(token_hash) = 64
                        ),

                        CHECK (
                            expires_at > created_at
                        )

                    )
                    """
                )

                connexion.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_personalization_tokens_expiration

                    ON personalization_tokens (
                        expires_at
                    )
                    """
                )


    # ========================================================
    # 5. EMPREINTE DU TOKEN
    # ========================================================

    @staticmethod
    def _calculer_empreinte(token):

        """
        Retourne l'empreinte SHA-256 du token.

        Le token brut n'est jamais enregistré dans SQLite.
        """

        if (
            not isinstance(token, str)
            or not TOKEN_PATTERN.fullmatch(token)
        ):

            raise PersonalizationTokenError(
                "Lien de personnalisation invalide."
            )

        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()


    # ========================================================
    # 6. VALIDATION DES INFORMATIONS PERSONNELLES
    # ========================================================

    def _valider_nom(self, valeur, champ):

        """
        Vérifie et normalise un prénom ou un nom.

        Autorise les lettres Unicode, les espaces,
        les tirets et les apostrophes.
        """

        if not isinstance(valeur, str):

            raise TypeError(
                f"{champ} doit être une chaîne de caractères."
            )

        valeur = unicodedata.normalize(
            "NFC",
            valeur
        )

        valeur = self.profile_store._normaliser_nom(
            valeur,
            champ
        )

        if not any(
            caractere.isalpha()
            for caractere in valeur
        ):

            raise ValueError(
                f"{champ} doit contenir des lettres."
            )

        for caractere in valeur:

            autorise = (

                caractere.isalpha()

                or unicodedata.category(
                    caractere
                ).startswith("M")

                or caractere in (
                    " ",
                    "-",
                    "'",
                    "’",
                )
            )

            if not autorise:

                raise ValueError(
                    f"{champ} contient des caractères invalides."
                )

        return valeur


    # ========================================================
    # 7. GÉNÉRATION DU TOKEN
    # ========================================================

    def generer_token(self, user_id):

        """
        Génère un nouveau token pour un utilisateur.

        Un ancien token associé au même utilisateur
        devient automatiquement invalide.

        Le profil définitif reste inchangé.
        """

        user_id = (
            self.profile_store._normaliser_user_id(
                user_id
            )
        )

        token = secrets.token_urlsafe(32)

        token_hash = self._calculer_empreinte(
            token
        )

        with closing(
            self.profile_store._connect()
        ) as connexion:

            with connexion:

                connexion.execute(
                    "BEGIN IMMEDIATE"
                )

                maintenant = float(
                    self.clock()
                )

                expiration = (
                    maintenant
                    + self.ttl_seconds
                )

                # Supprimer les tokens expirés.

                connexion.execute(
                    """
                    DELETE FROM personalization_tokens

                    WHERE expires_at <= ?
                    """,

                    (maintenant,)
                )

                # Créer ou remplacer le token utilisateur.

                connexion.execute(
                    """
                    INSERT INTO personalization_tokens (

                        user_id,

                        token_hash,

                        created_at,

                        expires_at

                    )

                    VALUES (?, ?, ?, ?)

                    ON CONFLICT(user_id)

                    DO UPDATE SET

                        token_hash =
                            excluded.token_hash,

                        created_at =
                            excluded.created_at,

                        expires_at =
                            excluded.expires_at
                    """,

                    (
                        user_id,
                        token_hash,
                        maintenant,
                        expiration,
                    )
                )

        return token


    # ========================================================
    # 8. VÉRIFICATION DU TOKEN
    # ========================================================

    def _charger_token_valide(
        self,
        connexion,
        token_hash
    ):

        """
        Charge un token encore valide.

        Cette méthode utilise la connexion fournie
        afin de pouvoir participer à une transaction.
        """

        maintenant = float(
            self.clock()
        )

        ligne = connexion.execute(
            """
            SELECT

                user_id,

                expires_at

            FROM personalization_tokens

            WHERE token_hash = ?

            AND expires_at > ?
            """,

            (
                token_hash,
                maintenant,
            )

        ).fetchone()

        if ligne is None:

            raise PersonalizationTokenError(
                "Ce lien est invalide, expiré "
                "ou déjà utilisé."
            )

        return ligne


    # ========================================================
    # 9. CHARGEMENT DU FORMULAIRE
    # ========================================================

    def charger_formulaire(self, token):

        """
        Retourne les informations nécessaires
        à l'affichage du formulaire.

        Ne consomme pas le token.
        Ne modifie pas le profil.
        """

        token_hash = self._calculer_empreinte(
            token
        )

        maintenant = float(
            self.clock()
        )

        with closing(
            self.profile_store._connect()
        ) as connexion:

            ligne = connexion.execute(
                """
                SELECT

                    p.first_name,

                    p.last_name,

                    p.personalization_status,

                    t.expires_at

                FROM personalization_tokens AS t

                LEFT JOIN user_profiles AS p

                    ON p.user_id = t.user_id

                WHERE t.token_hash = ?

                AND t.expires_at > ?
                """,

                (
                    token_hash,
                    maintenant,
                )

            ).fetchone()

        if ligne is None:

            raise PersonalizationTokenError(
                "Ce lien est invalide, expiré "
                "ou déjà utilisé."
            )

        modification = (

            ligne["personalization_status"]
            == STATUS_ACCEPTED
        )

        return {

            "mode": (
                "modification"
                if modification
                else "creation"
            ),

            "first_name": (
                ligne["first_name"]
                or ""
            ),

            "last_name": (
                ligne["last_name"]
                or ""
            ),

            "button_label": (

                "Modifier mes informations personnelles"

                if modification

                else "Valider mes informations"
            ),

            "expires_at":
                ligne["expires_at"],
        }


    # ========================================================
    # 10. VALIDATION ET ENREGISTREMENT
    # ========================================================

    def valider_formulaire(
        self,
        token,
        first_name,
        last_name
    ):

        """
        Enregistre ou remplace l'identité utilisateur.

        Les opérations suivantes sont atomiques :

        1. Vérification du token.
        2. Enregistrement du profil.
        3. Suppression de l'ancien brouillon.
        4. Consommation du token.

        En cas d'échec, la transaction entière est annulée.
        """

        token_hash = self._calculer_empreinte(
            token
        )

        first_name = self._valider_nom(
            first_name,
            "first_name"
        )

        last_name = self._valider_nom(
            last_name,
            "last_name"
        )

        with closing(
            self.profile_store._connect()
        ) as connexion:

            with connexion:

                connexion.execute(
                    "BEGIN IMMEDIATE"
                )

                ligne = self._charger_token_valide(
                    connexion,
                    token_hash
                )

                user_id = ligne["user_id"]

                # Identifier le mode réel de l'opération.

                ancien_profil = connexion.execute(
                    """
                    SELECT personalization_status

                    FROM user_profiles

                    WHERE user_id = ?
                    """,

                    (user_id,)

                ).fetchone()

                modification = (

                    ancien_profil is not None

                    and ancien_profil[
                        "personalization_status"
                    ] == STATUS_ACCEPTED
                )

                # Enregistrer ou remplacer le profil.

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
                        STATUS_ACCEPTED,
                    )
                )

                # Supprimer une éventuelle ancienne collecte.

                connexion.execute(
                    """
                    DELETE FROM personalization_drafts

                    WHERE user_id = ?
                    """,

                    (user_id,)
                )

                # Consommer définitivement le token.

                resultat = connexion.execute(
                    """
                    DELETE FROM personalization_tokens

                    WHERE user_id = ?

                    AND token_hash = ?
                    """,

                    (
                        user_id,
                        token_hash,
                    )
                )

                if resultat.rowcount != 1:

                    raise PersonalizationTokenError(
                        "Le token ne peut pas être consommé."
                    )

        return {

            "user_id":
                user_id,

            "first_name":
                first_name,

            "last_name":
                last_name,

            "personalization_status":
                STATUS_ACCEPTED,

            "personalization_offer_seen":
                True,

            "mode": (
                "modification"
                if modification
                else "creation"
            ),
        }


    # ========================================================
    # 11. ANNULATION DU FORMULAIRE
    # ========================================================

    def annuler_formulaire(self, token):

        """
        Invalide le token sans modifier le profil.

        Retourne True si le token était valide.

        Retourne False s'il était déjà inutilisable.
        """

        token_hash = self._calculer_empreinte(
            token
        )

        with closing(
            self.profile_store._connect()
        ) as connexion:

            with connexion:

                connexion.execute(
                    "BEGIN IMMEDIATE"
                )

                maintenant = float(
                    self.clock()
                )

                resultat = connexion.execute(
                    """
                    DELETE FROM personalization_tokens

                    WHERE token_hash = ?

                    AND expires_at > ?
                    """,

                    (
                        token_hash,
                        maintenant,
                    )
                )

                return resultat.rowcount == 1


    # ========================================================
    # 12. INVALIDATION PAR UTILISATEUR
    # ========================================================

    def invalider_tokens_utilisateur(
        self,
        user_id
    ):

        """
        Invalide le formulaire actif d'un utilisateur.

        Sera notamment utilisé lors d'un refus
        explicite de personnalisation.
        """

        user_id = (
            self.profile_store._normaliser_user_id(
                user_id
            )
        )

        with closing(
            self.profile_store._connect()
        ) as connexion:

            with connexion:

                resultat = connexion.execute(
                    """
                    DELETE FROM personalization_tokens

                    WHERE user_id = ?
                    """,

                    (user_id,)
                )

                return resultat.rowcount > 0
