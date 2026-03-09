import requests
import json
import os
import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote

ED_USERNAME  = os.environ["ED_USERNAME"]
ED_PASSWORD  = os.environ["ED_PASSWORD"]
ED_CN = os.environ["ED_CN"]
ED_CV = os.environ["ED_CV"]
TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID   = os.environ["TG_CHAT_ID"]

CACHE_FILE = "edt_cache.json"
BASE       = "https://api.ecoledirecte.com/v3"
HEADERS    = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.ecoledirecte.com",
    "Referer": "https://www.ecoledirecte.com/",
}

def send_telegram(message):
    requests.post(
        f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
        json={"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "HTML"},
        timeout=10
    ).raise_for_status()
    print("[Telegram] ✓")

def login():
    session = requests.Session()
    r = session.get(f"{BASE}/login.awp?gtk=1&v=4.75.0", headers=HEADERS, timeout=10)
    gtk = session.cookies.get("GTK", "")
    h = {**HEADERS, **({"X-Gtk": gtk} if gtk else {})}
    body = json.dumps({
        "identifiant": ED_USERNAME,
        "motdepasse": ED_PASSWORD,
        "isRelogin": False,
        "uuid": "",
        "fa": [{"cn": ED_CN, "cv": ED_CV}]
    })
    r = session.post(f"{BASE}/login.awp?verbe=post&v=4.75.0", data=f"data={quote(body)}", headers=h, timeout=15)
    resp = r.json()
    if resp.get("code") != 200:
        raise Exception(f"Login échoué ({resp.get('code')}) : {resp.get('message')}")
    token = resp.get("token") or r.headers.get("X-Token", "")
    accounts = resp.get("data", {}).get("accounts", [])
    eleve = next((a for a in accounts if a.get("typeCompte") == "E"), accounts[0] if accounts else {})
    eleve_id = eleve.get("id", os.environ.get("ED_ELEVE_ID", ""))
    print(f"[Login] ✓ {eleve.get('prenom','')} {eleve.get('nom','')} (id={eleve_id})")
    return token, eleve_id, h

def get_edt(token, eleve_id, h, date_debut, date_fin):
    body = json.dumps({"dateDebut": date_debut, "dateFin": date_fin, "avecTrous": False})
    r = requests.post(
        f"{BASE}/E/{eleve_id}/emploidutemps.awp?verbe=get&v=4.75.0",
        data=f"data={quote(body)}",
        headers={**h, "X-Token": token},
        timeout=15
    )
    resp = r.json()
    if resp.get("code") != 200:
        raise Exception(f"EDT échoué ({resp.get('code')}) : {resp.get('message')}")
    return resp["data"]

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hash_edt(cours):
    simplified = sorted([{
        "matiere":    c.get("matiere", ""),
        "prof":       c.get("prof", ""),
        "salle":      c.get("salle", ""),
        "heureDebut": c.get("heureDebut", ""),
        "jour":       c.get("jour", c.get("date", "")),
        "isAnnule":   c.get("isAnnule", False),
    } for c in cours], key=lambda x: (x["jour"], x["heureDebut"]))
    return hashlib.md5(json.dumps(simplified, sort_keys=True).encode()).hexdigest()

def format_diff(anciens, nouveaux):
    def key(c): return (c.get("jour", c.get("date", "")), c.get("heureDebut", ""))
    am, nm = {key(c): c for c in anciens}, {key(c): c for c in nouveaux}
    lignes = ["🔔 <b>Changement dans ton EDT !</b>\n"]
    for k, c in am.items():
        if k not in nm:
            lignes.append(f"❌ <b>Supprimé :</b> {c.get('matiere','?')} le {k[0]} à {k[1]}")
        elif nm[k].get("isAnnule") and not c.get("isAnnule"):
            lignes.append(f"🚫 <b>Annulé :</b> {c.get('matiere','?')} le {k[0]} à {k[1]}")
    for k, c in nm.items():
        if k not in am:
            lignes.append(f"✅ <b>Ajouté :</b> {c.get('matiere','?')} le {k[0]} à {k[1]} — salle {c.get('salle','?')}")
    for k in set(am) & set(nm):
        a, n = am[k], nm[k]
        if a.get("salle") != n.get("salle"):
            lignes.append(f"🏫 <b>Salle changée :</b> {n.get('matiere','?')} {k[0]} à {k[1]} : {a.get('salle','?')} ➡️ {n.get('salle','?')}")
        if a.get("prof") != n.get("prof"):
            lignes.append(f"👨‍🏫 <b>Prof changé :</b> {n.get('matiere','?')} {k[0]} → {n.get('prof','?')}")
    if len(lignes) == 1:
        lignes.append("(changement détecté mais non identifié précisément)")
    return "\n".join(lignes)

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Vérification EDT...")
    today  = datetime.today()
    lundi  = today - timedelta(days=today.weekday())
    d_deb  = lundi.strftime("%Y-%m-%d")
    d_fin  = (lundi + timedelta(days=13)).strftime("%Y-%m-%d")
    try:
        token, eleve_id, h = login()
        cours = get_edt(token, eleve_id, h, d_deb, d_fin)
        print(f"[EDT] {len(cours)} cours ({d_deb} → {d_fin})")
    except Exception as e:
        print(f"[ERREUR] {e}")
        send_telegram(f"⚠️ Erreur EDT :\n<code>{e}</code>")
        return
    cache = load_cache()
    key   = f"{d_deb}_{d_fin}"
    nhash = hash_edt(cours)
    if key not in cache:
        cache[key] = {"hash": nhash, "data": cours}
        save_cache(cache)
        send_telegram(f"✅ Bot EDT démarré !\nSurveillance du {d_deb} au {d_fin} ({len(cours)} cours).")
        print("[Cache] Premier enregistrement.")
    elif cache[key]["hash"] != nhash:
        send_telegram(format_diff(cache[key]["data"], cours))
        cache[key] = {"hash": nhash, "data": cours}
        save_cache(cache)
        print("[Changement] Notification envoyée !")
    else:
        print("[OK] Aucun changement.")

if __name__ == "__main__":
    main()
