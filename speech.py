
# ============================================================
# METEOGPT — SPEECH MODULE
# ============================================================

import os
import re
import time
import base64
import mimetypes
import wave

from dotenv import load_dotenv
from pathlib import Path

from google import genai
from google.genai import types

load_dotenv()
# ============================================================
# 1. CONFIGURATION
# ============================================================

STT_MODEL = "gemini-3.5-transcribe"

TTS_MODEL = "gemini-3.1-flash-tts-preview"


SPEECH_TIMEOUT_MS = 30_000

PROJECT_ROOT = Path(__file__).resolve().parent
# ============================================================
# 2. CONFIGURATION STT
# ============================================================

STT_LANGUAGE_CODES = []

STT_MODE = "smart"

STT_CUSTOM_VOCABULARY = [
    "ANACIM",
    "MeteoGPT",
]


# ============================================================
# 3. CONFIGURATION TTS
# ============================================================

TTS_VOICE = "Kore"

TTS_SAMPLE_RATE = 24_000

TTS_CHANNELS = 1

TTS_SAMPLE_WIDTH = 2

TTS_OUTPUT_MIME_TYPE = "audio/wav"


# ============================================================
# 4. DOSSIER AUDIO
# ============================================================

DEFAULT_TTS_OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "audio"
    / "generated"
)

DEFAULT_TTS_OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

# ============================================================
# 5. FORMATS AUDIO ACCEPTÉS
# ============================================================

SUPPORTED_AUDIO_MIME_TYPES = {

    "audio/wav",
    "audio/mp3",
    "audio/aiff",
    "audio/aac",
    "audio/ogg",
    "audio/flac",
    "audio/mpeg",
    "audio/m4a",
    "audio/l16",
    "audio/opus",
    "audio/alaw",
    "audio/mulaw",
    "audio/webm",
}


AUDIO_MIME_ALIASES = {

    "audio/x-wav":
        "audio/wav",

    "audio/x-m4a":
        "audio/m4a",

    "audio/mp4":
        "audio/m4a",
}


# ============================================================
# 6. CLÉ API
# ============================================================

def charger_gemini_api_key_speech():
    """
    Récupère la clé Gemini depuis l'environnement backend.
    """

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "Clé GEMINI_API_KEY introuvable."
        )

    return api_key

# ============================================================
# 7. CLIENT GEMINI SPEECH
# ============================================================

def creer_client_speech(
    api_key=None
):
    """
    Crée un client Gemini pour la couche Speech.
    """

    if api_key is None:

        api_key = (
            charger_gemini_api_key_speech()
        )


    return genai.Client(

        api_key=api_key,

        http_options=
            types.HttpOptions(

                timeout=
                    SPEECH_TIMEOUT_MS,

                retry_options=
                    types.HttpRetryOptions(
                        attempts=1
                    )
            )
    )


# ============================================================
# 8. MIME AUDIO
# ============================================================

def detecter_mime_audio(
    audio_path
):
    """
    Détecte et normalise le type MIME d'un fichier audio.
    """

    path = Path(
        audio_path
    )


    mime_type = (
        mimetypes.guess_type(
            str(path)
        )[0]
    )


    if mime_type:

        mime_type = (
            AUDIO_MIME_ALIASES.get(
                mime_type,
                mime_type
            )
        )


    return mime_type


# ============================================================
# 9. VALIDATION AUDIO
# ============================================================

def valider_audio(
    audio_path
):
    """
    Vérifie qu'un fichier audio peut être traité par le STT.
    """

    path = Path(
        audio_path
    )


    # --------------------------------------------------------
    # Existence
    # --------------------------------------------------------

    if not path.exists():

        return {

            "valid":
                False,

            "path":
                str(path),

            "mime_type":
                None,

            "size_bytes":
                0,

            "error":
                "file_not_found",
        }


    # --------------------------------------------------------
    # Type fichier
    # --------------------------------------------------------

    if not path.is_file():

        return {

            "valid":
                False,

            "path":
                str(path),

            "mime_type":
                None,

            "size_bytes":
                0,

            "error":
                "not_a_file",
        }


    # --------------------------------------------------------
    # Taille
    # --------------------------------------------------------

    size_bytes = (
        path.stat().st_size
    )


    if size_bytes <= 0:

        return {

            "valid":
                False,

            "path":
                str(path),

            "mime_type":
                None,

            "size_bytes":
                size_bytes,

            "error":
                "empty_file",
        }


    # --------------------------------------------------------
    # MIME
    # --------------------------------------------------------

    mime_type = (
        detecter_mime_audio(
            path
        )
    )


    if (
        mime_type
        not in
        SUPPORTED_AUDIO_MIME_TYPES
    ):

        return {

            "valid":
                False,

            "path":
                str(path),

            "mime_type":
                mime_type,

            "size_bytes":
                size_bytes,

            "error":
                "unsupported_audio_format",
        }


    # --------------------------------------------------------
    # OK
    # --------------------------------------------------------

    return {

        "valid":
            True,

        "path":
            str(path),

        "mime_type":
            mime_type,

        "size_bytes":
            size_bytes,

        "error":
            None,
    }


# ============================================================
# 10. CLASSIFICATION DES ERREURS
# ============================================================

def classifier_erreur_speech(
    exception
):
    """
    Classe les principales erreurs Gemini Speech.
    """

    message = str(
        exception
    ).lower()


    status_code = getattr(
        exception,
        "status_code",
        None
    )


    # --------------------------------------------------------
    # Quota
    # --------------------------------------------------------

    if (
        status_code == 429
        or
        "429" in message
        or
        "quota" in message
        or
        "resource_exhausted" in message
    ):

        return "rate_limit"


    # --------------------------------------------------------
    # Service indisponible
    # --------------------------------------------------------

    if (
        status_code == 503
        or
        "503" in message
        or
        "unavailable" in message
    ):

        return "service_unavailable"


    # --------------------------------------------------------
    # Timeout
    # --------------------------------------------------------

    if (
        "timeout" in message
        or
        "timed out" in message
        or
        "deadline" in message
    ):

        return "timeout"


    # --------------------------------------------------------
    # Authentification
    # --------------------------------------------------------

    if (
        status_code in {
            401,
            403,
        }
        or
        "api key" in message
        or
        "permission" in message
    ):

        return "authentication"


    return "api_error"


# ============================================================
# 11. SPEECH-TO-TEXT
# ============================================================

def transcribe_audio(
    audio_path,
    client=None
):
    """
    Convertit un fichier audio en texte.

    Étapes :
    1. validation locale ;
    2. upload temporaire ;
    3. transcription Gemini ;
    4. suppression du fichier distant ;
    5. retour structuré.
    """

    debut = (
        time.perf_counter()
    )


    # ========================================================
    # VALIDATION
    # ========================================================

    validation = (
        valider_audio(
            audio_path
        )
    )


    if not validation[
        "valid"
    ]:

        return {

            "success":
                False,

            "text":
                "",

            "model":
                STT_MODEL,

            "audio_path":
                str(
                    audio_path
                ),

            "mime_type":
                validation.get(
                    "mime_type"
                ),

            "latency_ms":
                (
                    time.perf_counter()
                    -
                    debut
                ) * 1000,

            "error":
                validation[
                    "error"
                ],
        }


    # ========================================================
    # CLIENT — CRÉATION LAZY
    # ========================================================

    try:

        active_client = (
            client
            or
            creer_client_speech()
        )

    except Exception as exception:

        return {

            "success":
                False,

            "text":
                "",

            "model":
                STT_MODEL,

            "audio_path":
                validation[
                    "path"
                ],

            "mime_type":
                validation[
                    "mime_type"
                ],

            "latency_ms":
                (
                    time.perf_counter()
                    -
                    debut
                ) * 1000,

            "error":
                classifier_erreur_speech(
                    exception
                ),

            "error_detail":
                str(exception)[:500],
        }


    uploaded_file = None


    try:

        # ====================================================
        # UPLOAD TEMPORAIRE
        # ====================================================

        uploaded_file = (
            active_client.files.upload(

                file=
                    validation[
                        "path"
                    ]
            )
        )


        # ====================================================
        # TRANSCRIPTION
        # ====================================================

        interaction = (
            active_client.interactions.create(

                model=
                    STT_MODEL,

                input=[
                    {
                        "type":
                            "audio",

                        "uri":
                            uploaded_file.uri,

                        "mime_type":
                            uploaded_file.mime_type,
                    }
                ],

                generation_config={
                    "transcription_config": {

                        "language_codes":
                            STT_LANGUAGE_CODES,

                        "custom_vocabulary":
                            STT_CUSTOM_VOCABULARY,

                        "mode":
                            STT_MODE,
                    }
                },
            )
        )


        # ====================================================
        # EXTRACTION DU TEXTE
        # ====================================================

        texte = (
            getattr(
                interaction,
                "output_text",
                None
            )
            or
            ""
        ).strip()


        latence_ms = (
            time.perf_counter()
            -
            debut
        ) * 1000


        if not texte:

            return {

                "success":
                    False,

                "text":
                    "",

                "model":
                    STT_MODEL,

                "audio_path":
                    validation[
                        "path"
                    ],

                "mime_type":
                    validation[
                        "mime_type"
                    ],

                "latency_ms":
                    latence_ms,

                "error":
                    "empty_transcription",
            }


        return {

            "success":
                True,

            "text":
                texte,

            "model":
                STT_MODEL,

            "audio_path":
                validation[
                    "path"
                ],

            "mime_type":
                validation[
                    "mime_type"
                ],

            "latency_ms":
                latence_ms,

            "error":
                None,
        }


    except Exception as exception:

        return {

            "success":
                False,

            "text":
                "",

            "model":
                STT_MODEL,

            "audio_path":
                validation[
                    "path"
                ],

            "mime_type":
                validation[
                    "mime_type"
                ],

            "latency_ms":
                (
                    time.perf_counter()
                    -
                    debut
                ) * 1000,

            "error":
                classifier_erreur_speech(
                    exception
                ),

            "error_detail":
                str(
                    exception
                )[:500],
        }


    finally:

        # ====================================================
        # NETTOYAGE DU FICHIER GEMINI
        # ====================================================

        if (
            uploaded_file
            is not None
            and
            getattr(
                uploaded_file,
                "name",
                None
            )
        ):

            try:

                active_client.files.delete(
                    name=
                        uploaded_file.name
                )

            except Exception:

                pass


# ============================================================
# 12. PRÉPARATION DU TEXTE TTS
# ============================================================

def preparer_texte_tts(
    texte: str
) -> str:
    """
    Prépare légèrement une réponse MeteoGPT
    avant synthèse vocale.

    Aucun contenu météorologique n'est reformulé.
    """

    if not isinstance(
        texte,
        str
    ):

        raise TypeError(
            "texte doit être une chaîne de caractères."
        )


    texte = texte.strip()


    if not texte:

        raise ValueError(
            "texte ne peut pas être vide."
        )


    # --------------------------------------------------------
    # Markdown gras / italique
    # --------------------------------------------------------

    texte = re.sub(
        r"\*\*(.*?)\*\*",
        r"\1",
        texte
    )


    texte = re.sub(
        r"__(.*?)__",
        r"\1",
        texte
    )


    texte = re.sub(
        r"\*(.*?)\*",
        r"\1",
        texte
    )


    # --------------------------------------------------------
    # Titres Markdown
    # --------------------------------------------------------

    texte = re.sub(
        r"(?m)^\s*#{1,6}\s*",
        "",
        texte
    )


    # --------------------------------------------------------
    # Puces simples
    # --------------------------------------------------------

    texte = re.sub(
        r"(?m)^\s*[-•]\s+",
        "",
        texte
    )


    # --------------------------------------------------------
    # Espaces
    # --------------------------------------------------------

    texte = re.sub(
        r"[ \t]+",
        " ",
        texte
    )


    texte = re.sub(
        r"\n{3,}",
        "\n\n",
        texte
    )


    return texte.strip()


# ============================================================
# 13. SAUVEGARDE PCM → WAV
# ============================================================

def sauvegarder_pcm_wav(
    pcm_data,
    output_path,
    *,
    channels=TTS_CHANNELS,
    rate=TTS_SAMPLE_RATE,
    sample_width=TTS_SAMPLE_WIDTH
):
    """
    Encapsule des données PCM brutes
    dans un fichier WAV.
    """

    if not isinstance(
        pcm_data,
        (bytes, bytearray)
    ):

        raise TypeError(
            "pcm_data doit contenir des données binaires."
        )


    if not pcm_data:

        raise ValueError(
            "pcm_data ne peut pas être vide."
        )


    output_path = Path(
        output_path
    )


    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with wave.open(
        str(output_path),
        "wb"
    ) as wav_file:

        wav_file.setnchannels(
            channels
        )

        wav_file.setsampwidth(
            sample_width
        )

        wav_file.setframerate(
            rate
        )

        wav_file.writeframes(
            pcm_data
        )


    return str(
        output_path
    )


# ============================================================
# 14. TEXT-TO-SPEECH
# ============================================================

def synthesize_speech(
    texte,
    output_path=None,
    *,
    voice=TTS_VOICE,
    client=None
):
    """
    Convertit une réponse textuelle MeteoGPT
    en fichier audio WAV.
    """

    debut = (
        time.perf_counter()
    )


    # ========================================================
    # PRÉPARATION DU TEXTE
    # ========================================================

    try:

        texte_prepare = (
            preparer_texte_tts(
                texte
            )
        )

    except Exception as exception:

        return {

            "success":
                False,

            "audio_path":
                None,

            "model":
                TTS_MODEL,

            "voice":
                voice,

            "text":
                "",

            "latency_ms":
                (
                    time.perf_counter()
                    -
                    debut
                ) * 1000,

            "error":
                "invalid_text",

            "error_detail":
                str(
                    exception
                )[:500],
        }


    # ========================================================
    # CHEMIN DE SORTIE
    # ========================================================

    if output_path is None:

        timestamp = int(
            time.time() * 1000
        )


        output_path = (
            DEFAULT_TTS_OUTPUT_DIR
            /
            f"meteogpt_tts_{timestamp}.wav"
        )

    else:

        output_path = Path(
            output_path
        )


    # ========================================================
    # CLIENT — CRÉATION LAZY
    # ========================================================

    try:

        active_client = (
            client
            or
            creer_client_speech()
        )

    except Exception as exception:

        return {

            "success":
                False,

            "audio_path":
                None,

            "model":
                TTS_MODEL,

            "voice":
                voice,

            "text":
                texte_prepare,

            "latency_ms":
                (
                    time.perf_counter()
                    -
                    debut
                ) * 1000,

            "error":
                classifier_erreur_speech(
                    exception
                ),

            "error_detail":
                str(
                    exception
                )[:500],
        }


    # ========================================================
    # APPEL TTS
    # ========================================================

    try:

        interaction = (
            active_client.interactions.create(

                model=
                    TTS_MODEL,

                input=
                    texte_prepare,

                response_format={
                    "type":
                        "audio"
                },

                generation_config={

                    "speech_config": [

                        {
                            "voice":
                                voice
                        }
                    ]
                },
            )
        )


        # ====================================================
        # RÉCUPÉRATION AUDIO
        # ====================================================

        output_audio = getattr(
            interaction,
            "output_audio",
            None
        )


        if output_audio is None:

            return {

                "success":
                    False,

                "audio_path":
                    None,

                "model":
                    TTS_MODEL,

                "voice":
                    voice,

                "text":
                    texte_prepare,

                "latency_ms":
                    (
                        time.perf_counter()
                        -
                        debut
                    ) * 1000,

                "error":
                    "empty_audio_response",
            }


        audio_base64 = getattr(
            output_audio,
            "data",
            None
        )


        if not audio_base64:

            return {

                "success":
                    False,

                "audio_path":
                    None,

                "model":
                    TTS_MODEL,

                "voice":
                    voice,

                "text":
                    texte_prepare,

                "latency_ms":
                    (
                        time.perf_counter()
                        -
                        debut
                    ) * 1000,

                "error":
                    "empty_audio_data",
            }


        # ====================================================
        # BASE64 → PCM
        # ====================================================

        pcm_data = (
            base64.b64decode(
                audio_base64
            )
        )


        if not pcm_data:

            return {

                "success":
                    False,

                "audio_path":
                    None,

                "model":
                    TTS_MODEL,

                "voice":
                    voice,

                "text":
                    texte_prepare,

                "latency_ms":
                    (
                        time.perf_counter()
                        -
                        debut
                    ) * 1000,

                "error":
                    "empty_pcm_data",
            }


        # ====================================================
        # PCM → WAV
        # ====================================================

        saved_path = (
            sauvegarder_pcm_wav(

                pcm_data=
                    pcm_data,

                output_path=
                    output_path
            )
        )


        # ====================================================
        # SORTIE
        # ====================================================

        return {

            "success":
                True,

            "audio_path":
                saved_path,

            "model":
                TTS_MODEL,

            "voice":
                voice,

            "text":
                texte_prepare,

            "mime_type":
                TTS_OUTPUT_MIME_TYPE,

            "sample_rate":
                TTS_SAMPLE_RATE,

            "channels":
                TTS_CHANNELS,

            "sample_width":
                TTS_SAMPLE_WIDTH,

            "size_bytes":
                Path(
                    saved_path
                ).stat().st_size,

            "latency_ms":
                (
                    time.perf_counter()
                    -
                    debut
                ) * 1000,

            "error":
                None,
        }


    except Exception as exception:

        return {

            "success":
                False,

            "audio_path":
                None,

            "model":
                TTS_MODEL,

            "voice":
                voice,

            "text":
                texte_prepare,

            "latency_ms":
                (
                    time.perf_counter()
                    -
                    debut
                ) * 1000,

            "error":
                classifier_erreur_speech(
                    exception
                ),

            "error_detail":
                str(
                    exception
                )[:500],
        }
