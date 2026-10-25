import json
import os
import subprocess
import sys
import urllib.request
VOICE = sys.argv[1] if len(sys.argv) > 1 else "ash"
LINES = [
 ("hook",  "11 p.m. One exercise. Stuck. Alone. That ends today."),
 ("chat",  "Chatbots hand you the answer. You learn nothing. And private tutors cost a fortune."),
 ("meet",  "Meet Gerald. The private tutor that lives on your screen."),
 ("td",    "Drop your courses. Gerald knows them, and reads your worksheet with you."),
 ("board", "You write on the board. Gerald follows every line, explains out loud, plots the exact curve. And you find the answer yourself."),
 ("desktop","One key, any app. Gerald guides you step by step, all the way to the red square. And you do the clicking."),
 ("cta",   "Gerald. It doesn't give you the answer. It helps you find it."),
]
key = os.environ["OPENAI_API_KEY"]
out = {}
for name, text in LINES:
    body = json.dumps({"model": "gpt-4o-mini-tts", "voice": VOICE, "input": text, "response_format": "mp3", "speed": 1.1,
        "instructions": "Native English narrator of a startup launch video. Natural, human, warm and confident, slight smile in the voice; brisk but relaxed pace, real breaths, never robotic or announcer-like."}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            open(f"public/audio/vo/{name}.mp3", "wb").write(r.read())
    except urllib.error.HTTPError as e:
        print(name, "HTTP", e.code, e.read()[:300])
        continue
    d = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f"public/audio/vo/{name}.mp3"],capture_output=True,text=True).stdout)
    out[name] = {"text": text, "dur": round(d, 2)}
    print(name, round(d,2), "s")
json.dump(out, open("public/audio/vo/manifest.json","w"), indent=1)
