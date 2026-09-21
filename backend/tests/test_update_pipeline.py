from qdrant_client import QdrantClient

from src.meteogpt_update_api_pipeline import (
    MeteoGPTApiConfig,
    indexer_qdrant_api,
)


VECTOR_SIZE = 768


def make_chunk(chunk_id: str, source_file: str):
    return {
        "chunk_id": chunk_id,
        "chunk_type": "text",
        "retrieval_role": "primary",
        "unit_type": "text",
        "unit_id": f"{chunk_id}_UNIT",
        "document_id": source_file,
        "source_file": source_file,
        "category": "Bulletin",
        "page": 1,
        "content": f"Contenu de test pour {source_file}",
        "metadata": {
            "date_publication": "2026-09-21",
            "date_debut_validite": "2026-09-21",
            "date_fin_validite": "2026-09-22",
            "document_type": "bulletin",
            "localite": "Dakar",
        },
    }


def make_embedding(chunk_id: str, value: float):
    return {
        "chunk_id": chunk_id,
        "embedding": [value] * VECTOR_SIZE,
    }


def test_incremental_upsert_preserves_existing_points(tmp_path):

    client = QdrantClient(location=":memory:")

    config = MeteoGPTApiConfig(
        root_dir=str(tmp_path),
        collection_name="test_b6_incremental",
    )

    chunk_a = make_chunk(
        "DOC_A_CHUNK_001",
        "doc_a.pdf",
    )

    indexer_qdrant_api(
        [chunk_a],
        [make_embedding("DOC_A_CHUNK_001", 0.1)],
        config,
        qdrant_client=client,
    )

    assert client.get_collection(
        config.collection_name
    ).points_count == 1

    chunk_b = make_chunk(
        "DOC_B_CHUNK_001",
        "doc_b.pdf",
    )

    result = indexer_qdrant_api(
        [chunk_b],
        [make_embedding("DOC_B_CHUNK_001", 0.2)],
        config,
        qdrant_client=client,
    )

    assert result["points_upserted"] == 1

    assert client.get_collection(
        config.collection_name
    ).points_count == 2

    client.close()


def test_modified_document_replaces_only_target_source(tmp_path):

    client = QdrantClient(location=":memory:")

    config = MeteoGPTApiConfig(
        root_dir=str(tmp_path),
        collection_name="test_b6_replace",
    )

    chunks_initial = [
        make_chunk(
            "DOC_A_CHUNK_001",
            "doc_a.pdf",
        ),
        make_chunk(
            "DOC_B_CHUNK_001",
            "doc_b.pdf",
        ),
    ]

    embeddings_initial = [
        make_embedding(
            "DOC_A_CHUNK_001",
            0.1,
        ),
        make_embedding(
            "DOC_B_CHUNK_001",
            0.2,
        ),
    ]

    indexer_qdrant_api(
        chunks_initial,
        embeddings_initial,
        config,
        qdrant_client=client,
    )

    assert client.get_collection(
        config.collection_name
    ).points_count == 2

    new_doc_a = make_chunk(
        "DOC_A_CHUNK_002",
        "doc_a.pdf",
    )

    result = indexer_qdrant_api(
        [new_doc_a],
        [make_embedding("DOC_A_CHUNK_002", 0.3)],
        config,
        qdrant_client=client,
        source_files_to_replace=[
            "doc_a.pdf"
        ],
    )

    assert result["source_files_replaced"] == [
        "doc_a.pdf"
    ]

    assert client.get_collection(
        config.collection_name
    ).points_count == 2

    points, _ = client.scroll(
        collection_name=config.collection_name,
        limit=10,
        with_payload=True,
        with_vectors=False,
    )

    source_files = sorted(
        point.payload.get("source_file")
        for point in points
    )

    assert source_files == [
        "doc_a.pdf",
        "doc_b.pdf",
    ]

    chunk_ids = {
        point.payload.get("chunk_id")
        for point in points
    }

    assert "DOC_A_CHUNK_001" not in chunk_ids
    assert "DOC_A_CHUNK_002" in chunk_ids
    assert "DOC_B_CHUNK_001" in chunk_ids

    client.close()


def test_resume_processing_reuses_existing_pdf(
    tmp_path,
    monkeypatch,
):
    from src import (
        meteogpt_update_api_pipeline as pipeline,
    )

    config = pipeline.MeteoGPTApiConfig(
        root_dir=str(tmp_path),
    )

    config.raw_api_pdf_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = (
        "Bulletin_Test_21-09-2026.pdf"
    )

    destination = (
        config.raw_api_pdf_dir /
        filename
    )

    destination.write_bytes(
        b"%PDF-1.4 test"
    )

    def fail_if_download_called(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Le PDF ne devait pas être "
            "retéléchargé."
        )

    monkeypatch.setattr(
        pipeline,
        "telecharger_un_pdf",
        fail_if_download_called,
    )

    bulletin = {
        "chemin": (
            "http://example.com/"
            + filename
        ),
        "date_modification":
            "2026-09-21",
        "update_status":
            "resume_processing",
    }

    fichiers = (
        pipeline.telecharger_bulletins_api(
            [bulletin],
            config,
        )
    )

    assert fichiers == [
        destination
    ]

    assert (
        bulletin["update_status"]
        == "downloaded"
    )

    assert (
        bulletin["local_pdf_path"]
        == str(destination)
    )

    assert (
        bulletin["sha256"]
        == pipeline.sha256_file(
            destination
        )
    )

    assert bulletin["pdf_reused"] is True

    assert (
        bulletin["pdf_downloaded_network"]
        is False
    )