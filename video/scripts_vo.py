import json, os, subprocess, sys, urllib.request
VOICE = sys.argv[1] if len(sys.argv) > 1 else "ash"
LINES = [
 ("hook",  "23 heures. Un exercice. Bloqué. Seul. Ça s'arrête aujourd'hui."),
 ("chat",  "Les chatbots donnent la réponse. On n'apprend rien. Et les profs particuliers coûtent une fortune."),
 ("meet",  "Voici Gerald. Le prof particulier qui vit sur votre écran."),
 ("td",    "Déposez vos cours. Gerald les connaît, et lit votre TD avec vous."),
 ("board", "Vous écrivez au tableau. Gerald suit chaque ligne, explique à voix haute, trace la courbe exacte. Et c'est vous qui trouvez."),
 ("desktop","Une touche, n'importe quelle appli. Gerald pointe le bon outil et vous guide pas à pas."),
 ("cta",   "Gerald. Il ne donne pas la réponse, il vous aide à la trouver."),
]
key = os.environ["OPENAI_API_KEY"]
out = {}
for name, text in LINES:
    body = json.dumps({"model": "gpt-4o-mini-tts", "voice": VOICE, "input": text, "response_format": "mp3", "speed": 1.1,
        "instructions": "Narrateur français natif d'une vidéo de lancement de startup. Naturel, humain, chaleureux et confiant, légèrement souriant ; rythme vif mais posé, vraies respirations, jamais robotique ni voix d'annonceur."}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            open(f"public/audio/vo/{name}.mp3", "wb").write(r.read())
    except urllib.error.HTTPError as e:
        print(name, "HTTP", e.code, e.read()[:300]); continue
    d = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f"public/audio/vo/{name}.mp3"],capture_output=True,text=True).stdout)
    out[name] = {"text": text, "dur": round(d, 2)}
    print(name, round(d,2), "s")
json.dump(out, open("public/audio/vo/manifest.json","w"), indent=1)
