#!/usr/bin/env python3
"""Generador del feed de reciclaje social para GatellAsociados.com.

Lee el catálogo de artículos de la API pública de WordPress, mantiene una
cola de rotación (los menos publicados primero, con mezcla de reciente +
antiguo) y genera un feed RSS 'feed.xml' con los artículos del día, que
dlvr.it (u otro servicio RSS-to-social) reparte a las redes.

Simple y sin dependencias externas: solo stdlib. Estado en estado.json.
"""
import json, os, ssl, time, urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

DIR = os.path.dirname(os.path.abspath(__file__))
CATALOGO = os.path.join(DIR, "catalogo.json")
ESTADO = os.path.join(DIR, "estado.json")
FEED = os.path.join(DIR, "feed.xml")
POR_DIA = 3          # articulos nuevos en el feed cada dia
MAX_ITEMS_FEED = 15  # dlvr.it solo mira los ultimos items

# Categorias con mas tiron social (se priorizan un poco)
CATS_TOP = {"Internet y derecho", "Consumidores y Usuarios", "Derecho Civil",
            "Derecho Penal", "Derecho Bancario", "Consejos Legales y Asesoramiento"}

HASHTAGS = {
    "Internet y derecho": "#DerechoDigital #Internet",
    "Consumidores y Usuarios": "#Consumidores #ReclamaTusDerechos",
    "Derecho Civil": "#DerechoCivil",
    "Derecho Administrativo": "#DerechoAdministrativo",
    "Derecho Penal": "#DerechoPenal",
    "Derecho Tributario": "#Impuestos #DerechoTributario",
    "Derecho Bancario": "#DerechoBancario #Banca",
    "Derecho Laboral": "#DerechoLaboral",
    "Hipotecas": "#Hipotecas",
    "Herencias y Donaciones": "#Herencias",
}


def actualizar_catalogo():
    """Refresca el catálogo desde la API de WP (detecta posts nuevos/actualizados)."""
    ctx = ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
    posts, page = [], 1
    while True:
        url = ("https://www.gatellasociados.com/wp-json/wp/v2/posts"
               f"?per_page=100&page={page}&_embed=wp:featuredmedia"
               "&_fields=id,date,modified,slug,link,title,excerpt,categories,_links,_embedded")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                batch = json.load(r)
        except Exception:
            break
        if not batch:
            break
        posts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        time.sleep(1)
    if not posts:  # sin red: usar catalogo previo
        return json.load(open(CATALOGO))
    req = urllib.request.Request(
        "https://www.gatellasociados.com/wp-json/wp/v2/categories?per_page=100&_fields=id,name",
        headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        cats = {c["id"]: c["name"] for c in json.load(r)}
    def imagen(p):
        m = p.get("_embedded", {}).get("wp:featuredmedia", [])
        return m[0].get("source_url", "") if m and isinstance(m, list) else ""
    catalogo = [{
        "id": p["id"],
        "fecha": p["date"][:10],
        "modificado": p["modified"][:10],
        "titulo": p["title"]["rendered"],
        "link": p["link"],
        "imagen": imagen(p),
        "extracto": p["excerpt"]["rendered"].replace("<p>", "").replace("</p>", "").strip()[:300],
        "categorias": [cats.get(c, str(c)) for c in p["categories"]],
    } for p in posts]
    json.dump(catalogo, open(CATALOGO, "w"), ensure_ascii=False, indent=1)
    return catalogo


def puntuacion(art, publicaciones):
    """Menor puntuación = antes en la cola."""
    veces = publicaciones.get(str(art["id"]), 0)
    p = veces * 100                       # lo menos publicado primero
    if art["modificado"] >= "2024-01-01":
        p -= 30                            # contenido fresco/actualizado sube
    if any(c in CATS_TOP for c in art["categorias"]):
        p -= 10                            # categorias con tiron
    if art["fecha"] < "2019-01-01" and art["modificado"] < "2021-09-03":
        p += 25                            # antiguo sin actualizar baja (ojo leyes nuevas)
    return p


def componer_texto(art):
    cat = next((c for c in art["categorias"] if c in HASHTAGS), None)
    tags = HASHTAGS.get(cat, "#Abogados")
    return f"{art['titulo']} — análisis de Gatell & Asociados {tags} #Malaga #Derecho"


def main():
    catalogo = actualizar_catalogo()
    estado = json.load(open(ESTADO)) if os.path.exists(ESTADO) else {"publicaciones": {}, "historial": []}
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # evitar regenerar dos veces el mismo dia (idempotente para cron)
    ya_hoy = [h for h in estado["historial"] if h["dia"] == hoy]
    if ya_hoy:
        seleccion = [a for a in catalogo if a["id"] in {x["id"] for x in ya_hoy}]
    else:
        cola = sorted(catalogo, key=lambda a: puntuacion(a, estado["publicaciones"]))
        seleccion = cola[:POR_DIA]
        for a in seleccion:
            estado["publicaciones"][str(a["id"])] = estado["publicaciones"].get(str(a["id"]), 0) + 1
            estado["historial"].append({"dia": hoy, "id": a["id"], "titulo": a["titulo"]})
        estado["historial"] = estado["historial"][-200:]
        json.dump(estado, open(ESTADO, "w"), ensure_ascii=False, indent=1)

    # construir feed con los ultimos MAX_ITEMS_FEED del historial
    ids_orden = [h["id"] for h in reversed(estado["historial"][-MAX_ITEMS_FEED:])]
    por_id = {a["id"]: a for a in catalogo}
    ahora = datetime.now(timezone.utc)
    items = []
    for n, i in enumerate(ids_orden):
        a = por_id.get(i)
        if not a:
            continue
        # pubDate escalonada para que dlvr.it respete el orden
        fecha_pub = format_datetime(ahora.replace(hour=max(0, 9 - n // 3), minute=(n * 7) % 60))
        img = a.get("imagen", "")
        img_xml = ""
        if img:
            img_xml = (f'\n    <enclosure url="{escape(img)}" type="image/jpeg" length="0"/>'
                       f'\n    <media:content url="{escape(img)}" medium="image"/>')
        items.append(f"""  <item>
    <title>{escape(componer_texto(a))}</title>
    <link>{escape(a['link'])}</link>
    <guid isPermaLink="false">gatell-social-{a['id']}-{estado['publicaciones'].get(str(a['id']), 1)}</guid>
    <pubDate>{fecha_pub}</pubDate>
    <description>{escape(a['extracto'][:250])}</description>{img_xml}
  </item>""")

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <title>Gatell &amp; Asociados — Selección diaria</title>
  <link>https://www.gatellasociados.com</link>
  <description>Artículos jurídicos seleccionados automáticamente del archivo de Gatell &amp; Asociados</description>
  <lastBuildDate>{format_datetime(ahora)}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
"""
    open(FEED, "w").write(rss)
    print(f"Feed generado con {len(items)} items. Hoy: {[a['titulo'][:60] for a in seleccion]}")


if __name__ == "__main__":
    main()
