import json, os, subprocess, urllib.request
LINES = [
 ("hook",  "Every student knows this moment. Eleven p.m. One exercise. Stuck. Alone. That ends today."),
 ("chat",  "Chatbots hand you the answer in three seconds. And you learn... nothing. Education deserves better."),
 ("stat",  "Maths scores are at a historic low. Private tutors cost a fortune. Until now."),
 ("meet",  "Meet Gerald. The world's first private tutor that lives on your screen."),
 ("board", "You write. Gerald watches every line, spots the mistake, circles it, and explains it out loud. Like the best teacher you ever had, sitting right next to you. And you still find the answer yourself."),
 ("desktop","One key. Any app. Gerald sees what you see, points at what matters, and guides you step by step. Design, code, maths. Anything."),
 ("td",    "Drop your courses. Gerald learns them. When a drawing helps, it opens a board and plots the exact curve, live."),
 ("proof", "Real-time voice and vision. Pedagogy measured at ninety-two percent. Private by design. This is not a chatbot. This is a revolution in learning."),
 ("cta",   "Gerald. It doesn't give you the answer. It helps you find it. Never be stuck again. Try it today."),
]
key = os.environ["OPENAI_API_KEY"]
out = {}
for name, text in LINES:
    body = json.dumps({"model": "gpt-4o-mini-tts", "voice": "marin", "input": text, "response_format": "mp3", "speed": 1.08,
        "instructions": "Narrator of a startup launch video. Warm, confident, energetic, inspiring — Apple keynote energy, never shouting. Brisk pace, crisp articulation, short pauses at punctuation."}).encode()
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
