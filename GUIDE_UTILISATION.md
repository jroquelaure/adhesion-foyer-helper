# Guide d'utilisation — Adhésions Foyer Rural de Mondonville

Cet outil récupère automatiquement les adhésions et inscriptions depuis **HelloAsso**, vérifie les incohérences, et prépare les fichiers à importer dans **Gestanet**. Aucune connaissance informatique n'est nécessaire : on remplit ses réglages une fois, puis on clique sur un bouton.

---

## En bref (une fois installé)

1. Double-cliquez sur **Lancer (Mac).command** ou **Lancer (Windows).bat**.
2. Cliquez sur **▶ Tout faire**.
3. Cliquez sur **📂 Ouvrir les résultats** : vos fichiers sont prêts.

---

## Étape 1 — Python (installé automatiquement)

L'application a besoin de « Python » pour fonctionner. **Vous n'avez normalement rien à faire** : au tout premier lancement, si Python n'est pas présent sur l'ordinateur, l'outil le **télécharge et l'installe tout seul**.

- **Sur Mac** : une fenêtre vous demande votre **mot de passe administrateur** (celui de votre session Mac) pour autoriser l'installation — saisissez-le et cliquez sur Installer. Puis l'application démarre.
- **Sur Windows** : laissez l'installation se dérouler (1 à 2 minutes), sans rien toucher. L'application démarre ensuite.

> Solution de secours (si l'installation automatique échoue : pas d'Internet, antivirus, etc.) : installez Python manuellement depuis **python.org/downloads**. Sur Windows, cochez « Add Python to PATH ». Sur Mac (python.org), lancez ensuite « Install Certificates.command ».

## Étape 2 — Obtenir votre clé API HelloAsso (une seule fois)

1. Connectez-vous à HelloAsso avec le compte de l'association.
2. Allez dans **Mon compte → Intégrations et API**, créez un client API.
3. Notez les deux codes : **client_id** et **client_secret** (gardez-les confidentiels).
4. Repérez le **nom court** de l'association : c'est la fin de l'adresse de votre page HelloAsso `helloasso.com/associations/`**`ce-nom-court`**.

## Étape 3 — Lancer l'application

- **Mac** : double-cliquez sur **Lancer (Mac).command**. La première fois, si macOS affiche un avertissement, faites **clic droit → Ouvrir → Ouvrir**.
- **Windows** : double-cliquez sur **Lancer (Windows).bat**.

Une **page « Adhésions & inscriptions — assistant » s'ouvre dans votre navigateur**. Une petite fenêtre noire (Terminal) reste ouverte en arrière-plan : c'est normal, **ne la fermez pas** pendant l'utilisation (elle fait tourner l'application). Pour quitter, il suffira de fermer cette fenêtre noire.

## Étape 4 — Remplir les réglages (une seule fois)

Dans la partie **1 · Réglages HelloAsso**, saisissez :
- l'**identifiant API** (client_id) et la **clé secrète** (client_secret) ;
- le **nom court** de l'association ;
- la **saison** (ex. `2025-2026`).

Cliquez sur **💾 Enregistrer les réglages**. C'est mémorisé pour les prochaines fois.

## Étape 5 — Lancer le traitement

Cliquez sur **▶ Tout faire**. L'application :
1. récupère les données de la saison depuis HelloAsso ;
2. les analyse et prépare tous les fichiers.

Le **Journal** affiche l'avancement. Quand c'est fini, il indique **✅ Terminé**.

> Vous pouvez aussi utiliser les boutons séparés **1)** puis **2)** si vous préférez.

## Étape 6 — Récupérer et utiliser les résultats

Cliquez sur **📂 Ouvrir les résultats**. Le dossier contient :
- **rapport.txt** — la synthèse à lire en premier (compteurs, contrôles).
- **consolide.csv** — la base finale : une ligne par personne, une colonne par activité (payé / à régler / gratuit).
- **anomalies_adhesion_manquante.csv** et **anomalies_activite_cochee_non_payee.csv** — les cas à régulariser.
- **relance_adhesion_manquante.csv** et **relance_activite_non_payee.csv** — prêts pour un envoi d'e-mails (publipostage).
- **gestanet/** — un fichier par activité, prêt à importer dans Gestanet (menu **Vos adhérents → Importer**), une activité à la fois.

---

## En cas de problème

**« Erreur de certificat / CERTIFICATE_VERIFY_FAILED » (Mac)**
- Python installé depuis python.org : lancez une fois **Install Certificates.command** (Applications → Python 3.x).
- Python installé via Homebrew : ouvrez le Terminal et tapez `pip3 install certifi` (l'application l'utilisera automatiquement).

**« Échec d'authentification (403) »**
La clé est peut-être bloquée ou recopiée avec une espace en trop. Recréez une clé API dans HelloAsso et recollez client_id / client_secret, puis Enregistrer.

**« python introuvable » ou la fenêtre se ferme aussitôt (Windows)**
Python n'est pas installé ou la case « Add Python to PATH » n'a pas été cochée. Réinstallez Python (Étape 1) en cochant la case.

**Rien ne se passe / bouton grisé**
Un traitement est déjà en cours ; attendez le message ✅ Terminé dans le Journal.

---

## Pour la personne qui met en place (facultatif, technique)

- Les réglages sont dans **helloasso.json** (créé automatiquement à l'enregistrement).
- Le regroupement des campagnes est dans **config.json**, par **mots-clés** (ex. `gymnastique` → Gym douce + Pilates + Stretching + Body sculpt ; `cardio` → Zumba + Step). Comme ce sont des mots-clés et non des noms de fichiers avec l'année, **ce fichier n'a pas besoin d'être modifié chaque saison**. On peut y ajouter une entrée si une nouvelle activité regroupée apparaît.
- Une suite de tests (`python3 -m pytest`) vérifie le bon fonctionnement (voir `LISEZMOI_foyer_controle.md`).
