
# ============================================================
# METEOGPT — PIPELINE RAG GLOBAL
# ============================================================

"""
MeteoGPT — Pipeline global d'orchestration.

Architecture :

    Texte / Audio
         ↓
       Speech STT
         ↓
        Agent
         ↓
    Retriever si RAG
         ↓
      Generation
         ↓
       Texte
         ↓
    Speech TTS optionnel

Le pipeline d'actualisation ANACIM est volontairement
indépendant de ce module.
"""

# ============================================================
# 1. IMPORTS
# ============================================================
from dotenv import load_dotenv
import sys
import time

from pathlib import Path
from typing import Any, Dict, Optional

load_dotenv()
# ============================================================
# 2. CONFIGURATION DU PROJET
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parent

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(PROJECT_ROOT)
    )


# ============================================================
# 3. MODULES METEOGPT
# ============================================================

import agent
import retriever
import generation
import speech


# ============================================================
# 4. CONSTANTES
# ============================================================

PIPELINE_NAME = (
    "METEOGPT_ADAPTIVE_RAG"
)


DEFAULT_TOP_K = getattr(
    retriever,
    "DEFAULT_TOP_K",
    5
)


INPUT_MODE_TEXT = "text"
INPUT_MODE_AUDIO = "audio"

OUTPUT_MODE_TEXT = "text"
OUTPUT_MODE_AUDIO = "audio"


VALID_INPUT_MODES = {
    INPUT_MODE_TEXT,
    INPUT_MODE_AUDIO,
}


VALID_OUTPUT_MODES = {
    OUTPUT_MODE_TEXT,
    OUTPUT_MODE_AUDIO,
}


# ============================================================
# 5. PIPELINE TEXTE
# ============================================================

def process_text_request(
    query: str,
    *,
    thread_id: str = "default",
    user_preferences=None,
    top_k: int = DEFAULT_TOP_K,
    now=None,
    generation_client=None
) -> Dict[str, Any]:

    """
    Traite une requête textuelle MeteoGPT.

    Flux :
        query
          ↓
        Agent
          ↓
        Retriever si route=rag
          ↓
        Generation

    Parameters
    ----------
    query : str
        Requête utilisateur.

    thread_id : str
        Identifiant de conversation LangGraph.

    user_preferences : optional
        Préférences utilisateur.

    top_k : int
        Nombre maximal de chunks retournés.

    now : optional
        Date/heure injectable pour les tests temporels.

    generation_client : optional
        Client Gemini éventuellement réutilisé.

    Returns
    -------
    dict
        Résultat complet du pipeline texte.
    """

    # ========================================================
    # 1. VALIDATION
    # ========================================================

    if not isinstance(
        query,
        str
    ):

        raise TypeError(
            "query doit être une chaîne de caractères."
        )


    query = " ".join(
        query.split()
    ).strip()


    if not query:

        raise ValueError(
            "query ne peut pas être vide."
        )


    if not isinstance(
        thread_id,
        str
    ):

        raise TypeError(
            "thread_id doit être une chaîne de caractères."
        )


    if (
        not isinstance(
            top_k,
            int
        )
        or
        top_k <= 0
    ):

        raise ValueError(
            "top_k doit être un entier strictement positif."
        )


    start_total = (
        time.perf_counter()
    )


    # ========================================================
    # 2. AGENT
    # ========================================================

    start_agent = (
        time.perf_counter()
    )


    agent_result = (
        agent.analyze_query(
            query=query,
            thread_id=thread_id,
            user_preferences=
                user_preferences
        )
    )


    agent_ms = (
        time.perf_counter()
        -
        start_agent
    ) * 1000


    effective_query = (
        agent_result.get(
            "effective_query"
        )
        or
        query
    )


    route = (
        agent_result.get(
            "route"
        )
    )


    # ========================================================
    # 3. RETRIEVAL CONDITIONNEL
    # ========================================================

    retrieval_result = None
    retrieval_executed = False
    retrieval_ms = 0.0


    if route == "rag":

        retrieval_executed = True


        start_retrieval = (
            time.perf_counter()
        )


        retrieval_result = (
            retriever.retrieve(
                query=
                    effective_query,
                top_k=
                    top_k,
                now=
                    now
            )
        )


        retrieval_ms = (
            time.perf_counter()
            -
            start_retrieval
        ) * 1000


    # ========================================================
    # 4. GENERATION
    # ========================================================

    start_generation = (
        time.perf_counter()
    )


    generation_result = (
        generation.generate_response(
            agent_result=
                agent_result,
            retrieval_result=
                retrieval_result,
            client=
                generation_client
        )
    )


    generation_ms = (
        time.perf_counter()
        -
        start_generation
    ) * 1000


    # ========================================================
    # 5. LATENCE TOTALE
    # ========================================================

    total_ms = (
        time.perf_counter()
        -
        start_total
    ) * 1000


    # ========================================================
    # 6. SORTIE
    # ========================================================

    return {

        "success":
            bool(
                generation_result.get(
                    "success",
                    False
                )
            ),

        "input_mode":
            INPUT_MODE_TEXT,

        "output_mode":
            OUTPUT_MODE_TEXT,

        "query":
            query,

        "effective_query":
            effective_query,

        "route":
            route,

        "intent":
            agent_result.get(
                "intent"
            ),

        "needs_retrieval":
            agent_result.get(
                "needs_retrieval",
                False
            ),

        "needs_visual":
            agent_result.get(
                "needs_visual",
                False
            ),

        "source_requires_visual":
            agent_result.get(
                "source_requires_visual",
                False
            ),

        "use_multimodal":
            agent_result.get(
                "use_multimodal",
                False
            ),

        "context_used":
            agent_result.get(
                "context_used",
                False
            ),

        "answer":
            generation_result.get(
                "answer",
                ""
            ),

        "generation_mode":
            generation_result.get(
                "generation_mode"
            ),

        "grounded":
            generation_result.get(
                "grounded",
                False
            ),

        "sources_used":
            generation_result.get(
                "sources_used",
                []
            ),

        "images_used":
            generation_result.get(
                "images_used",
                []
            ),

        "retrieval_executed":
            retrieval_executed,

        "retrieval_result":
            retrieval_result,

        "agent_result":
            agent_result,

        "generation_result":
            generation_result,

        "latencies_ms": {

            "agent":
                float(
                    agent_ms
                ),

            "retrieval":
                float(
                    retrieval_ms
                ),

            "generation":
                float(
                    generation_ms
                ),

            "total":
                float(
                    total_ms
                ),
        },

        "error":
            generation_result.get(
                "error"
            ),
    }


# ============================================================
# 6. PIPELINE AUDIO
# ============================================================

def process_audio_request(
    audio_path,
    *,
    output_mode: str = OUTPUT_MODE_AUDIO,
    thread_id: str = "default",
    user_preferences=None,
    top_k: int = DEFAULT_TOP_K,
    now=None,
    generation_client=None,
    speech_client=None,
    audio_output_path=None
) -> Dict[str, Any]:

    """
    Traite une requête audio.

    Flux :
        audio
          ↓
        STT
          ↓
        process_text_request()
          ↓
        texte
          ↓
        TTS optionnel
    """

    start_total = (
        time.perf_counter()
    )


    # ========================================================
    # 1. VALIDATION
    # ========================================================

    if output_mode not in (
        VALID_OUTPUT_MODES
    ):

        raise ValueError(
            "output_mode doit être 'text' ou 'audio'."
        )


    # ========================================================
    # 2. SPEECH-TO-TEXT
    # ========================================================

    start_stt = (
        time.perf_counter()
    )


    stt_result = (
        speech.transcribe_audio(
            audio_path,
            client=
                speech_client
        )
    )


    stt_ms = (
        time.perf_counter()
        -
        start_stt
    ) * 1000


    # ========================================================
    # 3. ÉCHEC STT
    # ========================================================

    if not isinstance(
        stt_result,
        dict
    ):

        raise TypeError(
            "speech.transcribe_audio() doit retourner un dictionnaire."
        )


    if not stt_result.get(
        "success",
        False
    ):

        total_ms = (
            time.perf_counter()
            -
            start_total
        ) * 1000


        return {

            "success":
                False,

            "status":
                "error",

            "input_mode":
                INPUT_MODE_AUDIO,

            "output_mode":
                output_mode,

            "audio_input_path":
                str(
                    audio_path
                ),

            "transcription":
                None,

            "answer":
                "",

            "audio_output_path":
                None,

            "stt_result":
                stt_result,

            "pipeline_result":
                None,

            "tts_result":
                None,

            "latencies_ms": {

                "stt":
                    float(
                        stt_ms
                    ),

                "pipeline":
                    0.0,

                "tts":
                    0.0,

                "total":
                    float(
                        total_ms
                    ),
            },

            "error":
                stt_result.get(
                    "error",
                    "stt_error"
                ),
        }


    # ========================================================
    # 4. TRANSCRIPTION
    # ========================================================

    transcription = (

        stt_result.get(
            "transcription"
        )

        or

        stt_result.get(
            "text"
        )

        or
        ""
    )


    transcription = str(
        transcription
    ).strip()


    if not transcription:

        total_ms = (
            time.perf_counter()
            -
            start_total
        ) * 1000


        return {

            "success":
                False,

            "status":
                "error",

            "input_mode":
                INPUT_MODE_AUDIO,

            "output_mode":
                output_mode,

            "audio_input_path":
                str(
                    audio_path
                ),

            "transcription":
                "",

            "answer":
                "",

            "audio_output_path":
                None,

            "stt_result":
                stt_result,

            "pipeline_result":
                None,

            "tts_result":
                None,

            "latencies_ms": {

                "stt":
                    float(
                        stt_ms
                    ),

                "pipeline":
                    0.0,

                "tts":
                    0.0,

                "total":
                    float(
                        total_ms
                    ),
            },

            "error":
                "empty_transcription",
        }


    # ========================================================
    # 5. PIPELINE TEXTE
    # ========================================================

    start_pipeline = (
        time.perf_counter()
    )


    pipeline_result = (
        process_text_request(
            query=
                transcription,
            thread_id=
                thread_id,
            user_preferences=
                user_preferences,
            top_k=
                top_k,
            now=
                now,
            generation_client=
                generation_client
        )
    )


    pipeline_ms = (
        time.perf_counter()
        -
        start_pipeline
    ) * 1000


    answer = (
        pipeline_result.get(
            "answer"
        )
        or
        ""
    )


    # ========================================================
    # 6. SORTIE TEXTE
    # ========================================================

    if output_mode == (
        OUTPUT_MODE_TEXT
    ):

        total_ms = (
            time.perf_counter()
            -
            start_total
        ) * 1000


        return {

            "success":
                pipeline_result.get(
                    "success",
                    False
                ),

            "status":
                (
                    "ok"
                    if pipeline_result.get(
                        "success"
                    )
                    else "error"
                ),

            "input_mode":
                INPUT_MODE_AUDIO,

            "output_mode":
                OUTPUT_MODE_TEXT,

            "audio_input_path":
                str(
                    audio_path
                ),

            "transcription":
                transcription,

            "answer":
                answer,

            "audio_output_path":
                None,

            "stt_result":
                stt_result,

            "pipeline_result":
                pipeline_result,

            "tts_result":
                None,

            "latencies_ms": {

                "stt":
                    float(
                        stt_ms
                    ),

                "pipeline":
                    float(
                        pipeline_ms
                    ),

                "tts":
                    0.0,

                "total":
                    float(
                        total_ms
                    ),
            },

            "error":
                pipeline_result.get(
                    "error"
                ),
        }


    # ========================================================
    # 7. ÉCHEC DU PIPELINE TEXTE
    # ========================================================

    if not pipeline_result.get(
        "success",
        False
    ):

        total_ms = (
            time.perf_counter()
            -
            start_total
        ) * 1000


        return {

            "success":
                False,

            "status":
                "error",

            "input_mode":
                INPUT_MODE_AUDIO,

            "output_mode":
                OUTPUT_MODE_AUDIO,

            "audio_input_path":
                str(
                    audio_path
                ),

            "transcription":
                transcription,

            "answer":
                answer,

            "audio_output_path":
                None,

            "stt_result":
                stt_result,

            "pipeline_result":
                pipeline_result,

            "tts_result":
                None,

            "latencies_ms": {

                "stt":
                    float(
                        stt_ms
                    ),

                "pipeline":
                    float(
                        pipeline_ms
                    ),

                "tts":
                    0.0,

                "total":
                    float(
                        total_ms
                    ),
            },

            "error":
                pipeline_result.get(
                    "error"
                ),
        }


    # ========================================================
    # 8. TEXT-TO-SPEECH
    # ========================================================

    start_tts = (
        time.perf_counter()
    )


    tts_result = (
        speech.synthesize_speech(
            answer,
            output_path=
                audio_output_path,
            client=
                speech_client
        )
    )


    tts_ms = (
        time.perf_counter()
        -
        start_tts
    ) * 1000


    generated_audio_path = (

        tts_result.get(
            "output_path"
        )

        or

        tts_result.get(
            "audio_path"
        )

        or

        tts_result.get(
            "file_path"
        )
    )


    # ========================================================
    # 9. TTS PARTIELLEMENT ÉCHOUÉ
    # ========================================================

    if not tts_result.get(
        "success",
        False
    ):

        total_ms = (
            time.perf_counter()
            -
            start_total
        ) * 1000


        return {

            "success":
                True,

            "status":
                "partial",

            "input_mode":
                INPUT_MODE_AUDIO,

            "output_mode":
                OUTPUT_MODE_AUDIO,

            "audio_input_path":
                str(
                    audio_path
                ),

            "transcription":
                transcription,

            "answer":
                answer,

            "audio_output_path":
                None,

            "stt_result":
                stt_result,

            "pipeline_result":
                pipeline_result,

            "tts_result":
                tts_result,

            "latencies_ms": {

                "stt":
                    float(
                        stt_ms
                    ),

                "pipeline":
                    float(
                        pipeline_ms
                    ),

                "tts":
                    float(
                        tts_ms
                    ),

                "total":
                    float(
                        total_ms
                    ),
            },

            "error":
                tts_result.get(
                    "error",
                    "tts_error"
                ),
        }


    # ========================================================
    # 10. SUCCÈS COMPLET
    # ========================================================

    total_ms = (
        time.perf_counter()
        -
        start_total
    ) * 1000


    return {

        "success":
            True,

        "status":
            "ok",

        "input_mode":
            INPUT_MODE_AUDIO,

        "output_mode":
            OUTPUT_MODE_AUDIO,

        "audio_input_path":
            str(
                audio_path
            ),

        "transcription":
            transcription,

        "answer":
            answer,

        "audio_output_path":
            generated_audio_path,

        "stt_result":
            stt_result,

        "pipeline_result":
            pipeline_result,

        "tts_result":
            tts_result,

        "latencies_ms": {

            "stt":
                float(
                    stt_ms
                ),

            "pipeline":
                float(
                    pipeline_ms
                ),

            "tts":
                float(
                    tts_ms
                ),

            "total":
                float(
                    total_ms
                ),
        },

        "error":
            None,
    }


# ============================================================
# 7. INTERFACE PUBLIQUE GLOBALE
# ============================================================

def process_request(
    input_data,
    *,
    input_mode: str = INPUT_MODE_TEXT,
    output_mode: str = OUTPUT_MODE_TEXT,
    thread_id: str = "default",
    user_preferences=None,
    top_k: int = DEFAULT_TOP_K,
    now=None,
    generation_client=None,
    speech_client=None,
    audio_output_path=None
) -> Dict[str, Any]:

    """
    Point d'entrée principal du pipeline MeteoGPT.

    Modes :
        text  -> text
        text  -> audio
        audio -> text
        audio -> audio
    """

    start_total = (
        time.perf_counter()
    )


    # ========================================================
    # 1. VALIDATION
    # ========================================================

    if input_mode not in (
        VALID_INPUT_MODES
    ):

        raise ValueError(
            f"input_mode invalide : {input_mode}"
        )


    if output_mode not in (
        VALID_OUTPUT_MODES
    ):

        raise ValueError(
            f"output_mode invalide : {output_mode}"
        )


    query_original = None
    query_text = None

    pipeline_result = None
    audio_result = None
    tts_result = None

    audio_path = None

    stt_ms = 0.0
    agent_ms = 0.0
    retriever_ms = 0.0
    generation_ms = 0.0
    tts_ms = 0.0


    try:

        # ====================================================
        # 2. ENTRÉE TEXTE
        # ====================================================

        if input_mode == (
            INPUT_MODE_TEXT
        ):

            if not isinstance(
                input_data,
                str
            ):

                raise TypeError(
                    "Une entrée textuelle doit être une chaîne."
                )


            query_original = (
                input_data
            )


            query_text = (
                input_data.strip()
            )


            if not query_text:

                raise ValueError(
                    "La requête textuelle ne peut pas être vide."
                )


            pipeline_result = (
                process_text_request(
                    query=
                        query_text,
                    thread_id=
                        thread_id,
                    user_preferences=
                        user_preferences,
                    top_k=
                        top_k,
                    now=
                        now,
                    generation_client=
                        generation_client
                )
            )


            latencies = (
                pipeline_result.get(
                    "latencies_ms",
                    {}
                )
            )


            agent_ms = float(
                latencies.get(
                    "agent",
                    0.0
                )
            )


            retriever_ms = float(
                latencies.get(
                    "retrieval",
                    0.0
                )
            )


            generation_ms = float(
                latencies.get(
                    "generation",
                    0.0
                )
            )


            # ================================================
            # SORTIE AUDIO
            # ================================================

            if (
                output_mode
                ==
                OUTPUT_MODE_AUDIO
                and
                pipeline_result.get(
                    "success",
                    False
                )
            ):

                start_tts = (
                    time.perf_counter()
                )


                tts_result = (
                    speech.synthesize_speech(
                        pipeline_result.get(
                            "answer",
                            ""
                        ),
                        output_path=
                            audio_output_path,
                        client=
                            speech_client
                    )
                )


                tts_ms = (
                    time.perf_counter()
                    -
                    start_tts
                ) * 1000


                audio_path = (

                    tts_result.get(
                        "output_path"
                    )

                    or

                    tts_result.get(
                        "audio_path"
                    )

                    or

                    tts_result.get(
                        "file_path"
                    )
                )


        # ====================================================
        # 3. ENTRÉE AUDIO
        # ====================================================

        else:

            query_original = str(
                input_data
            )


            audio_result = (
                process_audio_request(
                    audio_path=
                        input_data,
                    output_mode=
                        output_mode,
                    thread_id=
                        thread_id,
                    user_preferences=
                        user_preferences,
                    top_k=
                        top_k,
                    now=
                        now,
                    generation_client=
                        generation_client,
                    speech_client=
                        speech_client,
                    audio_output_path=
                        audio_output_path
                )
            )


            query_text = (
                audio_result.get(
                    "transcription"
                )
            )


            pipeline_result = (
                audio_result.get(
                    "pipeline_result"
                )
            )


            tts_result = (
                audio_result.get(
                    "tts_result"
                )
            )


            audio_path = (
                audio_result.get(
                    "audio_output_path"
                )
            )


            audio_latencies = (
                audio_result.get(
                    "latencies_ms",
                    {}
                )
            )


            stt_ms = float(
                audio_latencies.get(
                    "stt",
                    0.0
                )
            )


            tts_ms = float(
                audio_latencies.get(
                    "tts",
                    0.0
                )
            )


            if isinstance(
                pipeline_result,
                dict
            ):

                internal_latencies = (
                    pipeline_result.get(
                        "latencies_ms",
                        {}
                    )
                )


                agent_ms = float(
                    internal_latencies.get(
                        "agent",
                        0.0
                    )
                )


                retriever_ms = float(
                    internal_latencies.get(
                        "retrieval",
                        0.0
                    )
                )


                generation_ms = float(
                    internal_latencies.get(
                        "generation",
                        0.0
                    )
                )


        # ====================================================
        # 4. PIPELINE NON EXÉCUTÉ
        # ====================================================

        if not isinstance(
            pipeline_result,
            dict
        ):

            total_ms = (
                time.perf_counter()
                -
                start_total
            ) * 1000


            return {

                "success":
                    False,

                "status":
                    "error",

                "input_mode":
                    input_mode,

                "output_mode":
                    output_mode,

                "query_original":
                    query_original,

                "query_text":
                    query_text,

                "effective_query":
                    None,

                "route":
                    None,

                "intent":
                    None,

                "answer_text":
                    "",

                "audio_path":
                    audio_path,

                "retrieval_executed":
                    False,

                "use_multimodal":
                    False,

                "grounded":
                    False,

                "sources_used":
                    [],

                "images_used":
                    [],

                "timings": {

                    "stt_ms":
                        stt_ms,

                    "agent_ms":
                        0.0,

                    "retriever_ms":
                        0.0,

                    "generation_ms":
                        0.0,

                    "tts_ms":
                        tts_ms,

                    "total_ms":
                        float(
                            total_ms
                        ),
                },

                "error":
                    (
                        audio_result.get(
                            "error"
                        )
                        if isinstance(
                            audio_result,
                            dict
                        )
                        else
                        "pipeline_not_executed"
                    ),
            }


        # ====================================================
        # 5. STATUT GLOBAL
        # ====================================================

        pipeline_success = bool(
            pipeline_result.get(
                "success",
                False
            )
        )


        if not pipeline_success:

            status = "error"
            success = False

            error = (
                pipeline_result.get(
                    "error"
                )
            )


        elif (
            output_mode
            ==
            OUTPUT_MODE_AUDIO
            and
            isinstance(
                tts_result,
                dict
            )
            and
            not tts_result.get(
                "success",
                False
            )
        ):

            status = "partial"
            success = True

            error = (
                tts_result.get(
                    "error",
                    "tts_error"
                )
            )


        else:

            status = "ok"
            success = True
            error = None


        # ====================================================
        # 6. LATENCE TOTALE
        # ====================================================

        total_ms = (
            time.perf_counter()
            -
            start_total
        ) * 1000


        # ====================================================
        # 7. SORTIE STANDARDISÉE
        # ====================================================

        return {

            "success":
                success,

            "status":
                status,

            "input_mode":
                input_mode,

            "output_mode":
                output_mode,

            "query_original":
                query_original,

            "query_text":
                query_text,

            "effective_query":
                pipeline_result.get(
                    "effective_query"
                ),

            "route":
                pipeline_result.get(
                    "route"
                ),

            "intent":
                pipeline_result.get(
                    "intent"
                ),

            "use_multimodal":
                pipeline_result.get(
                    "use_multimodal",
                    False
                ),

            "retrieval_executed":
                pipeline_result.get(
                    "retrieval_executed",
                    False
                ),

            "answer_text":
                pipeline_result.get(
                    "answer",
                    ""
                ),

            "audio_path":
                audio_path,

            "generation_mode":
                pipeline_result.get(
                    "generation_mode"
                ),

            "grounded":
                pipeline_result.get(
                    "grounded",
                    False
                ),

            "sources_used":
                pipeline_result.get(
                    "sources_used",
                    []
                ),

            "images_used":
                pipeline_result.get(
                    "images_used",
                    []
                ),

            "timings": {

                "stt_ms":
                    float(
                        stt_ms
                    ),

                "agent_ms":
                    float(
                        agent_ms
                    ),

                "retriever_ms":
                    float(
                        retriever_ms
                    ),

                "generation_ms":
                    float(
                        generation_ms
                    ),

                "tts_ms":
                    float(
                        tts_ms
                    ),

                "total_ms":
                    float(
                        total_ms
                    ),
            },

            "error":
                error,
        }


    # ========================================================
    # 8. ERREUR INATTENDUE
    # ========================================================

    except Exception as exc:

        total_ms = (
            time.perf_counter()
            -
            start_total
        ) * 1000


        return {

            "success":
                False,

            "status":
                "error",

            "input_mode":
                input_mode,

            "output_mode":
                output_mode,

            "query_original":
                query_original,

            "query_text":
                query_text,

            "effective_query":
                None,

            "route":
                None,

            "intent":
                None,

            "answer_text":
                "",

            "audio_path":
                None,

            "retrieval_executed":
                False,

            "use_multimodal":
                False,

            "grounded":
                False,

            "sources_used":
                [],

            "images_used":
                [],

            "timings": {

                "stt_ms":
                    float(
                        stt_ms
                    ),

                "agent_ms":
                    float(
                        agent_ms
                    ),

                "retriever_ms":
                    float(
                        retriever_ms
                    ),

                "generation_ms":
                    float(
                        generation_ms
                    ),

                "tts_ms":
                    float(
                        tts_ms
                    ),

                "total_ms":
                    float(
                        total_ms
                    ),
            },

            "error":
                (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
        }


# ============================================================
# 8. API PUBLIQUE
# ============================================================

__all__ = [

    "process_request",

    "process_text_request",

    "process_audio_request",

    "PIPELINE_NAME",

    "DEFAULT_TOP_K",
]
