# 🌊 Vandkant Boliger

Finder automatisk alle ejendomme til salg i Danmark inden for 200 meter fra kysten.

Opdateres dagligt via GitHub Actions og publiceres på GitHub Pages.

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

Det nemmeste er via GitHub's webgrænseflade:
- Klik **Add file** → **Upload files**
- Træk filerne ind
- Klik **Commit changes**

For `.github/workflows/opdater.yml` skal du oprette mapperne manuelt:
- Klik **Add file** → **Create new file**
- Skriv `.github/workflows/opdater.yml` som filnavn
- Indsæt indholdet fra filen

### 3. Aktivér GitHub Pages

1. Gå til **Settings** → **Pages**
2. Under **Source**: vælg **Deploy from a branch**
3. Branch: `main`, mappe: `/docs`
4. Klik **Save**

### 4. Kør workflow første gang

1. Gå til **Actions** fanen
2. Klik på **Opdater Vandkant Boliger**
3. Klik **Run workflow** → **Run workflow**
4. Vent 5-10 minutter mens scriptet kører

### 5. Se din side

Din side er nu live på:
```
https://DITBRUGERNAVN.github.io/vandkant-boliger/
```

## Tilpasning

Rediger øverst i `vandkant_boliger.py`:

```python
MAX_AFSTAND_METER = 200      # Afstand til kyst
BOLIG_TYPER = [1, 2, 4, 5]  # Boligtyper
EKSKLUDER_BYER = { ... }     # Byer der filtreres væk
```

## Automatisk opdatering

Scriptet kører automatisk hver dag kl. 06:00 dansk tid.
Du kan også starte det manuelt under **Actions** → **Run workflow**.

## Output

- `docs/index.html` — interaktivt kort (GitHub Pages)
- `docs/vandkant_boliger.csv` — rådata til download
