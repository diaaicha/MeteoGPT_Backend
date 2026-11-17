
# -*- coding: utf-8 -*-

"""
Routes de personnalisation par formulaire web.

Ces routes ne réalisent aucun traitement météorologique.
Elles utilisent le service de personnalisation sécurisé.
"""
import re
import secrets
import logging

from fastapi import BackgroundTasks

from pathlib import Path

from fastapi.responses import HTMLResponse

from backend.app.core.config import get_settings
import json

from functools import lru_cache

from fastapi import (
    APIRouter,
    Depends,
    Request,
)

from fastapi.responses import JSONResponse

from starlette.concurrency import run_in_threadpool

from backend.app.services.personalization_service import (
    PersonalizationService,
    PersonalizationTokenError,
)




logger = logging.getLogger(__name__)

# ============================================================
# 1. CONFIGURATION
# ============================================================

router = APIRouter(
    prefix="/personnalisation",
    tags=["Personnalisation"],
)

MAX_BODY_SIZE = 4096

SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


# ============================================================
# 2. SERVICE
# ============================================================

@lru_cache(maxsize=1)
def get_personalization_service():

    return PersonalizationService()


# ============================================================
# 3. RÉPONSES HTTP
# ============================================================

def reponse_json(
    contenu,
    status_code=200,
):

    return JSONResponse(
        content=contenu,
        status_code=status_code,
        headers=SECURITY_HEADERS,
    )


def reponse_erreur(
    message,
    status_code=400,
):

    return reponse_json(
        {
            "success": False,
            "message": message,
        },
        status_code=status_code,
    )


def reponse_token_invalide():

    return reponse_erreur(
        (
            "Ce lien est invalide, expiré "
            "ou déjà utilisé. Demandez un nouveau "
            "formulaire sur WhatsApp."
        ),
        status_code=410,
    )


# ============================================================
# 4. LECTURE SÉCURISÉE DES DONNÉES
# ============================================================

async def lire_donnees_json(
    request: Request,
    champs_attendus: set[str],
):

    """
    Accepte uniquement un corps JSON de taille limitée.

    Les valeurs reçues ne sont jamais reproduites
    dans les messages d'erreur.
    """

    content_type = (
        request.headers.get(
            "content-type",
            ""
        )
        .split(";")[0]
        .strip()
        .lower()
    )

    if content_type != "application/json":

        raise ValueError(
            "Le format JSON est obligatoire."
        )

    contenu = bytearray()

    async for bloc in request.stream():

        if (
            len(contenu) + len(bloc)
            > MAX_BODY_SIZE
        ):

            raise ValueError(
                "La requête est trop volumineuse."
            )

        contenu.extend(bloc)

    try:

        donnees = json.loads(
            contenu
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        RecursionError,
    ):

        raise ValueError(
            "Le contenu JSON est invalide."
        )

    if not isinstance(
        donnees,
        dict
    ):

        raise ValueError(
            "Un objet JSON est attendu."
        )

    if set(donnees) != champs_attendus:

        raise ValueError(
            "Les champs transmis sont invalides."
        )

    return donnees


# ============================================================
# 5. OUVERTURE DU FORMULAIRE
# ============================================================

@router.post(
    "/ouvrir",
    summary="Charger le formulaire de personnalisation",
)
async def ouvrir_formulaire(

    request: Request,

    service: PersonalizationService = Depends(
        get_personalization_service
    ),

):

    """
    Vérifie le token et récupère les informations
    nécessaires au formulaire.

    Le token reste utilisable après l'ouverture.
    """

    try:

        donnees = await lire_donnees_json(
            request,
            {"token"},
        )

        formulaire = await run_in_threadpool(
            service.charger_formulaire,
            donnees["token"],
        )

        return reponse_json(
            {
                "success": True,
                "formulaire": formulaire,
            }
        )

    except PersonalizationTokenError:

        return reponse_token_invalide()

    except ValueError:

        return reponse_erreur(
            "La requête est invalide."
        )


# ============================================================
# NOTIFICATION WHATSAPP APRES VALIDATION
# ============================================================

def notifier_validation_whatsapp(
    resultat: dict,
) -> bool:

    """
    Envoie une confirmation après l'enregistrement
    définitif des informations personnelles.

    Une erreur WhatsApp ne doit jamais annuler
    l'enregistrement du profil.
    """

    from backend.app.services.whatsapp_service import (
        send_whatsapp_text_message,
    )

    user_id = resultat["user_id"]

    first_name = resultat["first_name"]

    last_name = resultat["last_name"]

    modification = (
        resultat["mode"] == "modification"
    )

    if modification:

        message = (

            f"C'est noté, {first_name} {last_name} ! ✨\n\n"

            "Vos informations personnelles ont "
            "bien été modifiées.\n\n"

            "Vous pouvez continuer à me poser "
            "toutes vos questions météorologiques."
        )

    else:

        message = (

            f"Merci, {first_name} {last_name} ! ✨\n\n"

            "Vos informations personnelles ont "
            "bien été enregistrées.\n\n"

            "Votre expérience est désormais "
            "personnalisée.\n\n"

            "Vous pouvez me poser toutes vos "
            "questions météorologiques."
        )

    try:

        send_whatsapp_text_message(

            recipient=user_id,

            text=message,
        )

        return True

    except Exception as exc:

        logger.warning(

            "Echec de la notification WhatsApp "
            "apres validation du profil | "
            "error_type=%s",

            type(exc).__name__,
        )

        return False



# ============================================================
# 6. VALIDATION DU FORMULAIRE
# ============================================================

@router.post(
    "/valider",
    summary="Enregistrer les informations personnelles",
)
async def valider_formulaire(

    request: Request,

    background_tasks: BackgroundTasks,

    service: PersonalizationService = Depends(
        get_personalization_service
    ),

):

    """
    Enregistre ou modifie l'identité utilisateur.

    Le token est consommé définitivement après
    l'enregistrement réussi.

    Une confirmation WhatsApp est ensuite envoyée.
    """

    try:

        donnees = await lire_donnees_json(

            request,

            {
                "token",
                "first_name",
                "last_name",
            },
        )

        # ====================================================
        # 1. ENREGISTREMENT ATOMIQUE DU PROFIL
        # ====================================================

        resultat = await run_in_threadpool(

            service.valider_formulaire,

            donnees["token"],

            donnees["first_name"],

            donnees["last_name"],
        )

        # ====================================================
        # 2. MESSAGE DE CONFIRMATION WEB
        # ====================================================

        if resultat["mode"] == "modification":

            message = (

                "Vos informations ont bien été "
                "modifiées."
            )

        else:

            message = (

                "Vos informations ont bien été "
                "enregistrées."
            )

        # ====================================================
        # 3. NOTIFICATION WHATSAPP
        # ====================================================

        background_tasks.add_task(

            notifier_validation_whatsapp,

            resultat,
        )

        # ====================================================
        # 4. REPONSE AU FORMULAIRE
        # ====================================================

        return reponse_json(

            {

                "success": True,

                "mode": resultat["mode"],

                "first_name": resultat["first_name"],

                "last_name": resultat["last_name"],

                "message": message,
            }
        )

    except PersonalizationTokenError:

        return reponse_token_invalide()

    except (
        ValueError,
        TypeError,
    ):

        return reponse_erreur(

            (

                "Veuillez vérifier votre prénom "
                "et votre nom. Utilisez uniquement "
                "des lettres, des espaces, des tirets "
                "ou des apostrophes."
            ),

            status_code=422,
        )



# ============================================================
# 7. ANNULATION DU FORMULAIRE
# ============================================================

@router.post(
    "/annuler",
    summary="Annuler la personnalisation",
)
async def annuler_formulaire(

    request: Request,

    service: PersonalizationService = Depends(
        get_personalization_service
    ),

):

    """
    Invalide le formulaire actif.

    Le profil définitif reste inchangé.
    """

    try:

        donnees = await lire_donnees_json(
            request,
            {"token"},
        )

        annule = await run_in_threadpool(

            service.annuler_formulaire,

            donnees["token"],
        )

        if not annule:

            return reponse_token_invalide()

        return reponse_json(
            {
                "success": True,

                "message": (
                    "Personnalisation annulée. "
                    "Vos informations restent "
                    "inchangées."
                ),
            }
        )

    except PersonalizationTokenError:

        return reponse_token_invalide()

    except ValueError:

        return reponse_erreur(
            "La requête est invalide."
        )

# ============================================================
# 8. AFFICHAGE DU FORMULAIRE HTML
# ============================================================

@router.get(
    "",
    response_class=HTMLResponse,
    summary="Afficher le formulaire de personnalisation",
)
def afficher_formulaire():

    """
    Retourne la page HTML de personnalisation.

    Le token est récupéré côté navigateur depuis
    le fragment de l'URL.

    Aucun profil n'est modifié par cette route.
    """

    template_path = (

        Path(__file__).resolve().parents[2]

        / "templates"

        / "personalization.html"
    )

    if not template_path.is_file():

        return HTMLResponse(

            content=(
                "Le formulaire de personnalisation "
                "est indisponible."
            ),

            status_code=503,

            headers=SECURITY_HEADERS,
        )

    html = template_path.read_text(
        encoding="utf-8"
    )

    # ========================================================
    # 1. LIEN DE RETOUR WHATSAPP
    # ========================================================

    settings = get_settings()

    numero = (
        settings.whatsapp_public_number
        or ""
    ).strip()

    return_url = ""

    if re.fullmatch(
        r"[1-9][0-9]{7,14}",
        numero,
    ):

        return_url = (
            "https://wa.me/"
            + numero
        )

    # ========================================================
    # 2. PROTECTION DU HTML
    # ========================================================

    nonce = secrets.token_urlsafe(24)

    html = html.replace(

        "__CSP_NONCE__",

        nonce,
    )

    html = html.replace(

        "__WHATSAPP_RETURN_URL__",

        return_url,
    )

    headers = {

        **SECURITY_HEADERS,

        "Content-Security-Policy": (

            "default-src 'none'; "

            f"script-src 'nonce-{nonce}'; "

            f"style-src 'nonce-{nonce}'; "

            "connect-src 'self'; "

            "base-uri 'none'; "

            "frame-ancestors 'none'; "

            "form-action 'none'"
        ),
    }

    # ========================================================
    # 3. RETOURNER LA PAGE
    # ========================================================

    return HTMLResponse(

        content=html,

        headers=headers,
    )