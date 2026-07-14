#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
helloasso_export.py — Récupère automatiquement les campagnes HelloAsso via l'API
et écrit un CSV par formulaire, directement exploitable par foyer_controle.py.
Aucune dépendance à installer (bibliothèque standard Python 3 uniquement).

PRÉ-REQUIS : une clé API HelloAsso
  HelloAsso → connectez-vous → « Mon compte » → « Intégrations et API »
  → créez un client API : vous obtenez un client_id et un client_secret.
  (Privilèges accordés : AccessPublicData, AccessTransactions — suffisants ici.)

CONFIGURATION : créez un fichier « helloasso.json » à côté de ce script :
  {
    "client_id":        "VOTRE_CLIENT_ID",
    "client_secret":    "VOTRE_CLIENT_SECRET",
    "organization_slug":"foyer-rural-mondonville",
    "environnement":    "production",           // ou "sandbox"
    "types_formulaires":["Membership","Event"], // formulaires à exporter
    "exclure":          []                        // slugs de formulaires à ignorer
  }
  (Le slug d'organisation est la fin de l'URL de votre page HelloAsso :
   https://www.helloasso.com/associations/<organization_slug>)

UTILISATION :
  python3 helloasso_export.py                 # config = ./helloasso.json, sortie = ./exports_api
  python3 helloasso_export.py --config x.json --sortie DOSSIER
Puis :
  python3 foyer_controle.py  DOSSIER  --saison "2025-2026"
"""
import argparse, csv, json, os, re, ssl, sys, time
import urllib.request, urllib.parse, urllib.error

def bornes_saison(s):
    """'2025-2026' -> ('2025-07-01T00:00:00', '2026-08-31T23:59:59'). '2021-22' accepté."""
    m = re.match(r"\s*(\d{4})\s*[-/]\s*(\d{2,4})\s*$", str(s or ""))
    if not m:
        return None, None
    y1 = int(m.group(1)); g2 = m.group(2)
    y2 = int(g2) if len(g2) == 4 else (y1 // 100) * 100 + int(g2)
    return f"{y1}-07-01T00:00:00", f"{y2}-08-31T23:59:59"

BASES = {
    "production": ("https://api.helloasso.com/v5", "https://api.helloasso.com/oauth2/token"),
    "sandbox":    ("https://api.helloasso-sandbox.com/v5", "https://api.helloasso-sandbox.com/oauth2/token"),
}

# Colonnes de base reproduisant l'export manuel HelloAsso.
# "Tarif" et "Options" portent l'activité/souscription réellement choisie (essentiel pour
# répartir les campagnes qui regroupent plusieurs activités, ex. gymnastique, zumba+cardio).
BASE_COLS = ["Référence commande", "Date de la commande", "Statut de la commande",
             "Nom adhérent", "Prénom adhérent", "Nom payeur", "Prénom payeur", "Email payeur",
             "Tarif", "Options"]

ETATS_VALIDES = {"processed", "registered", "authorized", "paid"}

MSG_SSL = (
    "Erreur de certificat SSL. Sur un Python installé depuis python.org (macOS), "
    "lancez une fois :\n"
    "    /Applications/Python\\ 3.10/Install\\ Certificates.command\n"
    "(ou : open \"/Applications/Python 3.10/Install Certificates.command\")\n"
    "Alternative : pip install certifi  — puis relancez.\n"
    "En dernier recours seulement : ajoutez \"verifier_ssl\": false dans helloasso.json "
    "(ou l'option --insecure), à éviter avec des identifiants."
)

def _make_context(verifier=True):
    if not verifier:
        c = ssl.create_default_context()
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
        return c
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

# User-Agent explicite : l'UA par défaut d'urllib ("Python-urllib/…") est souvent
# bloqué par le pare-feu applicatif de HelloAsso (403). On envoie un UA classique.
USER_AGENT = "FoyerRuralMondonville-API/1.0 (+python)"

# ----------------------------------------------------------------------------- HTTP
def _post_form(url, data, context=None):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60, context=context or _make_context()) as r:
        return json.loads(r.read().decode())

def _get(url, token, context=None):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90, context=context or _make_context()) as r:
        return json.loads(r.read().decode())

class HA:
    def __init__(self, cfg):
        env = cfg.get("environnement", "production")
        if env not in BASES:
            raise SystemExit("environnement doit être 'production' ou 'sandbox'")
        self.base, self.token_url = BASES[env]
        self.cfg = cfg
        self.token = None
        self.ctx = _make_context(cfg.get("verifier_ssl", True))

    def auth(self):
        try:
            j = _post_form(self.token_url, {"grant_type": "client_credentials",
                "client_id": self.cfg["client_id"], "client_secret": self.cfg["client_secret"]}, self.ctx)
        except urllib.error.HTTPError as e:
            corps = ""
            try: corps = e.read().decode()[:400]
            except Exception: pass
            indice = ("Requête probablement bloquée (User-Agent) ou privilèges insuffisants sur la clé API."
                      if e.code == 403 else "Vérifiez client_id / client_secret.")
            raise SystemExit(f"Échec d'authentification ({e.code}). {indice}\n{corps}")
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, ssl.SSLError) or "CERTIFICATE" in str(reason).upper():
                raise SystemExit(MSG_SSL)
            raise SystemExit(f"Impossible de joindre l'API HelloAsso : {reason}")
        self.token = j["access_token"]

    def get_pages(self, path, params=None):
        """Génère toutes les entrées 'data' en suivant la pagination (continuationToken)."""
        params = dict(params or {})
        params.setdefault("pageSize", 100)
        while True:
            url = f"{self.base}{path}?{urllib.parse.urlencode(params)}"
            try:
                j = _get(url, self.token, self.ctx)
            except urllib.error.HTTPError as e:
                raise SystemExit(f"Erreur API {e.code} sur {path} : {e.read().decode()[:300]}")
            for item in j.get("data", []):
                yield item
            pg = j.get("pagination", {}) or {}
            token = pg.get("continuationToken")
            if not token or not j.get("data"):
                break
            params["continuationToken"] = token

# ----------------------------------------------------------------------------- mapping
def g(d, *path, default=""):
    for k in path:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
        if d is None:
            return default
    return d if d is not None else default

def statut(state):
    return "Validé" if str(state).strip().lower() in ETATS_VALIDES else (state or "")

def ligne_depuis_item(it):
    """Construit une ligne 'plate' à partir d'un item (participant) de l'API."""
    order = it.get("order", {}) if isinstance(it.get("order"), dict) else {}
    payer = it.get("payer") or order.get("payer") or {}
    user = it.get("user") or {}
    options = it.get("options") or []
    row = {
        "Référence commande": g(order, "id") or g(it, "id"),
        "Date de la commande": g(order, "date") or g(it, "order", "date"),
        "Statut de la commande": statut(it.get("state")),
        "Nom adhérent": g(user, "lastName") or g(payer, "lastName"),
        "Prénom adhérent": g(user, "firstName") or g(payer, "firstName"),
        "Nom payeur": g(payer, "lastName"),
        "Prénom payeur": g(payer, "firstName"),
        "Email payeur": g(payer, "email"),
        "Tarif": g(it, "name"),                                   # libellé du tarif choisi = activité
        "Options": "; ".join(str(o.get("name", "")) for o in options if isinstance(o, dict)),
    }
    # champs personnalisés du formulaire (activités cochées, état civil, etc.)
    for cf in it.get("customFields") or []:
        nom = (cf.get("name") or "").strip()
        if nom:
            row[nom] = cf.get("answer", cf.get("value", ""))
    # repli sur les infos payeur/acheteur pour l'état civil si non présent en custom field
    for cle, val in [("Email", g(payer, "email")), ("Adresse", g(payer, "address")),
                     ("Code Postal", g(payer, "zipCode")), ("Ville", g(payer, "city")),
                     ("Date de naissance", g(payer, "dateOfBirth"))]:
        row.setdefault(cle, val)
    return row

def nom_forme(it):
    order = it.get("order", {}) if isinstance(it.get("order"), dict) else {}
    return (g(order, "formType") or g(it, "formType"),
            g(order, "formSlug") or g(it, "formSlug"),
            g(order, "formName") or g(it, "formName"))

def slugify(s):
    return "".join(c if c.isalnum() else "-" for c in str(s).lower()).strip("-")[:60] or "formulaire"

# ----------------------------------------------------------------------------- run
def run(config_path, sortie, insecure=False, depuis=None, jusqu_a=None, saison=None):
    if not os.path.isfile(config_path):
        raise SystemExit(f"Config introuvable : {config_path}\n"
                         "Créez un fichier helloasso.json (voir l'entête du script).")
    cfg = json.load(open(config_path, encoding="utf-8"))
    for k in ("client_id", "client_secret", "organization_slug"):
        if not cfg.get(k):
            raise SystemExit(f"Champ manquant dans la config : {k}")
    if insecure:
        cfg["verifier_ssl"] = False
        print("⚠ Vérification SSL désactivée (--insecure).")

    # Filtre de période (côté serveur, sur la date de commande) : réduit le volume et les appels
    depuis = depuis or cfg.get("depuis")
    jusqu_a = jusqu_a or cfg.get("jusqu_a")
    saison = saison or cfg.get("saison")
    if saison and not (depuis and jusqu_a):
        d, t = bornes_saison(saison)
        depuis = depuis or d
        jusqu_a = jusqu_a or t

    ha = HA(cfg)
    print("Authentification…")
    ha.auth()

    org = cfg["organization_slug"]
    types = set(cfg.get("types_formulaires") or ["Membership"])
    exclure = set(cfg.get("exclure") or [])
    exclure_contient = [s.lower() for s in (cfg.get("exclure_si_nom_contient") or [])]

    params = {"withDetails": "true"}
    if depuis: params["from"] = depuis
    if jusqu_a: params["to"] = jusqu_a
    if depuis or jusqu_a:
        print(f"Filtre période (date de commande) : {depuis or '…'} → {jusqu_a or '…'}")

    print("Récupération des participations (API /items)…")
    par_forme = {}          # (type,slug,name) -> [rows]
    n = 0
    for it in ha.get_pages(f"/organizations/{org}/items", params):
        ftype, fslug, fname = nom_forme(it)
        if types and ftype and ftype not in types:
            continue
        if fslug in exclure:
            continue
        cible = (str(fname) + " " + str(fslug)).lower()
        if any(s in cible for s in exclure_contient):
            continue
        par_forme.setdefault((ftype, fslug, fname), []).append(ligne_depuis_item(it))
        n += 1
        if n % 500 == 0:
            print(f"   … {n} participations")

    if not par_forme:
        raise SystemExit("Aucune donnée récupérée. Vérifiez le slug d'organisation, "
                         "les types de formulaires et les privilèges de la clé API.")

    os.makedirs(sortie, exist_ok=True)
    print(f"\n{n} participations réparties sur {len(par_forme)} formulaire(s) :")
    for (ftype, fslug, fname), rows in sorted(par_forme.items(), key=lambda x: x[0][2] or ""):
        # entêtes = colonnes de base + toutes les colonnes personnalisées rencontrées
        extra = []
        for r in rows:
            for k in r:
                if k not in BASE_COLS and k not in extra:
                    extra.append(k)
        cols = BASE_COLS + extra
        # nom de fichier : contient le nom du formulaire -> détection auto par foyer_controle.py
        prefixe = "export-adhesion-" if "adhesion" in slugify(fname) or "adhesion" in slugify(fslug) \
                  else "export-"
        chemin = os.path.join(sortie, f"{prefixe}{slugify(fname or fslug)}.csv")
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, delimiter=";", extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in cols})
        print(f"   - {fname or fslug}  ({len(rows)} lignes)  ->  {os.path.basename(chemin)}")

    print(f"\n→ CSV écrits dans : {sortie}")
    print(f"Étape suivante :  python3 foyer_controle.py  \"{sortie}\"  --saison \"2025-2026\"")

def main():
    p = argparse.ArgumentParser(description="Export automatique des campagnes HelloAsso via l'API.")
    p.add_argument("--config", default="helloasso.json", help="fichier de configuration (défaut : helloasso.json)")
    p.add_argument("--sortie", default="exports_api", help="dossier de sortie (défaut : exports_api)")
    p.add_argument("--saison", help="raccourci de période, ex. 2025-2026 (1er juil. → 31 août)")
    p.add_argument("--depuis", help="date de début (from), ex. 2025-07-01")
    p.add_argument("--jusqu-a", dest="jusqu_a", help="date de fin (to), ex. 2026-08-31")
    p.add_argument("--insecure", action="store_true",
                   help="désactive la vérification SSL (dernier recours, déconseillé)")
    a = p.parse_args()
    run(a.config, a.sortie, a.insecure, a.depuis, a.jusqu_a, a.saison)

if __name__ == "__main__":
    main()
