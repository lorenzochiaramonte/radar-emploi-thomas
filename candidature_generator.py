#!/usr/bin/env python3
"""
Générateur de candidatures — utilise l'API Claude pour produire un texte court
de candidature (80-120 mots) adapté à l'offre, à partir du profil de Thomas.

Sortie : un texte prêt à coller dans un formulaire de plateforme intérim,
ou à utiliser comme corps d'email.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import requests

# ─────────────────────────────────────────────────────────────────────────────
# PROFIL DE THOMAS (extrait du CV, statique)
# ─────────────────────────────────────────────────────────────────────────────

PROFIL_THOMAS = """
Thomas Chiaramonte, cariste CACES 3 et employé logistique basé à Lorette (42420),
disponible immédiatement.

Expérience principale :
- Lustucru Frais (jan-juin 2025) : opérateur de production agroalimentaire,
  conditionnement, mise en barquettes, approvisionnement de ligne, normes hygiène.
- FIT Heyrieux (juil-déc 2024) : cariste intérim, conduite chariot, chargement /
  déchargement camions, déplacement et stockage marchandises.
- Plast Moul Bourgoin-Jallieu (fév-juin 2024) : cariste manutentionnaire,
  réception, déchargement, approvisionnement lignes de fabrication.
- 12 ans (2012-2024) de missions intérim régulières en logistique, manutention,
  préparation de commandes sur Lyon et alentours.

Compétences clés : CACES 3, chargement/déchargement, préparation de commandes,
picking, filmage/cerclage/palettisation, approvisionnement de lignes, contrôle
réception. Rigoureux, autonome, sens de la sécurité.

Certifications : CACES 3, CAP Électricien.
"""

# ─────────────────────────────────────────────────────────────────────────────
# PROMPT
# ─────────────────────────────────────────────────────────────────────────────

PROMPT_SYSTEME = """Tu es un assistant qui rédige des candidatures courtes et naturelles
pour Thomas Chiaramonte, cariste cherchant un poste en logistique ou production
agroalimentaire dans la région stéphanoise.

Règles strictes :
- 80 à 120 mots, jamais plus.
- Ton professionnel mais simple, naturel, pas pompeux. Pas de "Madame, Monsieur"
  en ouverture ni de formules ampoulées.
- Reprendre 2-3 mots-clés exacts de l'annonce pour montrer que la candidature
  n'est pas générique.
- Mentionner explicitement : CACES 3, dispo immédiate, expérience cariste/logistique.
- Si l'offre est en agroalimentaire, mentionner Lustucru.
- Pas de mention de la fracture / arrêt maladie : c'est terminé, dispo immédiate.
- Pas de signature (le nom est ailleurs dans le formulaire).
- Pas de "P.S.", pas d'emoji, pas de markdown.
- Texte continu en 1 ou 2 paragraphes.

Sortie : uniquement le texte de candidature, rien d'autre."""


# ─────────────────────────────────────────────────────────────────────────────
# GÉNÉRATEUR
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TexteCandidature:
    contenu: str
    nb_mots: int
    modele: str
    cout_estime_eur: float


def generer_candidature_ia(
    titre_offre: str,
    entreprise: str,
    description_offre: str,
    api_key: str | None = None,
) -> TexteCandidature:
    """Appelle l'API Anthropic pour générer un texte de candidature.

    Utilise claude-3-5-haiku (rapide, économique : ~0,001€/candidature).
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY absent. Soit on configure le secret, "
            "soit on bascule sur le mode templates statiques."
        )

    user_message = f"""Voici le profil du candidat :

{PROFIL_THOMAS}

Voici l'offre à laquelle il veut postuler :

TITRE : {titre_offre}
ENTREPRISE : {entreprise}
DESCRIPTION : {(description_offre or '')[:1500]}

Rédige le texte de candidature."""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 400,
            "system": PROMPT_SYSTEME,
            "messages": [{"role": "user", "content": user_message}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    texte = data["content"][0]["text"].strip()
    usage = data.get("usage", {})
    # Tarif Haiku : ~0.80$/1M tokens input, 4$/1M output
    cout = (usage.get("input_tokens", 0) * 0.80 + usage.get("output_tokens", 0) * 4.0) / 1_000_000

    return TexteCandidature(
        contenu=texte,
        nb_mots=len(texte.split()),
        modele=data.get("model", "claude-3-5-haiku"),
        cout_estime_eur=cout,
    )


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK — TEMPLATES STATIQUES
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATES = {
    "cariste": """Bonjour,

Suite à votre offre de {poste} chez {entreprise}, je vous propose ma candidature.
Je suis cariste CACES 3 avec plusieurs années d'expérience en environnement
logistique et industriel : conduite de chariot, chargement et déchargement
de camions, préparation de commandes, picking et palettisation. Mes dernières
missions chez FIT (Heyrieux) et Plast Moul (Bourgoin-Jallieu) m'ont permis de
travailler dans le respect strict des consignes de sécurité.

Disponible immédiatement, basé à Lorette, je peux intervenir rapidement sur {ville}.
Mon CV est joint, je reste à votre disposition pour échanger.

Cordialement""",

    "agroalimentaire": """Bonjour,

Votre offre de {poste} chez {entreprise} retient toute mon attention.
J'ai récemment travaillé chez Lustucru Frais comme opérateur de production
agroalimentaire (conditionnement, mise en barquettes, approvisionnement de ligne)
en respectant strictement les normes d'hygiène, de sécurité et de qualité.
Je suis également cariste CACES 3 avec une solide expérience en logistique.

Disponible immédiatement, basé à Lorette, je peux rejoindre rapidement votre
équipe sur {ville}. Mon CV est joint, je reste à votre disposition.

Cordialement""",

    "preparateur": """Bonjour,

Je vous adresse ma candidature pour votre offre de {poste} chez {entreprise}.
Avec plus de 10 ans d'expérience en préparation de commandes, picking,
constitution de palettes, filmage et cerclage, je suis également titulaire
du CACES 3. Mes missions précédentes en intérim et en CDD m'ont habitué aux
environnements logistiques exigeants.

Disponible immédiatement, basé à Lorette à proximité de {ville}, je peux
démarrer rapidement. Vous trouverez mon CV en pièce jointe.

Cordialement""",

    "default": """Bonjour,

Suite à votre offre de {poste} chez {entreprise}, je vous propose ma candidature.
Cariste CACES 3 et employé logistique avec une expérience significative en
environnement industriel et logistique (chargement/déchargement, préparation
de commandes, approvisionnement de lignes), je suis rigoureux, autonome et
attentif aux règles de sécurité.

Disponible immédiatement, basé à Lorette, je peux rejoindre votre équipe
rapidement sur {ville}. Mon CV est joint, je reste à votre disposition.

Cordialement""",
}


def generer_candidature_template(
    titre_offre: str,
    entreprise: str,
    description_offre: str,
    ville: str = "votre site",
) -> TexteCandidature:
    """Fallback sans IA : choisit un template selon les mots-clés."""
    texte_normalise = (titre_offre + " " + description_offre).lower()

    if "agroalimentaire" in texte_normalise or "alimentaire" in texte_normalise or "production" in texte_normalise:
        template_key = "agroalimentaire"
    elif "préparateur" in texte_normalise or "preparateur" in texte_normalise or "picking" in texte_normalise:
        template_key = "preparateur"
    elif "cariste" in texte_normalise or "caces" in texte_normalise:
        template_key = "cariste"
    else:
        template_key = "default"

    contenu = TEMPLATES[template_key].format(
        poste=titre_offre,
        entreprise=entreprise or "votre société",
        ville=ville or "votre site",
    )

    return TexteCandidature(
        contenu=contenu,
        nb_mots=len(contenu.split()),
        modele=f"template:{template_key}",
        cout_estime_eur=0.0,
    )


def generer(
    titre_offre: str,
    entreprise: str,
    description_offre: str,
    ville: str = "",
    mode: str = "auto",
) -> TexteCandidature:
    """Point d'entrée principal.

    mode :
      - "ia"        → uniquement API Claude, échoue si pas de clé
      - "template"  → uniquement templates statiques
      - "auto"      → IA si clé dispo, sinon template (par défaut)
    """
    if mode == "template":
        return generer_candidature_template(titre_offre, entreprise, description_offre, ville)

    if mode == "ia":
        return generer_candidature_ia(titre_offre, entreprise, description_offre)

    # auto
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return generer_candidature_ia(titre_offre, entreprise, description_offre)
        except Exception as e:
            print(f"⚠️  IA KO ({e}), fallback template")
    return generer_candidature_template(titre_offre, entreprise, description_offre, ville)


# ─────────────────────────────────────────────────────────────────────────────
# CLI POUR TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Test avec une offre fictive
    resultat = generer(
        titre_offre="Cariste CACES 3 H/F",
        entreprise="ID Logistics",
        description_offre=(
            "Au sein de notre site de Saint-Chamond, vous assurez la conduite "
            "de chariot CACES 3, le chargement et déchargement de camions, "
            "le rangement des marchandises et la préparation de commandes."
        ),
        ville="Saint-Chamond",
        mode=sys.argv[1] if len(sys.argv) > 1 else "auto",
    )

    print("═" * 60)
    print(f"Modèle : {resultat.modele}")
    print(f"Mots   : {resultat.nb_mots}")
    print(f"Coût   : {resultat.cout_estime_eur:.5f} €")
    print("═" * 60)
    print(resultat.contenu)
    print("═" * 60)
