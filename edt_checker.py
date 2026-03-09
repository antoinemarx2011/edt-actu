import requests
import json
import os
import hashlib
from datetime import datetime, timedelta

# ─────────────────────────────────────────
#  CONFIG — à remplir / via secrets GitHub
# ─────────────────────────────────────────
ED_USERNAME   = os.environ.get("ED_USERNAME", "ton_identifiant")
ED_PASSWORD   = os.environ.get("ED_PASSWORD", "ton_mot_de_passe")
TG_BOT_TOKEN  = os.environ.get("TG_BOT_TOKEN", "123456:ABC...")
TG_CHAT_ID    = os.environ.get("TG_CHAT_ID",  "ton_chat_id")

CACHE_FILE    = "edt_cache.json"
BASE_URL      = "https://api.ecoledirecte.com/v3"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.ecoledirecte.com",
    "Referer": "https://www.ecoledirecte.com/",
}

# ─────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
    print(f"[Telegram] Message envoyé ✓")

# ─────────────────────────────────────────
#  AUTHENTIFICATION ECOLEDIRECTE
# ─────────────────────────────────────────
def login() -> tuple[str, int]:
    """Retourne (token, eleve_id)"""
    url = f"{BASE_URL}/login.awp?v=4.53.0"
    payload = f'data={json.dumps({"identifiant": ED_USERNAME, "motdepasse": ED_PASSWORD, "isReLogin": False, "uuid": ""})}'
    r = requests.post(url, data=payload, headers=HEADERS, timeout=15)
    data = r.json()

    if data.get("code") != 200:
        raise Exception(f"Erreur login EcoleDirecte : {data.get('message', data)}")

    accounts = data["data"]["accounts"]
    # On prend le premier compte élève
    account = next((a for a in accounts if a["typeCompte"] == "E"), accounts[0])
    token    = data["token"]
    eleve_id = account["id"]
    print(f"[Login] Connecté en tant que {account['prenom']} {account['nom']} (id={eleve_id})")
    return token, eleve_id

# ─────────────────────────────────────────
#  RÉCUPÉRATION EDT
# ─────────────────────────────────────────
def get_edt(token: str, eleve_id: int, date_debut: str, date_fin: str) -> list:
    url = f"{BASE_URL}/E/{eleve_id}/emploidutemps.awp?verbe=get&v=4.53.0"
    payload = f'data={json.dumps({"dateDebut": date_debut, "dateFin": date_fin, "avecTrous": False})}'
    headers = {**HEADERS, "X-Token": token}
    r = requests.post(url, data=payload, headers=headers, timeout=15)
    data = r.json()

    if data.get("code") != 200:
        raise Exception(f"Erreur récupération EDT : {data.get('message', data)}")

    return data["data"]

# ─────────────────────────────────────────
#  COMPARAISON / CACHE
# ─────────────────────────────────────────
def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(data: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hash_edt(cours_list: list) -> str:
    """Hash stable de l'EDT pour détecter les changements"""
    # On garde seulement les champs pertinents
    simplified = []
    for c in cours_list:
        simplified.append({
            "matiere":    c.get("matiere", ""),
            "prof":       c.get("prof", ""),
            "salle":      c.get("salle", ""),
            "heureDebut": c.get("heureDebut", ""),
            "heureFin":   c.get("heureFin", ""),
            "jour":       c.get("jour", c.get("date", "")),
            "isAnnule":   c.get("isAnnule", False),
        })
    simplified.sort(key=lambda x: (x["jour"], x["heureDebut"]))
    return hashlib.md5(json.dumps(simplified, sort_keys=True).encode()).hexdigest()

# ─────────────────────────────────────────
#  FORMATAGE MESSAGE TELEGRAM
# ─────────────────────────────────────────
def format_diff(ancien: list, nouveau: list) -> str:
    ancien_map = {(c.get("jour", c.get("date","")), c.get("heureDebut","")): c for c in ancien}
    nouveau_map = {(c.get("jour", c.get("date","")), c.get("heureDebut","")): c for c in nouveau}

    lignes = ["🔔 <b>Changement dans ton EDT !</b>\n"]

    # Cours supprimés / annulés
    for key, c in ancien_map.items():
        if key not in nouveau_map:
            lignes.append(f"❌ <b>Supprimé :</b> {c.get('matiere','')} le {key[0]} à {key[1]}")
        elif nouveau_map[key].get("isAnnule") and not c.get("isAnnule"):
            lignes.append(f"🚫 <b>Annulé :</b> {c.get('matiere','')} le {key[0]} à {key[1]}")

    # Cours ajoutés
    for key, c in nouveau_map.items():
        if key not in ancien_map:
            lignes.append(f"✅ <b>Ajouté :</b> {c.get('matiere','')} le {key[0]} à {key[1]} — salle {c.get('salle','?')}")

    # Changement de salle ou prof
    for key in ancien_map:
        if key in nouveau_map:
            a, n = ancien_map[key], nouveau_map[key]
            if a.get("salle") != n.get("salle"):
                lignes.append(f"🏫 <b>Salle changée :</b> {n.get('matiere','')} {key[0]} à {key[1]} → {a.get('salle','?')} ➡️ {n.get('salle','?')}")
            if a.get("prof") != n.get("prof"):
                lignes.append(f"👨‍🏫 <b>Prof changé :</b> {n.get('matiere','')} {key[0]} à {key[1]} → {n.get('prof','?')}")

    if len(lignes) == 1:
        lignes.append("(changement détecté mais non identifié précisément)")

    return "\n".join(lignes)

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Vérification EDT...")

    # Semaine courante + suivante
    today      = datetime.today()
    lundi      = today - timedelta(days=today.weekday())
    date_debut = lundi.strftime("%Y-%m-%d")
    date_fin   = (lundi + timedelta(days=13)).strftime("%Y-%m-%d")  # 2 semaines

    try:
        token, eleve_id = login()
        cours = get_edt(token, eleve_id, date_debut, date_fin)
        print(f"[EDT] {len(cours)} cours récupérés ({date_debut} → {date_fin})")
    except Exception as e:
        print(f"[ERREUR] {e}")
        send_telegram(f"⚠️ Erreur lors de la vérification EDT :\n<code>{e}</code>")
        return

    cache = load_cache()
    cache_key = f"{date_debut}_{date_fin}"
    nouveau_hash = hash_edt(cours)

    if cache_key not in cache:
        # Première exécution : on sauvegarde sans notif
        cache[cache_key] = {"hash": nouveau_hash, "data": cours}
        save_cache(cache)
        print("[Cache] Premier enregistrement, pas de notification.")
        send_telegram(f"✅ Bot EDT démarré !\nSurveillance du {date_debut} au {date_fin} ({len(cours)} cours).")
    elif cache[cache_key]["hash"] != nouveau_hash:
        # Changement détecté !
        ancien_cours = cache[cache_key]["data"]
        message = format_diff(ancien_cours, cours)
        send_telegram(message)
        cache[cache_key] = {"hash": nouveau_hash, "data": cours}
        save_cache(cache)
        print("[Changement] Notification envoyée !")
    else:
        print("[OK] Aucun changement détecté.")

if __name__ == "__main__":
    main()
