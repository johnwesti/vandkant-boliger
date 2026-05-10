# 🌊 Vandkant Boliger

[![Opdater Vandkant Boliger](https://github.com/johnwesti/vandkant-boliger/actions/workflows/opdater.yml/badge.svg)](https://github.com/johnwesti/vandkant-boliger/actions/workflows/opdater.yml)

**🗺 [Se kortet live](https://johnwesti.github.io/vandkant-boliger/)** &nbsp;|&nbsp; **⚙️ [Kør workflow manuelt](https://github.com/johnwesti/vandkant-boliger/actions/workflows/opdater.yml)**

---

Finder automatisk alle ejendomme til salg i Danmark inden for 200 meter fra kysten.
Opdateres to gange dagligt via GitHub Actions og publiceres på GitHub Pages.

## Kom i gang

### 1. Opret GitHub repository

1. Gå til [github.com](https://github.com) og log ind (eller opret gratis konto)
2. Klik **New repository**
3. Giv det et navn, fx `vandkant-boliger`
4. Sæt til **Public** (kræves for gratis GitHub Pages)
5. Klik **Create repository**

### 2. Upload filer

Upload disse filer til dit nye repository:
- `vandkant_boliger.py`
- `requirements.txt`
- `.github/workflows/opdater.yml`

### 3. Aktivér GitHub Pages

1. Gå til **Settings** → **Pages**
2. Under **Source**: vælg **Deploy from a branch**
3. Branch: `main`, mappe: `/docs`
4. Klik **Save**

### 4. Kør workflow første gang

1. Gå til **Actions** fanen
2. Klik på **Opdater Vandkant Boliger**
3. Klik **Run workflow** → **Run workflow**
4. Vent 5-10 minutter

## Tilpasning

Rediger øverst i `vandkant_boliger.py`:

```python
MAX_AFSTAND_METER = 200      # Afstand til kyst
BOLIG_TYPER = [1, 4, 5]     # 1=Villa, 4=Fritidshus, 5=Grund
EKSKLUDER_BYER = { ... }     # Byer der filtreres væk
```

## Automatisk opdatering

Scriptet kører automatisk to gange dagligt — kl. 06:00 og 18:00 dansk tid.
Du kan også starte det manuelt under [Actions](https://github.com/johnwesti/vandkant-boliger/actions/workflows/opdater.yml).

## Output

- **[Live kort](https://johnwesti.github.io/vandkant-boliger/)** — interaktivt kort med alle vandkant-boliger
- `docs/vandkant_boliger.csv` — rådata til download
