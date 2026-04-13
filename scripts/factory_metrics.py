"""Muestra metricas de la factory desde /stats"""
import json, sys, urllib.request, os

API_KEY = "mf-api-key-2026"
PORT    = os.environ.get("MF_PORT", "8000")
URL     = f"http://localhost:{PORT}/stats"

try:
    req = urllib.request.Request(URL, headers={"X-API-KEY": API_KEY})
    with urllib.request.urlopen(req, timeout=3) as r:
        d = json.load(r)
    print(f"  Scans totales:  {d.get('total_scans', 0)}")
    print(f"  Hosts unicos:   {d.get('unique_hosts', 0)}")
    last = (d.get("last_scan") or "")[:19].replace("T", " ") or "---"
    print(f"  Ultimo scan:    {last}")
    recent = d.get("recent", [])
    if recent:
        print()
        print("  Ultimos analisis:")
        for r in recent[:5]:
            ts = (r.get("timestamp") or "")[:10]
            h  = (r.get("hostname")  or "?")[:45]
            print(f"    {ts}  {h}")
except Exception:
    print("  (Servidor no disponible)")
