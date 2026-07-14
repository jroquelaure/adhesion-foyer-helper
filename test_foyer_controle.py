# -*- coding: utf-8 -*-
"""Tests unitaires de foyer_controle.py"""
import os, csv, json
import pytest
import foyer_controle as fc
from conftest import read_csv


# --------------------------------------------------------------------- helpers
def test_strip_accents_et_norm():
    assert fc.strip_accents("Aïcha Éòû") == "Aicha Eou"
    assert fc.norm("  Da Silva  ") == "dasilva"
    assert fc.cle_nom("DUPONT", "Aïcha") == ("dupont", "aicha")


def test_norm_email_et_clean():
    assert fc.norm_email("  Jon@Gajea.com. ") == "jon@gajea.com"
    assert fc.clean_email("aichahenni@orange.fr.") == "aichahenni@orange.fr"
    assert fc.norm_email(None) == ""


@pytest.mark.parametrize("statut,attendu", [
    ("Validé", True), ("validé", True), ("VALIDE", True),
    ("Annulé", False), ("", False), (None, False),
])
def test_valide(statut, attendu):
    assert fc.valide(statut) is attendu


@pytest.mark.parametrize("brut,attendu", [
    ("+33621661351", "0621661351"),
    ("0033700112233", "0700112233"),
    ("33621661351", "0621661351"),
    ("06 64 45 89 50", "0664458950"),
    ("05.32.59.20.07", "0532592007"),
    ("621661351", "0621661351"),
    ("0620424108", "0620424108"),
    ("", ""),
    (None, ""),
])
def test_tel(brut, attendu):
    assert fc.tel(brut) == attendu


@pytest.mark.parametrize("brut,attendu", [
    ("1967-06-11", "11/06/1967"),
    ("11/06/1967", "11/06/1967"),
    ("3/6/1990", "03/06/1990"),
    ("", ""),
    ("pas une date", "pas une date"),
])
def test_date_fr(brut, attendu):
    assert fc.date_fr(brut) == attendu


@pytest.mark.parametrize("brut,attendu", [
    ("Féminin", "Mme"), ("Masculin", "M"), ("", "M"),
    ("Madame", "Mme"), ("Homme", "M"), ("F", "Mme"),
])
def test_civilite_gestanet(brut, attendu):
    assert fc.civilite_gestanet(brut) == attendu


# --------------------------------------------------------------- colonnes activités
def test_colonnes_activites_export_manuel():
    entetes = ["Nom adhérent", "Zumba", "Montant Zumba", "Yoga", "Montant Yoga", "Email"]
    assert fc.colonnes_activites(entetes) == ["Zumba", "Yoga"]


def test_colonnes_activites_fallback_api():
    entetes = ["Nom adhérent", "Zumba", "Yoga", "Email", "Sexe/Civilité",
               "La personne inscrite est adhérente au Foyer Rural de Mondonville"]
    rows = [
        {"Zumba": "Oui", "Yoga": "", "Email": "a@b.c", "Sexe/Civilité": "Masculin",
         "La personne inscrite est adhérente au Foyer Rural de Mondonville": "Oui"},
        {"Zumba": "", "Yoga": "Oui", "Email": "d@e.f", "Sexe/Civilité": "Féminin",
         "La personne inscrite est adhérente au Foyer Rural de Mondonville": "Non"},
    ]
    acts = fc.colonnes_activites(entetes, rows)
    assert acts == ["Zumba", "Yoga"]           # champs "Email/Sexe/La personne…" exclus


def test_activites_payantes():
    entetes = ["Zumba", "Montant Zumba",
               "J'ai compris que cette activité est payante via un autre formulaire",
               "Généalogie", "Montant Généalogie"]
    assert fc.activites_payantes(entetes) == {"Zumba"}


# ---------------------------------------------------------------- résolution tokens
@pytest.mark.parametrize("token,attendu", [
    ("ttenfant", "Tennis de table"),
    ("ttadulte", "Tennis de table"),
    ("hata", "Yoga"),
    ("vinysa", "Yoga"),
    ("gym", "Gym douce"),
    ("zumba", "Zumba"),
    ("mondonville", None),
    ("xyzinconnu", None),
])
def test_resoudre_token(token, attendu):
    acts = ["Yoga", "Zumba", "Gym douce", "Tennis de table", "Eveil corporel (4-5 ans)"]
    assert fc.resoudre_token(token, acts) == attendu


# ---------------------------------------------------------------- détection fichier
ACTS = ["Yoga", "Zumba", "Gym douce", "Tennis de table"]
BASE_ACT_HEADERS = ["Référence commande", "Statut de la commande", "Nom adhérent", "Prénom adhérent"]


def test_detecter_activite_par_nom(write_csv):
    f = write_csv("export-yoga-vinysa-mondonville.csv", BASE_ACT_HEADERS,
                  [{"Référence commande": "1", "Statut de la commande": "Validé",
                    "Nom adhérent": "DUPONT", "Prénom adhérent": "Marie"}])
    lbl, methode, _ = fc.detecter_activite(f, ACTS, {}, "Statut de la commande")
    assert lbl == "Yoga"
    assert methode.startswith("nom de fichier")


def test_detecter_activite_non_reconnu_pas_de_devinette_contenu(write_csv):
    # nom de fichier sans indice -> NON reconnu (pas d'auto-classement par contenu)
    f = write_csv("export-mystere-2026.csv", BASE_ACT_HEADERS,
                  [{"Référence commande": "1", "Statut de la commande": "Validé",
                    "Nom adhérent": "DUPONT", "Prénom adhérent": "Marie"}])
    lbl, methode, _ = fc.detecter_activite(f, ACTS, {("dupont", "marie"): "x"}, "Statut de la commande")
    assert lbl is None
    assert "non reconnu" in methode


def test_construire_mappage_multi_fichiers(write_csv):
    f1 = write_csv("export-ttenfant.csv", BASE_ACT_HEADERS,
                   [{"Statut de la commande": "Validé", "Nom adhérent": "A", "Prénom adhérent": "a"}])
    f2 = write_csv("export-ttadulte.csv", BASE_ACT_HEADERS,
                   [{"Statut de la commande": "Validé", "Nom adhérent": "B", "Prénom adhérent": "b"}])
    mapping, rapport, file_labels = fc.construire_mappage("adh.csv", [f1, f2], ACTS, {}, "Statut de la commande", {})
    assert len(mapping["Tennis de table"]) == 2     # les deux campagnes fusionnées


def test_construire_mappage_forcer_et_ignorer(write_csv):
    f1 = write_csv("truc-bizarre.csv", BASE_ACT_HEADERS,
                   [{"Statut de la commande": "Validé", "Nom adhérent": "A", "Prénom adhérent": "a"}])
    f2 = write_csv("export-a-ignorer.csv", BASE_ACT_HEADERS,
                   [{"Statut de la commande": "Validé", "Nom adhérent": "B", "Prénom adhérent": "b"}])
    cfg = {"forcer": {"truc-bizarre.csv": "Zumba"}, "ignorer_fichiers": ["export-a-ignorer.csv"]}
    mapping, rapport, file_labels = fc.construire_mappage("adh.csv", [f1, f2], ACTS, {}, "Statut de la commande", cfg)
    assert mapping["Zumba"] == [f1]
    assert all("export-a-ignorer.csv" not in fs for fs in mapping.values())


def test_construire_mappage_forcer_par_mot_cle_independant_de_lannee(write_csv):
    # clé 'gymnastique' (mot-clé) -> matche le fichier quelle que soit l'année dans le nom
    f = write_csv("export-gymnastique-au-frm-2027-2028.csv", BASE_ACT_HEADERS,
                  [{"Statut de la commande": "Validé", "Nom adhérent": "A", "Prénom adhérent": "a"}])
    cfg = {"forcer": {"gymnastique": ["Gym douce", "Pilates"]}}
    mapping, rapport, file_labels = fc.construire_mappage("adh.csv", [f], ACTS, {}, "Statut de la commande", cfg)
    assert f in mapping["Gym douce"] and f in mapping["Pilates"]


def test_construire_mappage_cumul_mots_cles(write_csv):
    # un fichier 'zumba et cardio' matche 'zumba' ET 'cardio' -> cumul des libellés
    f = write_csv("export-zumba-et-cardio-step-2025-2026.csv", BASE_ACT_HEADERS,
                  [{"Statut de la commande": "Validé", "Nom adhérent": "A", "Prénom adhérent": "a"}])
    cfg = {"forcer": {"zumba": "Zumba", "cardio": ["Zumba", "Step"]}}
    mapping, rapport, file_labels = fc.construire_mappage("adh.csv", [f], ACTS, {}, "Statut de la commande", cfg)
    assert file_labels[f] == {"Zumba", "Step"}


def test_construire_mappage_forcer_liste_multi_activites(write_csv):
    f = write_csv("export-gymnastique-2025-2026.csv", BASE_ACT_HEADERS,
                  [{"Statut de la commande": "Validé", "Nom adhérent": "A", "Prénom adhérent": "a"}])
    cfg = {"forcer": {"export-gymnastique-2025-2026.csv": ["Gym douce", "Pilates", "Stretching", "Body sculpt"]}}
    mapping, rapport, file_labels = fc.construire_mappage("adh.csv", [f], ACTS, {}, "Statut de la commande", cfg)
    assert f in mapping["Gym douce"] and f in mapping["Pilates"]
    assert file_labels[f] == {"Gym douce", "Pilates", "Stretching", "Body sculpt"}


# ---------------------------------------------------------------- Gestanet
def test_ligne_gestanet_depuis_adhesion():
    r = {"Nom adhérent": "Dupont", "Prénom adhérent": "Marie", "Sexe/Civilité": "Féminin",
         "Date de naissance": "1990-03-12", "Adresse": "3 rue Haute", "Code Postal": "31700",
         "Ville": "mondonville", "Email": "marie@ex.com", "Téléphone portable": "06 12 34 56 78"}
    g = fc.ligne_gestanet_depuis_adhesion(r, "Yoga")
    assert g["Sexe/Civilité"] == "Mme"
    assert g["Date de naissance"] == "12/03/1990"
    assert g["Ville"] == "MONDONVILLE"          # majuscules (limitation Gestanet)
    assert g["Tél. portable"] == "0612345678"
    assert g["Commentaire"] == "Activité : Yoga"


# ---------------------------------------------------------------- intégration run()
@pytest.fixture
def dossier_demo(tmp_path, write_csv):
    adh_headers = ["Référence commande", "Date de la commande", "Statut de la commande",
                   "Nom adhérent", "Prénom adhérent", "Nom payeur", "Prénom payeur", "Email payeur",
                   "Sexe/Civilité", "Date de naissance", "Adresse", "Code Postal", "Ville",
                   "Email", "Téléphone portable", "Yoga", "Montant Yoga", "Zumba", "Montant Zumba"]
    adh_rows = [
        {"Référence commande": "1", "Statut de la commande": "Validé", "Nom adhérent": "DUPONT",
         "Prénom adhérent": "Marie", "Email payeur": "marie@ex.com", "Sexe/Civilité": "Féminin",
         "Date de naissance": "1990-03-12", "Adresse": "3 rue Haute", "Code Postal": "31700",
         "Ville": "mondonville", "Email": "marie@ex.com", "Téléphone portable": "0612345678",
         "Yoga": "Oui", "Zumba": "Oui"},
        {"Référence commande": "2", "Statut de la commande": "Validé", "Nom adhérent": "MARTIN",
         "Prénom adhérent": "Jean", "Email payeur": "jean@ex.com", "Sexe/Civilité": "Masculin",
         "Ville": "DAUX", "Email": "jean@ex.com", "Yoga": "Oui", "Zumba": ""},
    ]
    write_csv("export-adhesion-test.csv", adh_headers, adh_rows)

    yoga_headers = ["Référence commande", "Statut de la commande", "Nom adhérent", "Prénom adhérent",
                    "Nom payeur", "Prénom payeur", "Email payeur",
                    "La personne inscrite est adhérente à un autre Foyer Rural ? si oui lequel"]
    yoga_rows = [
        {"Référence commande": "10", "Statut de la commande": "Validé", "Nom adhérent": "DUPONT",
         "Prénom adhérent": "Marie", "Email payeur": "marie@ex.com"},
        {"Référence commande": "11", "Statut de la commande": "Validé", "Nom adhérent": "EXT",
         "Prénom adhérent": "Sophie", "Email payeur": "sophie@ex.com"},
        {"Référence commande": "12", "Statut de la commande": "Validé", "Nom adhérent": "AILLEURS",
         "Prénom adhérent": "Paul", "Email payeur": "paul@ex.com",
         "La personne inscrite est adhérente à un autre Foyer Rural ? si oui lequel": "FR Grenade"},
    ]
    write_csv("export-yoga-test.csv", yoga_headers, yoga_rows)
    return str(tmp_path)


def test_run_controles_et_gestanet(dossier_demo, tmp_path):
    sortie = str(tmp_path / "_out")
    fc.run(dossier_demo, sortie, "2025-2026")

    # fichiers produits
    for nom in ["consolide.csv", "anomalies_adhesion_manquante.csv",
                "anomalies_activite_cochee_non_payee.csv", "rapport.txt"]:
        assert os.path.isfile(os.path.join(sortie, nom))

    # adhésion manquante : Sophie (pas adhérente), pas Paul (autre foyer), pas Marie
    manq = read_csv(os.path.join(sortie, "anomalies_adhesion_manquante.csv"))
    noms = {r["Nom"] for r in manq}
    assert "EXT" in noms and "AILLEURS" not in noms and "DUPONT" not in noms

    # activité cochée non payée : Jean a coché Yoga sans s'inscrire
    coche = read_csv(os.path.join(sortie, "anomalies_activite_cochee_non_payee.csv"))
    assert any(r["Nom"] == "MARTIN" and r["Activité cochée non honorée"] == "Yoga" for r in coche)
    # Marie a coché Yoga MAIS s'est inscrite -> pas d'anomalie pour elle
    assert not any(r["Nom"] == "DUPONT" for r in coche)

    # Gestanet Yoga : Marie avec état civil repris de l'adhésion
    gpath = os.path.join(sortie, "gestanet", "yoga.csv")
    assert os.path.isfile(gpath)
    g = {r["Nom"]: r for r in read_csv(gpath)}
    assert g["DUPONT"]["Ville"] == "MONDONVILLE"
    assert g["DUPONT"]["Sexe/Civilité"] == "Mme"
    assert g["DUPONT"]["Date de naissance"] == "12/03/1990"
    # Sophie (autre foyer, absente de l'adhésion) : état civil à compléter
    assert "compléter" in g["EXT"]["Commentaire"]


def test_run_campagne_parapluie_et_activite_gratuite(tmp_path, write_csv):
    # Adhésion : Gym douce / Pilates (payantes via 'gymnastique') + Jeux de société (gratuite)
    adh_headers = ["Référence commande", "Statut de la commande", "Nom adhérent", "Prénom adhérent",
                   "Email", "Sexe/Civilité", "Ville",
                   "Gym douce", "Montant Gym douce", "Pilates", "Montant Pilates",
                   "Jeux de société", "Montant Jeux de société"]
    def row(ref, nom, gym="", pil="", jeux=""):
        return {"Référence commande": ref, "Statut de la commande": "Validé", "Nom adhérent": nom,
                "Prénom adhérent": nom.lower(), "Email": nom.lower() + "@ex.com",
                "Sexe/Civilité": "Masculin", "Ville": "mondonville",
                "Gym douce": gym, "Pilates": pil, "Jeux de société": jeux}
    adh_rows = [row("1", "A", gym="Oui", jeux="Oui"), row("2", "B", pil="Oui", jeux="Oui"),
                row("3", "C", gym="Oui"), row("4", "D", jeux="Oui"),
                row("5", "E", gym="Oui", pil="Oui")]
    write_csv("export-adhesion-2025-2026.csv", adh_headers, adh_rows)

    # Campagne 'gymnastique' regroupée : le TARIF choisi porte l'activité réellement souscrite.
    # E paie gym douce ET pilates -> deux lignes.
    camp_headers = ["Référence commande", "Statut de la commande", "Nom adhérent", "Prénom adhérent",
                    "Email payeur", "Tarif"]
    def crow(ref, nom, tarif):
        return {"Référence commande": ref, "Statut de la commande": "Validé", "Nom adhérent": nom,
                "Prénom adhérent": nom.lower(), "Tarif": tarif}
    write_csv("export-gymnastique-2025-2026.csv", camp_headers, [
        crow("10", "A", "Gym douce"), crow("11", "B", "Pilates"),
        crow("12", "E", "Gym douce"), crow("13", "E", "Pilates")])

    (tmp_path / "config.json").write_text(json.dumps({
        "adhesion_file": "export-adhesion-2025-2026.csv",
        "forcer": {"export-gymnastique-2025-2026.csv": ["Gym douce", "Pilates", "Stretching", "Body sculpt"]}
    }), encoding="utf-8")

    sortie = str(tmp_path / "_out")
    fc.run(str(tmp_path), sortie, "2025-2026")

    # cochée non payée : C a coché Gym douce mais n'a pas payé
    coche = read_csv(os.path.join(sortie, "anomalies_activite_cochee_non_payee.csv"))
    assert any(r["Nom"] == "C" and r["Activité cochée non honorée"] == "Gym douce" for r in coche)
    assert not any(r["Nom"] in ("A", "B", "E") for r in coche)

    # Gestanet 'Jeux de société' (gratuite) = tous les cocheurs A, B, D
    jeux = {r["Nom"] for r in read_csv(os.path.join(sortie, "gestanet", norm_label("Jeux de société")))}
    assert jeux == {"A", "B", "D"}
    # Gestanet 'Gym douce' = ceux qui ont PAYÉ gym douce -> A et E
    gym = {r["Nom"] for r in read_csv(os.path.join(sortie, "gestanet", norm_label("Gym douce")))}
    assert gym == {"A", "E"}
    # Gestanet 'Pilates' = ceux qui ont PAYÉ pilates -> B et E (E est bien dans les DEUX)
    pil = {r["Nom"] for r in read_csv(os.path.join(sortie, "gestanet", norm_label("Pilates")))}
    assert pil == {"B", "E"}

    # Consolidé : une colonne par activité avec le statut par personne
    cons = {r["Nom"]: r for r in read_csv(os.path.join(sortie, "consolide.csv"))}
    for col in ("Gym douce", "Pilates", "Jeux de société", "Adhésion", "Nb activités"):
        assert col in cons["E"]
    assert cons["E"]["Gym douce"] == "Payé" and cons["E"]["Pilates"] == "Payé"
    assert cons["E"]["Adhésion"] == "Validé"
    assert cons["C"]["Gym douce"] == "À régler"          # cochée, campagne existe, pas payée
    assert cons["D"]["Jeux de société"] == "Gratuit"     # activité gratuite cochée


def norm_label(lbl):
    return fc.norm(lbl) + ".csv"


def test_run_activites_depuis_colonne_options_api(tmp_path, write_csv):
    # Export API : les activités cochées sont dans la colonne 'Options' (séparées par ';'),
    # pas en colonnes distinctes. Les gratuites doivent apparaître dans le consolidé + Gestanet.
    adh_headers = ["Référence commande", "Statut de la commande", "Nom adhérent", "Prénom adhérent",
                   "Email", "Sexe/Civilité", "Ville", "Tarif", "Options"]
    def a(ref, nom, options):
        return {"Référence commande": ref, "Statut de la commande": "Validé", "Nom adhérent": nom,
                "Prénom adhérent": nom.lower(), "Email": nom.lower() + "@ex.com",
                "Sexe/Civilité": "Féminin", "Ville": "daux", "Tarif": "Adhésion Adulte", "Options": options}
    write_csv("export-adhesion-2025-2026.csv", adh_headers,
              [a("1", "UN", "Yoga; Jeux de société"), a("2", "DEUX", "Jeux de société")])
    write_csv("export-yoga-2025-2026.csv",
              ["Référence commande", "Statut de la commande", "Nom adhérent", "Prénom adhérent", "Tarif"],
              [{"Référence commande": "9", "Statut de la commande": "Validé",
                "Nom adhérent": "UN", "Prénom adhérent": "un", "Tarif": "Yoga"}])
    (tmp_path / "config.json").write_text(json.dumps({
        "adhesion_file": "export-adhesion-2025-2026.csv",
        "forcer": {"export-yoga-2025-2026.csv": "Yoga"}}), encoding="utf-8")

    sortie = str(tmp_path / "_out")
    fc.run(str(tmp_path), sortie, "2025-2026")

    cons = {r["Nom"]: r for r in read_csv(os.path.join(sortie, "consolide.csv"))}
    assert "Jeux de société" in cons["UN"]                       # activité gratuite = colonne présente
    assert cons["UN"]["Yoga"] == "Payé"
    assert cons["UN"]["Jeux de société"] == "Gratuit"
    assert cons["DEUX"]["Jeux de société"] == "Gratuit"
    # Gestanet de l'activité gratuite = les deux cocheurs
    jeux = {r["Nom"] for r in read_csv(os.path.join(sortie, "gestanet", norm_label("Jeux de société")))}
    assert jeux == {"UN", "DEUX"}


def test_routage_libelle_campagne_different_de_ladhesion(tmp_path, write_csv):
    # L'adhésion coche « Gym douce » ; la campagne dit « Gymnastique douce » dans Options.
    # La correspondance par mots doit router la personne vers Gym douce (Payé), pas « À régler ».
    adh_headers = ["Référence commande", "Statut de la commande", "Nom adhérent", "Prénom adhérent",
                   "Email", "Options"]
    write_csv("export-adhesion-2025-2026.csv", adh_headers, [
        {"Référence commande": "1", "Statut de la commande": "Validé", "Nom adhérent": "PROJETTI",
         "Prénom adhérent": "Danielle", "Email": "d@ex.com", "Options": "Gym douce; Stretching"}])
    write_csv("export-gymnastique-2025-2026.csv",
              ["Référence commande", "Statut de la commande", "Nom adhérent", "Prénom adhérent", "Tarif", "Options"],
              [{"Référence commande": "9", "Statut de la commande": "Validé", "Nom adhérent": "PROJETTI",
                "Prénom adhérent": "Danielle", "Tarif": "Adhésion annuelle 2 activités",
                "Options": "Gymnastique douce; Stretching"}])
    (tmp_path / "config.json").write_text(json.dumps({
        "adhesion_file": "export-adhesion-2025-2026.csv",
        "forcer": {"export-gymnastique-2025-2026.csv": ["Gym douce", "Pilates", "Stretching", "Body sculpt"]}
    }), encoding="utf-8")

    sortie = str(tmp_path / "_out")
    fc.run(str(tmp_path), sortie, "2025-2026")

    cons = {r["Nom"]: r for r in read_csv(os.path.join(sortie, "consolide.csv"))}
    assert cons["PROJETTI"]["Gym douce"] == "Payé"
    assert cons["PROJETTI"]["Stretching"] == "Payé"
    coche = read_csv(os.path.join(sortie, "anomalies_activite_cochee_non_payee.csv"))
    assert not any(r["Nom"] == "PROJETTI" for r in coche)     # plus d'anomalie « à régler »


def test_run_preserve_saisie_manuelle(tmp_path, write_csv):
    adh_headers = ["Référence commande", "Statut de la commande", "Nom adhérent", "Prénom adhérent",
                   "Email", "Options"]
    write_csv("export-adhesion-2025-2026.csv", adh_headers,
              [{"Référence commande": "1", "Statut de la commande": "Validé", "Nom adhérent": "UN",
                "Prénom adhérent": "Alice", "Email": "a@ex.com", "Options": "Jeux de société"}])
    (tmp_path / "config.json").write_text(json.dumps({"adhesion_file": "export-adhesion-2025-2026.csv"}),
                                          encoding="utf-8")
    sortie = str(tmp_path / "_out")
    fc.run(str(tmp_path), sortie, "2025-2026")

    # l'utilisateur saisit un n° Gestanet et AJOUTE une colonne "Remarques"
    path = os.path.join(sortie, "consolide.csv")
    rows = read_csv(path)
    cols = list(rows[0].keys()) + ["Remarques"]
    rows[0]["N° adhérent Gestanet"] = "F3102356"
    rows[0]["Remarques"] = "payé en espèces"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";"); w.writeheader(); w.writerows(rows)

    # 2e exécution : les saisies manuelles doivent être conservées
    fc.run(str(tmp_path), sortie, "2025-2026")
    r = {x["Nom"]: x for x in read_csv(path)}["UN"]
    assert r["N° adhérent Gestanet"] == "F3102356"
    assert r.get("Remarques") == "payé en espèces"


def test_run_dossier_vide(tmp_path):
    with pytest.raises(SystemExit):
        fc.run(str(tmp_path), str(tmp_path / "out"), "")
