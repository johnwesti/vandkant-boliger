import sys, os, glob, re, shutil, subprocess

DOWNLOADS = os.path.expanduser(r"~\Downloads")
GIT_DIR   = os.path.expanduser(r"~\dev\BOLIG\github")
DST       = os.path.join(GIT_DIR, "vandkant_boliger.py")

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=GIT_DIR)
    if r.stdout: print(r.stdout.strip())
    if r.stderr: print(r.stderr.strip())

def sorter_nummer(f):
    m = re.search(r'\((\d+)\)', f)
    return int(m.group(1)) if m else -1

msg = " ".join(sys.argv[1:]) or "Opdatering"

kandidater = glob.glob(os.path.join(DOWNLOADS, "vandkant_boliger*.py"))
if not kandidater:
    print("Ingen vandkant_boliger*.py filer fundet i Downloads")
    sys.exit(1)

SRC = max(kandidater, key=sorter_nummer)
print(f"Fandt:      {os.path.basename(SRC)}")
print(f"Kopierer -> {DST}")
shutil.copy2(SRC, DST)

run("git add vandkant_boliger.py")
run(f'git commit -m "{msg}"')
run("git push")
print("OK - pushed til GitHub")
