import json
import pathlib
from datetime import date

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Jugendheim-Platzvermittlung",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Dark Mode deaktivieren - Settings-Button ausblenden */
    button[title="Settings"] {display: none !important;}
    button[kind="header"] {display: none !important;}
    /* Footer ausblenden */
    footer {visibility: hidden;}
    
    /* Kachel-Stil */
    div.stColumn > div {
        padding: 0.25rem;
    }
    .card {
        background: var(--secondary-background-color, #f0f2f6);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
        border: 1px solid rgba(128,128,128,0.15);
        transition: box-shadow 0.2s;
    }
    .card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.10);
    }
    .card h4 {
        margin: 0 0 0.4rem 0;
    }
    .card p {
        margin: 0.4rem 0;
        font-size: 0.92rem;
        line-height: 1.5;
    }
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.82rem;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 4px;
    }
    .badge-green  { background: #c8e6c9; color: #2e7d32; }
    .badge-red    { background: #ffcdd2; color: #c62828; }
    .badge-blue   { background: #bbdefb; color: #1565c0; }
    .metric-row {
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
        margin-bottom: 1rem;
    }
    .detail-section {
        background: var(--secondary-background-color, #f0f2f6);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .detail-section p {
        margin: 0.5rem 0;
        line-height: 1.6;
    }
    .detail-section h4 {
        margin-top: 0;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Daten laden
# ---------------------------------------------------------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    data_path = pathlib.Path(__file__).parent / "data" / "demo_data.json"
    with open(data_path, encoding="utf-8") as f:
        records = json.load(f)
    df = pd.DataFrame(records)
    df["verfuegbar_ab"] = pd.to_datetime(df["verfuegbar_ab"]).dt.date
    return df


df_all = load_data()

# ---------------------------------------------------------------------------
# Session-State initialisieren
# ---------------------------------------------------------------------------
if "selected_id" not in st.session_state:
    st.session_state.selected_id = None
if "page" not in st.session_state:
    st.session_state.page = "uebersicht"


def go_to_detail(heim_id: int):
    st.session_state.selected_id = heim_id
    st.session_state.page = "detail"


def go_to_overview():
    st.session_state.selected_id = None
    st.session_state.page = "uebersicht"


# ---------------------------------------------------------------------------
# Sidebar – Filter
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://placehold.co/280x80/2196F3/white?text=Jugendheim+Vermittlung",
        use_container_width=True,
    )
    st.markdown("## Filter")

    # Bundesland
    bundeslaender = sorted(df_all["bundesland"].unique())
    sel_bundesland = st.multiselect(
        "Bundesland", bundeslaender, default=[], key="filter_bundesland"
    )

    # Betreuungsart
    betreuungsarten = sorted(df_all["betreuungsart"].unique())
    sel_betreuungsart = st.multiselect(
        "Betreuungsart", betreuungsarten, default=[], key="filter_betreuungsart"
    )

    # Altersgruppe
    alter_range = st.slider(
        "Altersgruppe",
        min_value=int(df_all["alter_min"].min()),
        max_value=int(df_all["alter_max"].max()),
        value=(int(df_all["alter_min"].min()), int(df_all["alter_max"].max())),
        key="filter_alter",
    )

    # Zimmergroesse
    min_zimmer = st.slider(
        "Mindest-Zimmergröße (m²)",
        min_value=int(df_all["zimmergroesse_qm"].min()),
        max_value=int(df_all["zimmergroesse_qm"].max()),
        value=int(df_all["zimmergroesse_qm"].min()),
        key="filter_zimmer",
    )

    # Verfuegbarkeit (Dauer)
    min_monate = st.slider(
        "Mindest-Verfügbarkeit (Monate)",
        min_value=1,
        max_value=int(df_all["verfuegbar_monate"].max()),
        value=1,
        key="filter_monate",
    )

    # Nur freie Plaetze
    nur_frei = st.checkbox("Nur mit freien Plätzen", value=True, key="filter_frei")

    st.markdown("---")
    if st.button("🔄 Filter zurücksetzen"):
        for k in [
            "filter_bundesland",
            "filter_betreuungsart",
            "filter_alter",
            "filter_zimmer",
            "filter_monate",
            "filter_frei",
        ]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

# ---------------------------------------------------------------------------
# Daten filtern
# ---------------------------------------------------------------------------
df = df_all.copy()

if sel_bundesland:
    df = df[df["bundesland"].isin(sel_bundesland)]

if sel_betreuungsart:
    df = df[df["betreuungsart"].isin(sel_betreuungsart)]

# Altersgruppen-Filter: mindestens Überlappung mit gewähltem Bereich
df = df[(df["alter_max"] >= alter_range[0]) & (df["alter_min"] <= alter_range[1])]

df = df[df["zimmergroesse_qm"] >= min_zimmer]
df = df[df["verfuegbar_monate"] >= min_monate]

if nur_frei:
    df = df[df["freie_plaetze"] > 0]

# ---------------------------------------------------------------------------
# Seiten-Routing
# ---------------------------------------------------------------------------
if st.session_state.page == "detail" and st.session_state.selected_id is not None:
    # -----------------------------------------------------------------------
    # DETAILSEITE
    # -----------------------------------------------------------------------
    heim = df_all[df_all["id"] == st.session_state.selected_id]
    if heim.empty:
        st.warning("Eintrag nicht gefunden.")
        go_to_overview()
        st.rerun()
    else:
        heim = heim.iloc[0]

        st.button("← Zurück zur Übersicht", on_click=go_to_overview)

        st.title(heim["name"])
        st.caption(f'{heim["stadt"]} · {heim["bundesland"]}')

        # Zwei Spalten: Bild + Infos
        col_img, col_info = st.columns([1, 2])

        with col_img:
            st.image(heim["bild_url"], use_container_width=True)
            # Mini-Karte
            m = folium.Map(
                location=[heim["latitude"], heim["longitude"]],
                zoom_start=13,
                width=350,
                height=250,
            )
            folium.Marker(
                [heim["latitude"], heim["longitude"]],
                tooltip=heim["name"],
                icon=folium.Icon(color="blue", icon="home", prefix="fa"),
            ).add_to(m)
            st_folium(m, width=350, height=250, key="detail_map")

        with col_info:
            st.markdown(
                f"""
                <div class="detail-section">
                <h4>Informationen</h4>
                <p><strong>Adresse:</strong> {heim['adresse']}</p>
                <p><strong>Betreuungsart:</strong> {heim['betreuungsart']}</p>
                <p><strong>Freie Plätze:</strong> {heim['freie_plaetze']}</p>
                <p><strong>Zimmergröße:</strong> {heim['zimmergroesse_qm']} m²</p>
                <p><strong>Altersgruppe:</strong> {heim['alter_min']}–{heim['alter_max']} Jahre</p>
                <p><strong>Verfügbar ab:</strong> {heim['verfuegbar_ab']}</p>
                <p><strong>Verfügbarkeit:</strong> {heim['verfuegbar_monate']} Monate</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
                <div class="detail-section">
                <h4>Beschreibung</h4>
                <p>{heim['beschreibung']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
                <div class="detail-section">
                <h4>Kontakt</h4>
                <p>📧 <a href="mailto:{heim['kontakt_email']}">{heim['kontakt_email']}</a></p>
                <p>📞 {heim['kontakt_telefon']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # -------------------------------------------------------------------
        # Kontaktformular
        # -------------------------------------------------------------------
        st.markdown("---")
        st.subheader("Anfrage senden")

        with st.form(key="contact_form"):
            c1, c2 = st.columns(2)
            with c1:
                contact_name = st.text_input("Ihr Name *")
                contact_email = st.text_input("Ihre E-Mail-Adresse *")
            with c2:
                contact_alter = st.number_input(
                    "Alter des Jugendlichen",
                    min_value=6,
                    max_value=25,
                    value=14,
                )
                contact_telefon = st.text_input("Ihre Telefonnummer (optional)")

            contact_nachricht = st.text_area(
                "Ihre Nachricht *",
                placeholder="Beschreiben Sie kurz Ihr Anliegen …",
                height=120,
            )

            submitted = st.form_submit_button("📨 Anfrage absenden")

            if submitted:
                if not contact_name or not contact_email or not contact_nachricht:
                    st.error("Bitte füllen Sie alle Pflichtfelder (*) aus.")
                else:
                    st.success(
                        f"Vielen Dank, {contact_name}! Ihre Anfrage an "
                        f"**{heim['name']}** wurde erfolgreich gesendet. "
                        f"Sie erhalten eine Bestätigung an {contact_email}."
                    )

else:
    # -----------------------------------------------------------------------
    # ÜBERSICHTSSEITE
    # -----------------------------------------------------------------------
    st.title("🏠 Jugendheim-Platzvermittlung")
    st.markdown(
        "Finden Sie den passenden Platz für Jugendliche in Einrichtungen der "
        "Kinder- und Jugendhilfe in ganz Deutschland."
    )

    # Metriken
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Einrichtungen", len(df))
    m2.metric("Freie Plätze gesamt", int(df["freie_plaetze"].sum()))
    m3.metric("Städte", df["stadt"].nunique())
    m4.metric("Bundesländer", df["bundesland"].nunique())

    if df.empty:
        st.info(
            "Keine Einrichtungen gefunden. Bitte passen Sie die Filter an."
        )
    else:
        # Tabs: Kacheln + Karte
        tab_cards, tab_map, tab_table = st.tabs(
            ["📋 Kachelansicht", "🗺️ Kartenansicht", "📊 Tabellenansicht"]
        )

        # -------------------------------------------------------------------
        # Tab 1: Kachelansicht
        # -------------------------------------------------------------------
        with tab_cards:
            # Jeweils 3 Kacheln pro Zeile
            rows = [df.iloc[i : i + 3] for i in range(0, len(df), 3)]
            for row_chunk in rows:
                cols = st.columns(3)
                for idx, (_, heim) in enumerate(row_chunk.iterrows()):
                    with cols[idx]:
                        frei_badge = (
                            '<span class="badge badge-green">Plätze frei</span>'
                            if heim["freie_plaetze"] > 0
                            else '<span class="badge badge-red">Belegt</span>'
                        )
                        art_badge = (
                            f'<span class="badge badge-blue">'
                            f'{heim["betreuungsart"]}</span>'
                        )

                        st.markdown(
                            f"""
                            <div class="card">
                                <h4>{heim['name']}</h4>
                                <p>📍 {heim['stadt']}</p>
                                <p>{heim['bundesland']}</p>
                                <p>{frei_badge} {art_badge}</p>
                                <p>🛏️ {heim['freie_plaetze']} freie Plätze</p>
                                <p>📐 {heim['zimmergroesse_qm']} m²</p>
                                <p>👤 {heim['alter_min']}–{heim['alter_max']} Jahre</p>
                                <p>📅 ab {heim['verfuegbar_ab']}</p>
                                <p>⏱️ {heim['verfuegbar_monate']} Monate</p>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        st.button(
                            "Details anzeigen",
                            key=f"btn_{heim['id']}",
                            on_click=go_to_detail,
                            args=(heim["id"],),
                            use_container_width=True,
                        )

        # -------------------------------------------------------------------
        # Tab 2: Kartenansicht
        # -------------------------------------------------------------------
        with tab_map:
            center_lat = df["latitude"].mean()
            center_lon = df["longitude"].mean()
            m = folium.Map(location=[center_lat, center_lon], zoom_start=6)

            for _, heim in df.iterrows():
                color = "green" if heim["freie_plaetze"] > 0 else "red"
                popup_html = (
                    f"<b>{heim['name']}</b><br>"
                    f"{heim['stadt']}<br>"
                    f"Freie Plätze: {heim['freie_plaetze']}<br>"
                    f"Zimmergröße: {heim['zimmergroesse_qm']} m²<br>"
                    f"{heim['betreuungsart']}"
                )
                folium.Marker(
                    location=[heim["latitude"], heim["longitude"]],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=heim["name"],
                    icon=folium.Icon(color=color, icon="home", prefix="fa"),
                ).add_to(m)

            st_folium(m, width=None, height=550, key="overview_map")

        # -------------------------------------------------------------------
        # Tab 3: Tabellenansicht
        # -------------------------------------------------------------------
        with tab_table:
            display_df = df[
                [
                    "name",
                    "stadt",
                    "bundesland",
                    "betreuungsart",
                    "freie_plaetze",
                    "zimmergroesse_qm",
                    "alter_min",
                    "alter_max",
                    "verfuegbar_ab",
                    "verfuegbar_monate",
                ]
            ].rename(
                columns={
                    "name": "Name",
                    "stadt": "Stadt",
                    "bundesland": "Bundesland",
                    "betreuungsart": "Betreuungsart",
                    "freie_plaetze": "Freie Plätze",
                    "zimmergroesse_qm": "Zimmer (m²)",
                    "alter_min": "Alter min",
                    "alter_max": "Alter max",
                    "verfuegbar_ab": "Verfügbar ab",
                    "verfuegbar_monate": "Dauer (Mon.)",
                }
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Footer
    st.markdown("---")
    st.markdown(
        "<center style='color:grey;font-size:0.85rem;'>"
        "Jugendheim-Platzvermittlung · Demo-Version · "
        f"Datenstand: {date.today().strftime('%d.%m.%Y')}"
        "</center>",
        unsafe_allow_html=True,
    )
