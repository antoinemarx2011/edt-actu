import asyncio
import json
import os
import hashlib
import requests
from datetime import datetime, timedelta
from pathlib import Path
from ecoledirecte_api.client import EDClient
from ecoledirecte_api.exceptions import BaseEcoleDirecteException

# ─────────────────────────────────────────
#  CONFIG — via secrets GitHub
# ─────────────────────────────────────────
ED_USERNAME  = os.environ["ED_USERNAME"]
ED_PASSWORD  = os.environ["ED_PASSWORD"]
TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID   = os.environ["TG_CHAT_ID"]

CACHE_FILE = "edt_cache.json"
QCM_FILE   = "qcm.json"

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
#  CACHE QCM — sauvegarde automatique
# ─────────────────────────────────────────
def load_qcm() -> dict:
    if Path(QCM_FILE).exists():
        with open(QCM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_qcm(qcm_json: dict):
    with open(QCM_FILE, "w", encoding="utf-8") as f:
        json.dump(qcm_json, f, ensure_ascii=False, indent=4)
    print(f"[QCM] Réponses sauvegardées dans {QCM_FILE}")

# ─────────────────────────────────────────
#  CACHE EDT
# ─────────────────────────────────────────
def load_cache() -> dict:
    if Path(CACHE_FILE).exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(data: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def cours_to_dict(c) -> dict:
    if isinstance(c, dict):
        return c
    # Objet Pydantic de la lib
    raw = c.model_dump() if hasattr(c, "model_dump") else vars(c)
    return {k: str(v) for k, v in raw.items()}

def hash_edt(cours_list: list) -> str:
    simplified = sorted([{
        "matiere":    str(c.get("matiere", c.get("subject", ""))),
        "prof":       str(c.get("prof", c.get("teacher", ""))),
        "salle":      str(c.get("salle", c.get("room", ""))),
        "heureDebut": str(c.get("heureDebut", c.get("start_time", c.get("startTime", "")))),
        "jour":       str(c.get("jour", c.get("date", ""))),
        "isAnnule":   c.get("isAnnule", c.get("cancelled", False)),
    } for c in cours_list], key=lambda x: (x["jour"], x["heureDebut"]))
    return hashlib.md5(json.dumps(simplified, sort_keys=True).encode()).hexdigest()

# ─────────────────────────────────────────
#  DIFF → MESSAGE
# ─────────────────────────────────────────
def format_diff(anciens: list, nouveaux: list) -> str:
    def key(c): return (
        str(c.get("jour", c.get("date", ""))),
        str(c.get("heureDebut", c.get("start_time", "")))
    )
    ancien_map  = {key(c): c for c in anciens}
    nouveau_map = {key(c): c for c in nouveaux}
    lignes = ["🔔 <b>Changement dans ton EDT !</b>\n"]
    for k, c in ancien_map.items():
        mat = c.get("matiere", c.get("subject", "?"))
        if k not in nouveau_map:
            lignes.append(f"❌ <b>Supprimé :</b> {mat} le {k[0]} à {k[1]}")
        elif nouveau_map[k].get("isAnnule") and not c.get("isAnnule"):
            lignes.append(f"🚫 <b>Annulé :</b> {mat} le {k[0]} à {k[1]}")
    for k, c in nouveau_map.items():
        if k not in ancien_map:
            mat   = c.get("matiere", c.get("subject", "?"))
            salle = c.get("salle", c.get("room", "?"))
            lignes.append(f"✅ <b>Ajouté :</b> {mat} le {k[0]} à {k[1]} — salle {salle}")
    for k in set(ancien_map) & set(nouveau_map):
        a, n = ancien_map[k], nouveau_map[k]
        sa, sn = a.get("salle", a.get("room","")), n.get("salle", n.get("room",""))
        pa, pn = a.get("prof", a.get("teacher","")), n.get("prof", n.get("teacher",""))
        mat = n.get("matiere", n.get("subject","?"))
        if sa != sn:
            lignes.append(f"🏫 <b>Salle changée :</b> {mat} {k[0]} à {k[1]} → {sa} ➡️ {sn}")
        if pa != pn:
            lignes.append(f"👨‍🏫 <b>Prof changé :</b> {mat} {k[0]} → {pn}")
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

    qcm_json = load_qcm()

    try:
        async with EDClient(ED_USERNAME, ED_PASSWORD, qcm_json) as client:
            client.on_new_question(save_qcm)
            await client.login()
            print(f"[Login] Connecté en tant que {client.username}")

            # Récupère le premier compte élève
            student = next(
                (a for a in client.accounts if hasattr(a, "get_schedule") or "student" in type(a).__name__.lower()),
                client.accounts[0]
            )
            cours_raw = await student.get_schedule(date_debut, date_fin)
            cours = [cours_to_dict(c) for c in cours_raw]
            print(f"[EDT] {len(cours)} cours récupérés ({date_debut} → {date_fin})")

    except BaseEcoleDirecteException as e:
        msg = getattr(e, "message", str(e))
        print(f"[ERREUR ED] {msg}")
        send_telegram(f"⚠️ Erreur EcoleDirecte :\n<code>{msg}</code>")
        return
    except Exception as e:
        print(f"[ERREUR] {e}")
        send_telegram(f"⚠️ Erreur inattendue :\n<code>{e}</code>")
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
