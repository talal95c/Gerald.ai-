import json, os, subprocess, sys, urllib.request
VOICE = sys.argv[1] if len(sys.argv) > 1 else "ash"
LINES = [
 ("cover",   "Hi, I'm Talal. Meet Gerald, the AI teacher that lives on your screen. Let me start with something everyone keeps telling me."),
 ("story",   "For years, everyone told me the same thing. Friends, teachers, LinkedIn, every ad: learn with AI. So I did. And for most subjects, it works."),
 ("notebook","Then I tried with maths. Before I can even ask my question, I have to retype my equations. Every. Single. Time. Maths isn't text. It's on paper, on a board, in a PDF. I spend five minutes turning my working into x caret two, and I still can't show it where I'm stuck."),
 ("problem", "Three frictions, everywhere. You retype everything. It can't point: the third icon on the left is the best it can do. And it gives you the answer, so the next morning you still can't solve it. And maths is exactly where students are dropping right now: minus twenty-one points in PISA."),
 ("solution","So I built Gerald. Not a maths teacher. A teacher. You hold control shift and talk. It sees what you see, only while you hold the key. It talks in real time. It draws circles, underlines, arrows and exact plots. And it teaches: hint first, answer last. You do the thinking."),
 ("different","One teacher, every subject, every app. Maths: it underlines the exact mistake. Sciences: it writes like a real board. Any software: it points at the right button and waits for your click. Zero retyping, zero screenshots, zero tutorials. Just ask."),
 ("demo1",   "Demo one. This is the real app. No retyping: the worksheet is already open in Notes. I say: delta equals twenty-five plus twenty-four, right? Gerald stops me and points at the exercise, instead of giving the answer."),
 ("demo2",   "Demo two. Now I write on the board, with the pen, and I make the classic mistake: plus twenty-four. Gerald underlines it in red and tells me the four a c term is subtracted. I fix it myself. Only then does it write the clean solution: x one equals three, x two equals two."),
 ("demo2b",  "And this is a real session, filmed on my phone: I write by hand, Gerald follows every line and underlines the exact term that's wrong."),
 ("demo3",   "Demo three. I ask to see the parabola. Gerald opens a blank board and plots the real curve: the two roots, two and three, and the vertex. It only draws when the picture helps."),
 ("demo4",   "Demo four. Same engine, different app: Photoshop. Nothing is scripted. Gerald reads the screen, points at Shapes, then Rectangle, then the fill colour and the hex code, and waits for my click at every step, until the red square is on the canvas."),
 ("clicky",  "Why not Clicky? Clicky is the closest thing to us, and it proved people want an AI next to their cursor. But Clicky is an assistant: it does the job for you. Gerald is a teacher: a hint, you try, it corrects you. It shows exactly where to click, it has a real board, it knows your course, and it runs on Windows and the web, where students are."),
 ("llms",    "Why not Claude, ChatGPT or Gemini? Brilliant brains. But you still feed them screenshots, or they only see your phone or your browser, and they answer in a chat box. None of them shows you where to click, writes on your exercise, or lets you try first. Gerald does all three."),
 ("table",   "One table to remember. Everyone has a piece. Chatbots can tutor, but only in a chat window. Clicky sees your screen, but it does the work for you. Gerald is the only one that sees your work, shows you exactly where, writes on it, and makes you think first."),
 ("how",     "How it works: one voice turn, from keypress to ink. Listen, think, aim, draw. The hard part is pointing. Raw model coordinates are ninety pixels off, so every gesture is anchored on the UI tree, OCR or Moondream: two point four pixels median error. And a harness scores sixteen tutoring scenarios on eight criteria: from seventy-seven to ninety-one percent."),
 ("market",  "The demand is already there: ninety-five percent of students use AI for their studies. AI in education grows seven x by twenty thirty-three, and private tutoring is a sixty-seven billion dollar market today. Gerald brings the tutor to everyone, at the price of an API call."),
 ("numbers", "By the numbers: zero equations retyped. Five times fewer steps to ask. Thirty-seven times more precise pointing. Plus sixteen points of pedagogy. Point six seconds to find any target. And two hundredths of a cent per gesture."),
 ("thanks",  "So: stop retyping, stop screenshotting, just ask Gerald. And if it gets too pedagogical... it's the first teacher you can actually mute. Thank you!"),
]
key = os.environ["OPENAI_API_KEY"]
out = {}
for name, text in LINES:
    body = json.dumps({"model": "gpt-4o-mini-tts", "voice": VOICE, "input": text, "response_format": "mp3", "speed": 1.06,
        "instructions": "Talal, a young founder pitching his startup to a hackathon jury, in English. Natural, human, dynamic and enthusiastic, slight smile, clear articulation, brisk pace with real breaths and small pauses for effect; never robotic or announcer-like."}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            open(f"public/audio/vo-pitch/{name}.raw.mp3", "wb").write(r.read())
    except urllib.error.HTTPError as e:
        print(name, "HTTP", e.code, e.read()[:300]); continue
    subprocess.run(["ffmpeg","-v","error","-y","-i",f"public/audio/vo-pitch/{name}.raw.mp3","-af","loudnorm=I=-16:TP=-1.5:LRA=9","-ar","44100","-b:a","160k",f"public/audio/vo-pitch/{name}.mp3"],check=True)
    os.remove(f"public/audio/vo-pitch/{name}.raw.mp3")
    d = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f"public/audio/vo-pitch/{name}.mp3"],capture_output=True,text=True).stdout)
    out[name] = {"text": text, "dur": round(d, 2)}
    print(name, round(d,2), "s")
json.dump(out, open("public/audio/vo-pitch/manifest.json","w"), indent=1)
open("src/voPitch.ts","w").write("/** Generated by scripts_vo_pitch.py (OpenAI gpt-4o-mini-tts, loudnorm -16 LUFS). */\nexport const VOP = {\n"+"".join(f'  {k}: {{ file: "vo-pitch/{k}.mp3", dur: {v["dur"]}, text: {json.dumps(v["text"])} }},\n' for k,v in out.items())+"} as const;\n")
print("total", round(sum(v["dur"] for v in out.values()),1))
