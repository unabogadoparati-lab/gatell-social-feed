#!/usr/bin/env python3
"""Bot Telegram RD 739/2026 — Jubilación Deportistas Profesionales v3.
   ⚡ Fechas de integración por deporte
   ⚡ Diferenciación jubilado / no jubilado
   ⚡ Escala pensión 2026 actualizada
   ⚡ Contador días hasta entrada en vigor
"""

import json
from datetime import datetime, date
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ConversationHandler,
    MessageHandler, filters, ContextTypes,
)

# ── Config ───────────────────────────────────────────
TOKEN = "8485673317:AAHna_rMv_rwFH7vS3YfgkjUQvjhW0S0sbo"
ANTONIO_CHAT_ID = 641654799
LEADS_FILE = Path(__file__).parent / "leads_deportistas.json"
ENTRADA_VIGOR = date(2026, 12, 25)

# ── Estados ──────────────────────────────────────────
(SPORT, YEARS, OVERLAP, JUBILADO, COTIZADOS, BASE, CONTACT) = range(7)

# ── Fechas de integración por deporte ────────────────
INTEGRACION = {
    "ciclismo":         date(1992, 2, 1),
    "baloncesto":       date(1993, 8, 1),
    "balonmano":        date(1998, 1, 1),
    "voleibol":         date(2003, 6, 1),
    "waterpolo":        date(2003, 6, 1),
    "hockey":           date(2003, 6, 1),
    "atletismo":        date(2003, 6, 1),
    "natacion":         date(2003, 6, 1),
    "natación":         date(2003, 6, 1),
    "judo":             date(2003, 6, 1),
    "tenis":            date(2003, 6, 1),
    "rugby":            date(2003, 6, 1),
    "balonmano playa":  date(2003, 6, 1),
}
# Deportes con fecha específica que tienen palabras clave para detectarlos
DEPORTE_ALIAS = {
    "cicli": "ciclismo", "bici": "ciclismo",
    "balonces": "baloncesto", "basket": "baloncesto",
    "balonman": "balonmano", "handball": "balonmano",
    "volei": "voleibol", "voley": "voleibol",
    "water": "waterpolo",
}

# ── Funciones de cálculo ─────────────────────────────

def detectar_deporte(texto):
    """Detecta el deporte y devuelve (nombre_canonico, fecha_integracion)."""
    t = texto.strip().lower()
    # Alias
    for alias, canon in DEPORTE_ALIAS.items():
        if alias in t:
            return canon, INTEGRACION.get(canon)
    # Búsqueda directa
    for dep, fecha in INTEGRACION.items():
        if dep in t:
            return dep, fecha
    return texto, date(2003, 6, 1)  # default: resto deportistas


def extraer_anos(texto):
    """Extrae número de años del input del usuario."""
    try:
        partes = texto.replace("–", "-").replace("—", "-").replace(" a ", "-").split("-")
        if len(partes) == 2:
            return int(partes[1].strip()) - int(partes[0].strip())
        # Si solo da un número
        return abs(int(partes[0].strip()))
    except (ValueError, IndexError):
        return 5  # default


def calc_porcentaje(anos_total):
    """Escala pensión 2026: 15a→50%, +0.21%/mes hasta 25a, +0.19%/mes hasta 36a."""
    if anos_total <= 0:
        return 0
    if anos_total <= 15:
        return anos_total / 15 * 50
    pct = 50.0
    meses = min((anos_total - 15) * 12, 10 * 12)
    pct += meses * 0.21
    if anos_total > 25:
        meses_extra = min((anos_total - 25) * 12, 11 * 12)
        pct += meses_extra * 0.19
    return min(pct, 100.0)


def calc_pension(anos_dep, base_reguladora, anos_otros=20, ya_jubilado=False):
    """Calcula simulación y devuelve dict con resultados."""
    anos_dep = max(1, min(anos_dep, 25))
    if base_reguladora <= 0:
        base_reguladora = 1800

    pct_sin = calc_porcentaje(anos_otros)
    pct_con = calc_porcentaje(anos_otros + anos_dep)
    pension_sin = base_reguladora * pct_sin / 100
    pension_con = base_reguladora * pct_con / 100
    inc_mes = pension_con - pension_sin

    return {
        "anos_dep": anos_dep,
        "anos_otros": anos_otros,
        "base": base_reguladora,
        "pct_sin": round(pct_sin, 1),
        "pct_con": round(pct_con, 1),
        "pension_sin": round(pension_sin),
        "pension_con": round(pension_con),
        "inc_mes": round(inc_mes),
        "inc_ano": round(inc_mes * 14),
        "ya_jubilado": ya_jubilado,
    }


# ── Mensajes ──────────────────────────────────────────

PRESENTACION = (
    "🏐 ¡Hola! Soy el asistente de *Antonio Gatell*, "
    "abogado y exjugador del Puleva Maristas (Liga Asobal).\ņ\n"
    "Estoy aquí para comprobar si el *Real Decreto 739/2026* "
    "aplica a tu caso y *calcular cuánto podría aumentar tu pensión*.\ņ\n"
    "👇 *¿En qué deporte fuiste profesional?*\n"
    "(balonmano, baloncesto, ciclismo, voleibol...)"
)

DESCARTE_FUTBOL = (
    "❌ El RD 739/2026 *excluye a futbolistas* (normativa propia).\n\n"
    "¿Consultas? [gatellasociados.com](https://www.gatellasociados.com)"
)

PREGUNTA_ANOS = (
    "📅 *¿En qué años competiste como profesional?*\n\n"
    "Ej: '1989-1995' o '1990-1994'"
)

DESCARTE_FUERA_RANGO = (
    "⚠️ El RD solo cubre desde el *15/03/1980* hasta la fecha "
    "de integración de tu deporte en la SS.\n\n"
    "Para {deporte}, la fecha límite es *{fecha_limite}*.\n\n"
    "Si empezaste después, no aplica. ¿Consultas? "
    "[gatellasociados.com](https://www.gatellasociados.com)"
)

PREGUNTA_SOLAPO = (
    "⚡ *Pregunta clave:*\n\n"
    "Durante esos años, *¿tenías otro trabajo por el que ya cotizaras* "
    "a la Seguridad Social?\n\nResponde *SÍ* o *NO*."
)

DESCARTE_SOLAPO = (
    "❌ *No pueden computarse periodos que se solapen con otras cotizaciones.*\n\n"
    "Si cotizabas por otro empleo, esos años no suman.\n"
    "¿Consultas? agatell@gatellasociados.com"
)

PREGUNTA_JUBILADO = (
    "📋 Una más:\n\n"
    "*¿Ya estás jubilado/a o todavía no?*\n\n"
    "Esto cambia el tipo de cálculo."
)

PREGUNTA_COTIZADOS = (
    "💼 *¿Aproximadamente cuántos años has cotizado*\n"
    "a la Seguridad Social fuera del deporte?\n\n"
    "🧐 Es el total de años que has trabajado por cuenta ajena\n"
    "o propia (no cuentes los años como deportista).\n\n"
    "📄 Puedes mirarlo en tu *vida laboral*.\n\n"
    "💰 Una persona que empezó a trabajar con 25 años y tiene 55,\n"
    "lleva unos 30 años cotizados.\n\n"
    "Si no lo sabes, escribe *'no'* y usaré 25 años."
)

PREGUNTA_BASE = (
    "💰 Último dato para tu simulación:\n\n"
    "*¿Sabes cuál es tu base reguladora?*\n\n"
    "🧐 *¿Qué es?* El promedio de tus bases de cotización.\n\n"
    "📄 *¿Dónde lo encuentras?*\n"
    "• Vida laboral (informe SS)\n"
    "• Resolución de pensión (si jubilado)\n"
    "• Nóminas (base cotización)\n\n"
    "💰 Suele estar entre *1.200€ y 2.500€*.\n\n"
    "Escríbela o escribe *'no'* (usaré 1.800€)."
)

PREGUNTA_CONTACTO = (
    "Ahora dime tu *nombre y teléfono* para que Antonio te llame.\n\n"
    "Ej: 'Pepe García, 612345678'"
)

DESPEDIDA = (
    "🙏 ¡Gracias! *Antonio te llamará pronto.*\n\n"
    "👉 Artículo: https://www.gatellasociados.com/jubilacion-deportistas-profesionales-real-decreto-739-2026/"
)


def simulacion_msg(r, anos_texto, fecha_limite):
    dias = (ENTRADA_VIGOR - date.today()).days
    tipo = "📊 *SIMULACIÓN — REVISIÓN DE PENSIÓN*" if r["ya_jubilado"] else "📊 *SIMULACIÓN — NUEVA PENSIÓN*"
    return (
        f"{tipo}\n\n"
        f"🏟 Perido deportista: {anos_texto} ({r['anos_dep']} años)\n"
        f"📆 Fecha límite {r.get('deporte','')}: *{fecha_limite}*\n"
        f"💼 Años cotizados (aprox): {r['anos_otros']}\n"
        f"💶 Base reguladora: *{r['base']:,}€*\n\n"
        f"📉 Sin RD: {r['pct_sin']}% → *{r['pension_sin']:,}€/mes*\n"
        f"📈 Con RD: {r['pct_con']}% → *{r['pension_con']:,}€/mes*\n\n"
        f"✨ *+{r['inc_mes']:,}€/mes* | 💰 *+{r['inc_ano']:,}€/año*\n\n"
        f"⚠️ Estimación orientativa.\n"
        f"⏳ *El RD entra en vigor en {dias} días* (25 dic 2026).\n"
        f"🔄 Si ya estás jubilado, efectos desde el mes siguiente a la solicitud."
    )


async def start(update, context):
    await update.message.reply_text(PRESENTACION, parse_mode="Markdown")
    return SPORT


async def sport(update, context):
    txt = update.message.text.strip()
    dep, fecha_limite = detectar_deporte(txt)

    if "futbol" in txt.lower() or "fútbol" in txt.lower() or "football" in txt.lower() or "soccer" in txt.lower():
        await update.message.reply_text(DESCARTE_FUTBOL, parse_mode="Markdown")
        return ConversationHandler.END

    context.user_data["deporte"] = dep
    context.user_data["fecha_limite"] = fecha_limite.strftime("%d/%m/%Y") if fecha_limite else "01/06/2003"

    await update.message.reply_text(
        f"✅ *{txt}* — fecha límite de integración: *{context.user_data['fecha_limite']}*\n\n"
        f"({'(Fecha específica)' if fecha_limite != date(2003, 6, 1) else '(Fecha general — resto de deportes)'})\n\n"
        f"{PREGUNTA_ANOS}",
        parse_mode="Markdown"
    )
    return YEARS


async def years(update, context):
    anos_texto = update.message.text.strip()
    context.user_data["anos_texto"] = anos_texto
    anos_dep = extraer_anos(anos_texto)

    # Validar rango
    fecha_limite_str = context.user_data.get("fecha_limite", "01/06/2003")
    try:
        fl = datetime.strptime(fecha_limite_str, "%d/%m/%Y").date()
    except ValueError:
        fl = date(2003, 6, 1)

    # Intentar extraer año inicial
    try:
        partes = anos_texto.replace("–", "-").replace("—", "-").split("-")
        anio_ini = int(partes[0].strip()) if len(partes) == 2 else int(partes[0].strip())
        if anio_ini < 1980 or (len(partes) == 2 and int(partes[1].strip()) < 1980):
            await update.message.reply_text(
                "⚠️ El RD solo cubre desde el *15 de marzo de 1980*.\n"
                "Periodos anteriores no computan.",
                parse_mode="Markdown"
            )
    except (ValueError, IndexError):
        pass

    context.user_data["anos_dep"] = anos_dep
    await update.message.reply_text(PREGUNTA_SOLAPO, parse_mode="Markdown")
    return OVERLAP


async def overlap(update, context):
    r = update.message.text.strip().lower()
    if r in ("sí", "si", "s", "yes", "y", "sip", "síi"):
        await update.message.reply_text(DESCARTE_SOLAPO, parse_mode="Markdown")
        return ConversationHandler.END
    await update.message.reply_text(PREGUNTA_JUBILADO, parse_mode="Markdown")
    return JUBILADO


async def jubilado(update, context):
    r = update.message.text.strip().lower()
    ya = r in ("sí", "si", "s", "yes", "y", "sip", "ya", "jubilado", "jubilada")
    context.user_data["ya_jubilado"] = ya
    await update.message.reply_text(PREGUNTA_COTIZADOS, parse_mode="Markdown")
    return COTIZADOS


async def cotizados(update, context):
    r = update.message.text.strip().lower()
    if r in ("no", "no sé", "no se", "n", "no lo se", "no lo sé"):
        context.user_data["anos_cotizados"] = 25
    else:
        try:
            context.user_data["anos_cotizados"] = int(r.replace(".", "").replace(" ", ""))
        except ValueError:
            context.user_data["anos_cotizados"] = 25
    await update.message.reply_text(PREGUNTA_BASE, parse_mode="Markdown")
    return BASE


async def base(update, context):
    r = update.message.text.strip().lower()
    if r in ("no", "no sé", "no se", "n", "no lo se", "no lo sé"):
        br = 0
    else:
        try:
            br = float(r.replace(".", "").replace(",", ".").replace("€", "").replace(" ", ""))
        except ValueError:
            br = 0
    context.user_data["base"] = br

    # Calcular
    result = calc_pension(
        context.user_data["anos_dep"],
        br,
        anos_otros=context.user_data.get("anos_cotizados", 25),
        ya_jubilado=context.user_data.get("ya_jubilado", False),
    )
    result["deporte"] = context.user_data.get("deporte", "")
    context.user_data["simulacion"] = result

    msg = simulacion_msg(result, context.user_data["anos_texto"], context.user_data["fecha_limite"])
    await update.message.reply_text(msg, parse_mode="Markdown")
    await update.message.reply_text(PREGUNTA_CONTACTO, parse_mode="Markdown")
    return CONTACT


async def contact(update, context):
    datos = update.message.text.strip()
    usuario = update.effective_user
    sim = context.user_data.get("simulacion", {})

    lead = {
        "fecha": datetime.now().isoformat(),
        "deporte": context.user_data.get("deporte", ""),
        "anos": context.user_data.get("anos_texto", ""),
        "anos_dep": context.user_data.get("anos_dep", 0),
        "anos_cotizados": context.user_data.get("anos_cotizados", 25),
        "base": context.user_data.get("base", 0),
        "ya_jubilado": context.user_data.get("ya_jubilado", False),
        "inc_mes": sim.get("inc_mes", 0),
        "inc_ano": sim.get("inc_ano", 0),
        "contacto": datos,
        "tg_user": usuario.username or usuario.full_name,
        "tg_id": usuario.id,
    }

    leads = []
    if LEADS_FILE.exists():
        try:
            leads = json.loads(LEADS_FILE.read_text())
        except json.JSONDecodeError:
            leads = []
    leads.append(lead)
    LEADS_FILE.write_text(json.dumps(leads, indent=2, ensure_ascii=False))

    tipo = "REVISIÓN" if lead["ya_jubilado"] else "NUEVA"
    noti = (
        f"🏐 *NUEVO LEAD — RD Deporistas [{tipo}]*\n\n"
        f"📅 {lead['fecha'][:19]}\n"
        f"🏟 {lead['deporte']} | {lead['anos']}\n"
        f"👴 Ya jubilado: {'Sí' if lead['ya_jubilado'] else 'No'}\n"
        f"💶 Base: {lead['base']}€\n"
        f"📈 +{lead['inc_mes']}€/mes estimado\n"
        f"📞 {lead['contacto']}\n"
        f"💬 @{lead['tg_user']}"
    )
    try:
        await context.bot.send_message(ANTONIO_CHAT_ID, noti, parse_mode="Markdown")
    except Exception:
        pass

    await update.message.reply_text(DESPEDIDA, parse_mode="Markdown")
    return ConversationHandler.END


async def cancel(update, context):
    await update.message.reply_text("Cancelado. /start para reintentar.")
    return ConversationHandler.END


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
                    SPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sport)],
                    YEARS: [MessageHandler(filters.TEXT & ~filters.COMMAND, years)],
                    OVERLAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, overlap)],
                    JUBILADO: [MessageHandler(filters.TEXT & ~filters.COMMAND, jubilado)],
                    COTIZADOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cotizados)],
                    BASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, base)],
                    CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact)],
                },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    print(f"🤖 Bot RD 739/2026 v3 INICIADO | Entrada en vigor: {ENTRADA_VIGOR} ({(ENTRADA_VIGOR - date.today()).days} días)")
    app.run_polling()


if __name__ == "__main__":
    main()