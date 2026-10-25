# Architecture

Gerald garde les choix propres aux appareils et à Qt dans les adaptateurs, afin
que le raisonnement sur les coordonnées et les outils reste testable sans
interface native.

| Module | Responsabilité |
| --- | --- |
| `config.py` | Charge `.env`, les paramètres et l'échelle DPI Windows avant Qt. |
| `capture/screen.py` | Sélectionne le moniteur sous le curseur, conserve son origine physique, redimensionne et encode une capture JPEG. |
| `perception/elements.py` | Interroge UI Automation et l'OCR si disponible, filtre et sérialise le contexte de l'écran. |
| `perception/grounding.py` | Résout un identifiant ou un point en rectangle physique sans dépendre de Qt. |
| `tools/registry.py` | Déclare les schémas Realtime et transforme les appels en commandes de dessin simples. |
| `brain/realtime.py` | Gère la session WebSocket, les tours push-to-talk, les outils, les transcriptions et l'usage. |
| `audio/` | Capture et restitue du PCM mono à 24 kHz. |
| `overlay/window.py` | Dessine les annotations dans une fenêtre transparente, au-dessus du bureau. |
| `app.py` | Assemble Qt, les raccourcis globaux, la zone de notification et la boucle asyncio. |
| `scripts/live_check.py` | Permet de lancer une question réelle avec une image, sans microphone. |

## Choix importants

- **Vision ponctuelle, pas continue.** Une capture est prise au début d'un
  maintien ou à la demande explicite d'une question texte. Elle est redimensionnée
  et envoyée avec les éléments visibles au moment de la question. Aucune boucle
  de capture d'écran ne tourne au repos.
- **Repères d'interface réutilisables.** Les fournisseurs UIA/OCR transmettent
  leurs observations avec une provenance; les appels d'outil privilégient
  `element_id` à des coordonnées estimées. Les points sont exprimés dans les
  pixels de l'image, puis convertis vers les coordonnées physiques du moniteur.
- **Overlay non interactif et exclu des captures.** Les commandes ne pilotent
  pas l'application cible. Windows reçoit les styles click-through/no-activate
  et `WDA_EXCLUDEFROMCAPTURE`; les autres systèmes masquent la fenêtre pendant
  une capture.
- **Séparation de l'I/O.** Le thread Qt garde l'interface réactive; asyncio
  supervise le WebSocket et les événements audio. Les commandes d'overlay
  restent des dataclasses sans dépendance Qt.
- **Dégradation douce.** UIA, OCR, fenêtre active et périphériques audio
  peuvent manquer. Leurs adaptateurs journalisent l'échec plutôt que de bloquer
  la question complète.

Le client utilise l'interface Realtime GA documentée par OpenAI :
[Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations).
La session maintient l'historique; les outils sont retournés comme
`function_call_output` avant une unique continuation par réponse achevée.
