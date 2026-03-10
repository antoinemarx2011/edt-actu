#🎓 EDT Checker — EcoleDirecte
Bot de surveillance automatique de l'emploi du temps EcoleDirecte. Détecte les changements (annulations, ajouts, changements de salle ou de prof) et envoie une notification Telegram en temps réel.
✨ Fonctionnalités

Surveillance des 2 prochaines semaines de cours
Détection précise des changements : cours annulé, ajouté, supprimé, salle ou prof modifié
Notification instantanée via Telegram
Exécution automatique toutes les 10 minutes via GitHub Actions (lun–ven, 6h–20h)

⚙️ Configuration
Ajoute les secrets suivants dans ton repo GitHub (Settings > Secrets and variables > Actions) :
SecretDescriptionED_USERNAMEIdentifiant EcoleDirecteED_PASSWORDMot de passe EcoleDirecteED_CNCode 2FA (laisser vide si non activé)ED_CVValeur 2FA (laisser vide si non activé)TG_BOT_TOKENToken du bot TelegramTG_CHAT_IDID du chat Telegram où envoyer les alertes
🚀 Lancement en local
bashexport ED_USERNAME="..."
export ED_PASSWORD="..."
export ED_CN=""
export ED_CV=""
export TG_BOT_TOKEN="..."
export TG_CHAT_ID="..."

pip install requests
python edt_checker.py
```

## 📬 Exemple de notification
```
🔔 Changement dans ton EDT !

🚫 Annulé : Mathématiques le 2025-05-12 à 08:00
🏫 Salle changée : Physique 2025-05-13 à 10:00 : B12 ➡️ A04
✅ Ajouté : Espagnol le 2025-05-14 à 14:00 — salle C01
