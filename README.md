# Gerald

Gerald est un assistant pédagogique de bureau : maintenez le raccourci, posez
votre question à voix haute et il explique ce qui est affiché en dessinant des
repères directement à l'écran. Il capture l'écran uniquement au déclenchement
du raccourci et ne commande une application qu'après une autorisation explicite.

## Installation (Windows)

Installez Python 3.11 ou plus récent, puis dans PowerShell :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows]"
Copy-Item .env.example .env
```

Ajoutez votre `OPENAI_API_KEY` dans `.env`, puis lancez `gerald` ou
`python -m gerald`. Le modèle par défaut est `gpt-realtime-2`, avec la voix
`marin`. Le microphone et les autorisations d'accessibilité doivent être
disponibles; la reconnaissance UIA et l'OCR Windows sont optionnels.

## Raccourcis

- Maintenir `Ctrl+Shift` : parler et partager une capture ponctuelle.
- `Ctrl+Shift+Enter` ou l'icône de zone de notification : saisir une question.
- `Ctrl+Shift+R` ou l'action de la zone de notification : enregistrer un récapitulatif de la leçon.
- `Ctrl+Shift+B` ou l'action « Tableau » de la zone de notification : ouvrir/fermer le tableau.
- `Échap` : annuler une demande d'action, interrompre Gerald ou effacer les dessins.
  Pendant une question, relâchez d'abord le raccourci puis appuyez sur `Échap` : sous Windows, `Ctrl+Shift+Échap` ouvre le Gestionnaire des tâches.

Avant la première action de chaque tour, Gerald demande une autorisation réelle
dans une capsule « Autoriser / Annuler »; le champ `confirmed` fourni par le
modèle ne suffit pas. `GERALD_REQUIRE_CONFIRMATION=0` désactive cette demande
uniquement pour le développement.

Modifiez `GERALD_HOTKEY`, `GERALD_MODEL`, `GERALD_VOICE`,
`GERALD_MAX_IMAGE_W` et `GERALD_OCR_BUDGET` (2,5 secondes par défaut) dans
`.env`. Sur Linux et macOS, l'application démarre
aussi; les fournisseurs d'éléments et les raccourcis globaux dépendent des
capacités du système. Pour les détails techniques, voir
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Le localisateur visuel optionnel est désactivé par défaut
(`GERALD_GROUNDER=none`). `GERALD_GROUNDER=openrouter` utilise
`OPENROUTER_API_KEY`; `GERALD_GROUNDER=moondream` nécessite
`python -m pip install -e ".[grounder-local]"` et charge Moondream sur le CPU.
`GERALD_GROUNDER=moondream-cloud` utilise `MOONDREAM_API_KEY`; un compte
Moondream gratuit comprend 5 $ de crédit par mois
([tarifs Moondream](https://moondream.ai/pricing)). Le modèle cloud par défaut
est `moondream3.1-9B-A2B`; `GERALD_GROUNDER_MODEL` permet de le remplacer.
Les valeurs enregistrées avec Grounder… dans `~/.gerald/grounder.json` priment
sur `MOONDREAM_ENDPOINT` et `MOONDREAM_API_KEY`; les variables d'environnement
servent de repli si une valeur n'est pas enregistrée.

## App

L’encoche de Gerald ouvre rapidement le chat, les réglages et les documents de démonstration.
Le TD local « Polynômes du second degré » s’ouvre à côté; choisis un exercice pour le travailler
sur le tableau blanc, puis termine la session pour retrouver la fiche de révision.
Les pages et les polices de l’interface sont compilées dans `gerald/home/webui/`; aucun accès
réseau n’est requis pour afficher le TD ou les formules KaTeX.

Captures : [accueil](docs/notch-greeting.png), [encoche réduite](docs/notch-collapsed.png),
[chat](docs/notch-panel.png), [documents](docs/notch-settings-documents.png),
[historique](docs/notch-settings-historique.png), [TD](docs/td-exercises.png) et
[exercice au tableau](docs/board-exercise.png).

## Free GPU fallback (Colab)

1. Ouvrez [`colab/gerald_grounder.ipynb`](colab/gerald_grounder.ipynb) dans Google Colab.
2. Dans Runtime > Change runtime type, choisissez un GPU T4, puis lancez Run all.
3. Quand le tunnel est prêt, copiez `MOONDREAM_ENDPOINT` et `MOONDREAM_API_KEY` dans
   Grounder… (menu de Gerald), et définissez `GERALD_GROUNDER=moondream-cloud` dans `.env`.
4. Gardez la session Colab ouverte tant que vous utilisez le tunnel; l'URL quick tunnel
   est temporaire et ne nécessite pas de compte Cloudflare.