# -*- coding: utf-8 -*-
"""Tests unitaires de helloasso_export.py (connecteur API, sans appel réseau réel)."""
import os, json, csv
import urllib.error
import pytest
import helloasso_export as he
from conftest import read_csv


# --------------------------------------------------------------------- helpers purs
def test_g_getter_imbrique():
    assert he.g({"a": {"b": 1}}, "a", "b") == 1
    assert he.g({}, "a", default="x") == "x"
    assert he.g({"a": None}, "a", "b", default="z") == "z"
    assert he.g("pas un dict", "a", default="d") == "d"


@pytest.mark.parametrize("state,attendu", [
    ("Processed", "Validé"), ("Registered", "Validé"), ("Authorized", "Validé"),
    ("Canceled", "Canceled"), ("", ""),
])
def test_statut(state, attendu):
    assert he.statut(state) == attendu


def test_slugify():
    assert he.slugify("Yoga Vinyasa !") == "yoga-vinyasa"
    assert he.slugify("") == "formulaire"


def test_nom_forme():
    it = {"order": {"formType": "Membership", "formSlug": "adhesion-2025",
                    "formName": "Adhesion annuelle"}}
    assert he.nom_forme(it) == ("Membership", "adhesion-2025", "Adhesion annuelle")


def test_ligne_depuis_item_flatten_et_fallback():
    it = {
        "id": 111, "state": "Processed",
        "order": {"id": 5001, "date": "2025-09-01", "formType": "Membership",
                  "formSlug": "adhesion", "formName": "Adhesion annuelle"},
        "payer": {"firstName": "Marie", "lastName": "DUPONT", "email": "marie@ex.com",
                  "zipCode": "31700", "city": "Mondonville"},
        "user": {"firstName": "Marie", "lastName": "DUPONT"},
        "customFields": [
            {"name": "Sexe/Civilité", "answer": "Féminin"},
            {"name": "Yoga", "answer": "Oui"},
        ],
    }
    row = he.ligne_depuis_item(it)
    assert row["Référence commande"] == 5001
    assert row["Statut de la commande"] == "Validé"
    assert row["Nom adhérent"] == "DUPONT"
    assert row["Email payeur"] == "marie@ex.com"
    assert row["Sexe/Civilité"] == "Féminin"      # depuis customFields
    assert row["Yoga"] == "Oui"                    # activité cochée aplatie
    assert row["Code Postal"] == "31700"           # repli payeur (absent des customFields)
    assert row["Ville"] == "Mondonville"


# --------------------------------------------------------------------- pagination
def test_get_pages_pagination(monkeypatch):
    pages = [
        {"data": [1, 2], "pagination": {"continuationToken": "t1"}},
        {"data": [3], "pagination": {"continuationToken": "t2"}},
        {"data": [], "pagination": {}},
    ]
    calls = {"n": 0}

    def fake_get(url, token, context=None):
        p = pages[calls["n"]]
        calls["n"] += 1
        return p

    monkeypatch.setattr(he, "_get", fake_get)
    ha = he.HA({"environnement": "production"})
    ha.token = "x"
    assert list(ha.get_pages("/organizations/org/items")) == [1, 2, 3]


# --------------------------------------------------------------------- auth
def test_auth_ok(monkeypatch):
    monkeypatch.setattr(he, "_post_form", lambda url, data, context=None: {"access_token": "tok123"})
    ha = he.HA({"environnement": "production", "client_id": "a", "client_secret": "b"})
    ha.auth()
    assert ha.token == "tok123"


def test_auth_echec(monkeypatch):
    def boom(url, data, context=None):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)
    monkeypatch.setattr(he, "_post_form", boom)
    ha = he.HA({"environnement": "production", "client_id": "a", "client_secret": "b"})
    with pytest.raises(SystemExit):
        ha.auth()


def test_environnement_invalide():
    with pytest.raises(SystemExit):
        he.HA({"environnement": "n'importe quoi"})


def test_make_context_insecure_desactive_verif():
    import ssl
    c = he._make_context(verifier=False)
    assert c.verify_mode == ssl.CERT_NONE


def test_auth_erreur_certificat_ssl(monkeypatch):
    import ssl
    def boom(url, data, context=None):
        raise urllib.error.URLError(ssl.SSLError("certificate verify failed"))
    monkeypatch.setattr(he, "_post_form", boom)
    ha = he.HA({"environnement": "production", "client_id": "a", "client_secret": "b"})
    with pytest.raises(SystemExit):
        ha.auth()


# --------------------------------------------------------------------- run() mocké
def test_run_ecrit_csv_par_formulaire(tmp_path, monkeypatch):
    items = [
        {"id": 1, "state": "Processed",
         "order": {"id": 5001, "date": "2025-09-01", "formType": "Membership",
                   "formSlug": "adhesion-annuelle", "formName": "Adhesion annuelle FRM"},
         "payer": {"firstName": "Marie", "lastName": "DUPONT", "email": "marie@ex.com"},
         "user": {"firstName": "Marie", "lastName": "DUPONT"},
         "customFields": [{"name": "Yoga", "answer": "Oui"}]},
        {"id": 2, "state": "Registered",
         "order": {"id": 6001, "date": "2025-09-05", "formType": "Event",
                   "formSlug": "yoga-vinyasa", "formName": "Yoga Vinyasa FRM"},
         "payer": {"firstName": "Marie", "lastName": "DUPONT", "email": "marie@ex.com"},
         "user": {"firstName": "Marie", "lastName": "DUPONT"},
         "customFields": []},
    ]
    monkeypatch.setattr(he.HA, "auth", lambda self: None)
    monkeypatch.setattr(he.HA, "get_pages", lambda self, path, params=None: iter(items))

    cfg = {"client_id": "a", "client_secret": "b", "organization_slug": "frm",
           "environnement": "production"}
    cfg_path = tmp_path / "helloasso.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    sortie = tmp_path / "exports_api"

    he.run(str(cfg_path), str(sortie))

    fichiers = sorted(os.listdir(sortie))
    assert len(fichiers) == 2
    # le formulaire d'adhésion est préfixé "export-adhesion-" (détection auto en aval)
    assert any(f.startswith("export-adhesion-") for f in fichiers)
    # contenu : la campagne yoga a bien une ligne DUPONT
    yoga_file = [f for f in fichiers if "yoga" in f][0]
    rows = read_csv(os.path.join(sortie, yoga_file))
    assert rows and rows[0]["Nom adhérent"] == "DUPONT"


@pytest.mark.parametrize("saison,attendu_from,attendu_to", [
    ("2025-2026", "2025-07-01T00:00:00", "2026-08-31T23:59:59"),
    ("2021-22", "2021-07-01T00:00:00", "2022-08-31T23:59:59"),
])
def test_bornes_saison(saison, attendu_from, attendu_to):
    assert he.bornes_saison(saison) == (attendu_from, attendu_to)


def test_bornes_saison_invalide():
    assert he.bornes_saison("nawak") == (None, None)


def test_run_filtre_periode_passe_from_to(tmp_path, monkeypatch):
    captured = {}
    def fake_get_pages(self, path, params=None):
        captured["params"] = params or {}
        return iter([])          # aucun item -> run lèvera SystemExit ensuite
    monkeypatch.setattr(he.HA, "auth", lambda self: None)
    monkeypatch.setattr(he.HA, "get_pages", fake_get_pages)
    cfg = {"client_id": "a", "client_secret": "b", "organization_slug": "frm"}
    (tmp_path / "helloasso.json").write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(SystemExit):
        he.run(str(tmp_path / "helloasso.json"), str(tmp_path / "out"), saison="2025-2026")
    assert captured["params"]["from"] == "2025-07-01T00:00:00"
    assert captured["params"]["to"] == "2026-08-31T23:59:59"
    assert captured["params"]["withDetails"] == "true"


def test_run_config_absente(tmp_path):
    with pytest.raises(SystemExit):
        he.run(str(tmp_path / "inexistant.json"), str(tmp_path / "out"))


def test_run_config_incomplete(tmp_path):
    cfg_path = tmp_path / "helloasso.json"
    cfg_path.write_text(json.dumps({"client_id": "a"}), encoding="utf-8")  # manque secret/slug
    with pytest.raises(SystemExit):
        he.run(str(cfg_path), str(tmp_path / "out"))
