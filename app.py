import json
import math
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
# Custom CSS – nur noch für Detail-Abschnitte, kein HTML in Kacheln mehr
# ---------------------------------------------------------------------------
st.markdown("""<style>
button[title="Settings"] {display: none !important;}
button[kind="header"] {display: none !important;}
footer {visibility: hidden;}
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
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def haversine_distance(lat1, lon1, lat2, lon2):
    """Berechnet die Entfernung zwischen zwei Koordinaten in Kilometern."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def render_card(heim):
    """Rendert eine Kachel mit nativen Streamlit-Komponenten."""
    with st.container(border=True):
        st.subheader(heim["name"], divider="blue")

        # Ort
        st.markdown(f"📍 **{heim['stadt']}**, {heim['bundesland']}")
        if "distance_km" in heim and pd.notna(heim.get("distance_km")):
            st.caption(f"🧭 {heim['distance_km']:.1f} km entfernt")

        st.divider()

        # Status
        if heim["freie_plaetze"] > 0:
            st.markdown(f"✅ **{heim['freie_plaetze']} freie Plätze**")
        else:
            st.markdown("❌ **Belegt**")
        st.markdown(f"🏷️ {heim['betreuungsart']}")
        if heim.get("inobhutnahme_geeignet"):
            st.markdown("🚨 Inobhutnahme geeignet")

        st.divider()

        # Details
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"👤 **{heim['alter_min']}–{heim['alter_max']}** Jahre")
        with c2:
            st.markdown(f"📅 ab **{heim['verfuegbar_ab']}**")
            st.markdown(f"⏱️ **{heim['verfuegbar_monate']}** Monate")

        st.divider()

        st.button(
            "Details anzeigen",
            key=f"btn_{heim['id']}",
            on_click=go_to_detail,
            args=(heim["id"],),
            use_container_width=True,
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
    for col in ("hilfeform", "aufnahmeart", "schulform_unterstuetzung"):
        df[col] = df[col].apply(lambda x: x if isinstance(x, list) else [])
    return df


df_all = load_data()

# ---------------------------------------------------------------------------
# Session-State
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

    # =================================================================
    # SCHNELLFILTER (Verfügbarkeit, Umkreis, Alter, Inobhutnahme)
    # =================================================================
    st.header("Schnellfilter")

    # 1 – Verfügbarkeit
    st.caption("Verfügbarkeit")
    nur_frei_jetzt = st.checkbox("Freie Plätze jetzt", value=True, key="f_frei")
    verfuegbar_ab_filter = st.date_input(
        "Frei ab Datum", value=None, min_value=date.today(), key="f_ab",
    )
    min_monate = st.slider(
        "Reservierbar wie lange (Monate)", 1,
        int(df_all["verfuegbar_monate"].max()), 1, key="f_mon",
    )

    st.divider()

    # 2 – Ort und Erreichbarkeit
    st.caption("Ort und Erreichbarkeit")
    umkreis_aktiv = st.checkbox("Umkreis-Suche", key="f_umkr")
    if umkreis_aktiv:
        umkreis_km = st.slider("Umkreis (km)", 5, 500, 100, key="f_umkr_km")
        user_lat = st.number_input("Latitude", value=51.1657, format="%.4f", key="u_lat")
        user_lon = st.number_input("Longitude", value=10.4515, format="%.4f", key="u_lon")
    bundeslaender = sorted(df_all["bundesland"].unique())
    sel_bundesland = st.multiselect("Bundesland", bundeslaender, key="f_bl")
    if sel_bundesland:
        lk_opts = sorted(
            df_all[df_all["bundesland"].isin(sel_bundesland)]["landkreis"].dropna().unique()
        )
    else:
        lk_opts = sorted(df_all["landkreis"].dropna().unique())
    sel_landkreis = st.multiselect("Landkreis", lk_opts, key="f_lk")

    st.divider()

    # 3 – Altersbereich
    st.caption("Altersbereich")
    alter_range = st.slider(
        "Alter (min – max)",
        int(df_all["alter_min"].min()),
        int(df_all["alter_max"].max()),
        (int(df_all["alter_min"].min()), int(df_all["alter_max"].max())),
        key="f_alter",
    )

    st.divider()

    # 4 – Aufnahmeart (Inobhutnahme = prominenter Schnellfilter)
    st.caption("Aufnahmeart")
    inobhutnahme = st.checkbox("Inobhutnahme geeignet", key="f_inob")
    krisenplatz = st.checkbox("Krisenplatz / Notaufnahme 24h", key="f_krise")
    sel_aufnahmeart = st.multiselect(
        "Aufnahmedauer",
        ["kurzfristig", "mittel", "langfristig"],
        key="f_aufn",
    )

    st.divider()

    # =================================================================
    # ERWEITERTE FILTER
    # =================================================================
    with st.expander("Erweiterte Filter"):

        # 5 – Hilfeform und Setting
        st.caption("Hilfeform und Setting")
        sel_hilfeform = st.multiselect(
            "Hilfeform",
            ["stationär", "betreute Wohngruppe", "intensivpädagogisch", "betreutes Wohnen"],
            key="f_hilfe",
        )
        einzelplatz = st.checkbox("Einzelplatz möglich", key="f_einzel")
        kleingruppe = st.checkbox("Kleingruppe", key="f_klein")

        st.divider()

        # 6 – Geschlecht (optional)
        st.caption("Geschlecht (optional)")
        sel_geschlecht = st.multiselect(
            "Geschlecht",
            ["Mädchen", "Jungen", "offen", "divers"],
            key="f_geschl",
        )

        st.divider()

        # 7 – Ausschluss und Mindestkriterien
        st.caption("Ausschluss und Mindestkriterien")
        keine_gewalt = st.checkbox("Keine Gewaltproblematik", key="f_kgew")
        keine_sucht = st.checkbox("Keine Suchtthematik", key="f_ksuc")
        schulbesuch = st.checkbox("Schulbesuch möglich", key="f_schul")
        schulformen = sorted(set(
            s for sub in df_all["schulform_unterstuetzung"] for s in sub
        ))
        sel_schulform = st.multiselect("Schulform-Unterstützung", schulformen, key="f_sf")
        haustiere = st.checkbox("Haustiere erlaubt", key="f_tier")

        st.divider()

        # 8 – Spezialisierungen
        st.caption("Spezialisierungen")
        trauma = st.checkbox("Traumapädagogik", key="f_trau")
        psychiatrie = st.checkbox("Psychiatrienahe Betreuung", key="f_psych")
        autismus_f = st.checkbox("Autismus", key="f_auti")
        geistige_beh = st.checkbox("Geistige Behinderung", key="f_geist")
        koerperlich = st.checkbox("Körperliche Einschränkungen", key="f_koerp")
        deutschkenntnisse = st.checkbox("Deutschkenntnisse erforderlich", key="f_deutsch")
        sprachunterstuetzung = st.checkbox("Sprachunterstützung vorhanden", key="f_sprach")

        st.divider()

        # 9 – Betreuungskapazität und Personal
        st.caption("Betreuungskapazität und Personal")
        eins_zu_eins = st.checkbox("1:1 möglich", key="f_11")
        nachtbereitschaft = st.checkbox("Nachtbereitschaft", key="f_nb")
        nachtdienst = st.checkbox("Nachtdienst", key="f_nd")
        deeskalation = st.checkbox("Deeskalationserfahrung", key="f_deesk")

        st.divider()

        # 10 – Administrative Filter
        st.caption("Administrativ")
        sel_einrichtungstyp = st.multiselect(
            "Einrichtungstyp",
            sorted(df_all["einrichtungstyp"].unique()),
            key="f_etyp",
        )
        traeger_f = st.multiselect(
            "Träger",
            ["öffentlich", "frei gemeinnützig", "privat"],
            key="f_traeg",
        )
        platz_bestaetigt = st.selectbox(
            "Platz bestätigt in",
            ["egal", "24 Stunden", "3 Tagen", "7 Tagen"],
            key="f_best",
        )
        kontaktzeit_opts = sorted(df_all["kontaktzeitfenster"].dropna().unique())
        sel_kontaktzeit = st.multiselect(
            "Kontaktzeitfenster",
            kontaktzeit_opts,
            key="f_kontakt",
        )

    st.divider()
    if st.button("🔄 Alle Filter zurücksetzen"):
        for k in list(st.session_state.keys()):
            if k.startswith("f_") or k.startswith("u_"):
                del st.session_state[k]
        st.rerun()

# ---------------------------------------------------------------------------
# Daten filtern
# ---------------------------------------------------------------------------
df = df_all.copy()

# 1 – Verfügbarkeit
if nur_frei_jetzt:
    df = df[df["freie_plaetze_jetzt"]]
if verfuegbar_ab_filter:
    df = df[df["verfuegbar_ab"] <= verfuegbar_ab_filter]
df = df[df["verfuegbar_monate"] >= min_monate]

# 2 – Ort und Erreichbarkeit
if sel_bundesland:
    df = df[df["bundesland"].isin(sel_bundesland)]
if sel_landkreis:
    df = df[df["landkreis"].isin(sel_landkreis)]
if umkreis_aktiv:
    df["distance_km"] = df.apply(
        lambda r: haversine_distance(user_lat, user_lon, r["latitude"], r["longitude"]),
        axis=1,
    )
    df = df[df["distance_km"] <= umkreis_km]
else:
    df["distance_km"] = None

# 3 – Altersbereich
df = df[(df["alter_max"] >= alter_range[0]) & (df["alter_min"] <= alter_range[1])]

# 4 – Aufnahmeart
if inobhutnahme:
    df = df[df["inobhutnahme_geeignet"]]
if krisenplatz:
    df = df[df["krisenplatz"] | df["notaufnahme_24_7"]]
if sel_aufnahmeart:
    df = df[df["aufnahmeart"].apply(lambda x: any(a in x for a in sel_aufnahmeart))]

# 5 – Hilfeform und Setting
if sel_hilfeform:
    df = df[df["hilfeform"].apply(lambda x: any(h in x for h in sel_hilfeform))]
if einzelplatz:
    df = df[df["einzelplatz_moeglich"]]
if kleingruppe:
    df = df[df["kleingruppe"]]

# 6 – Geschlecht
if sel_geschlecht:
    df = df[df["geschlecht"].isin(sel_geschlecht)]

# 7 – Ausschluss und Mindestkriterien
if keine_gewalt:
    df = df[df["keine_gewaltproblematik"]]
if keine_sucht:
    df = df[df["keine_suchtthematik"]]
if schulbesuch:
    df = df[df["schulbesuch_moeglich"]]
if sel_schulform:
    df = df[df["schulform_unterstuetzung"].apply(lambda x: any(s in x for s in sel_schulform))]
if haustiere:
    df = df[df["haustiere_erlaubt"]]

# 8 – Spezialisierungen
if trauma:
    df = df[df["traumapaedagogik"]]
if psychiatrie:
    df = df[df["psychiatrienahe_betreuung"]]
if autismus_f:
    df = df[df["autismus"]]
if geistige_beh:
    df = df[df["geistige_behinderung"]]
if koerperlich:
    df = df[df["koerperliche_einschraenkungen"]]
if deutschkenntnisse:
    df = df[df["deutschkenntnisse_erforderlich"]]
if sprachunterstuetzung:
    df = df[df["sprachunterstuetzung"]]

# 9 – Betreuungskapazität und Personal
if eins_zu_eins:
    df = df[df["eins_zu_eins_moeglich"]]
if nachtbereitschaft:
    df = df[df["nachtbereitschaft"]]
if nachtdienst:
    df = df[df["nachtdienst"]]
if deeskalation:
    df = df[df["deeskalationserfahrung"]]

# 10 – Administrativ
if sel_einrichtungstyp:
    df = df[df["einrichtungstyp"].isin(sel_einrichtungstyp)]
if traeger_f:
    df = df[df["traeger"].isin(traeger_f)]
if platz_bestaetigt == "24 Stunden":
    df = df[df["platz_bestaetigt_24h"]]
elif platz_bestaetigt == "3 Tagen":
    df = df[df["platz_bestaetigt_3d"]]
elif platz_bestaetigt == "7 Tagen":
    df = df[df["platz_bestaetigt_7d"]]
if sel_kontaktzeit:
    df = df[df["kontaktzeitfenster"].isin(sel_kontaktzeit)]

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
        st.caption(f'{heim["stadt"]} · {heim["bundesland"]} · {heim.get("landkreis", "")}')

        col_img, col_info = st.columns([1, 2])

        with col_img:
            st.image(heim["bild_url"], use_container_width=True)
            m = folium.Map(
                location=[heim["latitude"], heim["longitude"]],
                zoom_start=13, width=350, height=250,
            )
            folium.Marker(
                [heim["latitude"], heim["longitude"]],
                tooltip=heim["name"],
                icon=folium.Icon(color="blue", icon="home", prefix="fa"),
            ).add_to(m)
            st_folium(m, width=350, height=250, key="detail_map")

        with col_info:
            # Info-Box via native Streamlit
            with st.container(border=True):
                st.subheader("Informationen")
                st.markdown(f"**Adresse:** {heim['adresse']}")
                st.markdown(f"**Betreuungsart:** {heim['betreuungsart']}")
                st.markdown(f"**Hilfeform:** {', '.join(heim.get('hilfeform', []))}")
                st.markdown(f"**Freie Plätze:** {heim['freie_plaetze']}  ({'jetzt verfügbar' if heim.get('freie_plaetze_jetzt') else 'nicht sofort'})")
                st.markdown(f"**Reservierbar:** {'Ja' if heim.get('reservierbar') else 'Nein'}")
                st.markdown(f"**Altersgruppe:** {heim['alter_min']}–{heim['alter_max']} Jahre")
                st.markdown(f"**Geschlecht:** {heim.get('geschlecht', 'offen')}")
                st.markdown(f"**Verfügbar ab:** {heim['verfuegbar_ab']}")
                st.markdown(f"**Verfügbarkeit:** {heim['verfuegbar_monate']} Monate")
                st.markdown(f"**Aufnahmeart:** {', '.join(heim.get('aufnahmeart', []))}")
                st.markdown(f"**Inobhutnahme:** {'Ja' if heim.get('inobhutnahme_geeignet') else 'Nein'}")
                st.markdown(f"**Krisenplatz:** {'Ja' if heim.get('krisenplatz') else 'Nein'}")
                st.markdown(f"**Notaufnahme 24/7:** {'Ja' if heim.get('notaufnahme_24_7') else 'Nein'}")

            with st.container(border=True):
                st.subheader("Beschreibung")
                st.write(heim["beschreibung"])

            # Spezialisierungen
            spez = []
            if heim.get("traumapaedagogik"):
                spez.append("Traumapädagogik")
            if heim.get("psychiatrienahe_betreuung"):
                spez.append("Psychiatrienahe Betreuung")
            if heim.get("autismus"):
                spez.append("Autismus")
            if heim.get("geistige_behinderung"):
                spez.append("Geistige Behinderung")
            if heim.get("koerperliche_einschraenkungen"):
                spez.append("Körperliche Einschränkungen")
            if heim.get("sprachunterstuetzung"):
                spez.append("Sprachunterstützung")
            if spez:
                with st.container(border=True):
                    st.subheader("Spezialisierungen")
                    st.write(", ".join(spez))

            with st.container(border=True):
                st.subheader("Kontakt")
                st.markdown(f"📧 {heim['kontakt_email']}")
                st.markdown(f"📞 {heim['kontakt_telefon']}")
                st.markdown(f"⏰ {heim.get('kontaktzeitfenster', 'Nicht angegeben')}")

        # Kontaktformular
        st.divider()
        st.subheader("Anfrage senden")

        with st.form(key="contact_form"):
            c1, c2 = st.columns(2)
            with c1:
                contact_name = st.text_input("Ihr Name *")
                contact_organisation = st.text_input("Ihre Organisation (optional)")
                contact_email = st.text_input("Ihre E-Mail-Adresse *")
            with c2:
                contact_alter = st.number_input(
                    "Alter des Jugendlichen", min_value=6, max_value=25, value=14,
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
    m2.metric("Freie Plätze", int(df["freie_plaetze"].sum()))
    m3.metric("Städte", df["stadt"].nunique())
    m4.metric("Bundesländer", df["bundesland"].nunique())

    if df.empty:
        st.info("Keine Einrichtungen gefunden. Bitte passen Sie die Filter an.")
    else:
        tab_cards, tab_map, tab_table = st.tabs(
            ["📋 Kachelansicht", "🗺️ Kartenansicht", "📊 Tabellenansicht"]
        )

        # -- Kachelansicht --
        with tab_cards:
            if "distance_km" in df.columns and df["distance_km"].notna().any():
                df_display = df.sort_values("distance_km")
            else:
                df_display = df

            rows = [df_display.iloc[i : i + 3] for i in range(0, len(df_display), 3)]
            for row_chunk in rows:
                cols = st.columns(3)
                for idx, (_, heim) in enumerate(row_chunk.iterrows()):
                    with cols[idx]:
                        render_card(heim)

        # -- Kartenansicht --
        with tab_map:
            center_lat = df["latitude"].mean()
            center_lon = df["longitude"].mean()
            fmap = folium.Map(location=[center_lat, center_lon], zoom_start=6)

            for _, heim in df.iterrows():
                color = "green" if heim["freie_plaetze"] > 0 else "red"
                popup_html = (
                    f"<b>{heim['name']}</b><br>"
                    f"{heim['stadt']}<br>"
                    f"Freie Plätze: {heim['freie_plaetze']}<br>"
                    f"{heim['betreuungsart']}"
                )
                if pd.notna(heim.get("distance_km")):
                    popup_html += f"<br>Entfernung: {heim['distance_km']:.1f} km"
                folium.Marker(
                    location=[heim["latitude"], heim["longitude"]],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=heim["name"],
                    icon=folium.Icon(color=color, icon="home", prefix="fa"),
                ).add_to(fmap)

            st_folium(fmap, width=None, height=550, key="overview_map")

        # -- Tabellenansicht --
        with tab_table:
            cols_show = [
                "name", "stadt", "bundesland", "betreuungsart",
                "freie_plaetze",
                "alter_min", "alter_max", "verfuegbar_ab", "verfuegbar_monate",
            ]
            rename = {
                "name": "Name", "stadt": "Stadt", "bundesland": "Bundesland",
                "betreuungsart": "Betreuungsart", "freie_plaetze": "Freie Plätze",
                "alter_min": "Alter min",
                "alter_max": "Alter max", "verfuegbar_ab": "Verfügbar ab",
                "verfuegbar_monate": "Dauer (Mon.)",
            }
            if df["distance_km"].notna().any():
                cols_show.append("distance_km")
                rename["distance_km"] = "Entfernung (km)"

            display_df = df[cols_show].rename(columns=rename)
            if "Entfernung (km)" in display_df.columns:
                display_df["Entfernung (km)"] = display_df["Entfernung (km)"].apply(
                    lambda x: f"{x:.1f}" if pd.notna(x) else ""
                )
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Footer
    st.divider()
    st.caption(
        f"Jugendheim-Platzvermittlung · Demo-Version · "
        f"Datenstand: {date.today().strftime('%d.%m.%Y')}"
    )
