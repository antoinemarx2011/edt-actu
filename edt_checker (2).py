import asyncio
import json
import os
import hashlib
import requests
from datetime import datetime, timedelta

# pip install ecoledirecte-py-client
from ecoledirecte_py_client import Client

# ─────────────────────────────────────────
#  CONFIG — via secrets GitHub
# ─────────────────────────────────────────
ED_USERNAME  = os.environ["ED_USERNAME"]
ED_PASSWORD  = os.environ["ED_PASSWORD"]
TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID   = os.environ["TG_CHAT_ID"]

CACHE_FILE  = "edt_cache.json"
QCM_FILE    = "qcm.json"    # réponses MFA mises en cache
DEVICE_FILE = "device.json" # token device mis en cache

# ─────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }, timeout=10)
    r.raise_for_status()
    print("[Telegram] Message envoyé ✓")

# ─────────────────────────────────────────
#  CACHE EDT
# ─────────────────────────────────────────
def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(data: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def cours_to_dict(c) -> dict:
    if isinstance(c, dict):
        return c
    return {
        "matiere":    getattr(c, "matiere", ""),
        "prof":       getattr(c, "prof", ""),
        "salle":      getattr(c, "salle", ""),
        "heureDebut": str(getattr(c, "start", "")),
        "heureFin":   str(getattr(c, "end", "")),
        "jour":       str(getattr(c, "date", "")),
        "isAnnule":   getattr(c, "is_cancelled", False),
    }

def hash_edt(cours_list: list) -> str:
    simplified = sorted([{
        "matiere":    c.get("matiere", ""),
        "prof":       c.get("prof", ""),
        "salle":      c.get("salle", ""),
        "heureDebut": c.get("heureDebut", ""),
        "jour":       c.get("jour", ""),
        "isAnnule":   c.get("isAnnule", False),
    } for c in cours_list], key=lambda x: (x["jour"], x["heureDebut"]))
    return hashlib.md5(json.dumps(simplified, sort_keys=True).encode()).hexdigest()

# ─────────────────────────────────────────
#  DIFF EDT → MESSAGE TELEGRAM
# ─────────────────────────────────────────
def format_diff(anciens: list, nouveaux: list) -> str:
    def key(c): return (c.get("jour",""), c.get("heureDebut",""))
    ancien_map  = {key(c): c for c in anciens}
    nouveau_map = {key(c): c for c in nouveaux}
    lignes = ["🔔 <b>Changement dans ton EDT !</b>\n"]
    for k, c in ancien_map.items():
        if k not in nouveau_map:
            lignes.append(f"❌ <b>Supprimé :</b> {c.get('matiere','')} le {k[0]} à {k[1]}")
        elif nouveau_map[k].get("isAnnule") and not c.get("isAnnule"):
            lignes.append(f"🚫 <b>Annulé :</b> {c.get('matiere','')} le {k[0]} à {k[1]}")
    for k, c in nouveau_map.items():
        if k not in ancien_map:
            lignes.append(f"✅ <b>Ajouté :</b> {c.get('matiere','')} le {k[0]} à {k[1]} — salle {c.get('salle','?')}")
    for k in set(ancien_map) & set(nouveau_map):
        a, n = ancien_map[k], nouveau_map[k]
        if a.get("salle") != n.get("salle"):
            lignes.append(f"🏫 <b>Salle changée :</b> {n.get('matiere','')} {k[0]} à {k[1]} → {a.get('salle','?')} ➡️ {n.get('salle','?')}")
        if a.get("prof") != n.get("prof"):
            lignes.append(f"👨‍🏫 <b>Prof changé :</b> {n.get('matiere','')} {k[0]} → {n.get('prof','?')}")
    if len(lignes) == 1:
        lignes.append("(changement détecté mais non identifié précisément)")
    return "\n".join(lignes)

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
async def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Vérification EDT...")
    today      = datetime.today()
    lundi      = today - timedelta(days=today.weekday())
    date_debut = lundi.strftime("%Y-%m-%d")
    date_fin   = (lundi + timedelta(days=13)).strftime("%Y-%m-%d")
    try:
        client = Client(
            username=ED_USERNAME,
            password=ED_PASSWORD,
            qcm_file=QCM_FILE,
            device_file=DEVICE_FILE,
        )
        await client.login()
        student  = client.student
        cours_raw = await student.get_schedule(date_debut, date_fin)
        cours     = [cours_to_dict(c) for c in cours_raw]
        print(f"[EDT] {len(cours)} cours récupérés ({date_debut} → {date_fin})")
    except Exception as e:
        print(f"[ERREUR] {e}")
        send_telegram(f"⚠️ Erreur vérification EDT :\n<code>{e}</code>")
        return
    cache     = load_cache()
    cache_key = f"{date_debut}_{date_fin}"
    new_hash  = hash_edt(cours)
    if cache_key not in cache:
        cache[cache_key] = {"hash": new_hash, "data": cours}
        save_cache(cache)
        print("[Cache] Premier enregistrement.")
        send_telegram(f"✅ Bot EDT démarré !\nSurveillance du {date_debut} au {date_fin} ({len(cours)} cours).")
    elif cache[cache_key]["hash"] != new_hash:
        msg = format_diff(cache[cache_key]["data"], cours)
        send_telegram(msg)
        cache[cache_key] = {"hash": new_hash, "data": cours}
        save_cache(cache)
        print("[Changement] Notification envoyée !")
    else:
        print("[OK] Aucun changement détecté.")

if __name__ == "__main__":
    asyncio.run(main())
