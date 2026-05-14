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
import re
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
BOLIG_TYPER = [1, 4, 5, 6, 7, 8, 10]  # 1=Villa, 4=Fritidshus, 5=Landejendom, 6=Villalejlighed, 7=Helårsgrund, 8=Fritidsgrund, 10=Andet/Tvangsauktion
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
CACHE_BOLIGER_MAX_ALDER_TIMER = 12               # Genhent boliger hvis cachen er ældre end X timer
CACHE_VINDM_FIL   = "cache_vindmoeller.pkl"      # Vindmøller (ændrer sig sjældent)
CACHE_SOL_FIL     = "cache_solceller.pkl"        # Solcelleanlæg (ændrer sig sjældent)

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


def hent_vindmoeller():
    """
    Henter danske vindmøller fra OpenStreetMap via Overpass API.
    Returnerer en GeoDataFrame med vindmøllepunkter i UTM32N (EPSG:25832).
    """
    print("\n[1b/4] Henter vindmøller fra OpenStreetMap...")

    query = """
    [out:json][timeout:120];
    (
      node["power"="generator"]["generator:source"="wind"](54.5,7.5,58.0,15.7);
    );
    out;
    """

    headers = {
        "User-Agent": "vandkant-boliger-script/1.0 (research project)",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
    }

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
            break
        except requests.exceptions.RequestException as e:
            print(f"    ⚠ Fejl ({e}) – prøver næste server...")
            r = None

    if r is None:
        raise RuntimeError("Alle Overpass-servere fejlede ved hentning af vindmøller.")

    data = r.json()
    punkter = []
    for el in data["elements"]:
        if el["type"] == "node":
            from shapely.geometry import Point
            punkter.append(Point(el["lon"], el["lat"]))

    if not punkter:
        raise RuntimeError("Ingen vindmøller hentet fra OSM.")

    gdf = gpd.GeoDataFrame(geometry=punkter, crs="EPSG:4326").to_crs(epsg=25832)
    print(f"    ✓ {len(gdf)} vindmøller hentet")
    return gdf


def hent_solceller():
    """
    Henter store solcelleanlæg fra OpenStreetMap via Overpass API.
    Returnerer en GeoDataFrame med solcellepunkter i UTM32N (EPSG:25832).
    """
    print("\n[1c/4] Henter solcelleanlæg fra OpenStreetMap...")

    query = """
    [out:json][timeout:120];
    (
      way["power"="plant"]["plant:source"="solar"](54.5,7.5,58.0,15.7);
      relation["power"="plant"]["plant:source"="solar"](54.5,7.5,58.0,15.7);
      way["power"="generator"]["generator:source"="solar"](54.5,7.5,58.0,15.7);
    );
    out center;
    """

    headers = {
        "User-Agent": "vandkant-boliger-script/1.0 (research project)",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
    }

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
            break
        except requests.exceptions.RequestException as e:
            print(f"    ⚠ Fejl ({e}) – prøver næste server...")
            r = None

    if r is None:
        raise RuntimeError("Alle Overpass-servere fejlede ved hentning af solcelleanlæg.")

    data = r.json()
    from shapely.geometry import Point
    punkter = []
    for el in data["elements"]:
        if el["type"] == "node":
            punkter.append(Point(el["lon"], el["lat"]))
        elif "center" in el:
            punkter.append(Point(el["center"]["lon"], el["center"]["lat"]))

    if not punkter:
        raise RuntimeError("Ingen solcelleanlæg hentet fra OSM.")

    gdf = gpd.GeoDataFrame(geometry=punkter, crs="EPSG:4326").to_crs(epsg=25832)
    print(f"    ✓ {len(gdf)} solcelleanlæg hentet")
    return gdf


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
        type_navne = {1: "Villa/Parcelhus", 2: "Rækkehus", 3: "Ejerlejlighed", 4: "Fritidshus", 5: "Landejendom", 6: "Villalejlighed", 7: "Helårsgrund", 8: "Fritidsgrund", 9: "Andelsbolig", 10: "Tvangsauktion"}
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
                # Brug secondaryPropertyType hvis den er mere specifik
                sek_type = bolig.get("secondaryPropertyType")
                bolig_type_navn = type_navne.get(sek_type, None) if sek_type and sek_type != 6 else None
                if not bolig_type_navn:
                    bolig_type_navn = type_navne.get(bolig_type, str(bolig_type))

                alle_boliger.append({
                    "id":           bolig.get("id", ""),
                    "guid":         bolig.get("guid", ""),
                    "adresse":      bolig.get("street", ""),
                    "postnummer":   bolig.get("zipCode", ""),
                    "by":           bolig.get("city", ""),
                    "pris":         bolig.get("price", 0),
                    "type":         bolig_type_navn,
                    "kvm":          bolig.get("size", 0),
                    "grundkvm":     bolig.get("lotSize", 0),
                    "vaerelser":    bolig.get("rooms", 0),
                    "byggeaar":     bolig.get("buildYear", ""),
                    "energimaerke": bolig.get("energyClass", ""),
                    "ouAddress":    str(bolig.get("ouAddress", "")),
                    "ouId":         str(bolig.get("ouId", "")),
                    "adresseId":    str(bolig.get("adresseId", "") or ""),
                    "tvangsauktion": bolig.get("isForeclosure", False),
                    "liggetid":     bolig.get("daysForSale", 0),
                    "sekundaerType": bolig.get("secondaryPropertyType", None),
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
def dedupliker_boliger(boliger):
    """Fjerner dubletter fra boliglisten baseret på unikke Boliga-id'er eller adresse/koordinater."""
    keys = {}
    for bolig in boliger:
        ou_id = str(bolig.get("ouId", "")).strip()
        ou_addr = str(bolig.get("ouAddress", "")).strip().lower()
        if ou_id and ou_id not in ("", "None"):
            # Primær nøgle: ouId er ejendoms-ID og er unikt per fysisk ejendom
            nøgle = ("ou", ou_id)
        elif bolig.get("guid"):
            nøgle = ("guid", str(bolig["guid"]).strip())
        elif ou_addr and ou_id:
            nøgle = ("ouaddr", ou_addr, ou_id)
        else:
            adresse = re.sub(r"\s+", " ", str(bolig.get("adresse", "")).strip().lower())
            nøgle = ("addr", adresse, str(bolig.get("postnummer", "")).strip(), f"{bolig.get('lat', '')}|{bolig.get('lng', '')}")
        if nøgle not in keys:
            keys[nøgle] = bolig

    fjernet = len(boliger) - len(keys)
    if fjernet:
        print(f"  → Fjernet {fjernet} dubletter fra boligdata")
    return list(keys.values())


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

    # Fjern andelsboliger (dukker op under type Grund)
    # secondaryPropertyType 6 = andelsbolig ifølge Boligas API
    før_andel = len(resultat)
    resultat = [b for b in resultat if not (
        b.get("sekundaerType") == 6 or
        str(b.get("adresse", "")).upper().startswith("A/B") or
        "andel" in str(b.get("adresse", "")).lower()
    )]
    andel_fjernet = før_andel - len(resultat)
    if andel_fjernet:
        print(f"  → Ekskluderet {andel_fjernet} andelsboliger")

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


def beregn_afstand_vindmoeller(gdf, vindm_gdf):
    """Tilføjer kolonne afstand_vindm_m: afstand til nærmeste vindmølle (meter)."""
    print(f"\n[3b/4] Beregner afstand til nærmeste vindmølle for {len(gdf)} boliger...")
    samlet = vindm_gdf.geometry.union_all()
    gdf = gdf.copy()
    afstande = [round(samlet.distance(geom), 0) for geom in tqdm(gdf.geometry, desc="  Vindmølleafstand")]
    gdf["afstand_vindm_m"] = afstande
    print(f"  ✓ Afstande beregnet (median {int(gdf['afstand_vindm_m'].median())}m)")
    return gdf


def beregn_afstand_solceller(gdf, sol_gdf):
    """Tilføjer kolonne afstand_sol_m: afstand til nærmeste solcelleanlæg (meter)."""
    print(f"\n[3c/4] Beregner afstand til nærmeste solcelleanlæg for {len(gdf)} boliger...")
    samlet = sol_gdf.geometry.union_all()
    gdf = gdf.copy()
    afstande = [round(samlet.distance(geom), 0) for geom in tqdm(gdf.geometry, desc="  Solcelleafstand")]
    gdf["afstand_sol_m"] = afstande
    print(f"  ✓ Afstande beregnet (median {int(gdf['afstand_sol_m'].median())}m)")
    return gdf


# ─────────────────────────────────────────────
# TRIN 4: Gem resultater
# ─────────────────────────────────────────────
def gem_csv(gdf, filnavn=OUTPUT_CSV):
    """Gemmer resultater som CSV."""
    kolonner = ["adresse", "postnummer", "by", "pris", "type", "kvm",
                "vaerelser", "byggeaar", "energimaerke", "liggetid", "afstand_m", "afstand_vindm_m", "afstand_sol_m", "lat", "lng", "url"]
    
    # Behold kun kolonner der faktisk findes
    kolonner = [k for k in kolonner if k in gdf.columns]
    
    df = pd.DataFrame(gdf[kolonner])
    df.to_csv(filnavn, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel-kompatibilitet
    print(f"  ✓ CSV gemt: {filnavn}")
    return filnavn


def gem_boliger_json(gdf, filnavn="boliger.json"):
    """Gemmer let JSON til filtersiden (by, postnr, pris, type, afstand og liggetid)."""
    import json as _json
    data = []
    for _, row in gdf.iterrows():
        data.append({
            "by":       str(row.get("by", "")),
            "pnr":      str(row.get("postnummer", "")),
            "pris":     int(row["pris"]) if pd.notna(row.get("pris")) and row.get("pris") else 0,
            "type":     str(row.get("type", "")),
            "afstand":  float(row["afstand_m"]),
            "vindm":    int(row["afstand_vindm_m"]) if pd.notna(row.get("afstand_vindm_m")) else 0,
            "sol":      int(row["afstand_sol_m"]) if pd.notna(row.get("afstand_sol_m")) else 0,
            "liggetid": int(row["liggetid"]) if pd.notna(row.get("liggetid")) and row.get("liggetid") else 0,
        })
    with open(filnavn, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False)
    print(f"  ✓ boliger.json gemt: {filnavn}")


def gem_kort(gdf, filnavn=OUTPUT_HTML, vindm_gdf=None):
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
            "kvm":       int(row["kvm"]) if pd.notna(row.get("kvm")) and row.get("kvm") else 0,
            "grundkvm":  int(row["grundkvm"]) if pd.notna(row.get("grundkvm")) and row.get("grundkvm") else 0,
            "vaerelser": int(row["vaerelser"]) if pd.notna(row.get("vaerelser")) and row.get("vaerelser") else 0,
            "byggeaar":  str(row.get("byggeaar", "") or ""),
            "energi":    str(row.get("energimaerke", "") or ""),
            "afstand":   float(row["afstand_m"]),
            "vindm":     int(row["afstand_vindm_m"]) if pd.notna(row.get("afstand_vindm_m")) else 0,
            "sol":       int(row["afstand_sol_m"]) if pd.notna(row.get("afstand_sol_m")) else 0,
            "liggetid":  int(row["liggetid"]) if pd.notna(row.get("liggetid")) and row.get("liggetid") else 0,
            "url":       str(row.get("url", "#")),
            "ouAddress": str(row.get("ouAddress", "")),
            "ouId":      str(row.get("ouId", "")),
            "adresseId": str(row.get("adresseId", "") or ""),
            "bfeNr":     str(row.get("bfeNr", "")),
            "dingeo":    (lambda pnr, by, adr: f"https://www.dingeo.dk/adresse/{pnr}-{by.lower().replace(' ','-').replace('æ','ae').replace('ø','oe').replace('å','aa')}/{adr.lower().replace(' ','-').replace('æ','ae').replace('ø','oe').replace('å','aa')}/" if pnr and by and adr else "")(str(row.get("postnummer","")), str(row.get("by","")), str(row.get("adresse","") or "")),
            "billede":   (lambda i: f"https://i.boliga.org/dk/550x/{str(i)[:4]}/{i}.jpg" if i else "")(
                next((v for v in [row.get("id"), row.get("guid")] if v and str(v).isdigit()), None)
            ),
        })

    import json as _json
    data_js = _json.dumps(boliger_json, ensure_ascii=False)

    vindm_antal = len(vindm_gdf) if vindm_gdf is not None else 0

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
<script src="https://cdn.jsdelivr.net/npm/suncalc@1.9.0/suncalc.min.js"></script>
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

  .filter-group {{ margin-bottom: 14px; }}
  .filter-group label {{ display:block; font-size:12px; font-weight:600; color:#555; margin-bottom:4px; }}
  .range-row {{ display:flex; justify-content:space-between; font-size:12px; color:#1a5276; font-weight:600; margin-bottom:4px; }}
  .dual-range {{ position:relative; height:20px; }}
  .dual-range input[type=range] {{
    position:absolute; width:100%; height:4px; background:transparent;
    pointer-events:none; -webkit-appearance:none; outline:none;
  }}
  .dual-range input[type=range]::-webkit-slider-thumb {{
    -webkit-appearance:none; width:18px; height:18px; border-radius:50%;
    background:#1a5276; cursor:pointer; pointer-events:all;
    border:2px solid white; box-shadow:0 1px 4px rgba(0,0,0,.3);
  }}
  .dual-range input[type=range]::-webkit-slider-runnable-track {{
    height:4px; background:#dde8f0; border-radius:2px;
  }}

  .kl-btn {{
    width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;
    cursor: pointer; border-radius: 50%; background: #1a1a2e; color: white;
    box-shadow: 0 2px 8px rgba(0,0,0,.35); transition: background .15s, transform .1s;
    user-select: none; flex-shrink: 0;
  }}
  .kl-btn:hover {{ background: #2c2c4e; transform: scale(1.08); }}
  .kl-btn.aktiv {{ background: #1a5276; box-shadow: 0 2px 8px rgba(26,82,118,.5); }}

  @media (max-width: 700px) {{
    #map {{ right: 0; bottom: 45vh; }}
    #sidebar {{ top: 55vh; right: 0; left: 0; width: 100%; }}
    #kortlag-panel {{ left: 6px; top: auto; bottom: 47vh; }}
  }}
</style>
</head>
<body>

<div id="topbar">
  <h1>🌊 Vandkant Boliger</h1>
  <span class="count" id="result-count">{len(gdf)} boliger inden for {MAX_AFSTAND_METER}m fra kysten</span>
  <span class="count" style="margin-left:auto;margin-right:16px;font-size:11px;opacity:.7">Opdateret fra Boliga: {__import__("datetime").datetime.now().strftime("%d.%m.%Y %H:%M")}</span>
  <div class="filters">
    <div style="position:relative;display:inline-block">
      <button id="type-btn" onclick="toggleTypeMenu()" style="border:none;border-radius:6px;padding:5px 10px;font-size:13px;background:rgba(255,255,255,.15);color:white;cursor:pointer;outline:none">
        Boligtype ▾
      </button>
      <div id="type-menu" style="display:none;position:absolute;top:34px;left:0;background:white;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.2);padding:8px;z-index:2000;min-width:180px">
        <div id="type-checkboxes"></div>
      </div>
    </div>
    <button id="filter-btn" onclick="toggleFilterPanel()" style="border:none;border-radius:6px;padding:5px 12px;font-size:13px;background:rgba(255,255,255,.15);color:white;cursor:pointer;outline:none">
      Filtre ▾
    </button>
    <select id="filter-afstand" onchange="applyFilters()" title="Max afstand til kyst">
      <option value="200">Max 200m</option>
      <option value="75">Max 75m</option>
      <option value="30">Max 30m</option>
    </select>

  </div>
  <!-- Filter panel -->
  <div id="filter-panel" style="display:none;position:fixed;top:48px;right:380px;width:420px;background:white;border:1px solid #ddd;border-top:none;border-radius:0 0 0 10px;z-index:999;box-shadow:-4px 4px 16px rgba(0,0,0,.15);flex-direction:column;max-height:calc(100vh - 48px)">

    <!-- Faner -->
    <div style="display:flex;border-bottom:2px solid #eee">
      <button id="tab-filtre" onclick="skiftTab('filtre')" style="flex:1;padding:10px;border:none;background:none;font-size:13px;font-weight:600;color:#1a5276;border-bottom:2px solid #1a5276;margin-bottom:-2px;cursor:pointer">Filtre</button>
      <button id="tab-byer" onclick="skiftTab('byer')" style="flex:1;padding:10px;border:none;background:none;font-size:13px;font-weight:600;color:#999;cursor:pointer">Byer <span id="byer-badge" style="display:none;background:#e74c3c;color:white;border-radius:10px;padding:1px 6px;font-size:10px"></span></button>
      <button id="tab-lag" onclick="skiftTab('lag')" style="flex:1;padding:10px;border:none;background:none;font-size:13px;font-weight:600;color:#999;cursor:pointer">Kortlag</button>
      <button onclick="nulstilFiltre()" style="padding:8px 12px;border:none;background:none;font-size:11px;color:#999;cursor:pointer;border-left:1px solid #eee">Nulstil</button>
    </div>

    <!-- Tab: Sliders -->
    <div id="panel-filtre" style="padding:14px;overflow-y:auto">
      <div class="filter-group">
        <label>Pris</label>
        <div class="range-row"><span id="lbl-minpris">0 kr.</span><span id="lbl-maxpris">40 mio.</span></div>
        <div class="dual-range">
          <input type="range" id="slider-minpris" min="0" max="40000000" step="250000" value="0" oninput="updateSlider('pris')">
          <input type="range" id="slider-maxpris" min="0" max="40000000" step="250000" value="40000000" oninput="updateSlider('pris')">
        </div>
      </div>
      <div class="filter-group">
        <label>Boligareal (m²)</label>
        <div class="range-row"><span id="lbl-minkvm">0 m²</span><span id="lbl-maxkvm">500+ m²</span></div>
        <div class="dual-range">
          <input type="range" id="slider-minkvm" min="0" max="500" step="10" value="0" oninput="updateSlider('kvm')">
          <input type="range" id="slider-maxkvm" min="0" max="500" step="10" value="500" oninput="updateSlider('kvm')">
        </div>
      </div>
      <div class="filter-group">
        <label>Grundareal (m²)</label>
        <div class="range-row"><span id="lbl-mingrund">0 m²</span><span id="lbl-maxgrund">10.000+ m²</span></div>
        <div class="dual-range">
          <input type="range" id="slider-mingrund" min="0" max="10000" step="100" value="0" oninput="updateSlider('grund')">
          <input type="range" id="slider-maxgrund" min="0" max="10000" step="100" value="10000" oninput="updateSlider('grund')">
        </div>
      </div>
      <div class="filter-group">
        <label>Liggetid (dage)</label>
        <div class="range-row"><span id="lbl-minlig">0 dage</span><span id="lbl-maxlig">365+ dage</span></div>
        <div class="dual-range">
          <input type="range" id="slider-minlig" min="0" max="365" step="1" value="0" oninput="updateSlider('lig')">
          <input type="range" id="slider-maxlig" min="0" max="365" step="1" value="365" oninput="updateSlider('lig')">
        </div>
      </div>
      <div class="filter-group">
        <label>Min. afstand til vindmølle</label>
        <div class="range-row"><span id="lbl-vindm">0 m (alle)</span></div>
        <input type="range" id="slider-vindm" min="0" max="5000" step="100" value="0" style="width:100%" oninput="updateSlider('vindm')">
      </div>
      <div class="filter-group">
        <label>Min. afstand til solcelleanlæg</label>
        <div class="range-row"><span id="lbl-sol">0 m (alle)</span></div>
        <input type="range" id="slider-sol" min="0" max="5000" step="100" value="0" style="width:100%" oninput="updateSlider('sol')">
      </div>
      <div style="margin-top:10px;font-size:12px;color:#888;text-align:center" id="filter-result-info"></div>
    </div>

    <!-- Tab: Byer -->
    <div id="panel-byer" style="display:none;flex-direction:column;flex:1;overflow:hidden">
      <div style="padding:10px 12px;border-bottom:1px solid #eee">
        <input id="by-soeg" type="text" placeholder="Søg kommune eller by..." oninput="tegn()"
          style="width:100%;padding:6px 10px;border:1px solid #ddd;border-radius:6px;font-size:13px;outline:none">
        <div style="display:flex;gap:12px;margin-top:6px;font-size:12px;color:#1a5276">
          <a style="cursor:pointer;text-decoration:underline" onclick="selectAlleBy(true)">Vælg alle</a>
          <a style="cursor:pointer;text-decoration:underline" onclick="selectAlleBy(false)">Fravælg alle</a>
          <span id="by-info" style="margin-left:auto;color:#888"></span>
        </div>
      </div>
      <div style="overflow-y:auto;flex:1">
        <table style="width:100%;border-collapse:collapse;font-size:12px">
          <thead style="position:sticky;top:0;z-index:1">
            <tr>
              <th style="width:32px;background:#f0f4f8;padding:6px;border-bottom:2px solid #ddd;text-align:center">✓</th>
              <th id="bth-navn" onclick="bySort('navn')" style="background:#f0f4f8;padding:6px 8px;border-bottom:2px solid #ddd;cursor:pointer;text-align:left">Kommune</th>
              <th style="background:#f0f4f8;padding:6px 8px;border-bottom:2px solid #ddd;text-align:left;color:#999;font-weight:400">Postnr</th>
              <th id="bth-bef" onclick="bySort('bef')" style="background:#f0f4f8;padding:6px 8px;border-bottom:2px solid #ddd;cursor:pointer;text-align:right">Indb.</th>
              <th id="bth-boliger" onclick="bySort('boliger')" style="background:#f0f4f8;padding:6px 8px;border-bottom:2px solid #ddd;cursor:pointer;text-align:right">Boliger</th>
            </tr>
          </thead>
          <tbody id="by-tbody"></tbody>
        </table>
      </div>
    </div>

    <!-- Tab: Kortlag -->
    <div id="panel-lag" style="display:none;padding:14px;overflow-y:auto">
      <div style="font-size:12px;color:#555;font-weight:600;margin-bottom:10px">Skift kortlag til/fra:</div>

      <div style="display:flex;flex-direction:column;gap:8px">

        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px;border:1px solid #e0e0e0;border-radius:8px;background:#fafafa" onclick="toggleLuftfoto()">
          <span id="luftfoto-check" style="width:18px;height:18px;border-radius:4px;border:2px solid #555;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <span id="luftfoto-check-inner" style="display:none;width:10px;height:10px;background:#555;border-radius:2px"></span>
          </span>
          <span style="display:flex;flex-direction:column">
            <span style="font-weight:600;font-size:13px">🛰️ Luftfoto</span>
            <span style="font-size:11px;color:#888">Esri World Imagery</span>
          </span>
        </label>

        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px;border:1px solid #e0e0e0;border-radius:8px;background:#fafafa" onclick="toggleSolLys()">
          <span id="solind-check" style="width:18px;height:18px;border-radius:4px;border:2px solid #f39c12;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <span id="solind-check-inner" style="display:none;width:10px;height:10px;background:#f39c12;border-radius:2px"></span>
          </span>
          <span style="display:flex;flex-direction:column">
            <span style="font-weight:600;font-size:13px">☀️ Solens bane</span>
            <span style="font-size:11px;color:#888">SunCalc – sol-sti for valgt punkt og dato</span>
          </span>
        </label>

        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px;border:1px solid #e0e0e0;border-radius:8px;background:#fafafa" onclick="toggleStoj()">
          <span id="stoj-check" style="width:18px;height:18px;border-radius:4px;border:2px solid #8e44ad;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <span id="stoj-check-inner" style="display:none;width:10px;height:10px;background:#8e44ad;border-radius:2px"></span>
          </span>
          <span style="display:flex;flex-direction:column">
            <span style="font-weight:600;font-size:13px">🔊 Støj</span>
            <span style="font-size:11px;color:#888">Vejdirektoratet – vejstøjkort</span>
          </span>
        </label>

        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px;border:1px solid #e0e0e0;border-radius:8px;background:#fafafa" onclick="toggleOversvom()">
          <span id="oversvom-check" style="width:18px;height:18px;border-radius:4px;border:2px solid #2980b9;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <span id="oversvom-check-inner" style="display:none;width:10px;height:10px;background:#2980b9;border-radius:2px"></span>
          </span>
          <span style="display:flex;flex-direction:column">
            <span style="font-weight:600;font-size:13px">🌧️ Nedbør / oversvømmelse</span>
            <span style="font-size:11px;color:#888">Klimatilpasning.dk – havvand +20cm</span>
          </span>
        </label>

        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px;border:1px solid #e0e0e0;border-radius:8px;background:#fafafa" onclick="toggleMat()">
          <span id="mat-check" style="width:18px;height:18px;border-radius:4px;border:2px solid #1a5276;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <span id="mat-check-inner" style="display:none;width:10px;height:10px;background:#1a5276;border-radius:2px"></span>
          </span>
          <span style="display:flex;flex-direction:column">
            <span style="font-weight:600;font-size:13px">📐 Matrikler</span>
            <span style="font-size:11px;color:#888">Geodatastyrelsen – matrikelkort</span>
          </span>
        </label>

        <div style="height:1px;background:#eee;margin:4px 0"></div>
        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px;border:1px solid #e0e0e0;border-radius:8px;background:#fafafa" onclick="toggleVindmoellerLag()">
          <span id="vindm-check" style="width:18px;height:18px;border-radius:4px;border:2px solid #7c6daa;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <span id="vindm-check-inner" style="display:none;width:10px;height:10px;background:#7c6daa;border-radius:2px"></span>
          </span>
          <span style="display:flex;flex-direction:column">
            <span style="font-weight:600;font-size:13px">💨 Eksisterende vindmøller</span>
            <span style="font-size:11px;color:#888">BPST officielt register · {vindm_antal} afstandsmålte</span>
          </span>
          <span style="margin-left:auto;width:16px;height:16px;border-radius:50%;background:#7c6daa;flex-shrink:0"></span>
        </label>

        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px;border:1px solid #e0e0e0;border-radius:8px;background:#fafafa" onclick="toggleSolLag()">
          <span id="sol-check" style="width:18px;height:18px;border-radius:4px;border:2px solid #f4d03f;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <span id="sol-check-inner" style="display:none;width:10px;height:10px;background:#f4d03f;border-radius:2px"></span>
          </span>
          <span style="display:flex;flex-direction:column">
            <span style="font-weight:600;font-size:13px">☀️ Store solcelleanlæg</span>
            <span style="font-size:11px;color:#888">BPST officielt register</span>
          </span>
          <span style="margin-left:auto;width:16px;height:16px;border-radius:2px;background:#f4d03f;flex-shrink:0"></span>
        </label>

        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px;border:1px solid #e0e0e0;border-radius:8px;background:#fafafa" onclick="togglePlanLag()">
          <span id="planvindm-check" style="width:18px;height:18px;border-radius:4px;border:2px solid #e67e22;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <span id="planvindm-check-inner" style="display:none;width:10px;height:10px;background:#e67e22;border-radius:2px"></span>
          </span>
          <span style="display:flex;flex-direction:column">
            <span style="font-weight:600;font-size:13px">📋 Vindmølle-lokalplaner</span>
            <span style="font-size:11px;color:#888">Plandata.dk · vedtaget <span style="color:#e67e22">■</span> / forslag <span style="color:#f1c40f">■</span></span>
          </span>
          <span style="margin-left:auto;width:16px;height:16px;border-radius:4px;background:#f39c12;flex-shrink:0"></span>
        </label>
      </div>

      <div style="margin-top:14px;font-size:11px;color:#999;line-height:1.5">
        Klik på en lokalplan-polygon for at se plannavn, kommune og link til planen.<br>
        <a href="https://sologvindinfo.dk/spatialmap" target="_blank" style="color:#1a5276">Åbn fuld vindmøllekort på sologvindinfo.dk →</a>
      </div>
    </div>

  </div>
</div>

<div id="map"></div>

<!-- Sollys-kontrol panel -->
<div id="sollys-panel" style="display:none;position:fixed;top:60px;left:60px;z-index:950;background:white;border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,.2);padding:12px 16px;min-width:260px">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
    <span style="font-size:22px">☀️</span>
    <div>
      <div style="font-weight:600;font-size:13px">Solens bane</div>
      <div style="font-size:11px;color:#888">Klik på kortet for at vælge punkt</div>
    </div>
    <button onclick="toggleSolLys()" style="margin-left:auto;border:none;background:none;font-size:16px;cursor:pointer;color:#888">✕</button>
  </div>
  <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
    <input type="date" id="sollys-dato" style="flex:1;padding:5px 8px;border:1px solid #ddd;border-radius:6px;font-size:12px">
    <span id="sollys-tid-lbl" style="font-weight:700;font-size:14px;min-width:40px;text-align:center">12:00</span>
  </div>
  <input type="range" id="sollys-tid" min="0" max="1440" value="720" step="10" style="width:100%;accent-color:#f5a623" oninput="onSolTid()">
  <div id="sollys-info" style="font-size:11px;color:#888;margin-top:6px;text-align:center"></div>
</div>

<!-- Flydende kortlag-knapper (Boliga-stil) – venstre side af kortet -->
<div id="kortlag-panel" style="position:fixed;left:10px;top:110px;z-index:900;display:flex;flex-direction:column;gap:8px">
  <div id="kl-luftfoto" onclick="toggleLuftfoto()"         class="kl-btn" title="Luftfoto"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M21 3H3a2 2 0 00-2 2v14a2 2 0 002 2h18a2 2 0 002-2V5a2 2 0 00-2-2zm0 16H3V5h18v14zm-8-6l-3-4-4 5h14l-4-5-3 4z"/></svg></div>
  <div id="kl-solind"   onclick="toggleSolLys()"           class="kl-btn" title="Solens bane">☀️</div>
  <div id="kl-oversvom" onclick="toggleOversvom()"         class="kl-btn" title="Oversvømmelse"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a7 7 0 00-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 00-7-7zm-1 16.93V13H9l3-6v5h2l-3 6.93z"/></svg></div>
  <div id="kl-stoj"     onclick="toggleStoj()"             class="kl-btn" title="Støj"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg></div>
  <div id="kl-mat"      onclick="toggleMat()"              class="kl-btn" title="Matrikler"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4a2 2 0 00-2 2v16a2 2 0 002 2h16a2 2 0 002-2V4a2 2 0 00-2-2zm0 18H4V4h16v16zM6 6h5v5H6zm7 0h5v5h-5zm-7 7h5v5H6zm7 0h5v5h-5z"/></svg></div>
  <div id="kl-vindm"    onclick="toggleVindmoellerLag()"   class="kl-btn" title="Vindmøller"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L8 9l4 1-4 10h1l3-6 3 6h1L12 10l4-1L12 2zM6 17l-2 4h4l-2-4zm12 0l-2 4h4l-2-4z"/></svg></div>
  <div id="kl-sol"      onclick="toggleSolLag()"           class="kl-btn" title="Solcelleanlæg"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M3 6h18v12H3V6zm2 2v8h14V8H5zm1 1h3v2H6V9zm4 0h4v2h-4V9zm5 0h3v2h-3V9zM6 13h3v2H6v-2zm4 0h4v2h-4v-2zm5 0h3v2h-3v-2z"/></svg></div>
  <div id="kl-plan"     onclick="togglePlanLag()"          class="kl-btn" title="Vindmølle-lokalplaner"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm4 18H6V4h7v5h5v11zm-9-7h6v2H9v-2zm0-4h6v2H9V9z"/></svg></div>
</div>
<div id="sidebar">
  <div id="sidebar-header">Klik på en bolig for detaljer</div>
  <div id="kort-liste"></div>
</div>

<script>
const BOLIGER = {data_js};

// Byg type-dropdown dynamisk fra data
const alleTyper = [...new Set(BOLIGER.map(b => b.type))].sort();
const typeContainer = document.getElementById("type-checkboxes");
alleTyper.forEach(type => {{
  const label = document.createElement("label");
  label.style.cssText = "display:flex;align-items:center;gap:8px;padding:5px 8px;cursor:pointer;color:#333;font-size:13px;border-radius:4px";
  label.onmouseover = () => label.style.background = "#f0f7ff";
  label.onmouseout  = () => label.style.background = "";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.value = type;
  cb.checked = true;
  cb.onchange = applyFilters;
  label.appendChild(cb);
  label.appendChild(document.createTextNode(" " + type));
  typeContainer.appendChild(label);
}});

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

// Kort – to baselayers (topo og luftfoto)
const DF_USER = "LYNZPAJIGS", DF_PASS = "tJqYAcw8d-c";
const topoLag = L.tileLayer.wms(
  `https://services.datafordeler.dk/DKskaermkort/topo_skaermkort/1.0.0/wms?username=${{DF_USER}}&password=${{DF_PASS}}`, {{
  layers: "dtk_skaermkort_daempet", format: "image/png", transparent: false,
  version: "1.3.0", attribution: "© SDFI", maxZoom: 20
}});
const luftfotoLag = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}", {{
  attribution: "© Esri — Earthstar Geographics", maxZoom: 19
}});
const map = L.map("map", {{ layers: [topoLag] }}).setView([56.0, 10.5], 7);

function syncKl(id, aktiv) {{
  const el = document.getElementById(id);
  if (el) el.classList.toggle("aktiv", aktiv);
}}

let luftfotoAktiv = false;
function toggleLuftfoto() {{
  luftfotoAktiv = !luftfotoAktiv;
  if (luftfotoAktiv) {{ map.removeLayer(topoLag); luftfotoLag.addTo(map); }}
  else {{ map.removeLayer(luftfotoLag); topoLag.addTo(map); }}
  const ci = document.getElementById("luftfoto-check-inner");
  if (ci) ci.style.display = luftfotoAktiv ? "block" : "none";
  syncKl("kl-luftfoto", luftfotoAktiv);
}}

// Eksisterende vindmøller – WMS fra Bolig- og Planstyrelsen (BPST)
const BPST_WMS = "https://gisp.bpst.dk/ve/ows";
const vindmLag = L.tileLayer.wms(BPST_WMS, {{
  layers: "ve:vindmoeller",
  format: "image/png", transparent: true, version: "1.1.1", opacity: 0.9,
  attribution: "BPST – Bolig- og Planstyrelsen"
}});

let vindmLagAktiv = false;
function toggleVindmoellerLag() {{
  vindmLagAktiv = !vindmLagAktiv;
  if (vindmLagAktiv) {{ vindmLag.addTo(map); }} else {{ map.removeLayer(vindmLag); }}
  const ci = document.getElementById("vindm-check-inner");
  if (ci) ci.style.display = vindmLagAktiv ? "block" : "none";
  syncKl("kl-vindm", vindmLagAktiv);
}}

// Store solcelleanlæg – WMS fra BPST
const solLag = L.tileLayer.wms(BPST_WMS, {{
  layers: "ve:store_solcelleanlaeg",
  format: "image/png", transparent: true, version: "1.1.1", opacity: 0.85,
  attribution: "BPST – Bolig- og Planstyrelsen"
}});
let solLagAktiv = false;
function toggleSolLag() {{
  solLagAktiv = !solLagAktiv;
  if (solLagAktiv) {{ solLag.addTo(map); }} else {{ map.removeLayer(solLag); }}
  const ci = document.getElementById("sol-check-inner");
  if (ci) ci.style.display = solLagAktiv ? "block" : "none";
  syncKl("kl-sol", solLagAktiv);
}}

// ── Solens bane (SunCalc) ──────────────────────────────────────────
const solLysGroup = L.featureGroup();
let solLysAktiv = false;
let solLysCenter = null;

function sunPosToLatLng(lat, lng, azimuth, radiusKm) {{
  const R = 6371, d = radiusKm / R;
  const lat1 = lat * Math.PI / 180;
  const brg = azimuth + Math.PI; // SunCalc måler fra syd
  const lat2 = Math.asin(Math.sin(lat1)*Math.cos(d) + Math.cos(lat1)*Math.sin(d)*Math.cos(brg));
  const lng2 = lng * Math.PI / 180 + Math.atan2(Math.sin(brg)*Math.sin(d)*Math.cos(lat1), Math.cos(d)-Math.sin(lat1)*Math.sin(lat2));
  return L.latLng(lat2*180/Math.PI, lng2*180/Math.PI);
}}

function drawSolLys() {{
  solLysGroup.clearLayers();
  const c = solLysCenter || map.getCenter();
  const lat = c.lat, lng = c.lng;
  const dato = new Date(document.getElementById("sollys-dato").value || new Date());
  const minutter = parseInt(document.getElementById("sollys-tid").value);
  dato.setHours(Math.floor(minutter/60), minutter%60, 0, 0);
  const R = 0.25; // 250m radius

  // Sol-sti bue (solop til solnedgang)
  const arcPts = [];
  for (let m = 0; m < 1440; m += 5) {{
    const t = new Date(dato); t.setHours(0,m,0,0);
    const pos = SunCalc.getPosition(t, lat, lng);
    if (pos.altitude > 0.01) arcPts.push(sunPosToLatLng(lat, lng, pos.azimuth, R));
  }}
  if (arcPts.length > 1)
    L.polyline(arcPts, {{color:"#f5c842", weight:2, opacity:0.85, dashArray:"6,4"}}).addTo(solLysGroup);

  // Solens aktuelle position
  const pos = SunCalc.getPosition(dato, lat, lng);
  const times = SunCalc.getTimes(dato, lat, lng);
  if (pos.altitude > 0) {{
    const sunPt = sunPosToLatLng(lat, lng, pos.azimuth, R);
    // Sollinje
    L.polyline([L.latLng(lat,lng), sunPt], {{color:"#f5c842", weight:2, opacity:0.9}}).addTo(solLysGroup);
    // Skyggelinje
    L.polyline([L.latLng(lat,lng), sunPosToLatLng(lat, lng, pos.azimuth+Math.PI, R*0.7)],
      {{color:"#aaa", weight:3, opacity:0.6}}).addTo(solLysGroup);
    // Sol-ikon
    L.marker(sunPt, {{icon:L.divIcon({{html:"<div style='font-size:26px;line-height:1;filter:drop-shadow(0 1px 3px #f5a623)'>☀️</div>", iconAnchor:[13,13], className:""}})}} ).addTo(solLysGroup);
    const alt = Math.round(pos.altitude * 180/Math.PI);
    document.getElementById("sollys-info").textContent =
      `Højde: ${{alt}}° · Op: ${{times.sunrise.toLocaleTimeString("da-DK",{{hour:"2-digit",minute:"2-digit"}})}} · Ned: ${{times.sunset.toLocaleTimeString("da-DK",{{hour:"2-digit",minute:"2-digit"}})}}`;
  }} else {{
    document.getElementById("sollys-info").textContent = "Solen er under horisonten";
  }}
  // Centerpunkt
  L.circleMarker(L.latLng(lat,lng), {{radius:6, color:"#333", fillColor:"#fff", fillOpacity:1, weight:2}}).addTo(solLysGroup);
}}

function onSolTid() {{
  const m = parseInt(document.getElementById("sollys-tid").value);
  document.getElementById("sollys-tid-lbl").textContent =
    String(Math.floor(m/60)).padStart(2,"0") + ":" + String(m%60).padStart(2,"0");
  if (solLysAktiv) drawSolLys();
}}

function toggleSolLys() {{
  solLysAktiv = !solLysAktiv;
  const panel = document.getElementById("sollys-panel");
  panel.style.display = solLysAktiv ? "block" : "none";
  if (solLysAktiv) {{
    // Sæt dags dato som default
    const d = new Date();
    document.getElementById("sollys-dato").value = d.toISOString().substring(0,10);
    const m = d.getHours()*60 + d.getMinutes();
    document.getElementById("sollys-tid").value = m;
    onSolTid();
    solLysGroup.addTo(map);
    document.getElementById("sollys-dato").oninput = drawSolLys;
    map.on("click", function(e) {{ if(solLysAktiv) {{ solLysCenter = e.latlng; drawSolLys(); }} }});
  }} else {{
    map.removeLayer(solLysGroup);
    solLysCenter = null;
  }}
  const ci = document.getElementById("solind-check-inner");
  if (ci) ci.style.display = solLysAktiv ? "block" : "none";
  syncKl("kl-solind", solLysAktiv);
}}

// Vejstøj – Vejdirektoratets WMS
const stojLag = L.tileLayer.wms("https://gis.vd.dk/arcgis/services/OffentligData/Stoej/MapServer/WmsServer", {{
  layers: "0", format: "image/png", transparent: true, version: "1.3.0", opacity: 0.65,
  attribution: "Vejdirektoratet"
}});
let stojAktiv = false;
function toggleStoj() {{
  stojAktiv = !stojAktiv;
  if (stojAktiv) {{ stojLag.addTo(map); }} else {{ map.removeLayer(stojLag); }}
  const ci = document.getElementById("stoj-check-inner");
  if (ci) ci.style.display = stojAktiv ? "block" : "none";
  syncKl("kl-stoj", stojAktiv);
}}

// Oversvømmelsesrisiko – Klimatilpasning.dk
const oversvomLag = L.tileLayer.wms(
  `https://wms.datafordeler.dk/DHMNedboer/dhm/1.0.0/WMS?username=${{DF_USER}}&password=${{DF_PASS}}`, {{
  layers: "dhm_kote_0_5_m", format: "image/png", transparent: true, version: "1.3.0", opacity: 0.65,
  attribution: "© Styrelsen for Dataforsyning og Infrastruktur"
}});
let oversvomAktiv = false;
function toggleOversvom() {{
  oversvomAktiv = !oversvomAktiv;
  if (oversvomAktiv) {{ oversvomLag.addTo(map); }} else {{ map.removeLayer(oversvomLag); }}
  const ci = document.getElementById("oversvom-check-inner");
  if (ci) ci.style.display = oversvomAktiv ? "block" : "none";
  syncKl("kl-oversvom", oversvomAktiv);
}}

// Matrikelkort – Datafordeler MATRIKLEN2
const matLag = L.tileLayer.wms(
  "https://services.datafordeler.dk/MATRIKLEN2/MatGaeldendeOgForeloebigWMS/1.0.0/WMS?username=LYNZPAJIGS&password=tJqYAcw8d-c&token=4ed34c05cdeb91158ddb123f4958fb60", {{
  layers: "MatrikelSkel_Gaeldende,OptagetVej_Gaeldende,Centroide_Gaeldende",
  styles: "Roede_skel,Roed_OptagetVej,Sorte_centroider",
  format: "image/png", transparent: true, version: "1.3.0", opacity: 0.8,
  attribution: "Geodatastyrelsen – Datafordeler"
}});
let matAktiv = false;
function toggleMat() {{
  matAktiv = !matAktiv;
  if (matAktiv) {{ matLag.addTo(map); }} else {{ map.removeLayer(matLag); }}
  const ci = document.getElementById("mat-check-inner");
  if (ci) ci.style.display = matAktiv ? "block" : "none";
  syncKl("kl-mat", matAktiv);
}}

// Vindmølle-lokalplaner lag
function fmtDato(d) {{ return d ? d.substring(0,10) : null; }}
function planPopup(f) {{
  const p = f.properties;
  const mw = p.megawatt ? `<br>Kapacitet: ${{p.megawatt}} MW` : "";
  const dato = p.datovedt ? `<br>Vedtaget: ${{fmtDato(p.datovedt)}}` : (p.datoforsl ? `<br>Forslag: ${{fmtDato(p.datoforsl)}}` : "");
  const link = p.doklink ? `<br><a href="${{p.doklink}}" target="_blank" style="color:#1a5276">Se lokalplan →</a>` : "";
  return `<div style="font-size:13px;max-width:220px"><b>${{p.plannavn || "Vindmølle-lokalplan"}}</b><br>${{p.kommunenavn || ""}}${{dato}}${{mw}}${{link}}</div>`;
}}

// Vindmølle-lokalplaner som WMS tile-lag fra Plandata.dk
const PLANDATA_WMS = "https://geoserver.plandata.dk/geoserver/wms";
const planVedtagetLag = L.tileLayer.wms(PLANDATA_WMS, {{
  layers: "pdk:theme_pdk_lokalplan_vedtaget_vindmoelle",
  format: "image/png", transparent: true, version: "1.1.1", opacity: 0.75,
  attribution: "Plandata.dk"
}});
const planForslagLag = L.tileLayer.wms(PLANDATA_WMS, {{
  layers: "pdk:theme_pdk_lokalplan_forslag_vindmoelle",
  format: "image/png", transparent: true, version: "1.1.1", opacity: 0.85,
  attribution: "Plandata.dk"
}});

// GetFeatureInfo klik – henter planinfo fra Plandata WMS
let planKlikHandler = null;
async function planGetInfo(e) {{
  const bounds = map.getBounds();
  const size = map.getSize();
  const pt = map.latLngToContainerPoint(e.latlng);
  const url = PLANDATA_WMS +
    "?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetFeatureInfo" +
    "&LAYERS=pdk:theme_pdk_lokalplan_vedtaget_vindmoelle,pdk:theme_pdk_lokalplan_forslag_vindmoelle" +
    "&QUERY_LAYERS=pdk:theme_pdk_lokalplan_vedtaget_vindmoelle,pdk:theme_pdk_lokalplan_forslag_vindmoelle" +
    "&INFO_FORMAT=application/json&FEATURE_COUNT=3" +
    "&SRS=EPSG:4326" +
    `&BBOX=${{bounds.getWest()}},${{bounds.getSouth()}},${{bounds.getEast()}},${{bounds.getNorth()}}` +
    `&WIDTH=${{size.x}}&HEIGHT=${{size.y}}&X=${{Math.round(pt.x)}}&Y=${{Math.round(pt.y)}}`;
  try {{
    const data = await (await fetch(url)).json();
    if (data.features && data.features.length > 0)
      L.popup().setLatLng(e.latlng).setContent(planPopup(data.features[0])).openOn(map);
  }} catch(err) {{}}
}}

let planLagAktiv = false;
function togglePlanLag() {{
  planLagAktiv = !planLagAktiv;
  if (planLagAktiv) {{
    planVedtagetLag.addTo(map); planForslagLag.addTo(map);
    map.on("click", planGetInfo);
  }} else {{
    map.removeLayer(planVedtagetLag); map.removeLayer(planForslagLag);
    map.off("click", planGetInfo);
  }}
  const ci = document.getElementById("planvindm-check-inner");
  if (ci) ci.style.display = planLagAktiv ? "block" : "none";
  syncKl("kl-plan", planLagAktiv);
}}

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
      <table style="width:100%;border-collapse:collapse;font-size:12px;margin:6px 0">
        <tr>
          <td style="color:#888;padding:2px 6px 2px 0">Boligtype</td>
          <td style="font-weight:600">${{b.type || "–"}}</td>
        </tr>
        <tr>
          <td style="color:#888;padding:2px 6px 2px 0">Boligstørrelse</td>
          <td style="font-weight:600">${{b.kvm ? b.kvm + " m²" : "–"}}</td>
        </tr>
        <tr>
          <td style="color:#888;padding:2px 6px 2px 0">Grundstørrelse</td>
          <td style="font-weight:600">${{b.grundkvm ? b.grundkvm.toLocaleString("da-DK") + " m²" : "–"}}</td>
        </tr>
        <tr>
          <td style="color:#888;padding:2px 6px 2px 0">Antal værelser</td>
          <td style="font-weight:600">${{b.vaerelser || "–"}}</td>
        </tr>
        <tr>
          <td style="color:#888;padding:2px 6px 2px 0">Byggeår</td>
          <td style="font-weight:600">${{b.byggeaar || "–"}}</td>
        </tr>
        <tr>
          <td style="color:#888;padding:2px 6px 2px 0">Energimærke</td>
          <td style="font-weight:600">${{b.energi && b.energi !== "-" ? b.energi : "–"}}</td>
        </tr>
        <tr>
          <td style="color:#888;padding:2px 6px 2px 0">Liggetid</td>
          <td style="font-weight:600">${{b.liggetid ? b.liggetid + " dage" : "–"}}</td>
        </tr>
        <tr>
          <td style="color:#888;padding:4px 6px 2px 0">Afstand til kyst</td>
          <td style="font-weight:600;color:#c0392b">🌊 ${{b.afstand}} m</td>
        </tr>
        <tr>
          <td style="color:#888;padding:2px 6px 2px 0">Nærmeste vindmølle</td>
          <td style="font-weight:600;color:${{b.vindm < 500 ? '#c0392b' : b.vindm < 1000 ? '#e67e22' : '#27ae60'}}">💨 ${{b.vindm ? b.vindm.toLocaleString("da-DK") + " m" : "–"}}</td>
        </tr>
      </table>
      <a class="popup-link" href="https://www.boliga.dk/adresse/${{b.ouAddress}}-${{b.ouId}}" target="_blank">Se annonce på Boliga →</a>
      <a class="popup-link" style="margin-top:6px;background:#e67e22" href="https://www.boligsiden.dk/adresse/${{b.ouAddress}}" target="_blank">Se annonce på Boligsiden →</a>
      ${{b.bfeNr ? `<a class="popup-link" style="margin-top:6px;background:#1a6b3a" href="https://www.matriklen.dk/#/kort/sfe/${{b.bfeNr}}" target="_blank">🗺 Matrikel →</a>` : ""}}
      ${{b.bfeNr ? `<a class="popup-link" style="margin-top:6px;background:#7d3c98" href="https://www.ois.dk/search/${{b.bfeNr}}" target="_blank">📋 OIS →</a>` : ""}}
      <a class="popup-link" style="margin-top:6px;background:#1a4a6b" href="https://www.tinglysning.dk/tmv/forespoergul" target="_blank">⚖️ Tinglysning →</a>
      ${{b.dingeo ? `<a class="popup-link" style="margin-top:6px;background:#2e7d32" href="${{b.dingeo}}" target="_blank">📍 Dingeo →</a>` : ""}}
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
        <table style="width:100%;margin-top:8px;border-collapse:collapse;font-size:12px">
          <tr>
            <td style="color:#888;padding:2px 4px 2px 0">Boligtype</td>
            <td style="color:#888;padding:2px 4px">Boligstørrelse</td>
            <td style="color:#888;padding:2px 0">Grundstørrelse</td>
          </tr>
          <tr>
            <td style="font-weight:600;padding:0 4px 4px 0">${{b.type || "–"}}</td>
            <td style="font-weight:600;padding:0 4px 4px">${{b.kvm ? b.kvm + " m²" : "–"}}</td>
            <td style="font-weight:600;padding:0 0 4px">${{b.grundkvm ? b.grundkvm.toLocaleString("da-DK") + " m²" : "–"}}</td>
          </tr>
          <tr>
            <td style="color:#888;padding:2px 4px 2px 0">Antal værelser</td>
            <td style="color:#888;padding:2px 4px">Byggeår</td>
            <td style="color:#888;padding:2px 0">Energimærke</td>
          </tr>
          <tr>
            <td style="font-weight:600;padding:0 4px 4px 0">${{b.vaerelser || "–"}}</td>
            <td style="font-weight:600;padding:0 4px 4px">${{b.byggeaar || "–"}}</td>
            <td style="font-weight:600;padding:0 0 4px">${{b.energi && b.energi !== "-" ? b.energi : "–"}}</td>
          </tr>
          <tr>
            <td style="color:#888;padding:2px 4px 2px 0" colspan="2">Liggetid</td>
            <td style="color:#888;padding:2px 0">På markedet</td>
          </tr>
          <tr>
            <td style="font-weight:600;padding:0 4px 0 0" colspan="2">${{b.liggetid ? b.liggetid + " dage" : "–"}}</td>
            <td style="font-weight:600;padding:0">${{b.liggetid > 180 ? "⚠ Længe" : b.liggetid > 90 ? "Middel" : "Ny"}}</td>
          </tr>
        </table>
        ${{afstandBadge(b.afstand)}}
        ${{b.vindm > 0 ? `<span class="card-badge" style="background:${{b.vindm < 500 ? '#e74c3c' : b.vindm < 1000 ? '#e67e22' : '#27ae60'}};color:white;font-size:10px;padding:2px 7px;border-radius:10px;margin-top:3px;display:inline-block">💨 ${{b.vindm.toLocaleString("da-DK")}}m til vindmølle</span>` : ""}}
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
          <a href="https://www.boligsiden.dk/adresse/${{b.ouAddress}}" target="_blank" onclick="event.stopPropagation()" style="font-size:11px;color:#e67e22;text-decoration:none;font-weight:600;border:1px solid #e67e22;border-radius:4px;padding:2px 6px">🏠 Boligsiden</a>
          ${{b.bfeNr ? `<a href="https://www.matriklen.dk/#/kort/sfe/${{b.bfeNr}}" target="_blank" onclick="event.stopPropagation()" style="font-size:11px;color:#1a6b3a;text-decoration:none;font-weight:600;border:1px solid #1a6b3a;border-radius:4px;padding:2px 6px">🗺 Matrikel</a>` : ""}}
          ${{b.bfeNr ? `<a href="https://www.ois.dk/search/${{b.bfeNr}}" target="_blank" onclick="event.stopPropagation()" style="font-size:11px;color:#7d3c98;text-decoration:none;font-weight:600;border:1px solid #7d3c98;border-radius:4px;padding:2px 6px">📋 OIS</a>` : ""}}
          <a href="https://www.tinglysning.dk/tmv/forespoergul" target="_blank" onclick="event.stopPropagation()" style="font-size:11px;color:#1a4a6b;text-decoration:none;font-weight:600;border:1px solid #1a4a6b;border-radius:4px;padding:2px 6px">⚖️ Tinglysning</a>
          ${{b.dingeo ? `<a href="${{b.dingeo}}" target="_blank" onclick="event.stopPropagation()" style="font-size:11px;color:#2e7d32;text-decoration:none;font-weight:600;border:1px solid #2e7d32;border-radius:4px;padding:2px 6px">📍 Dingeo</a>` : ""}}
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

function toggleFilterPanel() {{
  const p = document.getElementById("filter-panel");
  const isOpen = p.style.display === "flex";
  p.style.display = isOpen ? "none" : "flex";
  document.getElementById("filter-btn").textContent = isOpen ? "Filtre ▾" : "Filtre ▴";
}}

function fmtPrisLbl(v) {{
  if (v >= 1000000) return (v/1000000).toFixed(v % 1000000 === 0 ? 0 : 1) + " mio.";
  if (v >= 1000) return Math.round(v/1000) + " t.";
  return v + " kr.";
}}

function updateSlider(type) {{
  if (type === 'pris') {{
    let min = parseInt(document.getElementById("slider-minpris").value);
    let max = parseInt(document.getElementById("slider-maxpris").value);
    if (min > max) {{ document.getElementById("slider-minpris").value = max; min = max; }}
    document.getElementById("lbl-minpris").textContent = fmtPrisLbl(min);
    document.getElementById("lbl-maxpris").textContent = max >= 40000000 ? "40+ mio." : fmtPrisLbl(max);
  }} else if (type === 'kvm') {{
    let min = parseInt(document.getElementById("slider-minkvm").value);
    let max = parseInt(document.getElementById("slider-maxkvm").value);
    if (min > max) {{ document.getElementById("slider-minkvm").value = max; min = max; }}
    document.getElementById("lbl-minkvm").textContent = min + " m²";
    document.getElementById("lbl-maxkvm").textContent = max >= 500 ? "500+ m²" : max + " m²";
  }} else if (type === 'grund') {{
    let min = parseInt(document.getElementById("slider-mingrund").value);
    let max = parseInt(document.getElementById("slider-maxgrund").value);
    if (min > max) {{ document.getElementById("slider-mingrund").value = max; min = max; }}
    document.getElementById("lbl-mingrund").textContent = min.toLocaleString("da-DK") + " m²";
    document.getElementById("lbl-maxgrund").textContent = max >= 10000 ? "10.000+ m²" : max.toLocaleString("da-DK") + " m²";
  }} else if (type === 'lig') {{
    let min = parseInt(document.getElementById("slider-minlig").value);
    let max = parseInt(document.getElementById("slider-maxlig").value);
    if (min > max) {{ document.getElementById("slider-minlig").value = max; min = max; }}
    document.getElementById("lbl-minlig").textContent = min + " dage";
    document.getElementById("lbl-maxlig").textContent = max >= 365 ? "365+ dage" : max + " dage";
  }} else if (type === 'vindm') {{
    const v = parseInt(document.getElementById("slider-vindm").value);
    document.getElementById("lbl-vindm").textContent = v === 0 ? "0 m (alle)" : "mindst " + v.toLocaleString("da-DK") + " m";
  }} else if (type === 'sol') {{
    const v = parseInt(document.getElementById("slider-sol").value);
    document.getElementById("lbl-sol").textContent = v === 0 ? "0 m (alle)" : "mindst " + v.toLocaleString("da-DK") + " m";
  }}
  applyFilters();
}}

function nulstilFiltre() {{
  document.getElementById("slider-minpris").value = 0;
  document.getElementById("slider-maxpris").value = 10000000;
  document.getElementById("slider-minkvm").value = 0;
  document.getElementById("slider-maxkvm").value = 500;
  document.getElementById("slider-mingrund").value = 0;
  document.getElementById("slider-maxgrund").value = 10000;
  document.getElementById("slider-minlig").value = 1;
  document.getElementById("slider-maxlig").value = 365;
  document.getElementById("slider-vindm").value = 0;
  document.getElementById("slider-sol").value = 0;
  ['pris','kvm','grund','lig','vindm','sol'].forEach(updateSlider);
}}

function toggleTypeMenu() {{
  const m = document.getElementById("type-menu");
  m.style.display = m.style.display === "none" ? "block" : "none";
}}

document.addEventListener("click", function(e) {{
  if (!document.getElementById("type-btn").contains(e.target) &&
      !document.getElementById("type-menu").contains(e.target)) {{
    document.getElementById("type-menu").style.display = "none";
  }}
}});

function applyFilters() {{
  const checkedTypes = Array.from(document.querySelectorAll("#type-menu input:checked")).map(i => i.value);
  const afstand   = parseInt(document.getElementById("filter-afstand").value);
  const minpris   = parseInt(document.getElementById("slider-minpris")?.value)  || 0;
  const maxpris   = parseInt(document.getElementById("slider-maxpris")?.value)  || 40000000;
  const minkvm    = parseInt(document.getElementById("slider-minkvm")?.value)   || 0;
  const maxkvm    = parseInt(document.getElementById("slider-maxkvm")?.value)   || 500;
  const mingrund  = parseInt(document.getElementById("slider-mingrund")?.value) || 0;
  const maxgrund  = parseInt(document.getElementById("slider-maxgrund")?.value) || 10000;
  const minlig    = parseInt(document.getElementById("slider-minlig")?.value)   || 0;
  const maxlig    = parseInt(document.getElementById("slider-maxlig")?.value)   || 365;
  const minvindm  = parseInt(document.getElementById("slider-vindm")?.value)    || 0;
  const minsol    = parseInt(document.getElementById("slider-sol")?.value)      || 0;
  const maxPrisEffektiv  = maxpris  >= 40000000 ? Infinity : maxpris;
  const maxKvmEffektiv   = maxkvm   >= 500      ? Infinity : maxkvm;
  const maxGrundEffektiv = maxgrund >= 10000    ? Infinity : maxgrund;
  const maxLigEffektiv   = maxlig   >= 365      ? Infinity : maxlig;

  // Hent ekskluderede postnumre fra filtersiden (localStorage)
  const ekskl = new Set(JSON.parse(localStorage.getItem('vb_ekskl_pnr') || '[]').map(String));

  visibleBoliger = BOLIGER.filter(b =>
    (checkedTypes.length === 0 || checkedTypes.includes(b.type)) &&
    b.afstand <= afstand &&
    (b.pris === 0 || (b.pris >= minpris && b.pris <= maxPrisEffektiv)) &&
    (b.kvm === 0   || (b.kvm >= minkvm   && b.kvm <= maxKvmEffektiv)) &&
    (b.grundkvm === 0 || (b.grundkvm >= mingrund && b.grundkvm <= maxGrundEffektiv)) &&
    (b.liggetid === 0 || (b.liggetid >= minlig && b.liggetid <= maxLigEffektiv)) &&
    (minvindm === 0 || b.vindm >= minvindm) &&
    (minsol === 0 || b.sol >= minsol) &&
    !ekskl.has(String(b.pnr))
  );
  
  const info = document.getElementById("filter-result-info");
  if (info) info.textContent = visibleBoliger.length + " boliger matcher filtrene";

  // Opdater knap-tekst
  const btn = document.getElementById("type-btn");
  const totalTypes = alleTyper.length;
  btn.textContent = checkedTypes.length === totalTypes ? "Boligtype ▾" : checkedTypes.length + "/" + totalTypes + " ▾";

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

// ─── KOMMUNEDATA (98 kommuner, befolkning 2025) ───
const KOMMUNER = [
  {{navn:"Københavns Kommune",bef:672000,pnr:["1000","1050","1051","1052","1053","1100","1150","1200","1250","1300","1350","1400","1450","1500","1550","1600","1650","1700","1800","1850","1900","2000","2100","2200","2300","2400","2450","2500"],gruppe:"Storkøbenhavn"}},
  {{navn:"Frederiksberg",bef:106000,pnr:["2000"],gruppe:"Storkøbenhavn"}},
  {{navn:"Gentofte",bef:76000,pnr:["2820","2830","2840","2900"],gruppe:"Storkøbenhavn"}},
  {{navn:"Gladsaxe",bef:70000,pnr:["2860","2880"],gruppe:"Storkøbenhavn"}},
  {{navn:"Lyngby-Taarbæk",bef:57000,pnr:["2800"],gruppe:"Storkøbenhavn"}},
  {{navn:"Herlev",bef:30000,pnr:["2730"],gruppe:"Storkøbenhavn"}},
  {{navn:"Ballerup",bef:48000,pnr:["2750"],gruppe:"Storkøbenhavn"}},
  {{navn:"Rødovre",bef:39000,pnr:["2610"],gruppe:"Storkøbenhavn"}},
  {{navn:"Hvidovre",bef:53000,pnr:["2650"],gruppe:"Storkøbenhavn"}},
  {{navn:"Tårnby",bef:43000,pnr:["2770"],gruppe:"Storkøbenhavn"}},
  {{navn:"Dragør",bef:14000,pnr:["2791"],gruppe:"Storkøbenhavn"}},
  {{navn:"Helsingør",bef:64000,pnr:["3000","3050","3060","3070","3080","3100"],gruppe:"Nordsjælland"}},
  {{navn:"Hillerød",bef:51000,pnr:["3400","3450","3480","3490"],gruppe:"Nordsjælland"}},
  {{navn:"Frederikssund",bef:54000,pnr:["3600","3630","3650","3670"],gruppe:"Nordsjælland"}},
  {{navn:"Halsnæs",bef:31000,pnr:["3300","3310","3320","3330","3390"],gruppe:"Nordsjælland"}},
  {{navn:"Gribskov",bef:41000,pnr:["3200","3210","3220","3230","3250","3280"],gruppe:"Nordsjælland"}},
  {{navn:"Fredensborg",bef:40000,pnr:["2990","3480","3490"],gruppe:"Nordsjælland"}},
  {{navn:"Aarhus Kommune",bef:354000,pnr:["8000","8200","8210","8220","8230","8240","8250","8260","8270","8310","8320","8330","8361","8362","8380"],gruppe:"Aarhus"}},
  {{navn:"Odder",bef:23000,pnr:["8300","8350","8370","8380"],gruppe:"Aarhus"}},
  {{navn:"Skanderborg",bef:60000,pnr:["8660","8670","8680"],gruppe:"Aarhus"}},
  {{navn:"Odense Kommune",bef:205000,pnr:["5000","5200","5210","5220","5230","5240","5250","5260","5270","5290"],gruppe:"Odense"}},
  {{navn:"Kerteminde",bef:24000,pnr:["5300","5310","5320","5330"],gruppe:"Odense"}},
  {{navn:"Nordfyn",bef:29000,pnr:["5400","5450","5456","5462","5471","5474","5485","5491","5492"],gruppe:"Odense"}},
  {{navn:"Aalborg Kommune",bef:217000,pnr:["9000","9200","9210","9220","9230","9240","9260","9270","9280","9290"],gruppe:"Aalborg"}},
  {{navn:"Rebild",bef:30000,pnr:["9500","9520","9530","9541","9574","9575"],gruppe:"Aalborg"}},
  {{navn:"Esbjerg Kommune",bef:117000,pnr:["6700","6705","6710","6715","6720","6731","6740","6752","6753","6760","6771"],gruppe:"Esbjerg"}},
  {{navn:"Fanø",bef:3400,pnr:["6720"],gruppe:"Esbjerg"}},
  {{navn:"Varde",bef:50000,pnr:["6800","6818","6823","6830","6840","6851","6870","6880"],gruppe:"Esbjerg"}},
  {{navn:"Randers Kommune",bef:97000,pnr:["8900","8920","8930","8940","8950","8960","8981","8983","8990"],gruppe:"Randers"}},
  {{navn:"Vejle Kommune",bef:120000,pnr:["7100","7120","7130","7140","7150","7160","7171","7173","7182","7183","7184"],gruppe:"Vejle"}},
  {{navn:"Fredericia",bef:51000,pnr:["7000","7007"],gruppe:"Vejle"}},
  {{navn:"Kolding Kommune",bef:94000,pnr:["6000","6040","6051","6052","6064","6070","6091","6092","6093","6094","6095"],gruppe:"Kolding"}},
  {{navn:"Horsens Kommune",bef:90000,pnr:["8700","8721","8722","8723","8732","8740","8751","8752","8762","8763","8781","8783"],gruppe:"Horsens"}},
  {{navn:"Silkeborg",bef:94000,pnr:["8600","8620","8632","8641","8643","8653","8654","8660"],gruppe:"Midtjylland"}},
  {{navn:"Viborg",bef:98000,pnr:["8800","8830","8850","8860","8870","8881","8882","8883"],gruppe:"Midtjylland"}},
  {{navn:"Herning",bef:89000,pnr:["7400","7430","7441","7442","7451","7480","7490"],gruppe:"Midtjylland"}},
  {{navn:"Ringkøbing-Skjern",bef:59000,pnr:["6900","6920","6933","6940","6950","6960","6971","6980","6990"],gruppe:"Midtjylland"}},
  {{navn:"Holstebro",bef:58000,pnr:["7500","7540","7550","7560","7570","7600"],gruppe:"Midtjylland"}},
  {{navn:"Skive",bef:46000,pnr:["7800","7830","7840","7850","7860","7870","7884"],gruppe:"Midtjylland"}},
  {{navn:"Norddjurs",bef:37000,pnr:["8500","8550","8560","8570","8581","8585","8586","8592"],gruppe:"Østjylland"}},
  {{navn:"Syddjurs",bef:44000,pnr:["8400","8410","8420","8444","8450","8462","8464","8471","8472"],gruppe:"Østjylland"}},
  {{navn:"Frederikshavn",bef:59000,pnr:["9900","9940","9950","9970","9981","9982","9990"],gruppe:"Nordjylland"}},
  {{navn:"Hjørring",bef:63000,pnr:["9800","9830","9850","9870","9881"],gruppe:"Nordjylland"}},
  {{navn:"Thisted",bef:43000,pnr:["7700","7730","7741","7742","7752","7755","7760","7770","7790"],gruppe:"Nordjylland"}},
  {{navn:"Morsø",bef:20000,pnr:["7900","7950","7960","7970","7980","7990"],gruppe:"Nordjylland"}},
  {{navn:"Jammerbugt",bef:38000,pnr:["9440","9460","9480","9490","9493"],gruppe:"Nordjylland"}},
  {{navn:"Vesthimmerland",bef:37000,pnr:["9600","9620","9631","9632","9640","9670","9681","9690"],gruppe:"Nordjylland"}},
  {{navn:"Brønderslev",bef:35000,pnr:["9700","9750","9760"],gruppe:"Nordjylland"}},
  {{navn:"Svendborg",bef:59000,pnr:["5700","5750","5762","5771","5772","5792"],gruppe:"Fyn"}},
  {{navn:"Nyborg",bef:32000,pnr:["5800","5853","5854","5856","5871","5874","5881","5882","5883","5884","5892"],gruppe:"Fyn"}},
  {{navn:"Assens",bef:40000,pnr:["5560","5580","5591","5592","5600","5610","5620","5631","5642","5672"],gruppe:"Fyn"}},
  {{navn:"Faaborg-Midtfyn",bef:51000,pnr:["5540","5550","5683","5690"],gruppe:"Fyn"}},
  {{navn:"Middelfart",bef:38000,pnr:["5466","5491","5500","5540"],gruppe:"Fyn"}},
  {{navn:"Langeland",bef:12000,pnr:["5900","5935","5953","5960","5970","5985"],gruppe:"Fyn"}},
  {{navn:"Ærø",bef:6300,pnr:["5960","5970","5985"],gruppe:"Fyn"}},
  {{navn:"Næstved",bef:82000,pnr:["4690","4700","4720","4733","4736","4750","4760","4771","4772","4773","4780"],gruppe:"Sydsjælland"}},
  {{navn:"Vordingborg",bef:44000,pnr:["4760","4771","4772","4773","4780","4800","4840","4850"],gruppe:"Sydsjælland"}},
  {{navn:"Guldborgsund",bef:61000,pnr:["4800","4840","4850","4862","4863","4871","4872","4873","4874","4880","4891","4892","4900","4930","4941","4943","4944","4952","4953","4960","4970","4983","4990"],gruppe:"Sydsjælland"}},
  {{navn:"Lolland",bef:44000,pnr:["4900","4912","4913","4930","4941","4943","4944","4952","4953","4960","4970","4983","4990"],gruppe:"Sydsjælland"}},
  {{navn:"Bornholm",bef:40000,pnr:["3700","3720","3730","3740","3751","3760","3782","3790"],gruppe:"Bornholm"}},
  {{navn:"Kalundborg",bef:48000,pnr:["4400","4420","4440","4450","4460","4470","4480","4490"],gruppe:"Vestsjælland"}},
  {{navn:"Holbæk",bef:71000,pnr:["4300","4320","4330","4340","4350","4360","4370","4390"],gruppe:"Vestsjælland"}},
  {{navn:"Slagelse",bef:77000,pnr:["4200","4220","4230","4241","4242","4250","4261","4262","4270","4281","4291"],gruppe:"Vestsjælland"}},
  {{navn:"Odsherred",bef:32000,pnr:["4500","4520","4532","4534","4540","4550","4560","4571","4572","4573","4581","4583","4591","4592","4593"],gruppe:"Vestsjælland"}},
  {{navn:"Aabenraa",bef:59000,pnr:["6200","6230","6240","6261","6270","6280","6300","6310","6318","6320","6330","6340","6360"],gruppe:"Sønderjylland"}},
  {{navn:"Sønderborg",bef:74000,pnr:["6400","6430","6440","6470","6510","6534","6535","6541","6580","6600"],gruppe:"Sønderjylland"}},
  {{navn:"Tønder",bef:37000,pnr:["6240","6261","6270","6280","6300","6310","6318","6320","6330","6340","6360","6372","6376"],gruppe:"Sønderjylland"}},
  {{navn:"Haderslev",bef:55000,pnr:["6100","6200","6230","6240"],gruppe:"Sønderjylland"}},
];

// Tæl boliger pr kommuner fra BOLIGER
function antalBoligerKom(kom) {{
  return BOLIGER.filter(b => kom.pnr.includes(String(b.pnr))).length;
}}

let ekskluderede = new Set(JSON.parse(localStorage.getItem('vb_ekskl_pnr') || '[]').map(String));
let bySortKol = 'bef', bySortDir = 'desc';

function skiftTab(tab) {{
  document.getElementById('panel-filtre').style.display = tab === 'filtre' ? 'block' : 'none';
  document.getElementById('panel-byer').style.display   = tab === 'byer'   ? 'flex'  : 'none';
  document.getElementById('panel-lag').style.display    = tab === 'lag'    ? 'block' : 'none';
  ['filtre','byer','lag'].forEach(function(t) {{
    const btn = document.getElementById('tab-' + t);
    const active = t === tab;
    btn.style.color = active ? '#1a5276' : '#999';
    btn.style.borderBottom = active ? '2px solid #1a5276' : 'none';
  }});
  if (tab === 'byer') tegn();
}}

function erEkskl(kom) {{
  return kom.pnr.length > 0 && kom.pnr.every(p => ekskluderede.has(p));
}}

function bySort(kol) {{
  bySortDir = bySortKol === kol ? (bySortDir === 'asc' ? 'desc' : 'asc') : (kol === 'bef' || kol === 'boliger' ? 'desc' : 'asc');
  bySortKol = kol;
  tegn();
}}

function tegn() {{
  const soeg = (document.getElementById('by-soeg')?.value || '').toLowerCase();
  const grupper = {{}};
  KOMMUNER
    .filter(k => !soeg || k.navn.toLowerCase().includes(soeg) || k.gruppe.toLowerCase().includes(soeg))
    .forEach(k => {{ if (!grupper[k.gruppe]) grupper[k.gruppe] = []; grupper[k.gruppe].push(k); }});

  // Sorter kommuner inden for hver gruppe
  Object.values(grupper).forEach(arr => arr.sort((a, b) => {{
    const va = bySortKol === 'navn' ? a.navn : bySortKol === 'bef' ? a.bef : antalBoligerKom(a);
    const vb = bySortKol === 'navn' ? b.navn : bySortKol === 'bef' ? b.bef : antalBoligerKom(b);
    return bySortDir === 'asc' ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
  }}));

  let html = '';
  Object.entries(grupper).forEach(([g, arr]) => {{
    const alleEkskl = arr.every(k => erEkskl(k));
    html += `<tr style="background:#edf2f7;cursor:pointer" onclick="toggleGruppe('${{g}}')">
      <td style="text-align:center;padding:5px">
        <input type="checkbox" ${{alleEkskl ? '' : 'checked'}} onclick="event.stopPropagation();toggleGruppe('${{g}}')" style="accent-color:#1a5276">
      </td>
      <td colspan="3" style="padding:5px 8px;font-weight:700;font-size:11px;color:#2c5282;letter-spacing:.3px">
        ${{g}} <span style="font-weight:400;color:#666">(${{arr.length}})</span>
      </td>
    </tr>`;
    arr.forEach(k => {{
      const ekskl = erEkskl(k);
      const boliger = antalBoligerKom(k);
      html += `<tr style="opacity:${{ekskl ? 0.4 : 1}}">
        <td style="text-align:center;padding:4px">
          <input type="checkbox" ${{ekskl ? '' : 'checked'}} data-pnr="${{k.pnr.join(',')}}"
            onchange="toggleKom(this)" style="accent-color:#1a5276">
        </td>
        <td style="padding:4px 8px;font-weight:500">${{k.navn}}</td>
        <td style="padding:4px 8px;color:#888;font-size:11px">${{k.pnr.slice(0,3).join(', ')}}${{k.pnr.length > 3 ? '…' : ''}}</td>
        <td style="padding:4px 8px;text-align:right;color:#888">${{k.bef.toLocaleString('da-DK')}}</td>
        <td style="padding:4px 8px;text-align:right">
          ${{boliger > 0 ? `<span style="background:#e8f4fd;color:#1a5276;border-radius:8px;padding:1px 6px;font-size:11px;font-weight:600">${{boliger}}</span>` : '–'}}
        </td>
      </tr>`;
    }});
  }});

  document.getElementById('by-tbody').innerHTML = html;
  opdaterByBadge();
}}

function toggleKom(cb) {{
  cb.dataset.pnr.split(',').forEach(p => ekskluderede[cb.checked ? 'delete' : 'add'](p));
  localStorage.setItem('vb_ekskl_pnr', JSON.stringify([...ekskluderede]));
  tegn(); applyFilters();
}}

function toggleGruppe(gruppe) {{
  const arr = KOMMUNER.filter(k => k.gruppe === gruppe);
  const alleEkskl = arr.every(k => erEkskl(k));
  arr.forEach(k => k.pnr.forEach(p => ekskluderede[alleEkskl ? 'delete' : 'add'](p)));
  localStorage.setItem('vb_ekskl_pnr', JSON.stringify([...ekskluderede]));
  tegn(); applyFilters();
}}

function selectAlleBy(inkl) {{
  KOMMUNER.forEach(k => k.pnr.forEach(p => ekskluderede[inkl ? 'delete' : 'add'](p)));
  localStorage.setItem('vb_ekskl_pnr', JSON.stringify([...ekskluderede]));
  tegn(); applyFilters();
}}

function opdaterByBadge() {{
  const n = KOMMUNER.filter(k => erEkskl(k)).length;
  const badge = document.getElementById('byer-badge');
  if (n > 0) {{ badge.style.display = 'inline'; badge.textContent = n; }}
  else badge.style.display = 'none';
  document.getElementById('by-info').textContent = n > 0 ? `${{n}} ekskluderet` : 'Alle medtaget';
}}

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
    global MAX_AFSTAND_METER, BRUG_CACHE
    parser = argparse.ArgumentParser(description="Find boliger tæt på dansk kyst")
    parser.add_argument("--refresh", choices=["alle", "boliger", "kyst", "vindm", "sol"],
                        help="Tving genhentning: 'alle', 'boliger', 'kyst', 'vindm' eller 'sol'")
    parser.add_argument("--afstand", type=int, default=None,
                        help=f"Max afstand til kyst i meter (default: {MAX_AFSTAND_METER})")
    parser.add_argument("--ingen-boliger", action="store_true",
                        help="Spring boligdata over – brug cache eller eksisterende CSV")
    args = parser.parse_args()

    if args.afstand is not None:
        MAX_AFSTAND_METER = args.afstand
        print(f"  → Afstand overstyret til {MAX_AFSTAND_METER}m via argument")

    if getattr(args, 'ingen_boliger', False):
        BRUG_CACHE = True
        print("  → --ingen-boliger: springer boligdata over, bruger cache")

    # Slet cache-filer hvis --refresh er angivet
    if args.refresh in ("alle", "kyst"):
        if os.path.exists(CACHE_KYST_FIL):
            os.remove(CACHE_KYST_FIL)
            print(f"🗑  Cache slettet: {CACHE_KYST_FIL}")
    if args.refresh in ("alle", "boliger"):
        if os.path.exists(CACHE_BOLIGER_FIL):
            os.remove(CACHE_BOLIGER_FIL)
            print(f"🗑  Cache slettet: {CACHE_BOLIGER_FIL}")
    if args.refresh in ("alle", "vindm"):
        if os.path.exists(CACHE_VINDM_FIL):
            os.remove(CACHE_VINDM_FIL)
            print(f"🗑  Cache slettet: {CACHE_VINDM_FIL}")
    if args.refresh in ("alle", "sol"):
        if os.path.exists(CACHE_SOL_FIL):
            os.remove(CACHE_SOL_FIL)
            print(f"🗑  Cache slettet: {CACHE_SOL_FIL}")

    print("=" * 60)
    print("  Ejendomme til salg max 200m fra danske farvande")
    print("=" * 60)
    
    # 1. Kystlinje (med cache + repo-backup)
    KYST_BACKUP = "kyst_backup.pkl"
    kyst_gdf = None
    if BRUG_CACHE:
        kyst_gdf = indlæs_cache(CACHE_KYST_FIL)
    # Fallback: brug repo-backup hvis cache mangler (GitHub Actions uden cache)
    if kyst_gdf is None and os.path.exists(KYST_BACKUP):
        print("[1/4] Kystlinje indlæst fra repo-backup ✓")
        kyst_gdf = indlæs_cache(KYST_BACKUP)
    if kyst_gdf is None:
        kyst_gdf = hent_kystlinje()
        if EKSKLUDER_VESTERHAV:
            kyst_gdf = ekskluder_vesterhav(kyst_gdf)
        else:
            print('    → Vesterhavet medtages')
        if BRUG_CACHE:
            gem_cache(kyst_gdf, CACHE_KYST_FIL)
        # Gem også som repo-backup så næste CI-kørsel ikke behøver Overpass
        gem_cache(kyst_gdf, KYST_BACKUP)
        print(f"    💾 Repo-backup gemt: {KYST_BACKUP} (commit dette til git)")
    else:
        print("[1/4] Kystlinje indlæst fra cache ✓")

    # 1b. Vindmøller (med cache + repo-backup)
    VINDM_BACKUP = "vindm_backup.pkl"
    vindm_gdf = None
    if BRUG_CACHE:
        vindm_gdf = indlæs_cache(CACHE_VINDM_FIL)
    if vindm_gdf is None and os.path.exists(VINDM_BACKUP):
        print("[1b/4] Vindmøller indlæst fra repo-backup ✓")
        vindm_gdf = indlæs_cache(VINDM_BACKUP)
    if vindm_gdf is None:
        vindm_gdf = hent_vindmoeller()
        if BRUG_CACHE:
            gem_cache(vindm_gdf, CACHE_VINDM_FIL)
        gem_cache(vindm_gdf, VINDM_BACKUP)
        print(f"    💾 Repo-backup gemt: {VINDM_BACKUP} (commit dette til git)")
    else:
        print("[1b/4] Vindmøller indlæst fra cache ✓")

    # 1c. Solcelleanlæg (med cache + repo-backup)
    SOL_BACKUP = "sol_backup.pkl"
    sol_gdf = None
    if BRUG_CACHE:
        sol_gdf = indlæs_cache(CACHE_SOL_FIL)
    if sol_gdf is None and os.path.exists(SOL_BACKUP):
        print("[1c/4] Solcelleanlæg indlæst fra repo-backup ✓")
        sol_gdf = indlæs_cache(SOL_BACKUP)
    if sol_gdf is None:
        sol_gdf = hent_solceller()
        if BRUG_CACHE:
            gem_cache(sol_gdf, CACHE_SOL_FIL)
        gem_cache(sol_gdf, SOL_BACKUP)
        print(f"    💾 Repo-backup gemt: {SOL_BACKUP} (commit dette til git)")
    else:
        print("[1c/4] Solcelleanlæg indlæst fra cache ✓")

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

    # Fjern dubletter før videre filtrering
    boliger = dedupliker_boliger(boliger)
    if not boliger:
        print("\n⚠ Ingen boliger tilbage efter deduplikering.")
        return
    
    # 2b. Ekskluder byer/kommuner/postnumre
    boliger = filtrer_ekskluderede(boliger)

    # 3. Filtrer på afstand til kyst
    resultat = filtrer_nær_vand(boliger, kyst_gdf)

    if resultat.empty:
        print("\n⚠ Ingen boliger fundet inden for 150m. Prøv at øge MAX_AFSTAND_METER.")
        return

    # 3b. Beregn afstand til nærmeste vindmølle
    resultat = beregn_afstand_vindmoeller(resultat, vindm_gdf)

    # 3c. Beregn afstand til nærmeste solcelleanlæg
    resultat = beregn_afstand_solceller(resultat, sol_gdf)

    # 4. Gem output
    print("\n[4/4] Gemmer resultater...")
    gem_csv(resultat)
    gem_kort(resultat, vindm_gdf=vindm_gdf)
    gem_boliger_json(resultat)
    
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
