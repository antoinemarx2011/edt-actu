# 🎓 EDT CHECKER — ECOLEDIRECTE
Bot de surveillance automatique de l'emploi du temps EcoleDirecte. Détecte les changements (annulations, ajouts, changements de salle ou de prof) et envoie une notification Telegram en temps réel.
✨ Fonctionnalités

Surveillance des 2 prochaines semaines de cours
Détection précise des changements : cours annulé, ajouté, supprimé, salle ou prof modifié
Notification instantanée via Telegram
Exécution automatique toutes les 10 minutes via GitHub Actions (lun–ven, 6h–20h)

⚙️ Configuration
Ajoute les secrets suivants dans ton repo GitHub (Settings > Secrets and variables > Actions) :
ED_USERNAME = Identifiant EcoleDirecte
ED_PASSWORD = Mot de passe EcoleDirecte
ED_CN = Code 2FA (laisser vide si non activé
ED_CV = Valeur 2FA (laisser vide si non activé)
TG_BOT_TOKEN = Token du bot Telegram
TG_CHAT_ID = ID du chat Telegram où envoyer les alertes

## 📬 Exemple de notification
```
🔔 Changement dans ton EDT !

🚫 Annulé : Mathématiques le 2025-05-12 à 08:00
🏫 Salle changée : Physique 2025-05-13 à 10:00 : B12 ➡️ A04
✅ Ajouté : Espagnol le 2025-05-14 à 14:00 — salle C01
