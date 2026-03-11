import re, pathlib
p = pathlib.Path("/app/alembic/versions")
patched = []
for f in sorted(p.glob("*.py")):
    s = f.read_text(encoding="utf-8")
    # quote down_revision if missing quotes
    s2 = re.sub(r"(?m)^(\\s*down_revision\\s*=\\s*)([0-9a-fA-F_]+)\\s*$", r"\\1'\\2'", s)
    # quote revision if missing quotes
    s2 = re.sub(r"(?m)^(\\s*revision\\s*=\\s*)([0-9a-fA-F_]+)\\s*$", r"\\1'\\2'", s2)
    if s2 != s:
        f.write_text(s2, encoding="utf-8")
        patched.append(str(f))
print('Patched files:', patched)


