# Automatisation HelloAsso → contrôles → Gestanet

Deux programmes, gratuits, sans dépendance à installer (Python 3 seulement) :

- `helloasso_export.py` — **récupère automatiquement** les campagnes via l'**API HelloAsso** (fini les exports manuels) et écrit un CSV par formulaire.
- `foyer_controle.py` — **consolide, contrôle, prépare les relances et génère les fichiers Gestanet** à partir de ces CSV.

## Étape 0 — Récupérer les données via l'API (au lieu des exports manuels)

1. Créer une clé API : HelloAsso → **Mon compte → Intégrations et API** → créer un client → notez `client_id` et `client_secret`.
2. Copier `helloasso.json.example` en `helloasso.json` et y coller vos identifiants + votre `organization_slug` (la fin de l'URL `helloasso.com/associations/<slug>`).
3. Lancer :

   ```
   python3 helloasso_export.py --sortie exports_api
   ```

   → écrit un CSV par campagne dans `exports_api/` (nommés d'après le formulaire, pour la détection automatique).
4. Enchaîner avec les contrôles :

   ```
   python3 foyer_controle.py  exports_api  --saison "2025-2026"
   ```

> Remarque : ce connecteur n'a pas pu être testé avec de vraies clés de mon côté (pas d'accès réseau à l'API ici). Sa logique de transformation a été validée sur une réponse d'API simulée ; testez-le une première fois avec vos identifiants et dites-moi si un champ diffère, je l'ajusterai.

Vous pouvez aussi continuer à travailler à partir d'**exports manuels** : déposez simplement les CSV dans un dossier et lancez directement `foyer_controle.py` (voir ci-dessous).

### Erreur « CERTIFICATE_VERIFY_FAILED » (macOS / python.org)

Le Python installé depuis python.org n'utilise pas le magasin de certificats du système.

- Correctif global : lancer une fois `/Applications/Python 3.10/Install Certificates.command`.
- Correctif venv (recommandé) : dans le venv activé, `pip install certifi` — le connecteur l'utilise automatiquement. Lancez le script avec le python du venv.
- Dernier recours (déconseillé) : `--insecure`, ou `"verifier_ssl": false` dans `helloasso.json`.

## Ce qu'il fait

À partir des exports HelloAsso (la campagne d'**adhésion** + une ou plusieurs campagnes par **activité**), le programme :

- **détecte automatiquement** quelle campagne correspond à quelle activité (voir plus bas) ;
- **consolide** tout en une base unique (une ligne par adhérent) ;
- **contrôle « adhésion manquante »** : personnes inscrites à une activité mais sans adhésion validée au FRM (les adhérents d'un *autre foyer* sont automatiquement exclus) ;
- **contrôle « activité cochée non payée »** : activités cochées dans la campagne d'adhésion mais jamais confirmées dans la campagne dédiée ;
- **prépare les relances** (fichiers prêts pour un publipostage e-mail) ;
- **génère les fichiers d'import Gestanet par activité**, au bon format (Ville en MAJUSCULES, tél. `0…`, date `jj/mm/aaaa`, Sexe/Civilité `Féminin/Masculin → Mme/M`), en récupérant l'état civil depuis l'adhésion.

## Utilisation

1. Dans HelloAsso : exporter en CSV la campagne d'adhésion et chaque campagne d'activité. Déposer tous ces fichiers dans un même dossier.
2. Lancer (une seule commande, aucune config à préparer) :

   ```
   python3 foyer_controle.py  MON_DOSSIER  --saison "2025-2026"
   ```

### Filtrer par période (gagner du temps, ménager l'API)

Par défaut le connecteur récupère toutes les saisons. Pour ne prendre qu'une période, filtrez **côté serveur** (sur la date de commande) :

```
python3 helloasso_export.py --sortie exports_api --saison 2025-2026
```

`--saison 2025-2026` = du 1er juillet 2025 au 31 août 2026. On peut aussi préciser les dates : `--depuis 2025-07-01 --jusqu-a 2026-08-31`, ou mettre `"saison": "2025-2026"` dans `helloasso.json`. Cela réduit le nombre de pages appelées et évite d'exporter les vieilles saisons.

Le programme de contrôle **détecte automatiquement** l'activité de chaque fichier à partir de son nom (dictionnaire d'abréviations : `ttenfant`→Tennis de table, `hata`/`vinysa`→Yoga, `gym`→Gym douce, `zumba`→Zumba…), le **contenu** servant de filet de secours. Il **accepte plusieurs exports pour une même activité** (ex. Yoga Vinyasa + Yoga Hata : fusionnés et dédoublonnés). Le mappage détecté est affiché à chaque exécution.

### Ajustements manuels (facultatifs)

Si un fichier n'est pas reconnu ou est mal classé, créez un `config.json` dans le dossier :

```json
{
  "forcer": { "mon-fichier.csv": "Nom exact de l'activité" },
  "ignorer_fichiers": [ "un-fichier-a-exclure.csv" ]
}
```

## Résultats (dossier `MON_DOSSIER/_resultats/`)

| Fichier | Contenu |
|---|---|
| `consolide.csv` | une ligne par adhérent : activités cochées, confirmées, cochées-non-confirmées |
| `anomalies_adhesion_manquante.csv` | inscrits activité sans adhésion validée |
| `anomalies_activite_cochee_non_payee.csv` | activités cochées mais non honorées |
| `relance_adhesion_manquante.csv` | e-mail + message prêt à envoyer |
| `relance_activite_non_payee.csv` | e-mail + message prêt à envoyer |
| `gestanet/<activite>.csv` | import Gestanet, une activité à la fois (campagnes multiples fusionnées) |
| `rapport.txt` | synthèse chiffrée + mappage détecté |

## Comment sont calculés les contrôles

- **Rapprochement des personnes** : par nom + prénom (accents/casse ignorés), avec l'e-mail en secours (utile quand le payeur diffère de l'adhérent, ex. parent/enfant).
- **« Activité cochée non payée »** : ne porte que sur les activités **payantes** ET **pour lesquelles une campagne a été trouvée** dans le dossier. Une activité payante sans campagne fournie n'est pas vérifiable (listée à part dans le rapport).
- **« Activités payantes SANS campagne trouvée »** = activités marquées payantes (repérées via la colonne de consentement du formulaire d'adhésion) pour lesquelles aucun fichier d'export n'a été détecté dans le dossier.

## Tests (Pytest)

Une suite de tests vérifie les deux programmes (`test_foyer_controle.py`, `test_helloasso_export.py`).

```
pip install -r requirements-dev.txt   # installe pytest
python3 -m pytest -q                   # lance les 62 tests
```

Ce qui est couvert : normalisation (téléphone `+33`/`0033`, dates, civilité, ville en majuscules), détection des activités (dictionnaire `tt*`/`hata`/`gym`…, non-classement par contenu, multi-fichiers, `forcer`/`ignorer`), contrôles de bout en bout (adhésion manquante, activité cochée non payée, sortie Gestanet), et le connecteur API (aplatissement des `customFields`, repli sur le payeur, pagination, authentification, `run()` mocké — sans appel réseau réel). Pour cibler un test : `python3 -m pytest test_foyer_controle.py -k gestanet -v`.

## Points d'attention

- **Gestanet importe une activité à la fois** : d'où un fichier par activité. Import via *Vos adhérents → Importer* ; les entêtes correspondent aux champs Gestanet (auto-association).
- **État civil** pour les inscrits venant d'un *autre foyer* (absents de l'adhésion) : laissé à compléter, signalé en commentaire.
- **RGPD** : fichiers réservés aux bénévoles habilités ; supprimer les CSV exportés une fois l'import Gestanet réalisé.
