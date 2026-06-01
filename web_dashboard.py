#!/usr/bin/env python3
"""
Génère une page web statique listant toutes les offres pertinentes,
déployée automatiquement sur GitHub Pages.

La page est self-contained (HTML+CSS+JS dans un seul fichier),
mobile-friendly, avec filtres et bouton 'Copier la candidature'.
"""

from __future__ import annotations

import json
import html as html_lib
from datetime import datetime
from pathlib import Path


def generer_dashboard(
    offres,
    offres_avec_candidatures,
    output_path: str = "docs/index.html",
) -> str:
    """Génère la page index.html dans docs/ pour GitHub Pages.

    Args:
        offres: liste complète d'Offre (avec score, distance, tags).
        offres_avec_candidatures: liste de dicts {offre, texte_candidature_html, ...}
            pour les top 5 (les autres n'ont pas de candidature pré-générée).

    Returns:
        Le chemin du fichier généré.
    """
    # Index par cle_dedup pour récupérer les candidatures
    candidatures_par_offre = {}
    for item in offres_avec_candidatures:
        candidatures_par_offre[item["offre"].cle_dedup()] = item["texte_candidature_html"]

    # Données JSON pour le JS de la page
    data_offres = []
    for o in offres:
        data_offres.append({
            "titre": o.titre,
            "entreprise": o.entreprise,
            "ville": o.ville,
            "code_postal": o.code_postal,
            "type_contrat": o.type_contrat,
            "description": (o.description or "")[:600],
            "url": o.url,
            "source": o.source,
            "score": o.score,
            "distance_km": o.distance_km,
            "tags": o.tags,
            "candidature": candidatures_par_offre.get(o.cle_dedup(), ""),
            "date_publication": o.date_publication,
        })

    data_json = json.dumps(data_offres, ensure_ascii=False, indent=2)
    derniere_maj = datetime.now().strftime("%d/%m/%Y à %H:%M")

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#1d3557">
<title>Radar emploi — Thomas</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f6f7fb;
  --card: #fff;
  --primary: #1d3557;
  --accent: #2a9d8f;
  --warn: #e76f51;
  --muted: #6b7280;
  --border: #e5e7eb;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: #222;
  line-height: 1.5;
  padding: 16px;
  max-width: 900px;
  margin: 0 auto;
}}
header {{
  background: var(--primary);
  color: #fff;
  padding: 24px 20px;
  border-radius: 10px;
  margin-bottom: 16px;
}}
header h1 {{ font-size: 22px; margin-bottom: 6px; }}
header p {{ font-size: 13px; opacity: 0.85; }}
.stats {{
  display: flex; gap: 8px; flex-wrap: wrap;
  margin: 16px 0;
}}
.stat {{
  background: var(--card); border-radius: 8px; padding: 10px 14px;
  flex: 1; min-width: 100px; text-align: center;
  border: 1px solid var(--border);
}}
.stat .v {{ font-size: 22px; font-weight: 700; color: var(--primary); }}
.stat .l {{ font-size: 11px; color: var(--muted); text-transform: uppercase; }}
.filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
.filter-btn {{
  background: var(--card); border: 1px solid var(--border);
  padding: 8px 14px; border-radius: 20px; font-size: 13px;
  cursor: pointer; transition: all 0.15s;
}}
.filter-btn.active {{ background: var(--primary); color: #fff; border-color: var(--primary); }}
.offre {{
  background: var(--card); border-radius: 10px; padding: 16px;
  margin-bottom: 12px; border: 1px solid var(--border);
}}
.offre h2 {{ font-size: 16px; color: var(--primary); margin-bottom: 6px; }}
.offre .meta {{ color: var(--muted); font-size: 13px; margin-bottom: 8px; }}
.offre .desc {{ font-size: 13px; color: #444; margin: 8px 0; }}
.tags {{ display: flex; gap: 4px; flex-wrap: wrap; margin: 8px 0; }}
.tag {{
  background: #eef2ff; color: var(--primary); font-size: 11px;
  padding: 2px 8px; border-radius: 4px;
}}
.tag.warn {{ background: #fff3cd; color: #856404; }}
.tag.bonus {{ background: #d4edda; color: #155724; }}
.actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }}
.btn {{
  display: inline-block; padding: 8px 14px; border-radius: 6px;
  text-decoration: none; font-size: 13px; font-weight: 500;
  border: none; cursor: pointer;
}}
.btn-primary {{ background: var(--accent); color: #fff; }}
.btn-secondary {{ background: var(--card); color: var(--primary); border: 1px solid var(--border); }}
.btn-state {{ background: #f1f5f9; color: #475569; }}
.btn-state.active {{ background: var(--accent); color: #fff; }}
.candidature {{
  display: none; margin-top: 12px; padding: 12px;
  background: #f8fafc; border-left: 3px solid var(--accent);
  border-radius: 4px; font-size: 13px; white-space: pre-wrap;
  font-family: ui-monospace, 'Cascadia Code', monospace;
}}
.candidature.visible {{ display: block; }}
.empty {{
  text-align: center; padding: 40px 20px; background: var(--card);
  border-radius: 10px; border: 1px solid var(--border);
}}
.score {{
  display: inline-block; background: var(--primary); color: #fff;
  padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;
}}
.toast {{
  position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  background: #222; color: #fff; padding: 10px 20px; border-radius: 6px;
  font-size: 13px; opacity: 0; transition: opacity 0.2s;
  pointer-events: none;
}}
.toast.show {{ opacity: 1; }}
footer {{
  text-align: center; padding: 20px 0; color: var(--muted);
  font-size: 12px;
}}
</style>
</head>
<body>

<header>
  <h1>🚛 Radar emploi — Thomas</h1>
  <p>Dernière mise à jour : <strong>{derniere_maj}</strong></p>
  <p style="margin-top:6px;">Lorette 42420 + 25 km • Cariste, logistique, agroalimentaire</p>
</header>

<div class="stats">
  <div class="stat"><div class="v" id="stat-total">0</div><div class="l">Offres</div></div>
  <div class="stat"><div class="v" id="stat-cdi">0</div><div class="l">CDI</div></div>
  <div class="stat"><div class="v" id="stat-proche">0</div><div class="l">&lt; 15 km</div></div>
  <div class="stat"><div class="v" id="stat-haute">0</div><div class="l">Score ≥ 8</div></div>
</div>

<div class="filters" id="filters">
  <button class="filter-btn active" data-filter="all">Toutes</button>
  <button class="filter-btn" data-filter="cdi">CDI uniquement</button>
  <button class="filter-btn" data-filter="proche">Moins de 15 km</button>
  <button class="filter-btn" data-filter="non-vues">Non vues</button>
</div>

<div id="offres-container"></div>

<footer>
  Radar emploi v3 · GitHub Actions · {derniere_maj}<br>
  Données : France Travail + Indeed
</footer>

<div class="toast" id="toast"></div>

<script>
const OFFRES = {data_json};
const STORAGE_KEY = 'radar_emploi_etats';

// Charger les états (vu/intéressé/postulé) depuis localStorage
function chargerEtats() {{
  try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}'); }}
  catch (e) {{ return {{}}; }}
}}
function sauverEtats(etats) {{
  localStorage.setItem(STORAGE_KEY, JSON.stringify(etats));
}}
function cleOffre(o) {{
  return (o.titre + '|' + o.entreprise + '|' + o.ville).toLowerCase();
}}

let etats = chargerEtats();
let filtreActif = 'all';

function escapeHtml(s) {{
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}}

function renderOffres() {{
  const container = document.getElementById('offres-container');
  const offresVisibles = OFFRES.filter(o => {{
    const cle = cleOffre(o);
    const etat = etats[cle] || {{}};
    if (filtreActif === 'cdi') return /CDI/i.test(o.type_contrat);
    if (filtreActif === 'proche') return o.distance_km > 0 && o.distance_km < 15;
    if (filtreActif === 'non-vues') return !etat.vu;
    return true;
  }});

  if (offresVisibles.length === 0) {{
    container.innerHTML = '<div class="empty">Aucune offre ne correspond à ce filtre.</div>';
    return;
  }}

  container.innerHTML = offresVisibles.map((o, idx) => {{
    const cle = cleOffre(o);
    const etat = etats[cle] || {{}};
    const distance = o.distance_km > 0 ? ` • ~${{o.distance_km.toFixed(0)}} km` : '';
    const tagsHtml = (o.tags || []).slice(0, 5).map(t => {{
      const cls = t.startsWith('⚠') ? 'tag warn' : (t.startsWith('⭐') ? 'tag bonus' : 'tag');
      return `<span class="${{cls}}">${{escapeHtml(t)}}</span>`;
    }}).join('');

    return `
      <div class="offre" data-cle="${{escapeHtml(cle)}}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
          <h2>${{escapeHtml(o.titre)}}</h2>
          <span class="score">${{o.score}}</span>
        </div>
        <div class="meta">
          <strong>${{escapeHtml(o.entreprise)}}</strong> — ${{escapeHtml(o.ville)}}${{distance}}
          ${{o.type_contrat ? ' • ' + escapeHtml(o.type_contrat) : ''}}
          • ${{escapeHtml(o.source)}}
        </div>
        <div class="tags">${{tagsHtml}}</div>
        <div class="desc">${{escapeHtml(o.description.slice(0, 280))}}${{o.description.length > 280 ? '...' : ''}}</div>
        <div class="actions">
          <a href="${{escapeHtml(o.url)}}" target="_blank" rel="noopener" class="btn btn-primary"
             onclick="marquerVu('${{escapeHtml(cle)}}')">Postuler ↗</a>
          ${{o.candidature ? `
            <button class="btn btn-secondary" onclick="toggleCandidature(${{idx}})">
              📝 Voir candidature
            </button>
            <button class="btn btn-secondary" onclick="copierCandidature(${{idx}})">
              📋 Copier
            </button>
          ` : ''}}
          <button class="btn btn-state ${{etat.interesse ? 'active' : ''}}"
                  onclick="toggleEtat('${{escapeHtml(cle)}}', 'interesse')">⭐ Intéressé</button>
          <button class="btn btn-state ${{etat.postule ? 'active' : ''}}"
                  onclick="toggleEtat('${{escapeHtml(cle)}}', 'postule')">✓ Postulé</button>
        </div>
        ${{o.candidature ? `
          <div class="candidature" id="cand-${{idx}}">${{escapeHtml(o.candidature)}}</div>
        ` : ''}}
      </div>
    `;
  }}).join('');
}}

function marquerVu(cle) {{
  if (!etats[cle]) etats[cle] = {{}};
  etats[cle].vu = true;
  sauverEtats(etats);
}}

function toggleEtat(cle, champ) {{
  if (!etats[cle]) etats[cle] = {{}};
  etats[cle][champ] = !etats[cle][champ];
  sauverEtats(etats);
  renderOffres();
}}

function toggleCandidature(idx) {{
  const el = document.getElementById('cand-' + idx);
  if (el) el.classList.toggle('visible');
}}

function copierCandidature(idx) {{
  const offresVisibles = OFFRES.filter(o => {{
    const etat = etats[cleOffre(o)] || {{}};
    if (filtreActif === 'cdi') return /CDI/i.test(o.type_contrat);
    if (filtreActif === 'proche') return o.distance_km > 0 && o.distance_km < 15;
    if (filtreActif === 'non-vues') return !etat.vu;
    return true;
  }});
  const offre = offresVisibles[idx];
  if (!offre || !offre.candidature) return;
  navigator.clipboard.writeText(offre.candidature).then(() => {{
    showToast('✓ Texte copié — colle-le sur la plateforme !');
  }}).catch(() => {{
    showToast('❌ Impossible de copier');
  }});
}}

function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}}

function updateStats() {{
  document.getElementById('stat-total').textContent = OFFRES.length;
  document.getElementById('stat-cdi').textContent = OFFRES.filter(o => /CDI/i.test(o.type_contrat)).length;
  document.getElementById('stat-proche').textContent = OFFRES.filter(o => o.distance_km > 0 && o.distance_km < 15).length;
  document.getElementById('stat-haute').textContent = OFFRES.filter(o => o.score >= 8).length;
}}

// Setup filtres
document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    filtreActif = btn.dataset.filter;
    renderOffres();
  }});
}});

updateStats();
renderOffres();
</script>

</body>
</html>
"""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_content, encoding="utf-8")
    return str(output)


if __name__ == "__main__":
    # Test rapide avec des données fictives
    from dataclasses import dataclass

    @dataclass
    class FakeOffre:
        titre: str
        entreprise: str
        ville: str
        code_postal: str
        type_contrat: str
        description: str
        url: str
        source: str
        score: int
        distance_km: float
        tags: list
        date_publication: str

        def cle_dedup(self):
            return f"{self.titre.lower()}|{self.entreprise.lower()}|{self.ville.lower()}"

    fakes = [
        FakeOffre(
            titre="Cariste CACES 3 H/F",
            entreprise="ID Logistics",
            ville="Saint-Chamond",
            code_postal="42400",
            type_contrat="CDI",
            description="Conduite chariot CACES 3, chargement camions, préparation commandes.",
            url="https://example.com/1",
            source="francetravail",
            score=12,
            distance_km=8.5,
            tags=["+caces 3", "+cariste", "+cdi", "⭐ id logistics"],
            date_publication="2026-06-01",
        ),
        FakeOffre(
            titre="Préparateur de commandes",
            entreprise="Easydis",
            ville="Andrézieux-Bouthéon",
            code_postal="42160",
            type_contrat="Intérim 6 mois",
            description="Préparation de commandes, picking, filmage palettes.",
            url="https://example.com/2",
            source="indeed",
            score=8,
            distance_km=12.0,
            tags=["+préparateur", "+caces 3"],
            date_publication="2026-06-01",
        ),
    ]

    cands = [
        {"offre": fakes[0], "texte_candidature_html": "Bonjour,\n\nSuite à votre offre de Cariste CACES 3...\n\nCordialement", "score": 12, "distance_km": 8.5},
        {"offre": fakes[1], "texte_candidature_html": "Bonjour,\n\nVotre offre de Préparateur retient mon attention...\n\nCordialement", "score": 8, "distance_km": 12.0},
    ]

    path = generer_dashboard(fakes, cands, "/tmp/test_dashboard.html")
    print(f"✓ Dashboard généré : {path}")
    print(f"  Taille : {Path(path).stat().st_size} octets")
