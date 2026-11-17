from pathlib import Path
import pytest
from lexique_meteo import reconnaitre_concepts_meteo


def codes(texte, chemin=None):
    return {item["concept"] for item in reconnaitre_concepts_meteo(texte, chemin)}


def test_verbe_pleuvoir():
    assert "pluie" in codes("Va-t-il pleuvoir demain ?")


def test_phenomene_complexe():
    assert "thalweg" in codes("C'est quoi un thalweg ?")


def test_synonyme():
    assert "bruine" in codes("Explique-moi le crachin")


def test_accents():
    assert "poussières sahariennes" in codes("Poussières sahariennes demain ?")


def test_plusieurs_phenomenes():
    assert {"houle", "rafale"}.issubset(codes("Houle et rafales demain"))


def test_expression_composee_prioritaire():
    resultats = codes("Brume sèche signalée")
    assert "brume sèche" in resultats
    assert "brume" not in resultats


def test_pourcentage_nom_general_pas_autoclassifie():
    assert codes("Filets de pêche en vente") == set()


def test_pas_sous_mots():
    assert codes("La vente de meubles va augmenter") == set()


def test_normalisation_ponctuation():
    assert "masse d'air" in codes("Les masses d’air ?")


def test_multiple_mention_un_seul_concept():
    assert [x["concept"] for x in reconnaitre_concepts_meteo("Pluie pluie pluies")] == ["pluie"]


def test_fichier_manquant(tmp_path):
    with pytest.raises(FileNotFoundError):
        reconnaitre_concepts_meteo("pluie", tmp_path / "absent.csv")


def test_ambiguite_refusee(tmp_path):
    fichier=tmp_path / "test.csv"
    fichier.write_text("famille;concept;variantes\na;concept 1;test\nb;concept 2;test\n",encoding="utf-8")
    with pytest.raises(ValueError, match="ambigu"):
        reconnaitre_concepts_meteo("test", fichier)


def test_colonnes_invalides(tmp_path):
    fichier=tmp_path / "test.csv"
    fichier.write_text("terme;synonyme\npluie;pluies\n",encoding="utf-8")
    with pytest.raises(ValueError, match="Colonnes"):
        reconnaitre_concepts_meteo("pluie", fichier)
