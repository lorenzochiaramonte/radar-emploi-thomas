#!/usr/bin/env python3
"""
Client Telegram simple — pour pousser le digest depuis le radar.

Pas de bot polling (qui demanderait un serveur 24/7). Le radar push tout
au moment de son run matinal, avec textes de candidature pré-générés
inclus dans les messages.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests


def telegram_envoyer_message(
    chat_id: str,
    texte: str,
    bot_token: Optional[str] = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> bool:
    """Envoie un message à un chat Telegram. Retourne True si OK."""
    bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return False

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": texte[:4000],  # limite Telegram = 4096 chars
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
            },
            timeout=15,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"⚠️  Telegram message KO : {e}")
        return False


def telegram_envoyer_digest(
    chat_id: str,
    offres_avec_candidatures: list[dict],
    url_dashboard: str = "",
    bot_token: Optional[str] = None,
) -> int:
    """Envoie le digest matinal sur Telegram.

    Format : 1 message d'intro + 1 message par offre (pour pouvoir copier
    facilement le texte de candidature de chacune).

    Args:
        chat_id: ID du chat Telegram (numérique).
        offres_avec_candidatures: liste de dicts contenant
            {offre, texte_candidature_html, score, distance_km}.
        url_dashboard: URL de la page web GitHub Pages (optionnel).

    Returns:
        Nombre de messages envoyés avec succès.
    """
    bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("⚠️  TELEGRAM_BOT_TOKEN absent → on saute Telegram")
        return 0

    if not offres_avec_candidatures:
        msg = (
            "📭 <b>Pas de nouvelle offre ce matin</b>\n\n"
            "Le radar n'a rien trouvé qui matche tes critères depuis hier.\n"
            "Je te re-notifie demain à 7h."
        )
        if url_dashboard:
            msg += f"\n\n🌐 <a href=\"{url_dashboard}\">Voir le tableau complet</a>"
        return 1 if telegram_envoyer_message(chat_id, msg, bot_token) else 0

    n_offres = len(offres_avec_candidatures)

    # Message d'intro
    intro = (
        f"🚛 <b>Bonjour Thomas !</b>\n\n"
        f"<b>{n_offres} offre{'s' if n_offres > 1 else ''}</b> ce matin "
        f"qui collent à ton profil (Lorette + 25 km).\n\n"
        f"Pour chaque offre tu auras :\n"
        f"• Le lien direct pour postuler\n"
        f"• Un texte de candidature prêt à copier-coller\n\n"
        f"Bon courage pour la chasse 💪"
    )
    if url_dashboard:
        intro += f"\n\n🌐 <a href=\"{url_dashboard}\">Tableau complet sur le web</a>"

    n_envoyes = 0
    if telegram_envoyer_message(chat_id, intro, bot_token):
        n_envoyes += 1
    time.sleep(0.5)

    # 1 message par offre
    for i, item in enumerate(offres_avec_candidatures, 1):
        offre = item["offre"]
        candidature = item.get("texte_candidature_html", "")
        score = item.get("score", 0)
        distance = item.get("distance_km", 0)

        ville_distance = offre.ville
        if distance:
            ville_distance += f" (~{distance:.0f} km)"

        msg = (
            f"<b>#{i} • {escape_html(offre.titre)}</b>\n"
            f"🏢 {escape_html(offre.entreprise)}\n"
            f"📍 {escape_html(ville_distance)}"
        )
        if offre.type_contrat:
            msg += f"\n📝 {escape_html(offre.type_contrat)}"
        msg += f"\n⭐ Score : {score}"
        msg += f"\n\n👉 <a href=\"{offre.url}\">Postuler sur la plateforme</a>"

        if candidature:
            # Tronquer si nécessaire pour rester sous 4000 chars
            place_dispo = 4000 - len(msg) - 100
            cand_tronquee = candidature[:place_dispo] if len(candidature) > place_dispo else candidature
            msg += (
                f"\n\n<b>📝 Texte de candidature prêt à copier :</b>\n"
                f"<blockquote>{cand_tronquee}</blockquote>"
            )

        if telegram_envoyer_message(chat_id, msg, bot_token):
            n_envoyes += 1
        time.sleep(0.6)  # rate limit Telegram = ~30 msg/sec, on reste large

    print(f"📲 Telegram : {n_envoyes}/{n_offres + 1} messages envoyés à chat_id={chat_id}")
    return n_envoyes


def escape_html(s: str) -> str:
    """Échappe les caractères HTML pour Telegram parse_mode=HTML."""
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


# ─────────────────────────────────────────────────────────────────────────────
# UTILITAIRE — RÉCUPÉRER LE CHAT_ID
# ─────────────────────────────────────────────────────────────────────────────

def trouver_chat_id(bot_token: str) -> None:
    """Affiche les chats récents du bot.

    Pour récupérer le chat_id de Thomas : lui faire envoyer un message
    au bot, puis lancer ce script. Le chat_id apparaîtra dans la sortie.
    """
    resp = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getUpdates",
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        print(f"❌ Erreur API : {data}")
        return

    chats_vus = {}
    for update in data.get("result", []):
        msg = update.get("message", {}) or update.get("edited_message", {})
        chat = msg.get("chat", {})
        if chat.get("id"):
            chats_vus[chat["id"]] = {
                "type": chat.get("type"),
                "first_name": chat.get("first_name"),
                "last_name": chat.get("last_name"),
                "username": chat.get("username"),
            }

    if not chats_vus:
        print("Aucun message reçu par le bot.")
        print("Demande à Thomas d'ouvrir le bot et de taper /start ou n'importe quoi.")
        return

    print("Chats détectés :")
    for cid, info in chats_vus.items():
        print(f"  chat_id = {cid}  →  {info}")


if __name__ == "__main__":
    import sys
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not token:
        print("Usage: python telegram_client.py <bot_token>")
        print("       (ou défini la variable d'env TELEGRAM_BOT_TOKEN)")
        sys.exit(1)
    trouver_chat_id(token)
