# Guide — Adhésions du Foyer Rural de Mondonville

**À quoi ça sert.** L'outil va chercher tout seul les adhésions et inscriptions sur HelloAsso, repère qui n'a pas payé ou pas adhéré, et prépare des fichiers prêts à importer dans Gestanet. Vous cliquez sur un bouton, vous récupérez les fichiers.

---

## La toute première fois

**1) Récupérez votre clé HelloAsso.**
Connectez-vous à HelloAsso avec le compte de l'association, puis allez dans **Mon compte → Intégrations et API → Créer un client**. Notez les deux codes affichés : l'**identifiant** et la **clé secrète**. Notez aussi le **nom court** de l'association : c'est ce qui se trouve à la fin de l'adresse de votre page HelloAsso.

**2) Ouvrez l'application.**
Double-cliquez sur **Lancer (Mac)** ou **Lancer (Windows)**.
La première fois, l'outil a peut-être besoin d'installer un composant (Python) : **laissez-le faire et patientez 1 à 2 minutes** (sur Mac, tapez votre mot de passe si on vous le demande). Une page s'ouvre ensuite dans votre navigateur.
> Laissez la petite fenêtre noire ouverte pendant que vous utilisez l'outil.

**3) Renseignez vos informations (une seule fois).**
Dans la page, recopiez l'**identifiant**, la **clé secrète**, le **nom court** et la **saison** (par exemple `2025-2026`). Cliquez sur **Enregistrer les réglages**.

---

## À chaque utilisation

1. Double-cliquez sur le lanceur.
2. Cliquez sur **▶ Tout faire**, puis patientez : l'avancement s'affiche et se termine par **✅ Terminé**.
3. Cliquez sur **📂 Ouvrir les résultats**.

---

## Ce que vous obtenez à la fin

Un dossier avec des fichiers prêts à l'emploi :

- **Un fichier par activité** (dans le sous-dossier `gestanet`) — à importer directement dans Gestanet, une activité à la fois.
- **La liste des personnes à relancer** : celles qui n'ont pas adhéré, et celles qui ont choisi une activité sans la payer.
- **Des e-mails de relance déjà rédigés**, prêts à envoyer.
- **Un tableau récapitulatif** (`consolide.csv`) : une ligne par personne, avec ses activités et ce qu'il reste à faire. Vous pouvez y écrire à la main (numéro Gestanet, remarques…) : vos notes sont conservées au prochain lancement.

---

## Si quelque chose ne va pas

- Un message en rouge apparaît dans le journal : lisez-le, il explique le problème (le plus souvent une information mal recopiée dans les réglages).
- Un bouton est grisé : un traitement est déjà en cours, attendez le **✅ Terminé**.
- Autre souci : contactez la personne qui a installé l'outil (voir `LISEZMOI_foyer_controle.md`).
