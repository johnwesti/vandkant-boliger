"""
vandkant_boliger.py
===================
Finder alle ejendomme til salg i Danmark der ligger max 150 meter
fra kysten til de indre danske farvande.

Datakilder:
  - Kystlinje: OpenStreetMap via Overpass API (gratis, ingen login)
  - Boligannoncer: Boliga.dk's søge-API (offentligt tilgængeligt)

Afhængigheder:
  pip install requests geopandas shapely pandas folium tqdm

Kør:
  python vandkant_boliger.py

Output:
  - vandkant_boliger.csv   → liste med alle matches
  - vandkant_kort.html     → interaktivt kort med alle matches
"""

import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, shape, MultiLineString, LineString
import folium
import json
import time
import pickle
import os
import argparse
from datetime import datetime, timedelta
from tqdm import tqdm

# ─────────────────────────────────────────────
# KONFIGURATION
# ─────────────────────────────────────────────
MAX_AFSTAND_METER = 200          # Filtrér boliger inden for denne afstand
BOLIG_TYPER = [1, 2, 4, 5]      # 1=Villa, 2=Rækkehus, 4=Fritidshus, 5=Grund
OUTPUT_CSV  = "vandkant_boliger.csv"
OUTPUT_HTML = "vandkant_kort.html"

# Sæt til True for kun at medtage indre farvande (ekskluder Nordsø/Vesterhavet)
EKSKLUDER_VESTERHAV = False

# ─────────────────────────────────────────────
# EKSKLUDERING AF BYER / KOMMUNER / POSTNUMRE
# ─────────────────────────────────────────────
# De 10 største byer ekskluderes – alle kendte bydele og postnumre medtaget
EKSKLUDER_BYER = {
    # København
    "København", "København K", "København V", "København N", "København NV",
    "København S", "København SV", "København Ø", "København SØ",
    "Frederiksberg", "Vanløse", "Brønshøj", "Valby", "Bispebjerg",
    "Amager", "Christianshavn", "Østerbro", "Nørrebro", "Vesterbro",
    # Aarhus
    "Aarhus", "Aarhus C", "Aarhus V", "Aarhus N", "Aarhus SV",
    "Brabrand", "Viby J", "Højbjerg", "Risskov", "Skejby",
    "Lystrup", "Egå", "Åbyhøj", "Tranbjerg J",
    # Odense
    "Odense", "Odense C", "Odense M", "Odense N", "Odense NE",
    "Odense NV", "Odense S", "Odense SE", "Odense SV",
    "Bellinge", "Hjallese", "Dalum", "Tarup",
    # Aalborg
    "Aalborg", "Aalborg C", "Aalborg SV", "Aalborg SØ", "Aalborg Øst",
    "Nørresundby", "Vestbjerg", "Svenstrup J", "Klarup",
    # Esbjerg
    "Esbjerg", "Esbjerg N", "Esbjerg Ø", "Esbjerg V",
    "Esbjerg C", "Bramming", "Guldager",
    # Randers
    "Randers", "Randers C", "Randers NV", "Randers NØ",
    "Randers SV", "Randers SØ", "Kristrup", "Dronningborg",
    # Vejle
    "Vejle", "Vejle Ø", "Vejle N", "Bredballe", "Hornstrup",
    # Kolding
    "Kolding", "Kolding Ø", "Bramdrupdam", "Skovby",
    # Horsens
    "Horsens", "Horsens Ø", "Endelave", "Hatting",
    # Fredericia
    "Fredericia", "Erritsø",
}

# Ekskluder kommuner (matcher på by-felt)
EKSKLUDER_KOMMUNER = {
    "Københavns Kommune",
    "Frederiksberg Kommune",
}

# Ekskluder specifikke postnumre for de 10 største byer
EKSKLUDER_POSTNUMRE = {
    # København og omegn
    "1000","1050","1051","1052","1053","1054","1055","1056","1057","1058","1059",
    "1060","1061","1062","1063","1064","1065","1066","1067","1068","1069",
    "1070","1071","1072","1073","1074","1075","1076","1077","1078","1079",
    "1100","1110","1111","1112","1113","1114","1115","1116","1117","1118","1119",
    "1120","1121","1122","1123","1124","1125","1126","1127","1128","1129",
    "1130","1131","1150","1151","1152","1153","1154","1155","1156","1157","1158","1159",
    "1160","1161","1162","1163","1164","1165","1166","1167","1168","1169",
    "1170","1171","1172","1173","1174","1175","1200","1201","1202","1203","1204",
    "1205","1206","1207","1208","1209","1210","1211","1212","1213","1214","1215",
    "1216","1217","1218","1219","1220","1221","1240","1250","1251","1252","1253",
    "1254","1255","1256","1257","1258","1259","1260","1261","1262","1263","1264",
    "1265","1266","1267","1268","1270","1271","1300","1301","1302","1303","1304",
    "1306","1307","1308","1309","1310","1311","1312","1313","1314","1315","1316",
    "1317","1318","1319","1320","1321","1322","1323","1324","1325","1326","1327",
    "1328","1329","1350","1352","1353","1354","1355","1356","1357","1358","1359",
    "1360","1361","1362","1363","1364","1365","1366","1367","1368","1369","1370",
    "1371","1400","1401","1402","1403","1404","1405","1406","1407","1408","1409",
    "1410","1411","1412","1413","1414","1415","1416","1417","1418","1419","1420",
    "1421","1422","1423","1424","1425","1426","1427","1428","1429","1430","1431",
    "1432","1433","1434","1435","1436","1437","1438","1439","1440","1441","1448",
    "1450","1451","1452","1453","1454","1455","1456","1457","1458","1459","1460",
    "1461","1462","1463","1464","1465","1466","1467","1468","1470","1471","1472",
    "1473","1500","1550","1551","1552","1553","1554","1555","1556","1557","1558",
    "1559","1560","1561","1562","1563","1564","1565","1566","1567","1568","1569",
    "1570","1571","1572","1573","1574","1575","1576","1577","1590","1592","1599",
    "1600","1601","1602","1603","1604","1605","1606","1607","1608","1609","1610",
    "1611","1612","1613","1614","1615","1616","1617","1618","1619","1620","1621",
    "1622","1623","1624","1625","1626","1627","1628","1629","1630","1631","1632",
    "1633","1634","1635","1636","1637","1638","1639","1640","1641","1650","1651",
    "1652","1653","1654","1655","1656","1657","1658","1659","1660","1661","1662",
    "1663","1664","1665","1666","1667","1668","1669","1670","1671","1672","1673",
    "1674","1675","1676","1677","1700","1701","1702","1703","1704","1705","1706",
    "1707","1708","1709","1710","1711","1712","1713","1714","1715","1716","1717",
    "1718","1719","1720","1721","1722","1723","1724","1725","1726","1727","1728",
    "1729","1730","1731","1732","1733","1734","1735","1736","1737","1738","1739",
    "1740","1741","1742","1743","1744","1745","1746","1747","1748","1749","1750",
    "1751","1752","1753","1754","1755","1756","1757","1758","1759","1760","1761",
    "1762","1763","1764","1765","1766","1767","1768","1769","1770","1771","1772",
    "1773","1774","1775","1776","1777","1778","1779","1780","1781","1782","1783",
    "1784","1785","1786","1787","1788","1789","1790","1791","1792","1793","1794",
    "1795","1796","1797","1798","1799","1800","1801","1802","1803","1804","1805",
    "1806","1807","1808","1809","1810","1811","1812","1813","1814","1815","1816",
    "1817","1818","1819","1820","1821","1822","1823","1824","1825","1826","1827",
    "1828","1829","1850","1851","1852","1853","1854","1855","1856","1857","1860",
    "1861","1870","1871","1872","1873","1874","1900","1901","1902","1903","1904",
    "2000","2100","2200","2300","2400","2450","2500","2720","2730","2750","2760",
    "2770","2800","2820","2830","2840","2860","2880","2900",
    # Aarhus
    "8000","8200","8210","8220","8230","8240","8250","8260","8270","8310","8320",
    "8330","8361","8362","8380",
    # Odense
    "5000","5200","5210","5220","5230","5240","5250","5260","5270","5290",
    # Aalborg
    "9000","9200","9210","9220","9230","9240","9260","9270","9280","9290",
    # Esbjerg
    "6700","6705","6710","6715","6720","6731","6740","6752","6753","6760","6771",
    # Randers
    "8900","8920","8930","8940","8950","8960","8981","8983","8990",
    # Vejle
    "7100","7120","7130","7140","7150","7160","7171","7173","7182","7183","7184",
    # Kolding
    "6000","6040","6051","6052","6064","6070","6091","6092","6093","6094","6095",
    # Horsens
    "8700","8721","8722","8723","8732","8740","8751","8752","8762","8763","8781","8783",
    # Fredericia
    "7000","7007",
}

# ─────────────────────────────────────────────
# CACHE-INDSTILLINGER
# ─────────────────────────────────────────────
# Cachede filer gemmes lokalt så du ikke skal hente data igen ved hver kørsel.
# Sæt BRUG_CACHE = False for at tvinge en frisk hentning.
BRUG_CACHE        = True
CACHE_KYST_FIL    = "cache_kystlinje.pkl"       # Kystlinje (ændrer sig sjældent)
CACHE_BOLIGER_FIL = "cache_boliger.pkl"          # Boligannoncer
CACHE_BOLIGER_MAX_ALDER_TIMER = 24               # Genhent boliger hvis cachen er ældre end X timer

# ─────────────────────────────────────────────
# CACHE-HJÆLPEFUNKTIONER
# ─────────────────────────────────────────────
def gem_cache(obj, filnavn):
    with open(filnavn, "wb") as f:
        pickle.dump(obj, f)
    print(f"    💾 Cache gemt: {filnavn}")

def indlæs_cache(filnavn, max_alder_timer=None):
    """Returnerer cachet objekt hvis filen findes og ikke er for gammel, ellers None."""
    if not os.path.exists(filnavn):
        return None
    alder = datetime.now() - datetime.fromtimestamp(os.path.getmtime(filnavn))
    if max_alder_timer and alder > timedelta(hours=max_alder_timer):
        print(f"    ⏰ Cache udløbet ({filnavn}, {int(alder.total_seconds()/3600)}t gammel) – henter friske data...")
        return None
    print(f"    ✓ Indlæser fra cache: {filnavn} ({int(alder.total_seconds()/3600)}t gammel)")
    with open(filnavn, "rb") as f:
        return pickle.load(f)


# ─────────────────────────────────────────────
# TRIN 1: Hent kystlinje fra OpenStreetMap
# ─────────────────────────────────────────────
def hent_kystlinje():
    """
    Henter den danske kystlinje fra OpenStreetMap via Overpass API.
    Returnerer en GeoDataFrame med kystlinjer i UTM32N (EPSG:25832).
    
    Vi henter 'natural=coastline' som er OSMs officielle kystlinje-tag.
    For Danmark svarer dette til grænsen mellem hav og land.
    """
    print("\n[1/4] Henter kystlinje fra OpenStreetMap...")
    
    # Overpass QL-forespørgsel: hent alle kystlinjer i Danmarks bounding box
    # Bounding box: Danmark inkl. øer (55.0°N–57.8°N, 8.0°E–15.3°E)
    query = """
    [out:json][timeout:120];
    (
      way["natural"="coastline"](54.5, 7.5, 58.0, 15.7);
    );
    out geom;
    """

    headers = {
        "User-Agent": "vandkant-boliger-script/1.0 (research project)",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Prøv flere Overpass-servere hvis én fejler
    servere = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]

    r = None
    for overpass_url in servere:
        try:
            print(f"    → Prøver {overpass_url} ...")
            r = requests.post(overpass_url, data={"data": query}, headers=headers, timeout=180)
            r.raise_for_status()
            break  # Succes – stop med at prøve
        except requests.exceptions.HTTPError as e:
            print(f"    ⚠ Fejl ({e}) – prøver næste server...")
            r = None
        except requests.exceptions.RequestException as e:
            print(f"    ⚠ Forbindelsesfejl ({e}) – prøver næste server...")
            r = None

    if r is None:
        raise RuntimeError("Alle Overpass-servere fejlede. Tjek din internetforbindelse og prøv igen.")
    data = r.json()
    
    linjer = []
    for element in data["elements"]:
        if element["type"] == "way" and "geometry" in element:
            coords = [(p["lon"], p["lat"]) for p in element["geometry"]]
            if len(coords) >= 2:
                linjer.append(LineString(coords))
    
    if not linjer:
        raise RuntimeError("Ingen kystlinjer hentet fra OSM. Prøv igen.")
    
    gdf = gpd.GeoDataFrame(geometry=linjer, crs="EPSG:4326")
    
    # Konvertér til metrisk projektion (UTM zone 32N) – nødvendigt for korrekt afstandsmåling i meter
    gdf = gdf.to_crs(epsg=25832)
    
    print(f"    ✓ {len(gdf)} kystlinjesegmenter hentet")
    return gdf


def ekskluder_vesterhav(kyst_gdf):
    """
    Fjerner kystlinjer vest for Vesterhav-grænsen (Nordsø/Vesterhavet).
    Vi beholder kun indre farvande: Kattegat, Øresund, Bælthavet,
    Limfjorden, fjorde og den jyske østkyst.
    
    Simpel metode: filtrer segmenter der primært ligger øst for grænsen.
    """
    print(f"    → Ekskluderer Vesterhav (vest for {VESTERHAV_GRÆNSE_LON}°E)...")
    
    # Konvertér tilbage til WGS84 for at filtrere på longitude
    gdf_wgs = kyst_gdf.to_crs(epsg=4326)
    
    def er_indre_farvand(geom):
        """Returner True hvis linjesegmentets centroid er øst for grænsen."""
        centroid = geom.centroid
        return centroid.x > VESTERHAV_GRÆNSE_LON
    
    mask = gdf_wgs.geometry.apply(er_indre_farvand)
    filtreret = kyst_gdf[mask.values].copy()
    
    fjernet = len(kyst_gdf) - len(filtreret)
    print(f"    ✓ {fjernet} Vesterhav-segmenter fjernet, {len(filtreret)} segmenter tilbage (indre farvande)")
    return filtreret


# ─────────────────────────────────────────────
# TRIN 2: Hent boligannoncer fra Boliga.dk
# ─────────────────────────────────────────────
def hent_boliger_fra_boliga(bolig_typer=BOLIG_TYPER, max_sider=50):
    """
    Henter aktuelle boligannoncer fra Boliga.dk's søge-API.
    
    Endpoint er Boligas offentlige søge-API som bruges af deres hjemmeside.
    Returnerer en liste af dicts med adresse, pris, koordinater m.m.
    
    Parametre:
      bolig_typer: liste af boligtypeindeks (1=Villa, 2=Rækkehus, 3=Ejerlejlighed, 4=Fritidshus, 5=Grund)
      max_sider:   max antal API-sider at hente (500 boliger pr. side → 50 sider = 25.000 boliger)
    """
    print("\n[2/4] Henter boligannoncer fra Boliga.dk...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; research-script/1.0)",
        "Accept": "application/json",
        "Referer": "https://www.boliga.dk/",
    }
    
    base_url = "https://api.boliga.dk/api/v2/search/results"
    alle_boliger = []
    
    # Hent for hver boligtype separat for bedre dækning
    for bolig_type in bolig_typer:
        type_navne = {1: "Villa/Parcelhus", 2: "Rækkehus", 3: "Ejerlejlighed", 4: "Fritidshus", 5: "Grund"}
        print(f"  → Henter type: {type_navne.get(bolig_type, str(bolig_type))}")
        
        side = 1
        type_total = 0
        while side <= max_sider:
            params = {
                "propertyType": bolig_type,
                "page": side,
                "pageSize": 500,
                "sort": "price-a",
            }

            try:
                print(f"    Side {side}...", end=" ", flush=True)
                r = requests.get(base_url, params=params, headers=headers, timeout=30)
                print(f"HTTP {r.status_code}", end=" ", flush=True)
                r.raise_for_status()
                data = r.json()
            except requests.exceptions.HTTPError as e:
                print(f"\n    ⚠ HTTP-fejl side {side}: {e}")
                print(f"    Svar fra server: {r.text[:300]}")
                break
            except requests.exceptions.ConnectionError as e:
                print(f"\n    ⚠ Forbindelsesfejl side {side}: {e}")
                break
            except requests.exceptions.Timeout:
                print(f"\n    ⚠ Timeout på side {side} – prøver næste...")
                side += 1
                continue
            except Exception as e:
                print(f"\n    ⚠ Uventet fejl side {side}: {e}")
                break

            resultater = data.get("results", [])
            total = data.get("meta", {}).get("totalCount", 0)

            if not resultater:
                print(f"→ ingen resultater, stopper")
                break

            med_koord = 0
            for bolig in resultater:
                lat = bolig.get("latitude")
                lng = bolig.get("longitude")
                if not lat or not lng:
                    continue
                med_koord += 1
                alle_boliger.append({
                    "id":           bolig.get("id", ""),
                    "guid":         bolig.get("guid", ""),
                    "adresse":      bolig.get("address", ""),
                    "postnummer":   bolig.get("zipCode", ""),
                    "by":           bolig.get("city", ""),
                    "pris":         bolig.get("price", 0),
                    "type":         type_navne.get(bolig_type, str(bolig_type)),
                    "kvm":          bolig.get("size", 0),
                    "vaerelser":    bolig.get("rooms", 0),
                    "byggeaar":     bolig.get("buildYear", ""),
                    "energimaerke": bolig.get("energyClass", ""),
                    "ouAddress":    str(bolig.get("ouAddress", "")),
                    "ouId":         str(bolig.get("ouId", "")),
                    "bfeNr":        str(bolig.get("bfeNr", "")),
                    "url":          f"https://www.boliga.dk/adresse/{bolig.get('ouAddress')}-{bolig.get('ouId', '')}",
                    "lat":          float(lat),
                    "lng":          float(lng),
                })

            type_total += med_koord
            print(f"→ {med_koord} boliger (total denne type: {type_total} / {total})")

            if (side * 500) >= total:
                break

            side += 1
            time.sleep(0.5)

        print(f"    ✓ Færdig: {type_total} {type_navne.get(bolig_type, str(bolig_type))} hentet")
    
    print(f"\n  ✓ Total: {len(alle_boliger)} boliger med koordinater hentet")
    return alle_boliger


# ─────────────────────────────────────────────
# TRIN 2b: Ekskluder byer/kommuner/postnumre
# ─────────────────────────────────────────────
def filtrer_ekskluderede(boliger):
    """
    Fjerner boliger i ekskluderede byer, kommuner eller postnumre.
    Sammenligning er case-insensitiv på by-navn.
    """
    før = len(boliger)
    resultat = []
    for b in boliger:
        by = (b.get("by") or "").strip()
        pnr = str(b.get("postnummer") or "").strip()

        # Tjek by (case-insensitiv)
        if any(by.lower() == e.lower() for e in EKSKLUDER_BYER):
            continue

        # Tjek kommune – Boliga returnerer ikke direkte kommunenavn,
        # men vi kan matche på postnummer-ranges der svarer til kommunerne.
        # Alternativt: brugeren tilføjer postnumre til EKSKLUDER_POSTNUMRE.
        # Her bruger vi EKSKLUDER_KOMMUNER som et by-præfiks-match som fallback.
        if any(by.lower() in e.lower() for e in EKSKLUDER_KOMMUNER):
            continue

        # Tjek postnummer
        if pnr in EKSKLUDER_POSTNUMRE:
            continue

        resultat.append(b)

    fjernet = før - len(resultat)
    print(f"  → Ekskluderet {fjernet} boliger pga. by/kommune/postnummer-filter")
    print(f"  ✓ {len(resultat)} boliger tilbage efter filtrering")
    return resultat


# ─────────────────────────────────────────────
# TRIN 3: Beregn afstand og filtrer
# ─────────────────────────────────────────────
def filtrer_nær_vand(boliger, kyst_gdf, max_afstand=MAX_AFSTAND_METER):
    """
    Beregner afstanden fra hver bolig til den nærmeste kystlinje
    og returnerer kun boliger inden for max_afstand meter.
    
    Bruger UTM32N-projektionen (EPSG:25832) hvor afstand er i meter.
    """
    print(f"\n[3/4] Beregner afstand til kyst for {len(boliger)} boliger...")
    
    # Byg GeoDataFrame af boliger
    df = pd.DataFrame(boliger)
    gdf_boliger = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lng"], df["lat"]),
        crs="EPSG:4326"
    ).to_crs(epsg=25832)  # Konvertér til meter-baseret projektion
    
    # Saml alle kystlinjer til én geometri for hurtigere afstandsberegning
    # union_all() er hurtigere end at iterere over hvert segment
    print("  → Sammensætter kystgeometri (kan tage 30-60 sek.)...")
    samlet_kyst = kyst_gdf.geometry.union_all()
    
    # Beregn afstand til kyst for hver bolig
    print(f"  → Beregner afstande (max {max_afstand}m filter)...")
    afstande = []
    for geom in tqdm(gdf_boliger.geometry, desc="  Afstandsberegning"):
        afstande.append(samlet_kyst.distance(geom))
    
    gdf_boliger["afstand_m"] = afstande
    gdf_boliger["afstand_m"] = gdf_boliger["afstand_m"].round(1)
    
    # Filtrer
    nær_vand = gdf_boliger[gdf_boliger["afstand_m"] <= max_afstand].copy()
    nær_vand = nær_vand.sort_values("afstand_m")
    
    print(f"\n  ✓ {len(nær_vand)} boliger fundet inden for {max_afstand}m fra kyst")
    return nær_vand


# ─────────────────────────────────────────────
# TRIN 4: Gem resultater
# ─────────────────────────────────────────────
def gem_csv(gdf, filnavn=OUTPUT_CSV):
    """Gemmer resultater som CSV."""
    kolonner = ["adresse", "postnummer", "by", "pris", "type", "kvm",
                "vaerelser", "byggeaar", "energimaerke", "afstand_m", "lat", "lng", "url"]
    
    # Behold kun kolonner der faktisk findes
    kolonner = [k for k in kolonner if k in gdf.columns]
    
    df = pd.DataFrame(gdf[kolonner])
    df.to_csv(filnavn, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel-kompatibilitet
    print(f"  ✓ CSV gemt: {filnavn}")
    return filnavn


def gem_kort(gdf, filnavn=OUTPUT_HTML):
    """Laver et interaktivt Folium-kort i Boliga-stil med clustering og property cards."""
    print(f"  → Genererer interaktivt kort...")

    center_lat = gdf["lat"].mean()
    center_lng = gdf["lng"].mean()

    # Byg kortet som ren HTML med Leaflet + MarkerCluster direkte
    # for fuld kontrol over styling
    boliger_json = []
    for _, row in gdf.iterrows():
        pris = int(row["pris"]) if pd.notna(row.get("pris")) and row.get("pris") else 0
        boliger_json.append({
            "lat":       row["lat"],
            "lng":       row["lng"],
            "adresse":   str(row.get("adresse", "")),
            "by":        str(row.get("by", "")),
            "pnr":       str(row.get("postnummer", "")),
            "pris":      pris,
            "type":      str(row.get("type", "")),
            "kvm":       int(row.get("kvm", 0) or 0),
            "vaerelser": int(row.get("vaerelser", 0) or 0),
            "byggeaar":  str(row.get("byggeaar", "") or ""),
            "energi":    str(row.get("energimaerke", "") or ""),
            "afstand":   float(row["afstand_m"]),
            "url":       str(row.get("url", "#")),
            "ouAddress": str(row.get("ouAddress", "")),
            "ouId":      str(row.get("ouId", "")),
            "bfeNr":     str(row.get("bfeNr", "")),
            "billede":   (lambda i: f"https://i.boliga.org/dk/550x/{str(i)[:4]}/{i}.jpg" if i else "")(
                next((v for v in [row.get("id"), row.get("guid")] if v and str(v).isdigit()), None)
            ),
        })

    import json as _json
    data_js = _json.dumps(boliger_json, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vandkant Boliger – {len(gdf)} resultater</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f5; }}

  #topbar {{
    position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
    background: #1a5276; color: white;
    display: flex; align-items: center; gap: 16px;
    padding: 10px 18px; box-shadow: 0 2px 8px rgba(0,0,0,.3);
  }}
  #topbar h1 {{ font-size: 16px; font-weight: 700; letter-spacing: .3px; }}
  #topbar .count {{ font-size: 13px; opacity: .85; }}
  #topbar .filters {{ margin-left: auto; display: flex; gap: 8px; align-items: center; }}
  #topbar select, #topbar input {{
    border: none; border-radius: 6px; padding: 5px 10px;
    font-size: 13px; background: rgba(255,255,255,.15); color: white;
    outline: none; cursor: pointer;
  }}
  #topbar select option {{ color: #222; background: white; }}
  #topbar input::placeholder {{ color: rgba(255,255,255,.6); }}

  #map {{ position: fixed; top: 48px; left: 0; bottom: 0; right: 380px; }}

  #sidebar {{
    position: fixed; top: 48px; right: 0; bottom: 0; width: 380px;
    background: white; overflow-y: auto;
    border-left: 1px solid #e0e0e0;
  }}
  #sidebar-header {{
    padding: 12px 16px; background: #f8f8f8;
    border-bottom: 1px solid #e8e8e8; font-size: 13px; color: #555;
  }}

  .bolig-card {{
    border-bottom: 1px solid #eee; cursor: pointer;
    transition: background .15s;
    text-decoration: none; color: inherit; display: block;
  }}
  .bolig-card:hover {{ background: #f0f7ff; }}
  .bolig-card.active {{ background: #e8f4fd; border-left: 3px solid #1a5276; }}
  .card-img {{
    width: 100%; height: 160px; object-fit: cover;
    background: #e8e8e8; display: block;
  }}
  .card-img-placeholder {{
    width: 100%; height: 120px; background: linear-gradient(135deg,#dde8f0,#c8d8e8);
    display: flex; align-items: center; justify-content: center;
    color: #7a9ab0; font-size: 28px;
  }}
  .card-body {{ padding: 10px 14px 12px; }}
  .card-pris {{ font-size: 18px; font-weight: 700; color: #1a5276; }}
  .card-adresse {{ font-size: 13px; color: #333; margin: 2px 0; }}
  .card-by {{ font-size: 12px; color: #777; }}
  .card-meta {{
    display: flex; gap: 10px; margin-top: 8px;
    font-size: 12px; color: #555;
  }}
  .card-meta span {{ display: flex; align-items: center; gap: 3px; }}
  .card-badge {{
    display: inline-block; font-size: 10px; font-weight: 600;
    padding: 2px 7px; border-radius: 10px; margin-top: 6px;
  }}
  .badge-roed  {{ background: #fde8e8; color: #c0392b; }}
  .badge-orange{{ background: #fef3e2; color: #d35400; }}
  .badge-blaa  {{ background: #e8f4fd; color: #1a5276; }}

  /* Leaflet popup */
  .leaflet-popup-content-wrapper {{
    border-radius: 10px; padding: 0; overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,.18);
  }}
  .leaflet-popup-content {{ margin: 0; width: 260px !important; }}
  .popup-inner {{ padding: 14px; }}
  .popup-pris {{ font-size: 16px; font-weight: 700; color: #1a5276; }}
  .popup-adresse {{ font-size: 13px; margin: 3px 0 8px; }}
  .popup-meta {{ font-size: 12px; color: #666; line-height: 1.7; }}
  .popup-link {{
    display: block; margin-top: 10px; text-align: center;
    background: #1a5276; color: white; padding: 8px;
    border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600;
  }}
  .popup-link:hover {{ background: #154360; }}

  /* Custom marker */
  .pris-marker {{
    background: white; border: 2px solid #1a5276;
    border-radius: 20px; padding: 3px 8px;
    font-size: 11px; font-weight: 700; color: #1a5276;
    white-space: nowrap; box-shadow: 0 2px 6px rgba(0,0,0,.2);
  }}
  .pris-marker.roed  {{ border-color: #c0392b; color: #c0392b; }}
  .pris-marker.orange{{ border-color: #d35400; color: #d35400; }}

  @media (max-width: 700px) {{
    #map {{ right: 0; bottom: 45vh; }}
    #sidebar {{ top: 55vh; right: 0; left: 0; width: 100%; }}
  }}
</style>
</head>
<body>

<div id="topbar">
  <h1>🌊 Vandkant Boliger</h1>
  <span class="count" id="result-count">{len(gdf)} boliger inden for {MAX_AFSTAND_METER}m fra kysten</span>
  <div class="filters">
    <select id="filter-type" onchange="applyFilters()">
      <option value="">Alle typer</option>
      <option value="Villa/Parcelhus">Villa</option>
      <option value="Rækkehus">Rækkehus</option>
      <option value="Fritidshus">Fritidshus</option>
      <option value="Grund">Grund</option>
    </select>
    <select id="filter-afstand" onchange="applyFilters()">
      <option value="200">Max 200m</option>
      <option value="75">Max 75m</option>
      <option value="30">Max 30m (vandkant)</option>
    </select>
    <input type="number" id="filter-maxpris" placeholder="Max pris (kr)" 
           onchange="applyFilters()" style="width:140px">
  </div>
</div>

<div id="map"></div>
<div id="sidebar">
  <div id="sidebar-header">Klik på en bolig for detaljer</div>
  <div id="kort-liste"></div>
</div>

<script>
const BOLIGER = {data_js};

// Formater pris
function fmtPris(p) {{
  if (!p) return "Pris ukendt";
  return p.toLocaleString("da-DK") + " kr.";
}}

// Afstandsbadge
function afstandBadge(a) {{
  if (a <= 30)  return `<span class="card-badge badge-roed">🌊 ${{a}}m – Direkte vandkant</span>`;
  if (a <= 75)  return `<span class="card-badge badge-orange">🌊 ${{a}}m fra kyst</span>`;
  return              `<span class="card-badge badge-blaa">🌊 ${{a}}m fra kyst</span>`;
}}

function markerKlasse(a) {{
  if (a <= 30)  return "roed";
  if (a <= 75)  return "orange";
  return "blaa";
}}

// Kort
const map = L.map("map").setView([56.0, 10.5], 7);
L.tileLayer("https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}{{r}}.png", {{
  attribution: "© OpenStreetMap © CARTO",
  subdomains: "abcd", maxZoom: 19
}}).addTo(map);

const cluster = L.markerClusterGroup({{
  maxClusterRadius: 50,
  spiderfyOnMaxZoom: true,
  showCoverageOnHover: false,
  zoomToBoundsOnClick: true,
  iconCreateFunction: function(c) {{
    const n = c.getChildCount();
    const sz = n > 100 ? 44 : n > 20 ? 36 : 28;
    return L.divIcon({{
      html: `<div style="background:#1a5276;color:white;border-radius:50%;width:${{sz}}px;height:${{sz}}px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;box-shadow:0 2px 8px rgba(0,0,0,.3)">${{n}}</div>`,
      className: "", iconSize: [sz, sz]
    }});
  }}
}});
map.addLayer(cluster);

let markers = [];
let activeIdx = null;

function buildMarker(b, idx) {{
  const icon = L.divIcon({{
    html: `<div class="pris-marker ${{markerKlasse(b.afstand)}}">${{(b.pris/1e6).toFixed(1)}}M</div>`,
    className: "", iconAnchor: [30, 12]
  }});
  const m = L.marker([b.lat, b.lng], {{icon}});

  const popupHtml = `
    <div class="popup-inner">
      <div class="popup-pris">${{fmtPris(b.pris)}}</div>
      <div class="popup-adresse"><b>${{b.adresse}}</b><br>${{b.pnr}} ${{b.by}}</div>
      <div class="popup-meta">
        ${{b.kvm ? b.kvm + " m²" : ""}}${{b.vaerelser ? " · " + b.vaerelser + " vær." : ""}}${{b.byggeaar ? " · Bygget " + b.byggeaar : ""}}<br>
        ${{b.type}}<br>
        🌊 <b>${{b.afstand}} m fra kyst</b>
      </div>
      <a class="popup-link" href="https://www.boliga.dk/adresse/${{b.ouAddress}}-${{b.ouId}}" target="_blank">Se annonce på Boliga →</a>
      <a class="popup-link" style="margin-top:6px;background:#e67e22" href="https://www.boligsiden.dk/adresse/${{b.ouAddress}}" target="_blank">Se annonce på Boligsiden →</a>
      ${{b.bfeNr ? `<a class="popup-link" style="margin-top:6px;background:#1a6b3a" href="https://www.matriklen.dk/#/kort/sfe/${{b.bfeNr}}" target="_blank">🗺 Matrikel →</a>` : ""}}
      ${{b.bfeNr ? `<a class="popup-link" style="margin-top:6px;background:#7d3c98" href="https://www.ois.dk/?search=${{encodeURIComponent(b.adresse + ' ' + b.pnr)}}" target="_blank">📋 OIS →</a>` : ""}}
      <a class="popup-link" style="margin-top:6px;background:#1a4a6b" href="https://www.tinglysning.dk/tinglysning/unsecured/adressesoegning.xhtml?query=${{encodeURIComponent(b.adresse)}}" target="_blank">⚖️ Tinglysning →</a>
    </div>`;

  m.bindPopup(popupHtml, {{maxWidth: 280}});
  m.on("click", () => scrollToCard(idx));
  return m;
}}

function buildCard(b, idx) {{
  const imgHtml = b.billede
    ? `<img class="card-img" src="${{b.billede}}" onerror="this.style.display='none'" loading="lazy">`
    : `<div class="card-img-placeholder">🏠</div>`;
  return `
    <a class="bolig-card" id="card-${{idx}}" href="https://www.boliga.dk/adresse/${{b.ouAddress}}-${{b.ouId}}" target="_blank"
       onmouseenter="highlightMarker(${{idx}})" onmouseleave="unhighlightMarker(${{idx}})">
      ${{imgHtml}}
      <div class="card-body">
        <div class="card-pris">${{fmtPris(b.pris)}}</div>
        <div class="card-adresse">${{b.adresse}}</div>
        <div class="card-by">${{b.pnr}} ${{b.by}}</div>
        <div class="card-meta">
          ${{b.kvm ? `<span>📐 ${{b.kvm}} m²</span>` : ""}}
          ${{b.vaerelser ? `<span>🛏 ${{b.vaerelser}} vær.</span>` : ""}}
          ${{b.byggeaar ? `<span>🏗 ${{b.byggeaar}}</span>` : ""}}
        </div>
        ${{afstandBadge(b.afstand)}}
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
          <a href="https://www.boligsiden.dk/adresse/${{b.ouAddress}}" target="_blank" onclick="event.stopPropagation()" style="font-size:11px;color:#e67e22;text-decoration:none;font-weight:600;border:1px solid #e67e22;border-radius:4px;padding:2px 6px">🏠 Boligsiden</a>
          ${{b.bfeNr ? `<a href="https://www.matriklen.dk/#/kort/sfe/${{b.bfeNr}}" target="_blank" onclick="event.stopPropagation()" style="font-size:11px;color:#1a6b3a;text-decoration:none;font-weight:600;border:1px solid #1a6b3a;border-radius:4px;padding:2px 6px">🗺 Matrikel</a>` : ""}}
          ${{b.bfeNr ? `<a href="https://www.ois.dk/?search=${{encodeURIComponent(b.adresse + ' ' + b.pnr)}}" target="_blank" onclick="event.stopPropagation()" style="font-size:11px;color:#7d3c98;text-decoration:none;font-weight:600;border:1px solid #7d3c98;border-radius:4px;padding:2px 6px">📋 OIS</a>` : ""}}
          <a href="https://www.tinglysning.dk/tinglysning/unsecured/adressesoegning.xhtml?query=${{encodeURIComponent(b.adresse)}}" target="_blank" onclick="event.stopPropagation()" style="font-size:11px;color:#1a4a6b;text-decoration:none;font-weight:600;border:1px solid #1a4a6b;border-radius:4px;padding:2px 6px">⚖️ Tinglysning</a>
        </div>
      </div>
    </a>`;
}}

function scrollToCard(idx) {{
  const el = document.getElementById("card-" + idx);
  if (el) {{
    document.querySelectorAll(".bolig-card").forEach(c => c.classList.remove("active"));
    el.classList.add("active");
    el.scrollIntoView({{behavior: "smooth", block: "nearest"}});
  }}
}}

function highlightMarker(idx) {{
  if (markers[idx]) markers[idx].openPopup();
}}
function unhighlightMarker(idx) {{
  if (markers[idx]) markers[idx].closePopup();
}}

let visibleBoliger = BOLIGER;

function applyFilters() {{
  const type     = document.getElementById("filter-type").value;
  const afstand  = parseInt(document.getElementById("filter-afstand").value);
  const maxpris  = parseInt(document.getElementById("filter-maxpris").value) || Infinity;

  visibleBoliger = BOLIGER.filter(b =>
    (!type || b.type === type) &&
    b.afstand <= afstand &&
    (!maxpris || b.pris <= maxpris || b.pris === 0)
  );

  render();
}}

function render() {{
  cluster.clearLayers();
  markers = [];
  const liste = document.getElementById("kort-liste");
  liste.innerHTML = "";
  document.getElementById("result-count").textContent =
    visibleBoliger.length + " boliger inden for {MAX_AFSTAND_METER}m fra kysten";

  // Sorter: tættest på vand først
  const sorted = [...visibleBoliger].sort((a,b) => a.afstand - b.afstand);

  // Tilføj alle markører til cluster på én gang (hurtigere)
  const newMarkers = sorted.map((b, idx) => buildMarker(b, idx));
  markers = newMarkers;
  cluster.addLayers(newMarkers);

  // Render sidebar lazy – kun 50 ad gangen
  renderSidebarChunk(sorted, 0);

  document.getElementById("sidebar-header").textContent =
    visibleBoliger.length + " boliger – sorteret efter afstand til kyst";
}}

const CHUNK = 50;
function renderSidebarChunk(sorted, start) {{
  const liste = start === 0 ? document.getElementById("kort-liste") : document.getElementById("kort-liste");
  if (start === 0) liste.innerHTML = "";
  const end = Math.min(start + CHUNK, sorted.length);
  const frag = document.createDocumentFragment();
  for (let i = start; i < end; i++) {{
    const div = document.createElement("div");
    div.innerHTML = buildCard(sorted[i], i);
    frag.appendChild(div.firstChild);
  }}
  liste.appendChild(frag);
  if (end < sorted.length) {{
    requestAnimationFrame(() => renderSidebarChunk(sorted, end));
  }}
}}

render();
</script>
</body>
</html>"""

    with open(filnavn, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓ Kort gemt: {filnavn}")
    return filnavn


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    global MAX_AFSTAND_METER
    parser = argparse.ArgumentParser(description="Find boliger tæt på dansk kyst")
    parser.add_argument("--refresh", choices=["alle", "boliger", "kyst"],
                        help="Tving genhentning: 'alle', 'boliger' eller 'kyst'")
    parser.add_argument("--afstand", type=int, default=None,
                        help=f"Max afstand til kyst i meter (default: {MAX_AFSTAND_METER})")
    args = parser.parse_args()

    if args.afstand is not None:
        MAX_AFSTAND_METER = args.afstand
        print(f"  → Afstand overstyret til {MAX_AFSTAND_METER}m via argument")

    # Slet cache-filer hvis --refresh er angivet
    if args.refresh in ("alle", "kyst"):
        if os.path.exists(CACHE_KYST_FIL):
            os.remove(CACHE_KYST_FIL)
            print(f"🗑  Cache slettet: {CACHE_KYST_FIL}")
    if args.refresh in ("alle", "boliger"):
        if os.path.exists(CACHE_BOLIGER_FIL):
            os.remove(CACHE_BOLIGER_FIL)
            print(f"🗑  Cache slettet: {CACHE_BOLIGER_FIL}")

    print("=" * 60)
    print("  Ejendomme til salg max 200m fra danske farvande")
    print("=" * 60)
    
    # 1. Kystlinje (med cache)
    kyst_gdf = None
    if BRUG_CACHE:
        kyst_gdf = indlæs_cache(CACHE_KYST_FIL)
    if kyst_gdf is None:
        kyst_gdf = hent_kystlinje()
        if EKSKLUDER_VESTERHAV:
            kyst_gdf = ekskluder_vesterhav(kyst_gdf)
        else:
            print('    → Vesterhavet medtages')
        if BRUG_CACHE:
            gem_cache(kyst_gdf, CACHE_KYST_FIL)
    else:
        print("[1/4] Kystlinje indlæst fra cache ✓")

    # 2. Boligannoncer (med cache)
    boliger = None
    if BRUG_CACHE:
        boliger = indlæs_cache(CACHE_BOLIGER_FIL, max_alder_timer=CACHE_BOLIGER_MAX_ALDER_TIMER)
    if boliger is None:
        boliger = hent_boliger_fra_boliga()
        if BRUG_CACHE:
            gem_cache(boliger, CACHE_BOLIGER_FIL)
    else:
        print(f"[2/4] Boligannoncer indlæst fra cache ({len(boliger)} stk.) ✓")
    
    if not boliger:
        print("\n⚠ Ingen boliger hentet. Tjek API-forbindelsen og prøv igen.")
        return
    
    # 2b. Ekskluder byer/kommuner/postnumre
    boliger = filtrer_ekskluderede(boliger)

    # 3. Filtrer på afstand
    resultat = filtrer_nær_vand(boliger, kyst_gdf)
    
    if resultat.empty:
        print("\n⚠ Ingen boliger fundet inden for 150m. Prøv at øge MAX_AFSTAND_METER.")
        return
    
    # 4. Gem output
    print("\n[4/4] Gemmer resultater...")
    gem_csv(resultat)
    gem_kort(resultat)
    
    # Udskriv statistik
    print("\n" + "=" * 60)
    print("  RESULTAT-OVERSIGT")
    print("=" * 60)
    print(f"  Boliger inden for {MAX_AFSTAND_METER}m fra kyst: {len(resultat)}")
    print(f"  Heraf direkte vandkant (≤30m):  {len(resultat[resultat['afstand_m'] <= 30])}")
    print(f"  Heraf ≤75m:                     {len(resultat[resultat['afstand_m'] <= 75])}")
    print()
    
    if "pris" in resultat.columns:
        priser = resultat["pris"].dropna()
        if len(priser):
            print(f"  Prisinterval:  {int(priser.min()):,} – {int(priser.max()):,} kr.".replace(",", "."))
            print(f"  Median pris:   {int(priser.median()):,} kr.".replace(",", "."))
    print()
    
    if "type" in resultat.columns:
        print("  Fordeling på boligtype:")
        for t, n in resultat["type"].value_counts().items():
            print(f"    {t}: {n}")
    
    print()
    print(f"  Output: {OUTPUT_CSV} og {OUTPUT_HTML}")
    print("=" * 60)
    
    # Vis de 10 tætteste på vandet
    print("\n  TOP 10 TÆTTEST PÅ VANDET:")
    print("-" * 60)
    vis_kolonner = ["adresse", "by", "pris", "type", "kvm", "afstand_m"]
    vis_kolonner = [k for k in vis_kolonner if k in resultat.columns]
    print(resultat[vis_kolonner].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
