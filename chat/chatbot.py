import json
import re
from difflib import get_close_matches
from datetime import datetime
import sqlite3


with open("scripts.json", "r", encoding="utf-8") as f:
    scripts = json.load(f)


def log_interactie(vraag, antwoord):
    with open("chatlog.txt", "a", encoding="utf-8") as log:
        log.write(f"[{datetime.now()}] Gebruiker: {vraag}\nChatbot: {antwoord}\n\n")

def zoek_antwoord(vraag):
    vraag = vraag.lower()

    # Check op reguliere expressies (patroonherkenning)
    for categorie, data in scripts.items():
        for patroon in data["patterns"]:
            match = re.search(patroon, vraag)
            if match:
                if "(.*)" in patroon:
                    item = match.group(1).strip().lower()
                    if categorie == "prijs":
                        conn = sqlite3.connect("prijzen.db")
                        c = conn.cursor()
                        c.execute("SELECT prijs FROM producten WHERE naam = ?", (item,))
                        result = c.fetchone()
                        conn.close()
                        if result:
                            return f"De prijs van {item} is €{result[0]:.2f}."
                        else:
                            return f"Sorry, ik ken de prijs van {item} niet."
                    else:
                        return data["response"].format(item=item)
                    
                else:
                    return data["response"]

    
    alle_patterns = [p for data in scripts.values() for p in data["patterns"]]
    match = get_close_matches(vraag, alle_patterns, n=1, cutoff=0.6)
    if match:
        for categorie, data in scripts.items():
            if match[0] in data["patterns"]:
                return data["response"]

    return "Sorry, ik weet niet wat ik moet zeggen."


print("Chatbot: Hallo! Typ 'stop' om te stoppen.\n")
while True:
    vraag = input("Jij: ")
    if vraag.lower() in ["stop", "exit", "quit"]:
        print("Chatbot: Tot ziens!")
        break
    antwoord = zoek_antwoord(vraag)
    print("Chatbot:", antwoord)
    log_interactie(vraag, antwoord)
