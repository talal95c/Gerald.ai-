# Gerald

Gerald est un assistant pédagogique de bureau : maintenez le raccourci, posez
votre question à voix haute et il explique ce qui est affiché en dessinant des
repères directement à l'écran. Il capture l'écran uniquement au déclenchement
du raccourci et ne commande pas vos applications.

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
- `Échap` : annuler une demande d'action, interrompre Gerald ou effacer les dessins.

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