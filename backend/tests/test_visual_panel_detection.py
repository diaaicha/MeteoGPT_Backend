
import fitz

from src.visual_panel_extraction import (
    analyser_panneaux_page,
    dedoublonner_panneaux,
)


def test_detecte_panneau_vectoriel_colore():
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)

    page.draw_rect(
        fitz.Rect(80, 100, 300, 210),
        color=None,
        fill=(0.1, 0.4, 0.9)
    )

    resultat = analyser_panneaux_page(page)

    assert len(resultat) == 1
    assert resultat[0]["bbox"] == (
        80.0, 100.0, 300.0, 210.0
    )

    doc.close()


def test_ignore_petit_rectangle():
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)

    page.draw_rect(
        fitz.Rect(20, 20, 60, 50),
        color=None,
        fill=(0.1, 0.4, 0.9)
    )

    assert analyser_panneaux_page(page) == []

    doc.close()


def test_dedoublonnage_iou():
    candidats = [
        {
            "bbox": (0, 0, 200, 100),
            "surface": 20000
        },
        {
            "bbox": (1, 1, 201, 101),
            "surface": 20000
        }
    ]

    resultat = dedoublonner_panneaux(candidats)

    assert len(resultat) == 1



from src.visual_panel_extraction import (
    resserrer_bbox,
    rendre_panneau,
)


def test_resserrement_panneau_inferieur():
    courant = (20, 20, 240, 160)
    dessous = (20, 120, 240, 235)

    resultat = resserrer_bbox(
        courant,
        [courant, dessous],
    )

    assert resultat == (20.0, 20.0, 240.0, 118.0)


def test_resserrement_panneau_droite():
    courant = (20, 20, 240, 160)
    droite = (190, 20, 340, 160)

    resultat = resserrer_bbox(
        courant,
        [courant, droite],
    )

    assert resultat == (20.0, 20.0, 188.0, 160.0)


def test_bbox_inchange_sans_chevauchement():
    courant = (20, 20, 240, 160)
    voisin = (30, 170, 245, 250)

    resultat = resserrer_bbox(
        courant,
        [courant, voisin],
    )

    assert resultat == (20.0, 20.0, 240.0, 160.0)


def test_rendu_png_sans_marge(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)

    page.draw_rect(
        fitz.Rect(30, 40, 130, 90),
        color=None,
        fill=(0.1, 0.4, 0.9),
    )

    chemin = tmp_path / "panneaux" / "panel.png"

    resultat = rendre_panneau(
        page,
        (30, 40, 130, 90),
        chemin,
    )

    assert resultat == chemin
    assert chemin.is_file()

    image = fitz.Pixmap(str(chemin))

    # Rectangle 100 × 50, rendu à l'échelle 2.
    assert (image.width, image.height) == (200, 100)

    doc.close()
