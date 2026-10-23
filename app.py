"""
app.py - Streamlit dashboard for the Alzheimer's drug repurposing knowledge base.

Run:
    streamlit run app.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st
from data_loader import load_datasets

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

st.set_page_config(page_title="Alzheimer's drug repurposing KB",
                   page_icon="\U0001f9ea", layout="wide")

# Muted and well separated in lightness as well as hue, so the charts still read
# when printed in black and white.
SCI_SEQ = ["#1f4e79", "#8a6d1f", "#2f6b3f", "#8f1d1d", "#4a5a6b",
           "#5d3a5a", "#2a6b6b", "#7a4a2a", "#555555"]
SCI_SCALE = ["#d6e0ea", "#aec2d4", "#7f9db9", "#4f769b", "#1f4e79"]
# single-series bars: one colour, because the length is already the encoding
BAR_FILL = "#4f769b"
# direction is semantic, never decorative
DIR_COLOR = {"helps": "#2f6b3f", "harms": "#8f1d1d", "no_effect": "#9a9a9a"}
px.defaults.template = "simple_white"
px.defaults.color_discrete_sequence = SCI_SEQ

st.markdown("""
<style>
  :root{ --line:#d4d4d4; --txt:#1a1a1a; --mut:#666666; --accent:#1f4e79; }
  .stApp{ background:#ffffff; }
  html,body,[class*="css"],.stMarkdown,button,input,textarea,select{
      font-family:Georgia,"Times New Roman",serif; color:var(--txt); }
  h1{ font-size:26px; font-weight:700; color:var(--accent); border-bottom:2px solid var(--accent);
      padding-bottom:6px; margin-bottom:14px; }
  h2{ font-size:19px; font-weight:700; color:var(--txt); margin-top:22px;
      border-left:4px solid var(--accent); padding-left:9px; }
  h3{ font-size:16px; font-weight:700; color:var(--txt); }
  [data-testid="stSidebar"]{ background:#f2f5f8; border-right:2px solid var(--accent); }
  [data-testid="stMetric"]{ border:1px solid var(--line); border-left:4px solid var(--accent);
      padding:10px 12px; background:#ffffff; }
  [data-testid="stMetricValue"]{ font-size:22px; font-weight:700; color:var(--txt) !important; }
  [data-testid="stMetricLabel"] *{ color:var(--mut) !important; font-size:12px;
      font-variant:small-caps; letter-spacing:.3px; }
  a,a:visited{ color:var(--accent) !important; }
  div.stButton>button,.stDownloadButton>button{ background:#ffffff; color:var(--txt);
      border:1px solid #999999; font-weight:normal; }
  div.stButton>button:hover,.stDownloadButton>button:hover{ background:#eeeeee;
      color:var(--txt); border-color:#666666; }
  [data-testid="stExpander"]{ border:1px solid var(--line); background:#ffffff; }
  blockquote{ border-left:3px solid #9bb2c6; padding:2px 0 2px 12px; color:#333333;
      font-size:14px; margin:8px 0; background:#fafcfd; }
  table{ font-size:13px; }
  hr{ border-color:var(--line); }
  *, *::before, *::after{ border-radius:0 !important; box-shadow:none !important; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ data loading
@st.cache_data(ttl=3600, show_spinner=False)
def app_data(sources: dict):
    return load_datasets(DATA, sources=sources)


try:
    with st.spinner("Loading knowledge-base data…"):
        sources = json.loads((HERE / "data_sources.json").read_text(encoding="utf-8"))
        datasets = app_data(sources)
except Exception as exc:
    st.title("Alzheimer's drug repurposing knowledge base")
    st.error("The app could not load its data. The Google Drive folder and its four "
             "JSON files must allow 'Anyone with the link' to view and download. "
             "Please try again if Drive is temporarily unavailable.")
    with st.expander("Data loading details"):
        st.write(str(exc))
    if st.button("Retry loading data"):
        app_data.clear()
        st.rerun()
    st.stop()

KB = datasets["06_knowledge_base.json"]
CLAIMS = datasets["04_claims_with_drugs.json"]
CHECKED = datasets["03_claims_checked.json"]
ENRICHED = datasets["05_claims_enriched.json"]

if not KB:
    st.title("Alzheimer's drug repurposing knowledge base")
    st.warning("App data is not configured yet. Connect the external JSON files "
               "or place the four required files in the data folder.")
    st.stop()

CANDIDATES = [d for d in KB if not d["is_alzheimers_drug"]]
CONTROLS = [d for d in KB if d["is_alzheimers_drug"]]


# ------------------------------------------------------------------ helpers
def hbar(counts: Counter, title: str, n: int = 20, unit: str = ""):
    """One series, one colour.

    An earlier version coloured each bar by its own value. That encodes the same number
    twice, and the tooltip said so out loud: "count=375 ... color=375". The bar length
    is the encoding; the colour was decoration.
    """
    if not counts:
        st.caption("-")
        return
    top = counts.most_common(n)
    vals = [v for _, v in top]
    fig = px.bar(x=vals, y=[k for k, _ in top], orientation="h",
                 labels={"x": unit or "count", "y": ""}, title=title)
    fig.update_traces(marker_color=BAR_FILL,
                      hovertemplate="%{y}<br>%{x:,} " + (unit or "claims") + "<extra></extra>")
    fig.update_layout(yaxis={"categoryorder": "total ascending"},
                      height=max(300, 24 * len(top)), margin=dict(l=10, r=10, t=40, b=10),
                      plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
    if len(counts) > n:
        st.caption(f"Showing top {n} of {len(counts)} values.")


def diverging_bar(rows, label_key: str, title: str, n: int = 15):
    """Helps and harms side by side for the same item, ranked by total evidence.

    A single net bar would be wrong here: a drug with 20 helps and 18 harms would show as
    a small positive, which is the opposite of the truth. Both directions get their own
    bar, so a contested item is visibly contested.
    """
    if not rows:
        st.caption("-")
        return
    top = sorted(rows, key=lambda r: -(r["helps"] + r["harms"]))[:n]
    labels = [r[label_key] for r in top]
    df = pd.DataFrame(
        [{"item": r[label_key], "direction": "helps", "papers": r["helps"]} for r in top]
        + [{"item": r[label_key], "direction": "harms", "papers": r["harms"]} for r in top])
    fig = px.bar(df, x="papers", y="item", color="direction", orientation="h",
                 title=title, barmode="group", color_discrete_map=DIR_COLOR,
                 labels={"papers": "papers", "item": ""})
    fig.update_layout(height=max(340, 30 * len(top)),
                      yaxis={"categoryorder": "array", "categoryarray": labels[::-1]},
                      margin=dict(l=10, r=10, t=44, b=10),
                      legend=dict(orientation="h", y=1.04, x=1, xanchor="right", title=""),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)


def drug_rows_for_chart(drugs):
    return [{"drug": d["drug_name"], "helps": d["n_papers_helps"],
             "harms": d["n_papers_harms"]} for d in drugs
            if d["n_papers_helps"] or d["n_papers_harms"]]


def category_rows_for_chart(drugs):
    """Sum per-entry paper counts; papers are not deduplicated across entries."""
    agg: Dict[str, Dict[str, int]] = {}
    for d in drugs:
        cat = d["normally_licensed_for"]
        if not cat:
            continue
        a = agg.setdefault(cat, {"category": cat, "helps": 0, "harms": 0, "drugs": 0})
        a["helps"] += d["n_papers_helps"]
        a["harms"] += d["n_papers_harms"]
        a["drugs"] += 1
    return list(agg.values())


def drugs_by_category(drugs):
    """Drugs grouped under their PRIMARY category, strongest evidence first.

    Grouped on the primary pick only, not on every indication, so each drug appears once
    and the category totals in the chart match what is listed here. A drug's other
    indications are shown in its row instead.
    """
    out: Dict[str, list] = {}
    for d in drugs:
        cat = d["normally_licensed_for"]
        if cat:
            out.setdefault(cat, []).append(d)
    for v in out.values():
        v.sort(key=lambda d: -max(d["helps_score"], d["harms_score"]))
    return out


# Study types, strongest evidence first rather than alphabetically, with labels a reader
# can parse at a glance. Alphabetical order put "animal" above "clinical_trial", which is
# the wrong way round for a list people scan to find the best evidence.
EVIDENCE_ORDER = ["clinical_trial", "meta_analysis", "patient_cohort", "case_control",
                  "animal", "cells", "computer_prediction", "review", "other"]
EVIDENCE_RANK = {e: i for i, e in enumerate(EVIDENCE_ORDER)}
EVIDENCE_LABEL = {
    "clinical_trial": "Clinical trial", "meta_analysis": "Meta-analysis",
    "patient_cohort": "Patient cohort", "case_control": "Case-control",
    "animal": "Animal study", "cells": "Cell study",
    "computer_prediction": "Computer prediction", "review": "Review", "other": "Other",
}


@st.cache_data(show_spinner=False)
def _therapeutic_categories() -> set:
    """The curated therapeutic categories included in this standalone app.

    Without this the filter offered all 828 raw DrugBank categories, including chemistry
    ("2-Pyridinylmethylsulfinylbenzimidazoles") and combination labels ("ACE Inhibitors and
    Diuretics"). Unusable as a dropdown, and none of them is an indication.
    """
    try:
        from categories import THERAPEUTIC_CATEGORIES
        return {category.lower() for category in THERAPEUTIC_CATEGORIES}
    except Exception:
        return set()


def indication_options(drugs) -> list:
    """Therapeutic classes present in this view, commonest first.

    Commonest first, because a filter list is scanned, not read: the categories with the
    most drugs behind them are the ones worth offering at the top.
    """
    good = _therapeutic_categories()
    counts: Dict[str, int] = {}
    for d in drugs:
        seen = {d["normally_licensed_for"], *(d.get("all_indications") or [])}
        for x in seen:
            if x and (not good or x.lower() in good):
                counts[x] = counts.get(x, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def verdict_badge(v: str) -> str:
    if v.startswith("helps"):
        bg, fg = "#e4ede6", "#1a5c2e"
    elif v.startswith("HARMS"):
        bg, fg = "#f2e4e4", "#8f1d1d"
    elif v == "CONTRADICTED":
        bg, fg = "#f3ecda", "#7a5200"
    else:
        bg, fg = "#ececec", "#444444"
    return (f"<span style='background:{bg};color:{fg};padding:3px 10px;border-radius:0;"
            f"font-size:12px;font-weight:600'>{v}</span>")


def chips(items: List[str], bg="#e8eef4", fg="#1f4e79") -> str:
    return " ".join(
        f"<span style='background:{bg};color:{fg};padding:2px 9px;border-radius:0;"
        f"font-size:12px;margin-right:4px'>{i}</span>" for i in items if i)


# Three kinds of thing live in this knowledge base and they are not interchangeable.
# The identifier prefix is enough to tell them apart, so no dictionary load is needed.
#   compound     a single molecular entity          DB00331, CHEBI:6801
#   class        a pharmacological class            MESH:D000477
#   as reported  the literature's own term, matched to nothing
# A class is NOT a repurposing candidate: nobody prescribes "anticholinergics".
TYPE_COMPOUND, TYPE_CLASS, TYPE_REPORTED = "compound", "class", "unresolved name"
ENTITY_TYPES = [TYPE_COMPOUND, TYPE_CLASS, TYPE_REPORTED]


def entity_type(d: Dict[str, Any]) -> str:
    i = d.get("drug_id") or ""
    if not i:
        return TYPE_REPORTED
    return TYPE_CLASS if i.upper().startswith("MESH:") else TYPE_COMPOUND


def kb_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame([{
        "drug": d["drug_name"],
        "type": entity_type(d),
        "therapeutic category": d["normally_licensed_for"] or "",
        "class-level entry": d["drug_name"] if entity_type(d) == TYPE_CLASS else "",
        "database categories": "; ".join(d.get("all_indications") or []),
        "verdict": d["verdict"],
        "helps:harms": d["helps_harms_ratio"],
        "papers": d["n_papers"],
        "helps": d["n_papers_helps"],
        "harms": d["n_papers_harms"],
        "score": max(d["helps_score"], d["harms_score"]),
        "study type": d["best_evidence"],
        "effect size": (d["fulltext_details"] or {}).get("effect_size", ""),
        "dose achievable": (d["fulltext_details"] or {}).get("dose_achievable", ""),
        "brain penetrant": (d["fulltext_details"] or {}).get("brain_penetrant", ""),
        "drug id": d["drug_id"],
    } for d in rows])


# ------------------------------------------------------------------ sidebar
st.sidebar.markdown("### Alzheimer's repurposing KB")
st.sidebar.caption(
    f"{len(KB):,} drugs · {len(CLAIMS):,} verified claims · "
    f"{len({c['pmid'] for c in CLAIMS}):,} papers")
page = st.sidebar.radio(
    "Page",
    ["Overview", "Key findings", "Drugs", "Therapeutic categories",
     "Drug card", "Verification"])
HELPS_ONLY = st.sidebar.toggle(
    "Helps only", value=False,
    help="Show only drugs with at least one 'helps' paper and no 'harms' papers. "
         "The data always contains both directions; this only changes the view.")
if HELPS_ONLY:
    st.sidebar.caption("Direction filter: **helps only**")


def visible_drugs() -> List[Dict[str, Any]]:
    rows = CANDIDATES
    if HELPS_ONLY:
        rows = [d for d in rows if d["n_papers_helps"] > 0 and d["n_papers_harms"] == 0]
    return rows


# ------------------------------------------------------------------ pages
def page_overview():
    st.title("Alzheimer's disease drug repurposing knowledge base")
    st.caption("Literature-derived drug–outcome associations in Alzheimer's disease "
               "and related conditions, with source-linked evidence sentences.")

    n_helps = sum(1 for c in CLAIMS if c["direction"] == "helps")
    n_harms = sum(1 for c in CLAIMS if c["direction"] == "harms")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Non-reference entries", f"{len(CANDIDATES):,}")
    c2.metric("Retained claims", f"{len(CLAIMS):,}")
    c3.metric("Publications with retained claims", f"{len({c['pmid'] for c in CLAIMS}):,}")
    c4.metric("Favourable / adverse claims", f"{n_helps:,} / {n_harms:,}")
    st.caption("Entries include compounds, class-level terms and unresolved names. "
               "Claim and publication totals include reference treatments. "
               "Directions describe extracted findings, not established clinical efficacy.")

    st.subheader("Evidence characteristics")
    st.caption("Retained claims by reported direction, factors affected and assigned "
               "study type, alongside distinct publications per year.")
    cc1, cc2 = st.columns(2)
    with cc1:
        direction_labels = {"helps": "Favourable", "harms": "Adverse", "no_effect": "No effect"}
        dirc = Counter(direction_labels.get(c["direction"], c["direction"]) for c in CLAIMS)
        fig = px.pie(values=list(dirc.values()), names=list(dirc),
                     title="Reported direction of claims", hole=.55,
                     color=list(dirc), color_discrete_map={
                         direction_labels.get(k, k): v for k, v in DIR_COLOR.items()})
        fig.update_layout(margin=dict(l=10, r=10, t=40, b=10),
                          paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        hbar(Counter(c["effect_category"].replace("_", " ").capitalize()
                     for c in CLAIMS if c["effect_category"]),
             "Factors affected", 10, unit="claims")

    cc3, cc4 = st.columns(2)
    with cc3:
        hbar(Counter(EVIDENCE_LABEL.get(c["study_type"], c["study_type"] or "Unspecified")
                     for c in CLAIMS), "Study types", 10, unit="claims")
    with cc4:
        publication_years = {c["pmid"]: str(c["year"]) for c in CLAIMS
                             if str(c.get("year") or "").isdigit()}
        yc = Counter(publication_years.values())
        if yc:
            ser = {y: yc[y] for y in sorted(yc)}
            vals = list(ser.values())
            fig = px.bar(x=list(ser), y=vals, labels={"x": "Publication year", "y": "Publications"},
                         title="Publications per year")
            fig.update_traces(marker_color=BAR_FILL,
                              hovertemplate="%{x}<br>%{y:,} publications<extra></extra>")
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)",
                              margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Entries ranked by directional publication counts")
    st.caption("Publications reporting favourable (helps) or adverse (harms) findings "
               "for each entry. Ranking uses the sum of the two counts. A publication "
               "can contribute to both directions and to multiple entries; counts do "
               "not represent effect sizes or study quality. The sidebar direction "
               "filter applies to this chart.")
    n_drugs = st.slider("Number of entries displayed", 5, 40, 15, key="n_drugs")
    diverging_bar(drug_rows_for_chart(visible_drugs()), "drug",
                  "Publications by entry and reported direction", n_drugs)

    if ENRICHED:
        st.subheader("Full-text evidence enrichment")
        have = [r for r in ENRICHED if r.get("details")]
        g1, g2, g3 = st.columns(3)
        g1.metric("Publication–drug records processed", f"{len(ENRICHED):,}")
        g2.metric("Records with retained details", f"{len(have):,}")
        g3.metric("Distinct publications processed", f"{len({r['pmid'] for r in ENRICHED}):,}")
        fields = ["effect_size", "sample_size", "duration", "comparator",
                  "dose_achievable", "brain_penetrant"]
        filled = Counter()
        for r in ENRICHED:
            for f in fields:
                if (r.get("details") or {}).get(f) not in (None, "", "not_discussed"):
                    filled[f.replace("_", " ").capitalize()] += 1
        hbar(filled, "Availability of retained full-text fields", 8, unit="publication–drug records")
        st.caption("Field counts indicate records with retained values. Missing values "
                   "may reflect unavailable full text, unreported information or "
                   "exclusion during verification. Extracted values and supporting "
                   "sentences are available on the Drug card page.")

    if CONTROLS:
        st.subheader("Reference treatments")
        st.markdown(
            "Treatments designated as Alzheimer's reference entries in the knowledge "
            "base are excluded from the repurposing candidate set.")
        st.markdown(chips([d["drug_name"] for d in CONTROLS], "#e4ede6", "#1a5c2e"),
                    unsafe_allow_html=True)

    with st.expander("Data provenance and methodological scope"):
        st.markdown("""
Built from PubMed abstracts and available open-access full text. Retained claims include
a source sentence checked for textual correspondence and drug identification.
Exclusions are documented on the Verification page.

These checks do not validate claim interpretation or study quality. Evidence varies
across designs, populations and outcomes; inaccessible text and figure-only results may
be omitted. Counts describe the corpus,
not pooled effects, causality or treatment recommendations.
        """)


def page_drugs():
    st.title("Drugs")
    rows = visible_drugs()
    st.caption(f"{len(rows):,} entries"
               + (" with helps and no harms" if HELPS_ONLY else ""))

    # Type first, because a class and a compound are different kinds of thing and mixing
    # them silently is what made the old table confusing.
    pick_type = st.radio(
        "Entry type", ["All"] + ENTITY_TYPES, horizontal=True,
        help="compound: a single molecule, resolved to DrugBank or ChEBI. "
             "class: a pharmacological class from MeSH, because the paper studied the "
             "class rather than a molecule. A class is not a prescribable candidate. "
             "unresolved name: the literature's own term, matched to no vocabulary.")

    typed_rows = [d for d in rows if pick_type == "All" or entity_type(d) == pick_type]

    f1, f2 = st.columns([3, 2])
    with f1:
        pick_ind = st.multiselect(
            "Therapeutic category", indication_options(typed_rows),
            help="What the drug is normally prescribed for. Only real therapeutic classes "
                 "are offered. DrugBank also tags drugs with chemistry ('Alkanes', "
                 "'4-Quinolones'), which are not useful filters, so they are left out. "
                 "A drug matches if ANY of its indications matches.")
    with f2:
        q = st.text_input("Drug name contains", "",
                          help="Free text, case insensitive. Searches the display name and "
                               "every spelling the papers used.")

    sel = [d for d in typed_rows
           if not pick_ind or d["normally_licensed_for"] in pick_ind
           or set(d.get("all_indications") or []) & set(pick_ind)]
    pick_entries = st.multiselect(
        "Specific compounds or class-level entries",
        sorted(d["drug_name"] for d in sel),
        help="Select individual entries within the chosen type and therapeutic categories. "
             "Selecting a class shows its class-level evidence; it does not select all "
             "member compounds. Compound-to-class membership is not stored in this KB.")
    if pick_entries:
        sel = [d for d in sel if d["drug_name"] in pick_entries]
    if q.strip():
        ql = q.strip().lower()
        sel = [d for d in sel
               if ql in (d["drug_name"] or "").lower()
               or any(ql in n.lower() for n in d.get("names_used_in_papers") or [])]
    # Ordered by STUDY TYPE first, then by weight of evidence within it. Study type is not
    # offered as a filter: hiding the weaker tiers invites reading a cell-culture result as
    # though nothing weaker existed, whereas ordering shows the whole range and puts the
    # trials where the eye lands first.
    sel.sort(key=lambda d: (EVIDENCE_RANK.get(d["best_evidence"], 99),
                            -max(d["helps_score"], d["harms_score"])))

    mix = Counter(entity_type(d) for d in sel)
    st.caption(f"{len(sel):,} entries match  ·  "
               + "  ·  ".join(f"{mix.get(k, 0):,} {k}" for k in ENTITY_TYPES))
    df = kb_dataframe(sel)
    st.dataframe(df, hide_index=True, use_container_width=True, height=560)
    st.caption("Ordered by study type, strongest first, then by weight of evidence. "
               "`score` is how well EVIDENCED a claim is (clinical trial 1.0, cohort 0.7, "
               "animal 0.4, cells 0.2, computer prediction 0.1, counted once per paper). "
               "It is not a probability the drug works. See SCORING.md.")


def page_drug_card():
    st.title("Drug card")
    rows = sorted(visible_drugs(), key=lambda d: -max(d["helps_score"], d["harms_score"]))
    if not rows:
        st.info("No drugs match the current filter.")
        return
    # The type is in the label because a class and a compound look identical otherwise,
    # and selecting "Cholinergic Antagonists" expecting a molecule is a real trap.
    names = [f"{d['drug_name']}  ({entity_type(d)}, {d['n_papers']} papers)"
             if entity_type(d) != TYPE_COMPOUND
             else f"{d['drug_name']}  ({d['n_papers']} papers)"
             for d in rows]
    idx = st.selectbox("Drug", range(len(rows)), format_func=lambda i: names[i])
    d = rows[idx]

    st.markdown(f"## {d['drug_name']}  {verdict_badge(d['verdict'])}",
                unsafe_allow_html=True)
    meta = [entity_type(d)]
    if d["normally_licensed_for"]:
        meta.append(f"normally licensed for **{d['normally_licensed_for']}**")
    if d["drug_id"]:
        meta.append(f"`{d['drug_id']}`")
    if d["drug_groups"]:
        meta.append(d["drug_groups"].replace("|", ", "))
    st.caption(" · ".join(meta) if meta else "not resolved to a drug database")

    if entity_type(d) == TYPE_CLASS:
        st.caption("This is a pharmacological class, not a single drug. The papers below "
                   "studied the class as a whole, so these counts describe the group and "
                   "cannot be attributed to any one member compound.")
    elif entity_type(d) == TYPE_REPORTED:
        st.caption("This term matched no entry in DrugBank, MeSH or ChEBI, so it is kept "
                   "exactly as the papers wrote it and nothing is asserted about its "
                   "identity.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Papers", d["n_papers"])
    c2.metric("Helps : harms", d["helps_harms_ratio"])
    c3.metric("Best evidence", d["best_evidence"] or "-")

    if d.get("all_indications"):
        st.markdown("**All indications:** "
                    + chips(d["all_indications"], "#e8eef4", "#1f4e79"),
                    unsafe_allow_html=True)
    if d["names_used_in_papers"]:
        st.markdown("**Written in papers as:** "
                    + chips(d["names_used_in_papers"]), unsafe_allow_html=True)

    ft = d["fulltext_details"] or {}
    if ft:
        st.subheader("From the full text")
        cols = st.columns(3)
        for i, (key, label) in enumerate([
                ("effect_size", "Effect size"), ("sample_size", "Sample size"),
                ("duration", "Duration"), ("comparator", "Comparator"),
                ("dose_achievable", "Dose achievable"),
                ("brain_penetrant", "Brain penetrant")]):
            if ft.get(key) in (None, "", "not_discussed"):
                continue
            with cols[i % 3]:
                st.markdown(f"**{label}:** {ft[key]}")
                q = ft.get(key + "_quote")
                if q:
                    st.markdown(f"<blockquote>{q}</blockquote>", unsafe_allow_html=True)
                    st.caption(f"PMID {ft.get(key + '_pmid', '')}")

    st.subheader(f"All {len(d['claims'])} claims, strongest evidence first")
    for c in d["claims"]:
        colour = DIR_COLOR.get(c["direction"], "#94a3b8")
        st.markdown(
            f"<span style='color:{colour};font-weight:700'>{c['direction']}</span> "
            f"· {c['effect_on']} "
            f"<span style='color:#64748b'>({c['effect_category']} · {c['study_type']} "
            f"· {c['year']})</span>", unsafe_allow_html=True)
        st.markdown(f"<blockquote>{c['evidence_sentence']}</blockquote>",
                    unsafe_allow_html=True)
        st.caption(f"`{c['claim_id']}` · written as \"{c['drug_as_written']}\" "
                   f"· [PMID {c['pmid']}]({c['url']})")
        st.divider()






def page_verification():
    st.title("Verification")
    st.markdown(
        "A **deterministic verification gate** applies rule-based checks to each extracted "
        "claim: the supporting sentence must match the source abstract and identify "
        "the associated drug. Claims that fail are excluded, with reasons recorded "
        "below. These checks use no model-based judgement and establish textual "
        "support, not clinical validity.")

    kept = sum(len(r["claims"]) for r in CHECKED)
    deleted = [d for r in CHECKED for d in r.get("deleted", [])]
    total = kept + len(deleted)
    reasons = Counter(d.get("deleted_because", "?") for d in deleted)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Claims extracted", f"{total:,}")
    c2.metric("Kept", f"{kept:,}", f"{100*kept/max(total,1):.0f}%")
    c3.metric("Deleted", f"{len(deleted):,}", f"-{100*len(deleted)/max(total,1):.0f}%",
              delta_color="inverse")
    c4.metric("Fabricated quotes",
              f"{100*reasons.get('NOT_IN_ABSTRACT',0)/max(total,1):.1f}%")

    LABEL = {
        "NOT_IN_ABSTRACT": "Invented or paraphrased: the sentence is not in the paper",
        "QUOTE_OMITS_DRUG": "Real sentence, but it does not name this drug",
        "VAGUE_DRUG": "Not a real drug name ('several compounds')",
        "too_short": "A fragment, not a sentence",
        "quoted_the_title": "Quoted the title instead of the abstract",
    }
    hbar(Counter({LABEL.get(k, k): v for k, v in reasons.items()}),
         "Why claims were deleted", 8)

    dropped = Counter(d["reason"] for r in ENRICHED for d in (r.get("dropped_fields") or []))
    if dropped:
        st.subheader("And in the full text")
        st.caption("The same check runs on every fact read out of the full text, FIELD BY "
                   "FIELD, so a fabricated dose does not discard a good effect size.")
        LAB2 = {"QUOTE_OMITS_DRUG": "Quote names a different drug",
                "NOT_IN_ABSTRACT": "Quote not in the passages sent",
                "too_short": "Too short to be a sentence", "empty": "No quote given"}
        hbar(Counter({LAB2.get(k, k): v for k, v in dropped.items()}),
             "Full-text fields rejected", 8)
        st.caption("`Quote names a different drug` is the commonest, and it is the failure "
                   "this check exists for: a Methods paragraph describes several compounds "
                   "in adjacent sentences, so a dose belonging to another drug reads "
                   "perfectly plausibly.")

    st.subheader("Read the deleted claims")
    st.caption("These are the claims the pipeline threw away. Judge the checks yourself.")
    pick = st.selectbox("Reason", ["all"] + [k for k, _ in reasons.most_common()])
    pool = [d for d in deleted if pick == "all" or d.get("deleted_because") == pick]
    for d in pool[:40]:
        st.markdown(f"**{d.get('drug','')}** "
                    f"<span style='color:#8f1d1d;font-size:12px'>"
                    f"{d.get('deleted_because','')}</span>", unsafe_allow_html=True)
        st.caption(LABEL.get(d.get("deleted_because", ""), ""))
        st.markdown(f"<blockquote>{d.get('evidence_sentence','')}</blockquote>",
                    unsafe_allow_html=True)
        st.divider()
    if len(pool) > 40:
        st.caption(f"Showing 40 of {len(pool):,}.")



def page_categories():
    st.title("Therapeutic categories")
    st.caption("What the drugs are normally prescribed for. This is the repurposing view: "
               "which corners of the pharmacopoeia the Alzheimer's literature keeps "
               "returning to.")

    # Class-level entries are optional; papers may overlap across entries either way.
    inc_classes = st.toggle(
        "Include pharmacological classes", value=False,
        help="Off: excludes class-level entries such as Benzodiazepines. "
             "On: adds those entries alongside individual drugs. Category bars sum "
             "paper counts across entries, so a paper linked to several entries can "
             "be counted several times, with either setting.")
    pool = visible_drugs()
    if not inc_classes:
        pool = [d for d in pool if entity_type(d) != TYPE_CLASS]
    n_cls = sum(1 for d in visible_drugs() if entity_type(d) == TYPE_CLASS)
    st.caption(f"{len(pool):,} entries in view"
               + (f"  ·  {n_cls} classes included" if inc_classes
                  else f"  ·  {n_cls} classes excluded"))

    st.subheader("Top categories")
    st.caption("Sum of paper counts across entries in each category, split by direction. "
               "These are not unique-paper totals: one paper may contribute to several "
               "entries, even when pharmacological classes are excluded.")
    n_cats = st.slider("How many categories", 5, 30, 12, key="n_cats")
    diverging_bar(category_rows_for_chart(pool), "category",
                  "Top categories: papers saying helps vs harms", n_cats)

    st.markdown("**Which drugs are in each category**")
    st.caption("A category total is only meaningful if you can see what is inside it. "
               "Open one to read the drugs, and whether each one points the same way as "
               "its category or against it.")
    cr = sorted(category_rows_for_chart(pool),
                key=lambda r: -(r["helps"] + r["harms"]))
    by_cat = drugs_by_category(pool)
    for r in cr[:n_cats]:
        members = by_cat.get(r["category"], [])
        head = (f"{r['category']}  ·  {r['drugs']} drugs  ·  "
                f"{r['helps']} helps / {r['harms']} harms")
        with st.expander(head):
            st.dataframe(
                pd.DataFrame([{
                    "drug": d["drug_name"],
                    "verdict": d["verdict"],
                    "helps:harms": d["helps_harms_ratio"],
                    "papers": d["n_papers"],
                    "score": round(max(d["helps_score"], d["harms_score"]), 2),
                    "study type": d["best_evidence"],
                    "also listed under": "; ".join(
                        [c for c in (d.get("all_indications") or [])
                         if c != r["category"]][:3]),
                } for d in members]),
                hide_index=True, use_container_width=True,
                height=min(420, 38 + 35 * max(len(members), 1)))
            # a category whose own members disagree is worth seeing as such
            against = [d["drug_name"] for d in members
                       if (r["helps"] > r["harms"] and d["n_papers_harms"] > d["n_papers_helps"])
                       or (r["harms"] > r["helps"] and d["n_papers_helps"] > d["n_papers_harms"])]
            if against:
                st.caption("Points against its own category: " + ", ".join(against[:10]))

    with st.expander("All categories as a plain table"):
        st.dataframe(pd.DataFrame([{"category": r["category"], "drugs": r["drugs"],
                                    "papers helps": r["helps"], "papers harms": r["harms"],
                                    "example drugs": ", ".join(
                                        d["drug_name"] for d in by_cat.get(r["category"], [])[:5])}
                                   for r in cr]),
                     hide_index=True, use_container_width=True)




# ------------------------------------------------------- the findings worth showing first
# Only the SELECTION and the argument are written here. Every number, quote, PMID and
# ratio is looked up live from the knowledge base when the page renders.
FINDINGS = [
    {"title": "Vaccination and dementia risk",
     "short": "Vaccines",
     "claim": "Cohort studies report associations between herpes zoster, Tdap and "
              "influenza vaccination and lower dementia risk, although vaccination "
              "was not explicitly targeted in the search queries.",
     "entities": ["Herpes Zoster Vaccine",
                  "Diphtheria-Tetanus-acellular Pertussis Vaccines",
                  "Influenza Vaccines", "Antiviral Agents"],
     "direction": "helps"},

    {"title": "Metformin: helpful:harmful ratio 74:8",
     "short": "Metformin",
     "claim": "Metformin has the highest evidence score in the knowledge base, "
              "with both favourable and adverse findings reported.",
     "why": "Both favourable and adverse findings are retained. Their relative "
            "frequency is reported as the helps:harms ratio.",
     "entities": ["Metformin"], "direction": "both"},

    {"title": "Anticholinergics: predominantly harmful findings (1:44)",
     "short": "Anticholinergics",
     "claim": "The strongest harm signal in the resource, and the most actionable.",
     "why": "The search strategy included adverse outcomes to capture evidence "
            "relevant to drug safety.",
     "entities": ["Cholinergic Antagonists"], "direction": "harms"},

    {"title": "Glucose-lowering drugs converge across five mechanisms",
     "short": "Glucose-lowering drugs",
     "claim": "GLP-1 agonists, SGLT2 inhibitors and DPP-4 inhibitors all point the same "
              "way, at the compound level and at the class level.",
     "why": "Coherence across separate mechanisms in one therapeutic area is hard to see "
            "reading papers one at a time, and easy to see once they are aggregated.",
     "entities": ["Liraglutide", "Semaglutide",
                  "Glucagon-Like Peptide-1 Receptor Agonists",
                  "Sodium-Glucose Transporter 2 Inhibitors",
                  "Dipeptidyl-Peptidase IV Inhibitors"],
     "direction": "helps",
     "caveat": "Several of these trials measured biomarkers or predicted risk scores "
               "rather than diagnosed dementia."},

    {"title": "Every licensed Alzheimer's drug was recovered, unprompted",
     "short": "Positive control",
     "claim": "All nine drugs licensed for Alzheimer's appear, and none was named in any "
              "query.",
     "why": "This is the positive control. It is not a finding about drugs, it is the "
            "finding that makes the other nine credible. If the pipeline could not find "
            "donepezil, nothing else in this list would be worth reading.",
     "entities": None, "direction": "controls",
     "caveat": "A coverage check, not a recall estimate. It shows the method finds known "
               "answers; it does not measure how many unknown ones it missed."},

    {"title": "Lithium, with long-term trial follow-up",
     "short": "Lithium",
     "claim": "Among the best evidenced candidates, carried by randomised data rather "
              "than observational signal alone.",
     "why": "Lithium is cheap, long off patent, and has decades of safety data, which "
            "makes the evidence weight behind it unusually actionable.",
     "entities": ["Lithium citrate"], "direction": "helps",
     "caveat": "This entry is the citrate salt. Other lithium salts are separate rows, so "
               "the total lithium literature is larger than this one row shows."},

    {"title": "Minocycline, the cleanest ratio at scale",
     "short": "Minocycline",
     "claim": "An antibiotic with trial-grade evidence and almost no dissent.",
     "why": "Few entities in the resource combine this many papers with this little "
            "disagreement.",
     "entities": ["Minocycline"], "direction": "helps",
     "caveat": "Several of the trials target neuroinflammation markers rather than "
               "cognition itself."},

    {"title": "Sirolimus, where the dissent carries a mechanism",
     "short": "Sirolimus",
     "claim": "Strongly favourable overall, with a specific mechanistic argument against "
              "it preserved alongside.",
     "why": "This is what a reviewer of a candidate actually needs, and precisely what a "
            "benefit-only resource destroys.",
     "entities": ["Sirolimus"], "direction": "both",
     "caveat": "Much of the favourable evidence comes from animal models."},

    {"title": "Statins, a contradiction that resolves",
     "short": "Statins",
     "claim": "Reported in both directions, but lopsidedly enough to be called a minority "
              "dissent rather than a genuine split.",
     "why": "The 4:1 rule exists for exactly this case. Calling this contradicted would "
            "misrepresent the literature; hiding the four papers would misrepresent it "
            "in the other direction.",
     "entities": ["Hydroxymethylglutaryl-CoA Reductase Inhibitors"], "direction": "both",
     "caveat": "A class entry. Individual statins differ in brain penetration."},

    {"title": "Drug classes with predominantly adverse findings",
     "short": "Adverse associations",
     "claim": "Benzodiazepines, antipsychotics, opioids and proton pump inhibitors "
              "have more adverse than favourable findings in the retrieved literature.",
     "entities": ["Benzodiazepines", "Antipsychotic Agents", "Analgesics, Opioid",
                  "Proton Pump Inhibitors"],
     "direction": "harms",
     "caveat": "Confounding by indication is severe here: the conditions these drugs "
               "treat are themselves associated with dementia risk."},
]

BY_NAME = {d["drug_name"]: d for d in KB}


def best_claim(d: Dict[str, Any], direction: str):
    """The claim from the strongest study, so no quote is picked for its wording."""
    cs = [c for c in d.get("claims") or [] if c["direction"] == direction]
    if not cs:
        return None
    return max(cs, key=lambda c: (-EVIDENCE_RANK.get(c["study_type"], 99),
                                  len(c["evidence_sentence"] or "")))


def render_evidence(d: Dict[str, Any], direction: str):
    c = best_claim(d, direction)
    if not c:
        return
    label = EVIDENCE_LABEL.get(c["study_type"], c["study_type"] or "unclassified")
    st.markdown("> " + (c["evidence_sentence"] or ""))
    st.caption(f"{label}, {c['year']} - [PMID {c['pmid']}]({c['url']})")


def render_entity(d: Dict[str, Any], direction: str):
    st.markdown(f"**{d['drug_name']}** &nbsp;·&nbsp; {entity_type(d)} &nbsp;·&nbsp; "
                f"{d['n_papers']} papers &nbsp;·&nbsp; helps:harms "
                f"**{d['helps_harms_ratio']}** &nbsp;·&nbsp; {verdict_badge(d['verdict'])}",
                unsafe_allow_html=True)
    if direction in ("helps", "both"):
        render_evidence(d, "helps")
    if direction in ("harms", "both"):
        if direction == "both":
            st.caption("and the dissent, kept rather than discarded:")
        render_evidence(d, "harms")


def page_findings():
    st.title("Key findings")

    sel = st.session_state.get("finding_open")

    # ---------------------------------------------------------------- the tile grid
    if sel is None:
        # Injected only while the grid is on screen. Nothing else here is a button, so
        # the tile styling cannot leak onto the Back button or any other control.
        st.markdown("""
<style>
  div.stButton{ display:flex; justify-content:center; }
  div.stButton > button{
      width:100%; max-width:250px; aspect-ratio:1 / 1;
      white-space:normal; line-height:1.35;
      color:#ffffff !important; border:none !important;
      font-size:1.02rem; font-weight:700; text-transform:uppercase; letter-spacing:1px;
      box-shadow:0 8px 16px rgba(0,0,0,.30) !important;
      transition:transform .2s, box-shadow .2s; }
  div.stButton > button:hover{
      transform:translateY(-10px); color:#ffffff !important;
      box-shadow:0 18px 36px rgba(0,0,0,.50) !important; }
  div.stButton > button:focus:not(:active){ color:#ffffff !important; }
  /* a shade per column, so the grid reads as columns rather than noise */
  [data-testid="stColumn"]:nth-child(3n+1) div.stButton > button,
  [data-testid="column"]:nth-child(3n+1) div.stButton > button{ background:#003366 !important; }
  [data-testid="stColumn"]:nth-child(3n+2) div.stButton > button,
  [data-testid="column"]:nth-child(3n+2) div.stButton > button{ background:#002855 !important; }
  [data-testid="stColumn"]:nth-child(3n+3) div.stButton > button,
  [data-testid="column"]:nth-child(3n+3) div.stButton > button{ background:#001f40 !important; }
  /* the positive control is a different kind of claim, so it is a wide bar, not a tile */
  .st-key-tile_control div.stButton > button,
  .st-key-tile_control button{
      max-width:none; aspect-ratio:auto; height:104px;
      background:#1f4e79 !important; }
</style>
""", unsafe_allow_html=True)

        grid = [(i, f) for i, f in enumerate(FINDINGS) if f["direction"] != "controls"]
        control = [(i, f) for i, f in enumerate(FINDINGS) if f["direction"] == "controls"]

        PER_ROW = 3
        for row_start in range(0, len(grid), PER_ROW):
            cols = st.columns(PER_ROW)
            for j, (i, f) in enumerate(grid[row_start:row_start + PER_ROW]):
                with cols[j]:
                    if st.button(f.get("short") or f["title"], key=f"tile_{i}",
                                 use_container_width=True):
                        st.session_state["finding_open"] = i
                        st.rerun()

        for i, f in control:
            with st.container(key="tile_control"):
                if st.button(f.get("short") or f["title"], key=f"tile_{i}",
                             use_container_width=True):
                    st.session_state["finding_open"] = i
                    st.rerun()

        st.caption("The paper total counts unique publications within each entry. helps:harms counts "
                   "publications reporting each direction; the same paper can appear in "
                   "both, so these counts need not add up to the paper total. "
                   "Title ratios combine the topic's main entries, counting each "
                   "publication once per direction. The Statins title reports the class-level ratio.")
        return

    # ---------------------------------------------------------------- one finding
    f = FINDINGS[sel]
    if st.button("Back to all findings", key="findings_back"):
        st.session_state["finding_open"] = None
        st.rerun()

    topic_entries = (CONTROLS if f["direction"] == "controls" else
                     [BY_NAME[name] for name in f["entities"] if name in BY_NAME])
    topic_claims = [c for d in topic_entries for c in d.get("claims", [])]
    helpful_papers = {c["pmid"] for c in topic_claims if c["direction"] == "helps"}
    harmful_papers = {c["pmid"] for c in topic_claims if c["direction"] == "harms"}
    st.subheader(f"{f.get('short') or f['title']} · helps:harms "
                 f"**{len(helpful_papers)}:{len(harmful_papers)}**")
    st.markdown(f"**{f['claim']}**")
    if f.get("why"):
        st.write(f["why"])

    if f["direction"] == "controls":
        st.markdown("**The nine, with the direction the literature gives each:**")
        for d in sorted(CONTROLS, key=lambda y: -y["n_papers"]):
            st.markdown(f"- {d['drug_name']} &nbsp;·&nbsp; {d['n_papers']} papers "
                        f"&nbsp;·&nbsp; {d['helps_harms_ratio']}")
    else:
        for name in f["entities"] or []:
            d = BY_NAME.get(name)
            if not d:
                st.caption(f"({name} is not in the current build of the data)")
                continue
            st.divider()
            render_entity(d, f["direction"])

    if f.get("short") == "Statins":
        st.divider()
        st.subheader("Individual statins")
        statins = [BY_NAME[name] for name in (
            "Simvastatin", "Atorvastatin", "Rosuvastatin",
            "Pravastatin", "Pitavastatin", "Lovastatin",
        ) if name in BY_NAME]
        st.caption("Compound-level entries, shown separately from the class above. "
                   "Counts are distinct papers within each entry; entries may share "
                   "papers and should not be added together. A paper can report both "
                   "helps and harms.")
        st.dataframe(pd.DataFrame([
            {"Statin": d["drug_name"], "Papers": d["n_papers"],
             "helps:harms": d["helps_harms_ratio"]}
            for d in statins
        ]), hide_index=True, use_container_width=True)
        for d in statins:
            with st.expander(f"{d['drug_name']}: supporting evidence"):
                render_entity(d, "both")



PAGES = {
    "Overview": page_overview, "Key findings": page_findings,
    "Drugs": page_drugs,
    "Therapeutic categories": page_categories,
    "Drug card": page_drug_card, "Verification": page_verification,
}
PAGES[page]()
