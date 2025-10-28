from flask import Flask, request, jsonify, render_template_string
import json
import re
import sqlite3
from difflib import get_close_matches
from datetime import datetime
import os
import time

# -----------------------
# CONFIG + DATA LADEN
# -----------------------
def laad_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def laad_scripts():
    with open("scripts.json", "r", encoding="utf-8") as f:
        return json.load(f)

config = laad_config()
scripts = laad_scripts()
laatste_laad = time.time()

# -----------------------
# FLASK-APP
# -----------------------
app = Flask(__name__)

laatste_item = None  # Context onthouden

def log_interactie(vraag, antwoord):
    with open(config["log_bestand"], "a", encoding="utf-8") as log:
        log.write(f"[{datetime.now()}] Gebruiker: {vraag}\nChatbot: {antwoord}\n\n")

def zoek_antwoord(vraag):
    global scripts, config, laatste_item

    # Herlaad config/scrips als ze zijn aangepast
    global laatste_laad
    if time.time() - laatste_laad > config.get("reload_interval", 10):
        scripts = laad_scripts()
        config = laad_config()
        laatste_laad = time.time()

    vraag = vraag.lower().strip()

    # Speciale vervolgvragen (context)
    if vraag.startswith("en van") and laatste_item:
        item = vraag.replace("en van", "").strip()
        if not item:
            item = laatste_item
        return zoek_prijs(item)

    # Zoek door scripts
    for categorie, data in scripts.items():
        for patroon in data["patterns"]:
            match = re.search(patroon, vraag)
            if match:
                if "(.*)" in patroon:
                    item = match.group(1).strip().lower()
                    laatste_item = item
                    if categorie == "prijs":
                        return zoek_prijs(item)
                    else:
                        return data["response"].format(item=item)
                else:
                    return data["response"]

    # Fuzzy matching
    alle_patterns = [p for data in scripts.values() for p in data["patterns"]]
    match = get_close_matches(vraag, alle_patterns, n=1, cutoff=0.6)
    if match:
        for categorie, data in scripts.items():
            if match[0] in data["patterns"]:
                return data["response"]

    return "Sorry, ik weet niet wat ik moet zeggen."

def zoek_prijs(item):
    """Prijs opzoeken in SQLite-database"""
    db_path = config["database"]
    if not os.path.exists(db_path):
        return "De database met prijzen is niet gevonden."
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT prijs FROM producten WHERE naam = ?", (item,))
    result = c.fetchone()
    conn.close()
    if result:
        return f"De prijs van {item} is €{result[0]:.2f}."
    else:
        return f"Sorry, ik ken de prijs van {item} niet."

# -----------------------
# WEBINTERFACE
# -----------------------

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Julubo Chatbot</title>
    <style>
        body { font-family: sans-serif; background: #f8f8f8; margin: 30px; }
        #chat { background: white; border-radius: 8px; padding: 20px; width: 400px; }
        .user { color: blue; margin-top: 10px; }
        .bot { color: green; margin-top: 5px; }
        input { width: 80%; padding: 10px; }
        button { padding: 10px; }
    </style>
</head>
<body>
    <div id="chat">
        <div id="messages"></div>
        <input type="text" id="vraag" placeholder="Typ hier..." autofocus>
        <button onclick="stuur()">Stuur</button>
    </div>

<script>
async function stuur() {
    let vraag = document.getElementById("vraag").value;
    document.getElementById("messages").innerHTML += "<div class='user'><b>Jij:</b> " + vraag + "</div>";
    let response = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({vraag: vraag})
    });
    let data = await response.json();
    document.getElementById("messages").innerHTML += "<div class='bot'><b>Bot:</b> " + data.antwoord + "</div>";
    document.getElementById("vraag").value = "";
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    vraag = data.get("vraag", "")
    antwoord = zoek_antwoord(vraag)
    log_interactie(vraag, antwoord)
    return jsonify({"antwoord": antwoord})

if __name__ == "__main__":
    print("Chatbot draait op http://127.0.0.1:5000") #localhost
    app.run(debug=True)
