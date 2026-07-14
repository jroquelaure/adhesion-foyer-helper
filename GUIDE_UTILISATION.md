# Guide d'utilisation — Adhésions Foyer Rural de Mondonville

Cet outil récupère automatiquement les adhésions et inscriptions depuis **HelloAsso**, vérifie les incohérences, et prépare les fichiers à importer dans **Gestanet**. Aucune connaissance informatique n'est nécessaire : on remplit ses réglages une fois, puis on clique sur un bouton.

---

## En bref (une fois installé)

1. Double-cliquez sur **Lancer (Mac).command** ou **Lancer (Windows).bat**.
2. Cliquez sur **▶ Tout faire**.
3. Cliquez sur **📂 Ouvrir les résultats** : vos fichiers sont prêts.

---

## Étape 1 — Installer Python (une seule fois)

L'application a besoin de « Python » pour fonctionner. C'est gratuit et rapide.

**Sur Mac**
1. Allez sur **python.org/downloads**, cliquez sur le bouton jaune (dernière version), installez.
2. Ouvrez le dossier `Applications > Python 3.x` et double-cliquez sur **Install Certificates.command** (important : évite une erreur de certificat). Une fenêtre s'ouvre, se termine toute seule, vous pouvez la fermer.

**Sur Windows**
1. Allez sur **python.org/downloads**, cliquez sur le bouton jaune, lancez l'installateur.
2. **Cochez la case « Add Python to PATH »** en bas de la première fenêtre, puis « Install Now ».

> À ne faire qu'une seule fois, sur l'ordinateur qui servira à la gestion.

## Étape 2 — Obtenir votre clé API HelloAsso (une seule fois)

1. Connectez-vous à HelloAsso avec le compte de l'association.
2. Allez dans **Mon compte → Intégrations et API**, créez un client API.
3. Notez les deux codes : **client_id** et **client_secret** (gardez-les confidentiels).
4. Repérez le **nom court** de l'association : c'est la fin de l'adresse de votre page HelloAsso `helloasso.com/associations/`**`ce-nom-court`**.

## Étape 3 — Lancer l'application

- **Mac** : double-cliquez sur **Lancer (Mac).command**. La première fois, si macOS affiche un avertissement, faites **clic droit → Ouvrir → Ouvrir**.
- **Windows** : double-cliquez sur **Lancer (Windows).bat**.

Une fenêtre « Adhésions & inscriptions — assistant » s'ouvre.

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
Lancez une fois **Install Certificates.command** (Applications → Python 3.x). Voir Étape 1.

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
