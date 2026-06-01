#!/usr/bin/env python3
"""
Radar emploi — Thomas Chiaramonte
=================================
Interroge l'API France Travail + Indeed RSS, score les offres,
dédoublonne avec un historique persistant, et envoie un digest par email.

Conçu pour tourner dans GitHub Actions une fois par jour.

Auteur : agent IA, juin 2026
"""

from __future__ import annotations

import json
import math
import os
import smtplib
import sys
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import requests

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Coordonnées GPS de Lorette (42420)
LORETTE_LAT = 45.5236
LORETTE_LON = 4.6736

# Rayon de recherche en kilomètres
RAYON_KM = 25

# Codes ROME ciblés (référentiel métier France Travail)
# N1103 = Cariste / N1101 = Magasinier / N1105 = Manutentionnaire
# H2102 = Conduite équipement de production alimentaire
# N1104 = Préparation de commandes
CODES_ROME = ["N1103", "N1101", "N1105", "N1104", "H2102"]

# Mots-clés positifs pour le scoring
MOTS_CLES_POSITIFS = {
    "caces 3": 3,
    "caces3": 3,
    "cariste": 3,
    "préparateur de commandes": 2,
    "préparation de commandes": 2,
    "magasinier": 2,
    "logistique": 1,
    "manutention": 1,
    "agroalimentaire": 1,
    "agro-alimentaire": 1,
    "production alimentaire": 1,
    "cdi": 2,
    "long terme": 1,
}

# Mots-clés à éviter (poste pas adapté au profil)
MOTS_CLES_NEGATIFS = {
    "caces 5 obligatoire": -3,
    "caces 6 obligatoire": -3,
    "anglais courant": -2,
    "permis poids lourd": -2,
    "permis ec": -2,
    "permis super lourd": -2,
    "port de charges 50": -2,
    "nuit obligatoire": -1,
}

# Employeurs directs prioritaires (bonus si l'offre vient d'eux)
EMPLOYEURS_PRIORITAIRES = [
    "id logistics", "easydis", "geodis", "dhl", "refresco",
    "lustucru", "brioche pasquier", "yoplait", "casino", "carrefour",
]

# Seuil minimum pour qu'une offre apparaisse dans le digest
SCORE_MIN = 2

# Fichier d'historique pour le dédoublonnage entre runs
HISTORIQUE_PATH = Path("data/historique.json")

# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE DE DONNÉES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Offre:
    """Une offre d'emploi normalisée."""
    source: str            # "francetravail", "indeed", etc.
    id_externe: str        # identifiant unique côté source
    titre: str
    entreprise: str
    ville: str
    code_postal: str
    type_contrat: str       # CDI / CDD / Intérim / etc.
    date_publication: str   # ISO 8601
    description: str
    url: str
    distance_km: float = 0.0
    score: int = 0
    tags: list[str] = field(default_factory=list)

    def cle_dedup(self) -> str:
        """Clé pour dédoublonner les mêmes offres entre sources."""
        norm = lambda s: normaliser(s)[:50]
        return f"{norm(self.titre)}|{norm(self.entreprise)}|{norm(self.ville)}"


# ─────────────────────────────────────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────

def normaliser(texte: str) -> str:
    """Minuscule, sans accent, sans espaces superflus."""
    if not texte:
        return ""
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return texte.lower().strip()


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en km entre 2 points GPS."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 1 — API FRANCE TRAVAIL
# ─────────────────────────────────────────────────────────────────────────────

def francetravail_token(client_id: str, client_secret: str) -> str:
    """Récupère un token OAuth2 pour l'API France Travail."""
    url = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    resp = requests.post(
        url,
        params={"realm": "/partenaire"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "api_offresdemploiv2 o2dsoffre",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def francetravail_chercher(token: str) -> list[Offre]:
    """Cherche les offres pertinentes via l'API officielle."""
    url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {"Authorization": f"Bearer {token}"}

    # On boucle sur les codes ROME pour ratisser large
    offres: list[Offre] = []
    for rome in CODES_ROME:
        params = {
            "codeROME": rome,
            "commune": "42124",  # code INSEE de Lorette
            "distance": str(RAYON_KM),
            "range": "0-49",     # 50 résultats max par appel
            "sort": "1",          # tri par date de publication
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
            if resp.status_code in (204, 206):
                # 206 = résultat partiel (normal)
                pass
            elif resp.status_code != 200:
                log(f"⚠️  France Travail {rome} → HTTP {resp.status_code}")
                continue
            data = resp.json() if resp.text else {}
        except Exception as e:
            log(f"⚠️  France Travail erreur ({rome}) : {e}")
            continue

        for raw in data.get("resultats", []):
            offre = _ft_parser(raw)
            if offre:
                offres.append(offre)
        time.sleep(0.5)  # être correct avec leur API

    log(f"France Travail : {len(offres)} offres récupérées")
    return offres


def _ft_parser(raw: dict) -> Offre | None:
    """Parse une offre de l'API France Travail."""
    try:
        lieu = raw.get("lieuTravail", {}) or {}
        return Offre(
            source="francetravail",
            id_externe=str(raw.get("id", "")),
            titre=raw.get("intitule", "Sans titre"),
            entreprise=(raw.get("entreprise") or {}).get("nom", "Non précisé"),
            ville=lieu.get("libelle", ""),
            code_postal=lieu.get("codePostal", ""),
            type_contrat=raw.get("typeContratLibelle", raw.get("typeContrat", "")),
            date_publication=raw.get("dateCreation", ""),
            description=raw.get("description", ""),
            url=f"https://candidat.francetravail.fr/offres/recherche/detail/{raw.get('id', '')}",
        )
    except Exception as e:
        log(f"⚠️  Parse FT KO : {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 2 — INDEED RSS
# ─────────────────────────────────────────────────────────────────────────────

def indeed_chercher() -> list[Offre]:
    """Récupère les offres via les flux RSS Indeed (pas d'API officielle gratuite).

    Indeed propose un endpoint RSS sur les pages de recherche. C'est plus
    léger que du scraping HTML et accepté tant qu'on garde un volume modeste.
    """
    requetes = [
        ("cariste CACES 3", "Lorette"),
        ("préparateur commandes", "Saint-Étienne"),
        ("opérateur production agroalimentaire", "Saint-Étienne"),
    ]

    offres: list[Offre] = []
    for mots_cles, ville in requetes:
        url = (
            f"https://fr.indeed.com/rss?q={quote_plus(mots_cles)}"
            f"&l={quote_plus(ville)}&radius={RAYON_KM}&fromage=3"
        )
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; RadarEmploi/1.0)"},
                timeout=15,
            )
            if resp.status_code != 200:
                log(f"⚠️  Indeed RSS '{mots_cles}' → HTTP {resp.status_code}")
                continue
            offres.extend(_indeed_parser(resp.content, mots_cles))
        except Exception as e:
            log(f"⚠️  Indeed erreur : {e}")
            continue
        time.sleep(1.0)

    log(f"Indeed : {len(offres)} offres récupérées")
    return offres


def _indeed_parser(xml_bytes: bytes, mots_cles_origine: str) -> list[Offre]:
    """Parse un flux RSS Indeed."""
    offres: list[Offre] = []
    try:
        root = ET.fromstring(xml_bytes)
        for item in root.iter("item"):
            titre_complet = (item.findtext("title") or "").strip()
            # Format Indeed : "Titre du poste - Entreprise - Ville"
            parties = [p.strip() for p in titre_complet.split(" - ")]
            titre = parties[0] if parties else titre_complet
            entreprise = parties[1] if len(parties) > 1 else "Non précisé"
            ville = parties[2] if len(parties) > 2 else ""

            offres.append(Offre(
                source="indeed",
                id_externe=item.findtext("guid") or item.findtext("link") or titre,
                titre=titre,
                entreprise=entreprise,
                ville=ville,
                code_postal="",
                type_contrat="",  # pas dispo dans le RSS
                date_publication=item.findtext("pubDate") or "",
                description=(item.findtext("description") or "")[:500],
                url=item.findtext("link") or "",
                tags=[f"recherche:{mots_cles_origine}"],
            ))
    except ET.ParseError as e:
        log(f"⚠️  Indeed XML invalide : {e}")
    return offres


# ─────────────────────────────────────────────────────────────────────────────
# DÉDOUBLONNAGE
# ─────────────────────────────────────────────────────────────────────────────

def charger_historique() -> set[str]:
    """Charge la liste des id d'offres déjà vues lors des runs précédents."""
    if not HISTORIQUE_PATH.exists():
        return set()
    try:
        return set(json.loads(HISTORIQUE_PATH.read_text(encoding="utf-8")))
    except Exception:
        return set()


def sauvegarder_historique(cles: set[str]) -> None:
    HISTORIQUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # On garde max 5000 entrées pour pas faire grossir indéfiniment
    cles_limitees = list(cles)[-5000:]
    HISTORIQUE_PATH.write_text(
        json.dumps(cles_limitees, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def dedoublonner(offres: Iterable[Offre], deja_vues: set[str]) -> list[Offre]:
    """Supprime les doublons inter-sources et les offres déjà vues."""
    vues_dans_ce_run: set[str] = set()
    nouvelles: list[Offre] = []
    for o in offres:
        cle = o.cle_dedup()
        if cle in vues_dans_ce_run or cle in deja_vues:
            continue
        vues_dans_ce_run.add(cle)
        nouvelles.append(o)
    return nouvelles


# ─────────────────────────────────────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────────────────────────────────────

def scorer(offre: Offre) -> int:
    """Attribue un score de pertinence à l'offre."""
    score = 0
    texte = normaliser(f"{offre.titre} {offre.description} {offre.entreprise} {offre.type_contrat}")

    # Mots-clés positifs et négatifs
    for mot, points in MOTS_CLES_POSITIFS.items():
        if normaliser(mot) in texte:
            score += points
            offre.tags.append(f"+{mot}")
    for mot, points in MOTS_CLES_NEGATIFS.items():
        if normaliser(mot) in texte:
            score += points
            offre.tags.append(f"⚠ {mot}")

    # Bonus employeur prioritaire
    entreprise_norm = normaliser(offre.entreprise)
    for emp in EMPLOYEURS_PRIORITAIRES:
        if emp in entreprise_norm:
            score += 2
            offre.tags.append(f"⭐ {emp}")
            break

    # Bonus distance (si on a une distance calculée)
    if offre.distance_km > 0:
        if offre.distance_km < 10:
            score += 2
        elif offre.distance_km < 20:
            score += 1
        elif offre.distance_km > 30:
            score -= 2

    return score


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────────────────────────────

def construire_email_html(offres: list[Offre]) -> str:
    """Génère le corps HTML du digest."""
    if not offres:
        return """
        <html><body style="font-family: Arial, sans-serif;">
        <h2>📭 Aucune nouvelle offre ce matin</h2>
        <p>Pas de nouvelles offres correspondant aux critères depuis hier.
        Le radar reste actif et te re-notifiera demain.</p>
        </body></html>
        """

    lignes = []
    for i, o in enumerate(offres, 1):
        tags_html = " ".join(f'<span style="background:#eef;padding:2px 6px;border-radius:3px;font-size:11px;margin-right:4px;">{t}</span>' for t in o.tags[:5])
        ville_distance = f"{o.ville}"
        if o.distance_km:
            ville_distance += f" (~{o.distance_km:.0f} km)"
        lignes.append(f"""
        <div style="border:1px solid #ddd;border-radius:6px;padding:14px;margin-bottom:12px;">
            <div style="font-size:11px;color:#888;">#{i} • Score {o.score} • {o.source}</div>
            <h3 style="margin:6px 0;color:#234;">{o.titre}</h3>
            <div style="color:#555;margin-bottom:6px;">
                <strong>{o.entreprise}</strong> — {ville_distance}
                {f' • {o.type_contrat}' if o.type_contrat else ''}
            </div>
            <div style="margin:8px 0;">{tags_html}</div>
            <p style="font-size:13px;color:#444;margin:8px 0;">
                {(o.description or '')[:280]}{'...' if len(o.description or '') > 280 else ''}
            </p>
            <a href="{o.url}" style="display:inline-block;background:#2a6;color:white;padding:8px 14px;border-radius:4px;text-decoration:none;font-size:13px;">
                Voir l'offre →
            </a>
        </div>
        """)

    return f"""
    <html><body style="font-family: Arial, sans-serif; max-width:680px; margin:0 auto;">
        <h2>🚛 Radar emploi Thomas — {len(offres)} offre{'s' if len(offres) > 1 else ''} aujourd'hui</h2>
        <p style="color:#666;">Lorette 42420 • Rayon {RAYON_KM} km • {datetime.now().strftime('%d/%m/%Y')}</p>
        {''.join(lignes)}
        <hr/>
        <p style="font-size:11px;color:#999;">
            Sources : France Travail + Indeed RSS. Trié par score de pertinence.
            Les offres déjà vues lors d'un run précédent sont filtrées automatiquement.
        </p>
    </body></html>
    """


def envoyer_email(html: str, sujet: str) -> None:
    """Envoie le digest par SMTP Gmail."""
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    destinataire = os.environ.get("EMAIL_DESTINATAIRE", user)

    if not user or not password:
        log("❌ SMTP_USER ou SMTP_PASSWORD absent → impossible d'envoyer le mail")
        log("   (Le digest a quand même été généré, voir digest.html dans les artefacts)")
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = user
    msg["To"] = destinataire
    msg["Subject"] = sujet
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(user, password)
            smtp.sendmail(user, [destinataire], msg.as_string())
        log(f"📧 Mail envoyé à {destinataire}")
    except Exception as e:
        log(f"❌ Erreur SMTP : {e}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    log("════════════════════════════════════════════")
    log("  Radar emploi Thomas — démarrage")
    log("════════════════════════════════════════════")

    # 1. Collecte
    toutes_offres: list[Offre] = []

    ft_id = os.environ.get("FT_CLIENT_ID")
    ft_secret = os.environ.get("FT_CLIENT_SECRET")
    if ft_id and ft_secret:
        try:
            token = francetravail_token(ft_id, ft_secret)
            toutes_offres.extend(francetravail_chercher(token))
        except Exception as e:
            log(f"❌ France Travail KO : {e}")
    else:
        log("⚠️  FT_CLIENT_ID/SECRET absents → on saute France Travail")

    try:
        toutes_offres.extend(indeed_chercher())
    except Exception as e:
        log(f"❌ Indeed KO : {e}")

    log(f"Total brut collecté : {len(toutes_offres)} offres")

    # 2. Dédoublonnage
    deja_vues = charger_historique()
    nouvelles = dedoublonner(toutes_offres, deja_vues)
    log(f"Après dédoublonnage : {len(nouvelles)} nouvelles offres")

    # 3. Scoring + filtrage
    for o in nouvelles:
        o.score = scorer(o)
    pertinentes = [o for o in nouvelles if o.score >= SCORE_MIN]
    pertinentes.sort(key=lambda x: x.score, reverse=True)
    pertinentes = pertinentes[:15]  # top 15 max
    log(f"Après scoring (seuil {SCORE_MIN}) : {len(pertinentes)} offres dans le digest")

    # 4. Génération des textes de candidature pour le top 5
    log("Génération des textes de candidature (top 5)...")
    offres_avec_candidatures: list[dict] = []
    cout_ia_total = 0.0

    try:
        from candidature_generator import generer as generer_candidature
        cand_disponible = True
    except ImportError:
        log("⚠️  candidature_generator absent → pas de génération")
        cand_disponible = False

    for i, offre in enumerate(pertinentes[:5]):
        candidature_html = ""
        if cand_disponible:
            try:
                resultat = generer_candidature(
                    titre_offre=offre.titre,
                    entreprise=offre.entreprise,
                    description_offre=offre.description,
                    ville=offre.ville,
                    mode="auto",
                )
                candidature_html = resultat.contenu
                cout_ia_total += resultat.cout_estime_eur
                log(f"  #{i+1} — {resultat.modele} — {resultat.nb_mots} mots — {resultat.cout_estime_eur:.5f}€")
            except Exception as e:
                log(f"  ⚠️  Génération offre #{i+1} KO : {e}")

        offres_avec_candidatures.append({
            "offre": offre,
            "texte_candidature_html": candidature_html,
            "score": offre.score,
            "distance_km": offre.distance_km,
        })

    log(f"Coût total IA pour ce run : {cout_ia_total:.4f}€")

    try:
        from web_dashboard import generer_dashboard
        Path("docs").mkdir(exist_ok=True)
        generer_dashboard(pertinentes, offres_avec_candidatures)
        log("🌐 Dashboard web généré : docs/index.html")
    except ImportError:
        log("⚠️  web_dashboard absent → pas de dashboard")
    except Exception as e:
        log(f"⚠️  Dashboard KO : {e}")

    url_pages = os.environ.get("PAGES_URL", "")

    html = construire_email_html(pertinentes)
    sujet = f"🚛 Radar emploi Thomas — {len(pertinentes)} offre{'s' if len(pertinentes) > 1 else ''} ({datetime.now().strftime('%d/%m')})"

    Path("data").mkdir(exist_ok=True)
    Path("data/digest.html").write_text(html, encoding="utf-8")

    envoyer_email(html, sujet)

    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if chat_id:
        try:
            from telegram_client import telegram_envoyer_digest
            telegram_envoyer_digest(chat_id, offres_avec_candidatures, url_pages)
        except ImportError:
            log("⚠️  telegram_client absent → pas de push Telegram")
        except Exception as e:
            log(f"⚠️  Telegram KO : {e}")
    else:
        log("ℹ️  TELEGRAM_CHAT_ID absent → on saute Telegram")

    nouvelles_cles = deja_vues | {o.cle_dedup() for o in nouvelles}
    sauvegarder_historique(nouvelles_cles)
    log(f"Historique sauvegardé : {len(nouvelles_cles)} offres mémorisées")

    log("════════════════════════════════════════════")
    log("  Terminé ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
