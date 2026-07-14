#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
foyer_controle.py — Consolidation, contrôles et préparation Gestanet à partir des exports HelloAsso.
Foyer Rural de Mondonville · 0 € · aucun service en ligne requis.

NOUVEAU : détection AUTOMATIQUE des campagnes présentes dans le dossier
(par nom de fichier, avec repli sur le contenu) et prise en charge de
PLUSIEURS exports pour une même activité (ex. Yoga Vinyasa + Yoga Hata).

UTILISATION
-----------
1) Déposer dans un dossier : l'export d'ADHÉSION + chaque export de campagne d'ACTIVITÉ (CSV).
2) Lancer :
       python3 foyer_controle.py  MON_DOSSIER  --saison "2025-2026"
   Le programme détecte seul quelle campagne correspond à quelle activité et
   affiche le mappage. Aucune config n'est obligatoire.
3) Résultats dans MON_DOSSIER/_resultats/ (voir le LISEZMOI).

AJUSTEMENTS MANUELS (facultatifs) — via config.json dans le dossier :
   {
     "forcer":  { "un-fichier.csv": "Nom exact de l'activité" },
     "ignorer_fichiers": [ "un-autre-fichier.csv" ]
   }
Options : --sortie dossier   --saison "2025-2026"
"""
import argparse, csv, json, os, re, sys, unicodedata
from collections import defaultdict

# ----------------------------------------------------------------------------- utils
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")

def norm(s):
    return re.sub(r"[^a-z0-9]", "", strip_accents((s or "").strip().lower()))

def cle_nom(nom, prenom):
    return (norm(nom), norm(prenom))

def norm_email(s):
    return (s or "").strip().lower().strip(" .")

def clean_email(s):
    return (s or "").strip().strip(" .")

def valide(statut):
    return strip_accents((statut or "").strip().lower()).startswith("valid")

def est_coche(v):
    """Case cochée : toute valeur non vide et non négative (gère 'Oui', 'true', libellé…)."""
    v = strip_accents((v or "").strip().lower())
    return v not in ("", "non", "no", "false", "0", "n", "na")

def tel(v):
    if not v: return ""
    v = re.sub(r"[ .\-/]", "", v.strip())
    if v.startswith("+33"): v = "0" + v[3:]
    elif v.startswith("0033"): v = "0" + v[4:]
    elif v.startswith("33") and len(v) == 11: v = "0" + v[2:]
    if len(v) == 9 and not v.startswith("0"): v = "0" + v
    return v

def date_fr(v):
    v = (v or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", v)
    if m: return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", v)
    if m: return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    return v

def civilite_gestanet(v):
    x = strip_accents((v or "").strip().lower())
    if x.startswith("f") or x.startswith("mme") or x.startswith("mad"): return "Mme"
    return "M"

def lire_csv(chemin):
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        head = f.readline()
    delim = ";" if head.count(";") >= head.count(",") else ","
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delim))

CHAMPS_GESTANET = ["Nom","Prénom","Sexe/Civilité","Date de naissance","Adresse (ligne 1)",
    "Adresse (ligne 2)","Code postal","Ville","Pays","Email","Email 2","Tél. fixe","Tél. portable","Commentaire"]

# Abréviations de noms de campagnes -> fragment à retrouver dans le libellé d'activité
SYNONYMES = {
    "zumba":"zumba","step":"step","pilates":"pilates","stretching":"stretching","couture":"couture",
    "yoga":"yoga","hata":"yoga","hatha":"yoga","vinyasa":"yoga","vinysa":"yoga",
    "gym":"gymdouce","douce":"gymdouce",
    "sculpt":"bodysculpt","body":"bodysculpt","bodysculpt":"bodysculpt",
    "peinture":"peinture","art":"artfloral","floral":"artfloral",
    "eveil":"eveil","corporel":"eveil",
    "tt":"tennisdetable","ttenfant":"tennisdetable","ttado":"tennisdetable",
    "tennis":"tennisdetable","pingpong":"tennisdetable","table":"tennisdetable",
    "italien":"italien","italiano":"italien","parliamo":"italien",
    "genealogie":"genealogie","histoire":"histoire","patrimoine":"histoire",
    "nature":"nature","environnement":"nature","rando":"randonnee","randonnee":"randonnee",
    "jeux":"jeux","societe":"jeux","sophro":"sophrologie","sophrologie":"sophrologie",
    "brico":"bricotheque","bricotheque":"bricotheque","evenement":"evenement","evenements":"evenement",
}
STOP_FN = {"mondonville","foyer","rural","export","rectification","erreur","erreurs","prelevement",
    "prelevements","annuelle","annuel","saison","pour","avec","les","des","aux","foyerrural","adhesion"}

# ----------------------------------------------------------------------------- détection
EXCL_ACT_PREFIX = ("j'ai", "j'autorise", "conform", "la personne", "si la personne",
                   "je comprends", "montant ", "pere", "père", "mere", "mère")
EXCL_ACT = {"référence commande","date de la commande","statut de la commande","nom adhérent",
    "prénom adhérent","nom payeur","prénom payeur","email payeur","raison sociale","moyen de paiement",
    "tarif","montant tarif","code promo","montant code promo","carte d'adhérent","email","email 2",
    "adresse","complément d'adresse","code postal","ville","pays","sexe/civilité","date de naissance",
    "téléphone","téléphone fixe","téléphone portable","commentaire","commentaires (hors ligne)",
    "nom et prénom du père","nom et prénom de la mère","téléphone du père","téléphone de la mère",
    "père représentant légal de l'enfant","mère représentante légale de l'enfant"}

def colonnes_activites(entetes, rows=None):
    """Export manuel : activité = colonne suivie d'une 'Montant <activité>'.
       Export API (pas de 'Montant X') : repli sur les colonnes de type case à cocher (Oui/Non)."""
    montant = [h for h in entetes if ("Montant " + h) in entetes]
    if montant:
        return montant
    if not rows:
        return []
    acts = []
    for h in entetes:
        hl = h.strip().lower()
        if hl in EXCL_ACT or any(hl.startswith(p) for p in EXCL_ACT_PREFIX):
            continue
        vals = {(r.get(h) or "").strip().lower() for r in rows}
        vals.discard("")
        if vals and vals <= {"oui", "non"} and "oui" in vals:
            acts.append(h)
    return acts

def activites_payantes(entetes):
    payantes = set()
    for i, h in enumerate(entetes):
        if h.startswith("J'ai compris que cette activité est payante") and i >= 2:
            payantes.add(entetes[i-2])
    return payantes

def resoudre_token(tok, acts):
    if tok.startswith("tt"):          # tt, ttenfant, ttadulte, ttado… -> tennis de table
        sub = "tennisdetable"
    else:
        sub = SYNONYMES.get(tok, tok if len(tok) >= 4 else None)
    if not sub:
        return None
    matches = [a for a in acts if sub in norm(a)]
    return matches[0] if len(matches) == 1 else None

def detecter_activite(fichier, acts, checked_sets, col_statut):
    """Détection par NOM DE FICHIER (fiable). Le contenu ne sert qu'à départager
    des candidats à égalité, jamais à classer seul (trop risqué : mêmes adhérents
    d'une activité à l'autre). Un fichier sans indice de nom est 'non reconnu'."""
    base = os.path.basename(fichier)
    tokens = [t for t in re.findall(r"[a-z]+", strip_accents(base.lower())) if t not in STOP_FN]
    votes = defaultdict(int)
    for t in tokens:
        a = resoudre_token(t, acts)
        if a:
            votes[a] += 1
    rows = lire_csv(fichier)
    P = {cle_nom(r.get("Nom adhérent"), r.get("Prénom adhérent")) for r in rows if valide(r.get(col_statut))}
    def score(a):
        return (len(P & checked_sets.get(a, set())) / len(P)) if P else 0.0
    if votes:
        top = max(votes.values())
        cands = [a for a, v in votes.items() if v == top]
        if len(cands) == 1:
            return cands[0], "nom de fichier", round(score(cands[0]), 2)
        best = max(cands, key=score)   # départage par contenu entre candidats du nom
        return best, "nom de fichier + contenu", round(score(best), 2)
    # aucun indice dans le nom -> non reconnu (on donne juste une piste indicative)
    piste = max(acts, key=score) if (P and acts) else None
    methode = f"non reconnu (piste : {piste} {int(score(piste)*100)}%)" if piste else "non reconnu"
    return None, methode, 0.0

def _match_cle(nk, nb):
    """Une clé de config matche un fichier si elle est égale au nom normalisé,
    ou (mot-clé) si elle en est une sous-chaîne (>= 3 caractères)."""
    return nk == nb or (len(nk) >= 3 and nk in nb)

def construire_mappage(adhesion_file, activity_files, acts, checked_sets, col_statut, cfg):
    """Retourne mapping (activité -> [fichiers]), rapport, et file_labels (fichier -> {activités}).
    Les clés de 'forcer'/'ignorer_fichiers' peuvent être un nom de fichier exact OU un mot-clé
    (ex. 'gymnastique'), ce qui rend la config indépendante de l'année. Une valeur 'forcer' peut
    être une chaîne OU une liste (campagne couvrant plusieurs activités). Les libellés de toutes
    les clés qui matchent un fichier sont cumulés."""
    forcer = [(norm(k), (v if isinstance(v, list) else [v])) for k, v in (cfg.get("forcer") or {}).items()]
    ignorer = [norm(x) for x in (cfg.get("ignorer_fichiers") or [])]
    mapping = defaultdict(list)
    file_labels = {}
    rapport = []
    for f in activity_files:
        b = os.path.basename(f); nb = norm(b)
        if any(_match_cle(ig, nb) for ig in ignorer):
            rapport.append((b, "(ignoré)", "config", 0.0)); continue
        labels = []
        for nk, labs in forcer:
            if _match_cle(nk, nb):
                for l in labs:
                    if l not in labels:
                        labels.append(l)
        if labels:
            for lbl in labels:
                mapping[lbl].append(f)
            file_labels[f] = set(labels)
            rapport.append((b, " + ".join(labels), "forcé (config)", 0.0)); continue
        lbl, methode, sc = detecter_activite(f, acts, checked_sets, col_statut)
        if lbl:
            mapping[lbl].append(f); file_labels[f] = {lbl}
        rapport.append((b, lbl or "??? à mapper manuellement", methode, sc))
    return mapping, rapport, file_labels

# ----------------------------------------------------------------------------- Gestanet
def ligne_gestanet_depuis_adhesion(r, activite):
    return {"Nom": (r.get("Nom adhérent") or "").strip(), "Prénom": (r.get("Prénom adhérent") or "").strip(),
        "Sexe/Civilité": civilite_gestanet(r.get("Sexe/Civilité")), "Date de naissance": date_fr(r.get("Date de naissance")),
        "Adresse (ligne 1)": (r.get("Adresse") or "").strip(), "Adresse (ligne 2)": "",
        "Code postal": (r.get("Code Postal") or "").strip(), "Ville": (r.get("Ville") or "").strip().upper(),
        "Pays": "France", "Email": clean_email(r.get("Email") or r.get("Email payeur")), "Email 2": "",
        "Tél. fixe": tel(r.get("Téléphone fixe")), "Tél. portable": tel(r.get("Téléphone portable")),
        "Commentaire": f"Activité : {activite}"}

def ligne_gestanet_depuis_activite(r, activite):
    return {"Nom": (r.get("Nom adhérent") or "").strip(), "Prénom": (r.get("Prénom adhérent") or "").strip(),
        "Sexe/Civilité": "", "Date de naissance": "", "Adresse (ligne 1)": "", "Adresse (ligne 2)": "",
        "Code postal": "", "Ville": "", "Pays": "France", "Email": clean_email(r.get("Email payeur")), "Email 2": "",
        "Tél. fixe": "", "Tél. portable": tel(r.get("Téléphone")),
        "Commentaire": f"Activité : {activite} — adhérent autre foyer / état civil à compléter"}

def ecrire_csv(chemin, entetes, lignes):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=entetes, delimiter=";")
        w.writeheader(); w.writerows(lignes)

# ----------------------------------------------------------------------------- traitement
def run(dossier, sortie, saison, config_path=None):
    fichiers = [os.path.join(dossier, x) for x in os.listdir(dossier)
                if x.lower().endswith(".csv") and not x.startswith("_")]
    if not fichiers:
        print("Aucun CSV trouvé dans le dossier.", file=sys.stderr); sys.exit(1)

    cfg = {}
    cfg_path = config_path or os.path.join(dossier, "config.json")
    if os.path.isfile(cfg_path):
        try: cfg = json.load(open(cfg_path, encoding="utf-8"))
        except Exception: cfg = {}
    col_statut = cfg.get("colonne_statut", "Statut de la commande")

    # exclure tôt les fichiers ignorés (autres saisons, tests, etc.) — clé exacte ou mot-clé
    ignorer = [norm(x) for x in (cfg.get("ignorer_fichiers") or [])]
    fichiers = [f for f in fichiers
                if not any(_match_cle(ig, norm(os.path.basename(f))) for ig in ignorer)]

    def nb_lignes(f):
        try: return len(lire_csv(f))
        except Exception: return 0

    # fichier d'adhésion : soit pinné par la config (nom exact ou mot-clé), soit le plus gros parmi les "adhesion"
    if cfg.get("adhesion_file"):
        cible = norm(cfg["adhesion_file"])
        cands = [f for f in fichiers if _match_cle(cible, norm(os.path.basename(f)))]
        if not cands:
            raise SystemExit("adhesion_file de la config introuvable dans le dossier : " + cfg["adhesion_file"])
        adhesion_file = max(cands, key=nb_lignes)
    else:
        cands = [f for f in fichiers if "adhesion" in norm(os.path.basename(f))]
        adhesion_file = (max(cands, key=nb_lignes) if cands
                         else max(fichiers, key=lambda f: len(lire_csv(f)[0].keys()) if lire_csv(f) else 0))
    activity_files = [f for f in fichiers if f != adhesion_file]
    col_autre = cfg.get("colonne_autre_foyer",
                        "La personne inscrite est adhérente à un autre Foyer Rural ? si oui lequel")

    adh = lire_csv(adhesion_file)
    entetes = list(adh[0].keys()) if adh else []
    acts_colonnes = colonnes_activites(entetes, adh)   # colonnes cases (export manuel)

    def coche_row(r):
        # activités cochées : colonne "Options" (export API, séparateur ';') ET/OU colonnes cases (manuel)
        s = {t.strip() for t in re.split(r"[;|]", (r.get("Options") or "")) if t.strip()}
        for a in acts_colonnes:
            if est_coche(r.get(a)):
                s.add(a)
        return s

    # index adhérents validés + activités cochées (par clé et par activité)
    idx_nom, idx_email, checked_sets = {}, {}, defaultdict(set)
    coche_par_cle, acts_set = {}, set()
    for r in adh:
        if not valide(r.get(col_statut)):
            continue
        k = cle_nom(r.get("Nom adhérent"), r.get("Prénom adhérent"))
        idx_nom.setdefault(k, r)
        for e in (r.get("Email"), r.get("Email payeur")):
            e = norm_email(e)
            if e: idx_email.setdefault(e, r)
        cochees = coche_row(r)
        coche_par_cle[k] = coche_par_cle.get(k, set()) | cochees
        for a in cochees:
            checked_sets[a].add(k); acts_set.add(a)
    acts = sorted(acts_set)

    def est_adherent(nom, prenom, email):
        return cle_nom(nom, prenom) in idx_nom or norm_email(email) in idx_email

    # ---- mapping activité <-> fichiers (une campagne peut couvrir plusieurs activités) ----
    mapping, rapport_map, file_labels = construire_mappage(
        adhesion_file, activity_files, acts, checked_sets, col_statut, cfg)

    # lecture des fichiers de campagne (une fois)
    rows_fichier = {f: lire_csv(f) for f in file_labels}

    # colonne d'adhésion (case) correspondant à une activité
    def col_adhesion_pour(a):
        if a in entetes:
            return a
        return next((h for h in entetes if norm(h) == norm(a)), None)

    # activités réellement SOUSCRITES par une ligne de campagne, d'après le Tarif/Options choisi.
    # Correspondance par MOTS (tous les mots significatifs de l'activité présents dans le texte),
    # pour tolérer les variantes de libellé entre campagne et adhésion (ex. « Gymnastique douce » ↔ « Gym douce »).
    STOP_TARIF = {"de", "la", "le", "les", "du", "des", "au", "aux", "et", "un", "une", "tous", "toutes",
                  "ans", "cours", "adulte", "enfant", "enfants", "annuelle", "adhesion", "activite", "activites"}
    def tokens_sig(s):
        return [t for t in re.findall(r"[a-z]+", strip_accents((s or "").lower()))
                if len(t) >= 3 and t not in STOP_TARIF]
    def activites_du_row(r, labels):
        txt = norm((r.get("Tarif") or "") + " " + (r.get("Options") or "") + " " + (r.get("Formule") or ""))
        res = []
        for a in labels:
            toks = tokens_sig(a)
            if toks and all(t in txt for t in toks):
                res.append(a)
        return res

    # inscrits (= ceux qui ont PAYÉ) par activité, routés par le tarif choisi.
    #  - campagne directe (1 activité)      : tous les inscrits -> cette activité
    #  - campagne regroupée (n activités)   : chacun -> l'activité (ou les) de son tarif ;
    #    si le tarif est illisible, repli sur les cases cochées à l'adhésion.
    inscrits = defaultdict(set)
    rowbykey = defaultdict(dict)     # activité -> {clé: ligne de campagne} (pour non-adhérents)
    for f, labels in file_labels.items():
        labs = sorted(labels)
        direct = (len(labs) == 1)
        for r in rows_fichier[f]:
            if not valide(r.get(col_statut)):
                continue
            k = cle_nom(r.get("Nom adhérent"), r.get("Prénom adhérent"))
            if direct:
                matched = labs
            else:
                matched = activites_du_row(r, labs)
                if not matched:      # tarif illisible -> repli sur les cases cochées à l'adhésion
                    matched = [a for a in labs if a in coche_par_cle.get(k, set())]
            for a in matched:
                inscrits[a].add(k)
                rowbykey[a].setdefault(k, r)

    # ---------- Contrôle A : adhésion manquante ----------
    anomalies_adh, vus = [], set()
    for f, rows in rows_fichier.items():
        labs = sorted(file_labels.get(f, {"?"}))
        for r in rows:
            if not valide(r.get(col_statut)):
                continue
            nom, prenom, email = r.get("Nom adhérent"), r.get("Prénom adhérent"), r.get("Email payeur")
            autre = (r.get(col_autre) or "").strip()
            if est_adherent(nom, prenom, email) or autre:
                continue
            libelle = " + ".join(labs if len(labs) == 1 else (activites_du_row(r, labs) or labs))
            sig = (cle_nom(nom, prenom), libelle)
            if sig in vus: continue
            vus.add(sig)
            anomalies_adh.append({"Activité": libelle, "Nom": nom, "Prénom": prenom,
                "Email": clean_email(email), "Téléphone": tel(r.get("Téléphone")),
                "Motif": "Inscrit à l'activité sans adhésion validée au FRM"})

    # ---------- Contrôle B : activité cochée non payée ----------
    # Pour chaque activité qui a une campagne : cochée à l'adhésion mais absent des inscrits.
    anomalies_coche = []
    for lbl, fs in mapping.items():
        if not fs:
            continue
        for k in sorted(checked_sets.get(lbl, set())):
            if k not in inscrits[lbl]:
                r = idx_nom.get(k, {})
                anomalies_coche.append({"Nom": r.get("Nom adhérent"), "Prénom": r.get("Prénom adhérent"),
                    "Email": clean_email(r.get("Email") or r.get("Email payeur")),
                    "Activité cochée non honorée": lbl,
                    "Motif": "Activité cochée à l'adhésion mais aucune inscription payée"})

    # ---------- Consolidé : base finale, une ligne par personne, une colonne par activité ----------
    activites_all = sorted(set(acts) | set(mapping.keys()))
    entetes_consolide = (["Réf. commande", "Nom", "Prénom", "Sexe/Civilité", "Date de naissance",
                          "Email", "Téléphone", "Adresse", "Code Postal", "Ville", "Adhésion"]
                         + activites_all
                         + ["Nb activités", "N° adhérent Gestanet", "Statut saisie Gestanet"])

    # union des personnes : adhérents + inscrits (y compris d'un autre foyer, absents de l'adhésion)
    personnes = {}   # clé -> {"src": ligne adhésion|None, "camp": ligne campagne|None, "autre": str}
    for k, r in idx_nom.items():
        personnes[k] = {"src": r, "camp": None, "autre": ""}
    for f, rows in rows_fichier.items():
        for r in rows:
            if not valide(r.get(col_statut)):
                continue
            k = cle_nom(r.get("Nom adhérent"), r.get("Prénom adhérent"))
            p = personnes.setdefault(k, {"src": None, "camp": None, "autre": ""})
            if p["camp"] is None:
                p["camp"] = r
            a = (r.get(col_autre) or "").strip()
            if a and not p["autre"]:
                p["autre"] = a

    def infos_personne(p):
        s = p["src"]
        if s:
            return {"Réf. commande": s.get("Référence commande", ""),
                    "Nom": s.get("Nom adhérent", ""), "Prénom": s.get("Prénom adhérent", ""),
                    "Sexe/Civilité": civilite_gestanet(s.get("Sexe/Civilité")) if s.get("Sexe/Civilité") else "",
                    "Date de naissance": date_fr(s.get("Date de naissance")),
                    "Email": clean_email(s.get("Email") or s.get("Email payeur")),
                    "Téléphone": tel(s.get("Téléphone portable") or s.get("Téléphone fixe")),
                    "Adresse": (s.get("Adresse") or "").strip(),
                    "Code Postal": (s.get("Code Postal") or "").strip(),
                    "Ville": (s.get("Ville") or "").strip().upper()}
        r = p["camp"] or {}
        return {"Réf. commande": r.get("Référence commande", ""),
                "Nom": r.get("Nom adhérent", ""), "Prénom": r.get("Prénom adhérent", ""),
                "Sexe/Civilité": "", "Date de naissance": "",
                "Email": clean_email(r.get("Email payeur")), "Téléphone": tel(r.get("Téléphone")),
                "Adresse": "", "Code Postal": "", "Ville": ""}

    consolide = []
    for k in sorted(personnes, key=lambda x: (x[0], x[1])):
        p = personnes[k]
        row = infos_personne(p)
        row["Adhésion"] = ("Validé" if p["src"]
                           else (f"Autre foyer : {p['autre']}" if p["autre"] else "MANQUANTE"))
        nb = 0
        for a in activites_all:
            paye = k in inscrits.get(a, set())
            coche = k in checked_sets.get(a, set())
            if paye:
                row[a] = "Payé"; nb += 1
            elif mapping.get(a) and coche:
                row[a] = "À régler"
            elif not mapping.get(a) and coche:
                row[a] = "Gratuit"; nb += 1
            else:
                row[a] = ""
        row["Nb activités"] = nb
        row["N° adhérent Gestanet"] = ""
        row["Statut saisie Gestanet"] = ""
        consolide.append(row)

    # ---------- Relances ----------
    relance_adh = [{"Email": a["Email"], "Nom": a["Nom"], "Prénom": a["Prénom"], "Activité": a["Activité"],
        "Message": f"Bonjour {a['Prénom']}, vous êtes inscrit(e) à « {a['Activité']} » mais votre adhésion au "
                   f"Foyer Rural n'est pas enregistrée. L'adhésion est obligatoire : merci de la régulariser."}
        for a in anomalies_adh if a["Email"]]
    relance_coche = [{"Email": a["Email"], "Nom": a["Nom"], "Prénom": a["Prénom"],
        "Activité": a["Activité cochée non honorée"],
        "Message": f"Bonjour {a['Prénom']}, vous aviez indiqué vouloir participer à « {a['Activité cochée non honorée']} » "
                   f"mais l'inscription (et le paiement) n'a pas été finalisée. Merci de compléter votre inscription."}
        for a in anomalies_coche if a["Email"]]

    # ---------- Gestanet : UN fichier par ACTIVITÉ (pas par campagne) ----------
    #  - activité AVEC campagne : les inscrits qui ont PAYÉ cette activité (routés par tarif).
    #    Une personne ayant payé gym douce + pilates apparaît dans les DEUX fichiers.
    #  - activité SANS campagne (gratuite / paiement sur place) : les cocheurs de l'adhésion.
    gestanet = {}
    labels_import = set(acts) | set(mapping.keys())
    for lbl in labels_import:
        lignes = []
        if mapping.get(lbl):
            src_rows = rowbykey.get(lbl, {})
            for k in sorted(inscrits.get(lbl, set())):
                src = idx_nom.get(k)
                if src:
                    lignes.append(ligne_gestanet_depuis_adhesion(src, lbl))
                elif src_rows.get(k):
                    lignes.append(ligne_gestanet_depuis_activite(src_rows[k], lbl))
        else:
            keys = checked_sets.get(lbl, set())     # gratuite / sur place -> cocheurs de l'adhésion
            lignes = [ligne_gestanet_depuis_adhesion(idx_nom[k], lbl) for k in sorted(keys) if k in idx_nom]
        if lignes:
            gestanet[lbl] = lignes

    # ---------- Écritures ----------
    os.makedirs(sortie, exist_ok=True)
    ecrire_csv(os.path.join(sortie, "consolide.csv"), entetes_consolide, consolide)
    ecrire_csv(os.path.join(sortie, "anomalies_adhesion_manquante.csv"),
               ["Activité","Nom","Prénom","Email","Téléphone","Motif"], anomalies_adh)
    ecrire_csv(os.path.join(sortie, "anomalies_activite_cochee_non_payee.csv"),
               ["Nom","Prénom","Email","Activité cochée non honorée","Motif"], anomalies_coche)
    ecrire_csv(os.path.join(sortie, "relance_adhesion_manquante.csv"),
               ["Email","Nom","Prénom","Activité","Message"], relance_adh)
    ecrire_csv(os.path.join(sortie, "relance_activite_non_payee.csv"),
               ["Email","Nom","Prénom","Activité","Message"], relance_coche)
    for lbl, lignes in gestanet.items():
        ecrire_csv(os.path.join(sortie, "gestanet", norm(lbl) + ".csv"), CHAMPS_GESTANET, lignes)

    # ---------- Rapport ----------
    L = []
    L.append("=== SYNTHÈSE — Foyer Rural de Mondonville" + (f" — saison {saison}" if saison else "") + " ===")
    L.append(f"Adhésions validées : {len(idx_nom)}")
    L.append("")
    L.append("MAPPAGE DÉTECTÉ (fichier -> activité) :")
    for b, lbl, methode, sc in rapport_map:
        L.append(f"   - {b}\n        -> {lbl}   [{methode}" + (f", recoupement {int(sc*100)}%" if sc else "") + "]")
    multi = {lbl: fs for lbl, fs in mapping.items() if len(fs) > 1}
    if multi:
        L.append("")
        L.append("Activités à plusieurs campagnes (fusionnées) :")
        for lbl, fs in multi.items():
            L.append(f"   - {lbl} : {len(fs)} fichiers")
    non_reconnus = [b for b, lbl, m, s in rapport_map if lbl.startswith("???")]
    if non_reconnus:
        L.append("")
        L.append("Fichiers NON reconnus (à mapper via config.json > \"forcer\") :")
        for b in non_reconnus: L.append("   - " + b)
    L.append("")
    L.append(f"ANOMALIE — Adhésion manquante : {len(anomalies_adh)}")
    L.append(f"ANOMALIE — Activité cochée non payée : {len(anomalies_coche)}")
    parapluie = {f: file_labels[f] for f in file_labels if len(file_labels[f]) > 1}
    if parapluie:
        L.append("")
        L.append("Campagnes couvrant plusieurs activités (réparties selon les cases cochées) :")
        for f, labels in parapluie.items():
            L.append(f"   - {os.path.basename(f)} : {', '.join(sorted(labels))}")
    sans_campagne = sorted(a for a in acts if not mapping.get(a))
    if sans_campagne:
        L.append("")
        L.append(f"Activités SANS campagne (importées dans Gestanet depuis les cases cochées "
                 f"— gratuites ou paiement sur place) : {len(sans_campagne)}")
        for m in sans_campagne: L.append("   - " + m)
    with open(os.path.join(sortie, "rapport.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n→ Résultats écrits dans : {sortie}")


def main():
    p = argparse.ArgumentParser(description="Consolidation + contrôles HelloAsso + préparation Gestanet (détection auto).")
    p.add_argument("dossier", help="dossier contenant les exports HelloAsso (.csv)")
    p.add_argument("--sortie", help="dossier de sortie (défaut : DOSSIER/_resultats)")
    p.add_argument("--saison", default="", help="libellé de saison, ex. 2025-2026")
    p.add_argument("--config", help="chemin du config.json (défaut : DOSSIER/config.json) — "
                                    "utile pour le garder hors du dossier d'export")
    a = p.parse_args()
    if not os.path.isdir(a.dossier):
        print("Dossier introuvable : " + a.dossier, file=sys.stderr); sys.exit(1)
    run(a.dossier, a.sortie or os.path.join(a.dossier, "_resultats"), a.saison, a.config)


if __name__ == "__main__":
    main()
