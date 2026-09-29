import html
import json
import re

import requests
import streamlit as st
from groq import Groq, GroqError

TARIFF_CHECKS = (
    "Unité de tarif",
    "Tarif forfaitaire ou unitaire",
    "Grille tarifaire jointe",
    "Indexation CNR",
    "Part gazole",
    "Part GNR",
    "Massification des volumes",
    "Coût d'ouverture de portes",
    "Traction",
    "Distribution",
    "Transport de bout en bout",
    "Nature alimentaire et température",
    "Consigne de température",
    "Nombre et type de palettes",
    "Dimensions des palettes",
    "Gerbabilité (gerbable / non gerbable)",
    "Poids total brut",
    "Poids moyen par palette",
    "Hauteur des palettes ou du chargement",
    "Lieu de chargement",
    "Lieu de livraison",
    "Fréquence et volume des expéditions",
    "Date de démarrage",
    "Prise de rendez-vous et préavis",
    "Délai d'acheminement garanti",
    "Date limite de remise de l'offre",
)

SOURCE_EVIDENCE_PATTERNS = {
    "Unité de tarif": (r"\b(?:au|par)\s+(?:voyage|tonne|palette|palettes)\b",),
    "Tarif forfaitaire ou unitaire": (
        r"\bforfait(?:aire)?\b",
        r"\bunitaire\b",
        r"\bà\s+l['’]unité\b",
    ),
    "Grille tarifaire jointe": (
        r"\bgrille\s+tarifaire\b",
        r"\bpi[eè]ce\s+jointe\b",
        r"\bPJ\b",
    ),
    "Indexation CNR": (r"\bCNR\b", r"\bindexation\b"),
    "Part gazole": (r"\bpart\s+(?:gazole|gasoil|diesel)\b",),
    "Part GNR": (r"\bpart\s+GNR\b", r"\bgazole\s+non\s+routier\b"),
    "Massification des volumes": (r"\bmassification\b", r"\bmassifi(?:er|cation)\b"),
    "Coût d'ouverture de portes": (
        r"\bouverture\s+de\s+portes?\b",
        r"\bfrais?\s+de\s+portes?\b",
    ),
    "Traction": (r"\btraction\b",),
    "Distribution": (r"\bdistribution\b",),
    "Transport de bout en bout": (
        r"\bbout\s+en\s+bout\b",
        r"\bporte\s+[àa]\s+porte\b",
    ),
    "Nature alimentaire et température": (
        r"\b(?:produits?|marchandises?)\s+(?:alimentaires?|frais|laitiers?)\b",
        r"\btemp[eé]rature\s+dirig[eé]e\b",
    ),
    "Consigne de température": (r"[+-]\s*\d+\s*°?\s*C\b",),
    "Nombre et type de palettes": (r"\b\d+\s*palettes?\b", r"\bpalettes?\s+Europe\b"),
    "Dimensions des palettes": (r"\b\d+\s*[x×]\s*\d+\s*cm\b", r"\b\d+\s*[x×]\s*\d+\b"),
    "Gerbabilité (gerbable / non gerbable)": (
        r"\bnon\s+gerbables?\b",
        r"\bgerbables?\b",
    ),
    "Poids total brut": (
        r"\bpoids\s+total(?:\s+brut)?\s*:?\s*\d+(?:[,.]\d+)?\s*(?:tonnes?|t|kg)\b",
        r"\b\d+(?:[,.]\d+)?\s*(?:tonnes?|t)\b",
    ),
    "Poids moyen par palette": (r"\bpoids\s+moyen\b", r"\bmasse\s+moyenne\b"),
    "Hauteur des palettes ou du chargement": (r"\bhauteur\b", r"\bhaut(?:e|es)?\b"),
    "Lieu de chargement": (
        r"\blieu\s+de\s+chargement\b[^.\n]*",
        r"\bchargement\s+(?:à|a|de|depuis)\s+[^,.\n]+",
        r"\bdépart\s+(?:de|à)\s+[^,.\n]+",
    ),
    "Lieu de livraison": (
        r"\blieu\s+de\s+livraison\b[^.\n]*",
        r"\blivraison\s+(?:à|a|de)\s+[^,.\n]+",
        r"\barrivée\s+(?:à|a)\s+[^,.\n]+",
    ),
    "Fréquence et volume des expéditions": (
        r"\b\d+\s*(?:à|a|-)\s*\d*\s*expéditions?\b[^.\n]*",
        r"\bexpéditions?\s+par\s+(?:jour|semaine|mois)\b[^.\n]*",
        r"\bfréquence\b[^.\n]*",
    ),
    "Date de démarrage": (
        r"\bà\s+partir\s+du\s+[^,.\n]+",
        r"\bdémarrage\b[^.\n]*",
    ),
    "Prise de rendez-vous et préavis": (
        r"\b(?:prise de\s+)?R[.]?D[.]?V[.]?\b[^.\n]*",
        r"\brendez[- ]vous\b[^.\n]*",
        r"\bpréavis\b[^.\n]*",
    ),
    "Délai d'acheminement garanti": (
        r"\bdélai\b[^.\n]*\bachminement\b[^.\n]*",
        r"\bachminement\b[^.\n]*\bgaranti\b[^.\n]*",
        r"\bdélai\s+garanti\b[^.\n]*",
    ),
    "Date limite de remise de l'offre": (
        r"\bavant\s+le\s+[^,.\n]+",
        r"\bdate\s+limite\b[^.\n]*",
    ),
}

CONTROL_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "statut_global": {
            "type": "string",
            "enum": ["INCOMPLET", "COMPLET"],
        },
        "analyse_criteres": {
            "type": "array",
            "minItems": len(TARIFF_CHECKS),
            "maxItems": len(TARIFF_CHECKS),
            "items": {
                "type": "object",
                "properties": {
                    "critere": {
                        "type": "string",
                        "enum": list(TARIFF_CHECKS),
                    },
                    "statut": {
                        "type": "string",
                        "enum": ["PRESENT", "MANQUANT", "NON_APPLICABLE"],
                    },
                    "valeur_trouvee": {"type": "string"},
                    "commentaire": {"type": "string"},
                },
                "required": [
                    "critere",
                    "statut",
                    "valeur_trouvee",
                    "commentaire",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["statut_global", "analyse_criteres"],
    "additionalProperties": False,
}

ANALYSIS_SYSTEM_PROMPT = """
Tu es un expert en tarification et gestion des opérations de transport / ADV logistique.
Analyse la demande du client et évalue chaque critère de la liste fournie exactement une fois.

Pour chaque critère, renseigne son nom exact dans la clé 'critere', un statut `PRESENT`, `MANQUANT` ou `NON_APPLICABLE`, la valeur précise extraite (normalisée si besoin) dans la clé 'valeur_trouvee' (ou `Aucune` si elle manque), et un commentaire court dans la clé 'commentaire'.

La seule source de faits est le texte placé entre les balises `<courrier_client>` et `</courrier_client>`. Si une information n'y figure pas, mets `MANQUANT` et `Aucune`.

Tu dois répondre EXCLUSIVEMENT avec un objet JSON strictement valide au format exact suivant :
{
  "statut_global": "INCOMPLET",
  "analyse_criteres": [
    {
      "critere": "Nom exact du critère",
      "statut": "PRESENT",
      "valeur_trouvee": "Valeur normalisée",
      "commentaire": "Commentaire explicatif"
    }
  ]
}

N'ajoute aucun texte avant ou après le JSON, ni balise Markdown.
""".strip()


def afficher_badge(texte, color_hex="#3b82f6", text_color="#ffffff"):
    """Remplace st.badge de façon sécurisée"""
    st.markdown(
        f'<span style="background-color: {color_hex}; color: {text_color}; '
        f'padding: 4px 10px; border-radius: 12px; font-size: 13px; font-weight: 600;">'
        f'{html.escape(texte)}</span>',
        unsafe_allow_html=True
    )


def parse_analysis_response(content):
    if not isinstance(content, str) or not content.strip():
        raise ValueError("La réponse du modèle est vide.")

    cleaned_content = content.strip()
    
    # Utilisation de re.search pour ignorer le blabla avant ou après le JSON
    fenced_response = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned_content, re.IGNORECASE | re.DOTALL)
    if fenced_response:
        cleaned_content = fenced_response.group(1)
    else:
        # Fallback de sécurité au cas où le LLM omet les balises markdown
        fallback_match = re.search(r"(\{.*\})", cleaned_content, re.DOTALL)
        if fallback_match:
            cleaned_content = fallback_match.group(1)

    analysis = json.loads(cleaned_content)
    
    if not isinstance(analysis, dict) or "analyse_criteres" not in analysis:
        raise ValueError("La réponse JSON doit contenir la clé 'analyse_criteres'.")

    statut_global = analysis.get("statut_global", "INCOMPLET")
    if statut_global not in {"INCOMPLET", "COMPLET"}:
        statut_global = "INCOMPLET"
    analysis["statut_global"] = statut_global

    criteria = analysis["analyse_criteres"]
    if not isinstance(criteria, list):
        raise ValueError("La clé 'analyse_criteres' doit être une liste.")

    expected_criterion_names = list(TARIFF_CHECKS)
    criteria_by_name = {}
    allowed_statuses = {"PRESENT", "MANQUANT", "NON_APPLICABLE"}

    for item in criteria:
        if not isinstance(item, dict):
            continue

        # Mapping tolérant pour les clés JSON
        criterion = item.get("critere") or item.get("nom")
        statut = item.get("statut", "MANQUANT")
        valeur_trouvee = item.get("valeur_trouvee") or item.get("valeur", "Aucune")
        commentaire = item.get("commentaire") or item.get("explication", "")

        if not criterion or criterion not in expected_criterion_names:
            continue

        if statut not in allowed_statuses:
            statut = "MANQUANT"

        if statut == "MANQUANT":
            valeur_trouvee = "Aucune"

        criteria_by_name[criterion] = {
            "critere": criterion,
            "statut": statut,
            "valeur_trouvee": str(valeur_trouvee),
            "commentaire": str(commentaire),
        }

    for criterion in expected_criterion_names:
        if criterion not in criteria_by_name:
            criteria_by_name[criterion] = {
                "critere": criterion,
                "statut": "MANQUANT",
                "valeur_trouvee": "Aucune",
                "commentaire": "Aucune mention correspondante dans le courrier fourni.",
            }

    analysis["analyse_criteres"] = [
        criteria_by_name[criterion] for criterion in expected_criterion_names
    ]
    analysis["statut_global"] = (
        "INCOMPLET"
        if any(item["statut"] == "MANQUANT" for item in analysis["analyse_criteres"])
        else "COMPLET"
    )

    return analysis


def extract_source_evidence(courrier, criterion):
    if criterion == "Nature alimentaire et température":
        food_match = re.search(
            r"\b(?:produits?|marchandises?)\s+(?:alimentaires?|frais|laitiers?)\b",
            courrier,
            re.IGNORECASE,
        )
        temperature_match = re.search(
            r"\btemp[eé]rature\s+dirig[eé]e\b", courrier, re.IGNORECASE
        )
        matches = [match for match in (food_match, temperature_match) if match]
        if len(matches) < 2:
            return None
    else:
        patterns = SOURCE_EVIDENCE_PATTERNS.get(criterion, ())
        matches = [
            match
            for pattern in patterns
            for match in re.finditer(pattern, courrier, re.IGNORECASE)
        ]
        if not matches:
            return None

    snippets = []
    for match in sorted(matches, key=lambda item: item.start()):
        snippet = re.sub(r"\s+", " ", match.group(0)).strip(" ,;:-")
        if snippet and snippet not in snippets:
            snippets.append(snippet)
    return " ; ".join(snippets)


def validate_analysis_against_courrier(analysis, courrier):
    normalized_source = re.sub(r"\s+", " ", courrier).casefold()
    for item in analysis["analyse_criteres"]:
        evidence = extract_source_evidence(courrier, item["critere"])
        reported_value = re.sub(r"\s+", " ", item["valeur_trouvee"]).strip()
        reported_value_is_source_text = (
            reported_value.casefold() in normalized_source
            and reported_value.casefold() not in {"aucune", "aucun", "non précisé"}
        )

        if evidence:
            item["statut"] = "PRESENT"
            # On n'écrase plus la valeur trouvée par le LLM, on ajoute juste une preuve en commentaire.
            if not reported_value_is_source_text:
                item["commentaire"] = f"Valeur reformulée par l'IA. Confirmé en source par : '{evidence}'"
            else:
                item["commentaire"] = "Valeur exacte reprise du courrier fourni."
                
        elif item["statut"] == "NON_APPLICABLE":
            explicit_not_applicable = re.search(
                r"\b(?:sans objet|non applicable|ne concerne pas)\b",
                courrier,
                re.IGNORECASE,
            )
            if explicit_not_applicable and reported_value_is_source_text:
                item["commentaire"] = "Non-applicabilité explicitement indiquée dans le courrier."
            else:
                item["statut"] = "MANQUANT"
                item["valeur_trouvee"] = "Aucune"
                item["commentaire"] = "Aucune mention correspondante dans le courrier fourni."
        elif item["statut"] == "PRESENT":
            # Le LLM a trouvé quelque chose mais la RegEx ne l'a pas confirmé
            item["commentaire"] = "Présence détectée par l'IA (à vérifier manuellement)."

    analysis["statut_global"] = (
        "INCOMPLET"
        if any(item["statut"] == "MANQUANT" for item in analysis["analyse_criteres"])
        else "COMPLET"
    )
    return analysis


def build_analysis_messages(courrier):
    criteria = "\n".join(f"- {criterion}" for criterion in TARIFF_CHECKS)
    normalized_courrier = re.sub(
        r"(?<=[.!?])(?=[A-ZÀ-Þ\[])|(?<=Bonjour,)(?=[A-ZÀ-Þ])",
        "\n",
        courrier.strip(),
    )
    return [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Critères techniques à vérifier :\n"
                f"{criteria}\n\n"
                "Le texte entre les balises suivantes est l'unique source de faits :\n"
                "<courrier_client>\n"
                f"{normalized_courrier}\n"
                "</courrier_client>"
            ),
        },
    ]


def get_ollama_models(ollama_url):
    response = requests.get(f"{ollama_url}/api/tags", timeout=5)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("La réponse d'Ollama doit être un objet JSON.")
    models = data.get("models")
    if not isinstance(models, list):
        raise ValueError("La réponse d'Ollama ne contient pas de liste de modèles.")
    return [
        model["name"]
        for model in models
        if isinstance(model, dict) and isinstance(model.get("name"), str)
    ]


def render_control_table(headers, rows):
    table_headers = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    table_rows = []
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            if index == 0:
                cell_class = "criterion-cell"
            elif index == 1:
                status_class = {
                    "PRESENT": "status-present",
                    "MANQUANT": "status-missing",
                    "NON_APPLICABLE": "status-not-applicable",
                }.get(value, "status-missing")
                cell_class = f"status-cell {status_class}"
            else:
                cell_class = "detail-cell"
            cells.append(f'<td class="{cell_class}">{html.escape(value)}</td>')
        table_rows.append(f"<tr>{''.join(cells)}</tr>")

    return (
        """
        <style>
          .control-table-wrap { overflow-x: auto; margin: 0.5rem 0 1rem; }
          .control-table {
            width: 100%; min-width: 900px; table-layout: fixed;
            border-collapse: separate; border-spacing: 0 7px;
            font-size: 0.88rem; line-height: 1.45;
          }
          .control-table th {
            padding: 10px 12px; background: #394852; color: #f0f4f5;
            text-align: left; font-weight: 700;
          }
          .control-table th:first-child { width: 26%; }
          .control-table th:nth-child(2) { width: 18%; }
          .control-table th:nth-child(3) { width: 28%; }
          .control-table th:last-child { width: 28%; }
          .control-table td {
            padding: 11px 12px; vertical-align: top; overflow-wrap: anywhere;
          }
          .control-table td:first-child { border-radius: 7px 0 0 7px; }
          .control-table td:last-child { border-radius: 0 7px 7px 0; }
          .control-table .criterion-cell {
            background: #2d3942; color: #f0f4f5; font-weight: 650;
          }
          .control-table .detail-cell {
            background: #e8edf0; color: #27323a;
          }
          .control-table .status-cell { font-weight: 700; }
          .control-table .status-present {
            background: #d8f2e3; color: #174b34;
          }
          .control-table .status-missing {
            background: #ffe8c2; color: #704400;
          }
          .control-table .status-not-applicable {
            background: #e3e8eb; color: #46535e;
          }
        </style>
        <div class="control-table-wrap"><table class="control-table">
          <thead><tr>
        """
        + table_headers
        + "</tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table></div>"
    )


st.set_page_config(
    page_title="Assistant ADV — cotation transport",
    page_icon="🚚",
    layout="wide",
)

st.markdown(
    """
    <style>
        [data-testid="stMain"] h1#assistant-adv {
            margin: 0 0 4px;
            padding: 0;
            border: 0;
            border-radius: 0;
            background: linear-gradient(180deg, #ffffff 0%, #a1a1aa 100%);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            box-shadow: none;
            font-size: 2.2rem;
            font-weight: 800;
            transition: none;
        }

        [data-testid="stMain"] h3#reception-d-une-demande-de-cotation-transport {
            margin: 0 0 8px;
            padding: 0;
            border: 0;
            border-radius: 0;
            background: none;
            box-shadow: none;
            color: #d4d4d8;
            font-size: 1.15rem;
            font-weight: 400;
            line-height: 1.35;
            transition: none;
        }

        [data-testid="stMain"] h2,
        [data-testid="stMain"] h3:not(#reception-d-une-demande-de-cotation-transport),
        [data-testid="stMain"] h4 {
            margin: 30px 0 16px;
            padding: 0 0 8px 12px;
            border: 0;
            border-left: 3px solid #3b82f6;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 0;
            background: transparent;
            box-shadow: none;
            color: #f0f4f8;
            transition: border-color 0.3s ease, color 0.3s ease;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("ASSISTANT ADV")
st.subheader("Réception d'une demande de cotation transport")
st.write(
    "Centralise les éléments reçus et prépare leur qualification. Le prototype couvre "
    "la réception ; les étapes suivantes sont visibles mais pas encore activées."
)
afficher_badge("Prototype", "#3b82f6")

st.markdown("#### Parcours de la demande")
st.caption(
    "Le suivi complet est présenté ; seule la réception est traitée dans cette version."
)

workflow_steps = (
    ("01", "Réception des éléments", "EN COURS", "green"),
    ("02", "Analyse juridique", "À VENIR", "red"),
    ("03", "Analyse exploitation", "À VENIR", "red"),
    ("04", "Conception des tarifs", "À VENIR", "red"),
    ("05", "Validation", "À VENIR", "red"),
    ("06", "Envoi", "À VENIR", "red"),
    ("07", "En attente de retour", "À VENIR", "red"),
    ("08", "Confirmé ou refusé", "À VENIR", "red"),
)

workflow_cards = []
for number, title, status, color in workflow_steps:
    state = "active" if color == "green" else "pending"
    workflow_cards.append(
        f'<li class="workflow-step workflow-step--{state}">'
        f'<span class="workflow-step__number">{number}</span>'
        f'<strong class="workflow-step__title">{title}</strong>'
        f'<span class="workflow-step__status"><span class="workflow-step__dot" '
        f'aria-hidden="true"></span>{status}</span></li>'
    )

st.markdown(
    """
    <style>
        .workflow-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin: 0;
            padding: 0;
            list-style: none;
        }
        .workflow-step {
            display: flex;
            min-height: 132px;
            flex-direction: column;
            justify-content: space-between;
            padding: 16px;
            border: 1px solid #46555f;
            border-radius: 8px;
            background: #2d3942;
            box-shadow: 0 2px 5px rgb(0 0 0 / 16%);
        }
        .workflow-step--active {
            border-color: #4b9f89;
            background: #293c3b;
            box-shadow: inset 3px 0 #62d1a2, 0 4px 10px rgb(0 0 0 / 18%);
        }
        .workflow-step__number {
            color: #aebac1;
            font-size: 0.8rem;
            font-weight: 700;
        }
        .workflow-step--active .workflow-step__number,
        .workflow-step--active .workflow-step__status {
            color: #75ddb4;
        }
        .workflow-step--pending .workflow-step__status {
            color: #ff9a9f;
        }
        .workflow-step__title {
            color: #f0f4f5;
            font-size: 1rem;
            line-height: 1.35;
        }
        .workflow-step__status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.75rem;
            font-weight: 700;
        }
        .workflow-step__dot {
            width: 8px;
            height: 8px;
            flex: 0 0 8px;
            border-radius: 50%;
            background: currentColor;
            box-shadow: 0 0 10px currentColor;
        }
    </style>
    <ol class="workflow-grid" aria-label="Étapes du parcours de demande">
    """
    + "".join(workflow_cards)
    + "</ol>",
    unsafe_allow_html=True
)

with st.sidebar:
    st.subheader("Configuration de l'IA")
    ai_provider = st.radio("Fournisseur", ["Ollama (Local)", "Groq (Cloud)"])
    
    selected_model = None
    groq_api_key = None
    ollama_url = None
    
    if ai_provider == "Ollama (Local)":
        ollama_url = (
            st.text_input(
                "Adresse du serveur",
                value="http://localhost:11434",
                help="Adresse de l'API Ollama, sans slash final.",
            )
            .strip()
            .rstrip("/")
        )
        models = []
        ollama_error = None
        if ollama_url:
            try:
                models = get_ollama_models(ollama_url)
            except requests.exceptions.RequestException as exc:
                ollama_error = f"Erreur de connexion : {exc}"
            except ValueError as exc:
                ollama_error = f"Réponse invalide : {exc}"

        if models:
            selected_model = st.selectbox("Modèle installé", options=models)
            afficher_badge("IA locale prête", "#15803d")
        else:
            if ollama_error:
                st.caption(ollama_error)
            afficher_badge("Ollama non détecté", "#c2410c")
            
    elif ai_provider == "Groq (Cloud)":
        if "GROQ_API_KEY" in st.secrets and st.secrets["GROQ_API_KEY"]:
            groq_api_key = str(st.secrets["GROQ_API_KEY"]).strip()
        else:
            groq_api_key = st.text_input("Clé API Groq", type="password").strip()
            
        # Vos modèles spécifiques conservés :
        groq_models = [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b"
        ]
        selected_model = st.selectbox("Modèle Groq", options=groq_models)
        
        if groq_api_key:
            afficher_badge("Clé Groq renseignée", "#15803d")
        else:
            afficher_badge("Clé requise", "#c2410c")


courrier = st.text_area(
    "Courrier du client",
    value="",
    height=220,
    placeholder="Colle ici le courrier reçu du client…",
)

st.subheader("Générer l'analyse")
run_live = st.button(
    "Générer l'analyse",
    type="primary",
    disabled=not selected_model and (ai_provider == "Ollama (Local)"),
)

if run_live:
    if not courrier.strip():
        st.warning("Ajoute le courrier du client avant de lancer l'analyse.")
    else:
        messages = build_analysis_messages(courrier)
        content = None
        
        # ----------------------------------------------------
        # EXÉCUTION OLLAMA
        # ----------------------------------------------------
        if ai_provider == "Ollama (Local)":
            if not ollama_url or not selected_model:
                st.warning("Renseigne l'adresse du serveur Ollama et le nom du modèle.")
                st.stop()
                
            try:
                response = requests.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": selected_model,
                        "messages": messages,
                        "format": CONTROL_RESPONSE_SCHEMA,
                        "stream": False,
                    },
                    timeout=180,
                )
                response.raise_for_status()
                result = response.json()
                content = result.get("message", {}).get("content")
            except Exception as exc:
                st.error(f"Erreur lors de l'appel à Ollama : {exc}")
                
        # ----------------------------------------------------
        # EXÉCUTION GROQ
        # ----------------------------------------------------
        elif ai_provider == "Groq (Cloud)":
            if not groq_api_key:
                st.warning("Renseigne ta clé API Groq dans la barre latérale.")
                st.stop()
                
            try:
                client = Groq(api_key=groq_api_key)
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model=selected_model,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                content = chat_completion.choices[0].message.content
            except GroqError as exc:
                st.error(f"Erreur lors de l'appel à l'API Groq : {exc}")

        # ----------------------------------------------------
        # ANALYSE ET AFFICHAGE
        # ----------------------------------------------------
        if content:
            try:
                analysis = validate_analysis_against_courrier(
                    parse_analysis_response(content), courrier
                )
            except (json.JSONDecodeError, ValueError) as exc:
                st.error(f"Réponse JSON invalide ({ai_provider}) : {exc}")
                st.code(content)
            else:
                criteria = analysis["analyse_criteres"]
                display_rows = [
                    [
                        item["critere"],
                        item["statut"],
                        item["valeur_trouvee"],
                        item["commentaire"],
                    ]
                    for item in criteria
                ]
                dossier_status = analysis["statut_global"]
                st.subheader("Grille de contrôle — synthèse")
                
                if dossier_status == "COMPLET":
                    afficher_badge(f"Dossier {dossier_status}", "#15803d")
                else:
                    afficher_badge(f"Dossier {dossier_status}", "#c2410c")

                st.markdown(
                    render_control_table(
                        ["Critère", "Statut", "Valeur trouvée", "Commentaire"],
                        display_rows,
                    ),
                    unsafe_allow_html=True
                )