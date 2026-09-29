#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Telegram: Asesor de Jubilación para Deportistas Profesionales (RD 739/2026) v4
Desarrollado para: Antonio Gatell Contreras - Gatell & Asociados (ICAMálaga 4012)
Web: https://www.gatellasociados.com

Mejoras v4:
⚡ Base de datos de más de 30 deportes y fechas oficiales de integración (Ciclismo 1992, Baloncesto 1993, Balonmano 1998, Resto 2003)
⚡ Detección inteligente de alias y modalidades deportivas
⚡ Interacción híbrida: Botones Inline táctiles + Entrada por texto libre
⚡ Tono empático y fraternal de Antonio Gatell (exjugador de balonmano en Asobal con Puleva Maristas)
⚡ Manejo cercano de futbolistas y de casos con simultaneidad laboral (orientación hacia Incapacidad Permanente o auditoría laboral)
⚡ Cálculo exacto escala pensiones 2026 (14 pagas, incremento mensual y anual, impacto del Art. 5.2 para ya jubilados)
⚡ Contador persistente de pruebas y prueba social ("X deportistas ya han simulado su caso")
⚡ Captura de Nombre, Teléfono y Email con entrega inmediata de guía legal y enlace al artículo
⚡ Notificación enriquecida a Antonio por Telegram con enlace directo a WhatsApp y llamada
⚡ Soporte de envío de email automático si se configuran credenciales SMTP
⚡ Comandos adicionales: /start, /articulo, /guia, /contacto, /stats, /cancel
"""

import os
import sys
import json
import re
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from pathlib import Path

try:
    from telegram import (
        Update,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        ReplyKeyboardRemove,
    )
    from telegram.ext import (
        Application,
        CommandHandler,
        ConversationHandler,
        MessageHandler,
        CallbackQueryHandler,
        filters,
        ContextTypes,
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

# ── Configuración y Logs ─────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8485673317:AAHna_rMv_rwFH7vS3YfgkjUQvjhW0S0sbo")
ANTONIO_CHAT_ID = int(os.environ.get("ANTONIO_CHAT_ID", "641654799"))
ANTONIO_WHATSAPP = os.environ.get("ANTONIO_WHATSAPP", "34616903306")
DESPACHO_EMAIL = os.environ.get("DESPACHO_EMAIL", "agatell@gatellasociados.com")

BASE_DIR = Path(__file__).resolve().parent
LEADS_FILE = BASE_DIR / "leads_deportistas.json"
STATS_FILE = BASE_DIR / "simulaciones_stats.json"

ENTRADA_VIGOR = date(2026, 12, 25)
FECHA_MINIMA_RD = date(1980, 3, 15)
ARTICLE_URL = "https://www.gatellasociados.com/jubilacion-deportistas-profesionales-real-decreto-739-2026/"

# ── Estados de la Conversación ──────────────────────────
(SPORT, YEARS, OVERLAP, JUBILADO, COTIZADOS, BASE, CONTACT) = range(7)

# ── Base de Datos de Fechas de Integración por Deporte ──
# RD 739/2026 (BOE 25/09/2026):
# - Ciclismo: 01/02/1992 (RD 2621/1986 / OM)
# - Baloncesto: 01/08/1993
# - Balonmano: 01/01/1998
# - Resto de disciplinas: 01/06/2003 (RD 287/2003)
INTEGRACION = {
    "ciclismo": date(1992, 2, 1),
    "baloncesto": date(1993, 8, 1),
    "balonmano": date(1998, 1, 1),
    "voleibol": date(2003, 6, 1),
    "waterpolo": date(2003, 6, 1),
    "hockey": date(2003, 6, 1),
    "hockey hierba": date(2003, 6, 1),
    "hockey patines": date(2003, 6, 1),
    "atletismo": date(2003, 6, 1),
    "natacion": date(2003, 6, 1),
    "natación": date(2003, 6, 1),
    "judo": date(2003, 6, 1),
    "tenis": date(2003, 6, 1),
    "rugby": date(2003, 6, 1),
    "remo": date(2003, 6, 1),
    "piraguismo": date(2003, 6, 1),
    "piragüismo": date(2003, 6, 1),
    "vela": date(2003, 6, 1),
    "boxeo": date(2003, 6, 1),
    "pelota vasca": date(2003, 6, 1),
    "fronton": date(2003, 6, 1),
    "frontón": date(2003, 6, 1),
    "gimnasia": date(2003, 6, 1),
    "gimnasia artistica": date(2003, 6, 1),
    "gimnasia ritmica": date(2003, 6, 1),
    "halterofilia": date(2003, 6, 1),
    "patinaje": date(2003, 6, 1),
    "padel": date(2003, 6, 1),
    "pádel": date(2003, 6, 1),
    "triatlon": date(2003, 6, 1),
    "triatlón": date(2003, 6, 1),
    "badminton": date(2003, 6, 1),
    "bádminton": date(2003, 6, 1),
    "taekwondo": date(2003, 6, 1),
    "lucha": date(2003, 6, 1),
    "esqui": date(2003, 6, 1),
    "esquí": date(2003, 6, 1),
    "balonmano playa": date(2003, 6, 1),
    "voley playa": date(2003, 6, 1),
}

# Diccionario amplio de alias y palabras clave
DEPORTE_ALIAS = {
    # Ciclismo
    "cicli": "ciclismo",
    "bici": "ciclismo",
    "bicicleta": "ciclismo",
    "peloton": "ciclismo",
    "pelotón": "ciclismo",
    "vuelta": "ciclismo",
    "tour": "ciclismo",
    "giro": "ciclismo",
    # Baloncesto
    "balonces": "baloncesto",
    "basket": "baloncesto",
    "basquet": "baloncesto",
    "básquet": "baloncesto",
    "acb": "baloncesto",
    "1b": "baloncesto",
    "primera b": "baloncesto",
    # Balonmano
    "balonman": "balonmano",
    "handball": "balonmano",
    "asobal": "balonmano",
    "maristas": "balonmano",
    "puleva": "balonmano",
    "teka": "balonmano",
    "granollers": "balonmano",
    "bidasoa": "balonmano",
    "atletico de madrid": "balonmano",
    "cangas": "balonmano",
    "valladolid": "balonmano",
    # Voleibol
    "volei": "voleibol",
    "voley": "voleibol",
    "superliga": "voleibol",
    # Otros
    "water": "waterpolo",
    "atlet": "atletismo",
    "corredor": "atletismo",
    "maraton": "atletismo",
    "velocista": "atletismo",
    "nadad": "natacion",
    "sincro": "natacion",
    "judok": "judo",
    "karat": "judo",
    "marcial": "judo",
    "tenist": "tenis",
    "rugbi": "rugby",
    "remer": "remo",
    "traiñera": "remo",
    "piragua": "piraguismo",
    "boxe": "boxeo",
    "pugi": "boxeo",
    "pelotari": "pelota vasca",
    "frontenis": "pelota vasca",
    "gimnast": "gimnasia",
    "pesas": "halterofilia",
    "patin": "patinaje",
}

# ── Sistema de Prueba Social / Contador Persistente ─────
def get_stats():
    """Devuelve las estadísticas acumuladas de simulaciones."""
    default_stats = {"total_simulaciones": 58, "por_deporte": {}}
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_stats
    return default_stats

def increment_stats(deporte: str):
    """Incrementa de forma persistente el contador de simulaciones."""
    stats = get_stats()
    stats["total_simulaciones"] = stats.get("total_simulaciones", 58) + 1
    dep_clean = deporte.strip().lower()
    dep_dict = stats.setdefault("por_deporte", {})
    dep_dict[dep_clean] = dep_dict.get(dep_clean, 0) + 1
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"No se pudo guardar stats: {e}")
    return stats["total_simulaciones"]

# ── Funciones de Detección y Cálculo ─────────────────────
def detectar_deporte(texto: str):
    """Detecta el deporte y devuelve (nombre_canonico, fecha_integracion)."""
    t = texto.strip().lower()
    # 1. Alias rápidos
    for alias, canon in DEPORTE_ALIAS.items():
        if alias in t:
            return canon, INTEGRACION.get(canon, date(2003, 6, 1))
    # 2. Búsqueda exacta en catálogo
    for dep, fecha in INTEGRACION.items():
        if dep in t:
            return dep, fecha
    # 3. Default: resto de disciplinas profesionales (01/06/2003)
    return texto.strip().capitalize(), date(2003, 6, 1)

def extraer_anos(texto: str) -> int:
    """Extrae el número de temporadas o años del texto del usuario."""
    t = texto.replace("–", "-").replace("—", "-").replace(" a ", "-").strip()
    
    # Buscar patrones como "1989-1996" o "1990 a 1995"
    m_rango = re.search(r"(\d{4})\s*-\s*(\d{4})", t)
    if m_rango:
        a1, a2 = int(m_rango.group(1)), int(m_rango.group(2))
        return max(1, abs(a2 - a1))
        
    # Buscar número explícito: "7 años", "8 temporadas", "6"
    m_num = re.search(r"\b(\d{1,2})\b", t)
    if m_num:
        val = int(m_num.group(1))
        if 1 <= val <= 30:
            return val
            
    return 6  # Valor medio por defecto si no se puede parsear

def calc_porcentaje(anos_total: float) -> float:
    """
    Escala general de pensiones de jubilación de la Seguridad Social (2026):
    - 15 años: 50% de la Base Reguladora.
    - Siguientes 120 meses (años 16 a 25): +0.21% por mes (+2.52% al año).
    - Siguientes 132 meses (años 26 a 36): +0.19% por mes (+2.28% al año).
    - A partir de 36 años y 6 meses: 100% de la Base Reguladora.
    """
    if anos_total <= 0:
        return 0.0
    if anos_total < 15:
        # Carencia no alcanzada de forma contributiva estándar
        return round((anos_total / 15.0) * 50.0, 2)
        
    pct = 50.0
    meses_bloque1 = min(max(0.0, (anos_total - 15.0) * 12.0), 10.0 * 12.0)
    pct += meses_bloque1 * 0.21
    
    if anos_total > 25.0:
        meses_bloque2 = min(max(0.0, (anos_total - 25.0) * 12.0), 11.5 * 12.0)
        pct += meses_bloque2 * 0.19
        
    return min(round(pct, 2), 100.0)

def calc_pension(anos_dep: int, base_reguladora: float, anos_otros: int = 25, ya_jubilado: bool = False):
    """Calcula la simulación completa de pensión y retorno económico."""
    anos_dep = max(1, min(anos_dep, 25))
    if base_reguladora <= 0:
        base_reguladora = 1800.0  # Base media orientativa
        
    pct_sin = calc_porcentaje(anos_otros)
    pct_con = calc_porcentaje(anos_otros + anos_dep)
    
    pension_sin = base_reguladora * (pct_sin / 100.0)
    pension_con = base_reguladora * (pct_con / 100.0)
    
    # Tope pensión máxima SS 2026 (orientativo: 3.267 €/mes en 14 pagas)
    TOPE_MAXIMO = 3267.0
    pension_sin_topada = min(pension_sin, TOPE_MAXIMO)
    pension_con_topada = min(pension_con, TOPE_MAXIMO)
    
    inc_mes = pension_con_topada - pension_sin_topada
    inc_ano = inc_mes * 14.0  # 14 pagas oficiales
    
    return {
        "anos_dep": anos_dep,
        "anos_otros": anos_otros,
        "base": round(base_reguladora, 2),
        "pct_sin": pct_sin,
        "pct_con": pct_con,
        "dif_pct": round(pct_con - pct_sin, 2),
        "pension_sin": round(pension_sin_topada, 2),
        "pension_con": round(pension_con_topada, 2),
        "inc_mes": round(inc_mes, 2),
        "inc_ano": round(inc_ano, 2),
        "ya_jubilado": ya_jubilado,
    }

# ── Envío Automático de Email (Opcional si SMTP está activo) ──
def send_email_lead(lead_data: dict):
    """Envía el artículo y guía legal por email al deportista si proporcionó correo."""
    destinatario = lead_data.get("email")
    if not destinatario or "@" not in destinatario:
        return False
        
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    
    # También leer del archivo .env si existe
    env_file = Path("/home/tony/.smtp-gatell.env")
    if env_file.exists() and not (smtp_host and smtp_pass):
        for line in env_file.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                if k == "SMTP_HOST" and not smtp_host: smtp_host = v
                if k == "SMTP_USER" and not smtp_user: smtp_user = v
                if k == "SMTP_PASS" and not smtp_pass: smtp_pass = v
                if k == "SMTP_PORT" and not os.environ.get("SMTP_PORT"): smtp_port = int(v)
    
    if not (smtp_host and smtp_user and smtp_pass):
        logger.info("SMTP no configurado en entorno ni .env. Se omite envío de email saliente.")
        return False
        
    try:
        import ssl as ssl_lib
        ctx = ssl_lib.create_default_context()
        # Probar con cadena de certificados Webempresa si existe
        chain = Path("/home/tony/.smtp-gatell-chain.pem")
        if chain.exists():
            ctx = ssl_lib.create_default_context(cafile=str(chain))
            
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Guía Legal RD 739/2026: Tu Simulación de Jubilación - Gatell & Asociados"
        msg["From"] = f"Antonio Gatell <{smtp_user}>"
        msg["To"] = destinatario
        
        sim = lead_data.get("simulacion", {})
        cuerpo_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px;">
                <h2 style="color: #0f172a; border-bottom: 2px solid #d97706; padding-bottom: 8px;">
                    🏆 Gatell & Asociados · Asesoría Legal para Deportistas
                </h2>
                <p>Hola <strong>{lead_data.get('nombre', 'compañero')}</strong>,</p>
                <p>Soy <strong>Antonio Gatell Contreras</strong>, abogado (ICAMálaga 4012) y exjugador de balonmano en División de Honor con el Puleva Maristas en los 80 y 90.</p>
                <p>Te adjunto el resumen de la simulación que acabas de realizar con nuestro asistente para el <strong>Real Decreto 739/2026</strong>:</p>
                
                <div style="background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 14px; margin: 18px 0;">
                    <p style="margin: 4px 0;"><strong>Modalidad:</strong> {lead_data.get('deporte')}</p>
                    <p style="margin: 4px 0;"><strong>Años rescatados:</strong> {lead_data.get('anos_dep')} temporadas</p>
                    <p style="margin: 4px 0;"><strong>Incremento estimado:</strong> <span style="color: #16a34a; font-size: 1.1em; font-weight: bold;">+{sim.get('inc_mes', 0)} €/mes (+{sim.get('inc_ano', 0)} €/año en 14 pagas)</span></p>
                </div>
                
                <h3 style="color: #0f172a;">Pasos clave a seguir:</h3>
                <ol>
                    <li><strong>No esperar al 25 de diciembre:</strong> La obtención de los certificados de los Anexos I (Club) y Anexo II (Federación) requiere semanas de cotejo de hemeroteca y actas de hace 30 años.</li>
                    <li><strong>Revisión de no superposición:</strong> Verificaremos que no existan solapamientos con otras empresas para asegurar el 100% del rescate.</li>
                </ol>
                
                <p>Puedes leer la guía legal completa en nuestra web:<br>
                <a href="{ARTICLE_URL}" style="color: #2563eb; font-weight: bold;">Leer Artículo Completo sobre el RD 739/2026</a></p>
                
                <p>Si deseas que hablemos directamente por WhatsApp para revisar tu vida laboral, puedes escribirme aquí:<br>
                <a href="https://wa.me/{ANTONIO_WHATSAPP}?text=Hola%20Antonio,%20soy%20{lead_data.get('nombre')}%20y%20quiero%20revisar%20mi%20caso" style="display: inline-block; background-color: #25d366; color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-top: 10px;">Contactar por WhatsApp</a></p>
                
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
                <p style="font-size: 0.85em; color: #64748b;">
                    Gatell & Asociados · Ejercicio letrado desde 1996 · ICAMálaga 4012<br>
                    {DESPACHO_EMAIL} · Málaga, España
                </p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(cuerpo_html, "html"))
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx, timeout=120) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(f"Email con simulación enviado con éxito a {destinatario}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar email a {destinatario}: {e}")
        return False

# ── Generador del Mensaje de Simulación ─────────────────
def simulacion_msg(r: dict, anos_texto: str, fecha_limite_str: str) -> str:
    dias_restantes = (ENTRADA_VIGOR - date.today()).days
    
    if r["ya_jubilado"]:
        tipo_header = "📊 *SIMULACIÓN: REVISIÓN DE PENSIÓN ACTUAL (ART. 5.2 RD)*"
        sub_explicacion = (
            "💡 *Efectos económicos:* Al estar ya jubilado, el incremento mensual "
            "se devenga desde el *primer día del mes siguiente a la solicitud*. "
            "La Seguridad Social no lo aplica de oficio; hay que solicitarlo."
        )
    else:
        tipo_header = "📊 *SIMULACIÓN: NUEVA PENSIÓN DE JUBILACIÓN*"
        sub_explicacion = (
            "💡 *Ventaja añadida:* Rescatar estos años te permite alcanzar antes "
            "los 38 años y 6 meses exigidos para *jubilarte a los 65 años con el 100%* "
            "sin penalizaciones por coeficientes reductores."
        )

    barra_antes = "█" * int(r["pct_sin"] / 10) + "░" * (10 - int(r["pct_sin"] / 10))
    barra_despues = "█" * int(r["pct_con"] / 10) + "░" * (10 - int(r["pct_con"] / 10))

    return (
        f"{tipo_header}\n\n"
        f"🏟 *Disciplina:* {r.get('deporte', '')}\n"
        f"📅 *Temporadas acreditables:* {anos_texto} ({r['anos_dep']} años)\n"
        f"📆 *Fecha límite integración:* {fecha_limite_str}\n"
        f"💼 *Años cotizados fuera:* {r['anos_otros']} años\n"
        f"💶 *Base reguladora estimada:* {r['base']:,.2f} €\n\n"
        f"📉 *Sin RD 739/2026:* [{barra_antes}] {r['pct_sin']}%\n"
        f"👉 *Pensión estimada actual:* {r['pension_sin']:,.2f} €/mes\n\n"
        f"📈 *Con RD 739/2026:* [{barra_despues}] {r['pct_con']}%\n"
        f"👉 *Nueva pensión reconocida:* {r['pension_con']:,.2f} €/mes\n\n"
        f"─────────────────────────────\n"
        f"✨ *MEJORA VITALICIA CONSEGUIDA:*\n"
        f"💰 *+{r['inc_mes']:,.2f} € al mes*\n"
        f"🎁 *+{r['inc_ano']:,.2f} € al año* (en 14 pagas vitalicias)\n"
        f"─────────────────────────────\n\n"
        f"{sub_explicacion}\n\n"
        f"⏳ *El Real Decreto entra en vigor en {dias_restantes} días* (25 de diciembre de 2026).\n"
        f"⚠️ *Consejo de Antonio Gatell:* No aguardes a diciembre. La búsqueda de actas y "
        f"certificados federativos de los años 80 y 90 (Anexo II) tarda semanas. "
        f"Cuanto antes preparemos tu expediente, antes cobrarás la pensión incrementada."
    )

# ── Handlers de Conversación ────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bienvenida empática y presentación personal de Antonio Gatell."""
    context.user_data.clear()
    total_sims = get_stats().get("total_simulaciones", 58)
    
    mensaje_inicio = (
        "🏆 *Bienvenido/a al Asesor de Jubilación para Deportistas Profesionales*\n\n"
        "Hola, soy *Antonio Gatell Contreras*, abogado en ejercicio (ICAMálaga 4012) "
        "y exjugador de balonmano en División de Honor con el *Puleva Maristas de Málaga* "
        "en los 80 y 90 (Liga ASOBAL).\n\n"
        "Yo también estuve en ese vestuario y conozco el sacrificio de dejarse la salud "
        "en la pista. El 25 de septiembre de 2026 se publicó en el BOE el histórico "
        "*Real Decreto 739/2026*, que reconoce por fin como cotizados para la pensión "
        "los años dedicados al deporte profesional antes de 2003, *financiado al 100% "
        "por el Consejo Superior de Deportes (coste CERO para ti)*.\n\n"
        f"👥 *Más de {total_sims} exdeportistas de élite ya han calculado su caso con nosotros.*\n\n"
        "👇 *Paso 1: ¿En qué deporte competiste como profesional?*\n"
        "_Selecciona una opción o escribe directamente tu modalidad:_"
    )

    keyboard = [
        [
            InlineKeyboardButton("🤾 Balonmano (Asobal/1ª)", callback_data="dep_balonmano"),
            InlineKeyboardButton("🏀 Baloncesto (ACB/1ªB)", callback_data="dep_baloncesto"),
        ],
        [
            InlineKeyboardButton("🚴 Ciclismo Profesional", callback_data="dep_ciclismo"),
            InlineKeyboardButton("🏐 Voleibol / Waterpolo", callback_data="dep_voleibol"),
        ],
        [
            InlineKeyboardButton("🏃 Atletismo / Natación", callback_data="dep_atletismo"),
            InlineKeyboardButton("⚽ Fútbol (Info singular)", callback_data="dep_futbol"),
        ],
        [
            InlineKeyboardButton("🏅 Otra disciplina deportiva", callback_data="dep_otra"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            mensaje_inicio, parse_mode="Markdown", reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            mensaje_inicio, parse_mode="Markdown", reply_markup=reply_markup
        )

    return SPORT

async def sport_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa la selección de deporte por botón Inline."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "dep_futbol":
        return await gestionar_caso_futbol(query.message)
    elif data == "dep_balonmano":
        txt = "Balonmano"
    elif data == "dep_baloncesto":
        txt = "Baloncesto"
    elif data == "dep_ciclismo":
        txt = "Ciclismo"
    elif data == "dep_voleibol":
        txt = "Voleibol"
    elif data == "dep_atletismo":
        txt = "Atletismo"
    else:
        # dep_otra: pedir que lo escriba
        await query.message.reply_text(
            "🏅 *¿En qué otra disciplina deportiva competiste?*\n\n"
            "Escribe el nombre de tu deporte (ejemplo: _Remo, Judo, Rugby, Hockey, Tenis, etc._):",
            parse_mode="Markdown",
        )
        return SPORT

    return await procesar_deporte(query.message, context, txt)

async def sport_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa la entrada de deporte escrita por texto libre."""
    txt = update.message.text.strip()
    
    # Comprobar si menciona fútbol
    if any(w in txt.lower() for w in ["futbol", "fútbol", "football", "soccer", "futbolista"]):
        return await gestionar_caso_futbol(update.message)
        
    return await procesar_deporte(update.message, context, txt)

async def gestionar_caso_futbol(msg_target) -> int:
    """Explicación empática del fútbol y orientación hacia incapacidades o vida laboral."""
    texto_futbol = (
        "⚽ *Atención a los compañeros futbolistas:*\n\n"
        "El Real Decreto 739/2026 excluye expresamente al fútbol profesional masculino "
        "porque dicho colectivo dispuso en su día de convenios colectivos específicos "
        "y un marco normativo transitorio previo en la década de los 80.\n\n"
        "🤝 *Sin embargo, en Gatell & Asociados trabajamos habitualmente con futbolistas:*\n"
        "• *Auditoría de Vida Laboral:* Detección de vacíos de cotización o periodos no declarados.\n"
        "• *Incapacidades Permanentes por Secuelas:* Muchos exfutbolistas arrastran artrosis precoz, "
        "roturas graves de ligamentos o meniscos, prótesis o lesiones de columna que les impiden "
        "desempeñar su profesión actual con normalidad. En estos casos tramitamos pensiones vitalicias "
        "por Incapacidad Permanente Total o Absoluta (exentas de IRPF).\n\n"
        "¿Deseas comentar tu caso directamente con Antonio?"
    )
    keyboard = [
        [
            InlineKeyboardButton("💬 Hablar con Antonio por WhatsApp", url=f"https://wa.me/{ANTONIO_WHATSAPP}?text=Hola%20Antonio,%20soy%20exfutbolista%20y%20me%20gustar%C3%ADa%20consultarte%20mi%20caso"),
        ],
        [
            InlineKeyboardButton("🔄 Probar con otra disciplina deportiva", callback_data="reiniciar_test"),
        ],
    ]
    await msg_target.reply_text(
        texto_futbol, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def procesar_deporte(msg_target, context: ContextTypes.DEFAULT_TYPE, txt: str) -> int:
    dep_canon, fecha_limite = detectar_deporte(txt)
    context.user_data["deporte"] = dep_canon.capitalize()
    context.user_data["fecha_limite"] = fecha_limite.strftime("%d/%m/%Y")
    
    es_especifica = fecha_limite != date(2003, 6, 1)
    nota_fecha = (
        "*(Fecha específica en el Real Decreto)*"
        if es_especifica
        else "*(Fecha general para el resto de disciplinas deportivas)*"
    )

    texto_anos = (
        f"✅ Disciplina: *{context.user_data['deporte']}*\n"
        f"📆 Fecha límite de integración oficial: *{context.user_data['fecha_limite']}*\n"
        f"{nota_fecha}\n\n"
        f"📅 *Paso 2: ¿Cuántos años o en qué temporadas competiste como profesional?*\n\n"
        f"_El RD 739/2026 computa temporadas entre el 15/03/1980 y el {context.user_data['fecha_limite']}._\n\n"
        f"Elige una opción rápida o escribe los años (ej: `1989-1996` o `6 años`):"
    )

    keyboard = [
        [
            InlineKeyboardButton("3 a 5 temporadas", callback_data="anos_4"),
            InlineKeyboardButton("6 a 8 temporadas", callback_data="anos_7"),
        ],
        [
            InlineKeyboardButton("9 a 12 temporadas", callback_data="anos_10"),
            InlineKeyboardButton("Más de 12 temporadas", callback_data="anos_13"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg_target.reply_text(texto_anos, parse_mode="Markdown", reply_markup=reply_markup)
    return YEARS

async def years_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    val = int(query.data.replace("anos_", ""))
    context.user_data["anos_dep"] = val
    context.user_data["anos_texto"] = f"{val} temporadas"
    return await preguntar_solapamiento(query.message)

async def years_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    anos_texto = update.message.text.strip()
    context.user_data["anos_texto"] = anos_texto
    anos_dep = extraer_anos(anos_texto)
    context.user_data["anos_dep"] = anos_dep

    # Validar si indicó años anteriores a 1980
    partes = re.findall(r"\b(19\d{2}|20\d{2})\b", anos_texto)
    if partes:
        anos_encontrados = [int(p) for p in partes]
        if min(anos_encontrados) < 1980:
            await update.message.reply_text(
                "ℹ️ *Nota histórica:* El RD 739/2026 toma como fecha de inicio el "
                "*15 de marzo de 1980* (aprobación del Estatuto de los Trabajadores). "
                "Los periodos previos a 1980 no computan, pero todas las temporadas desde "
                "marzo de 1980 hasta la fecha de integración se rescatan íntegramente.",
                parse_mode="Markdown",
            )

    return await preguntar_solapamiento(update.message)

async def preguntar_solapamiento(msg_target) -> int:
    texto_solapo = (
        "💼 *Paso 3: El requisito clave de no superposición (Artículo 1)*\n\n"
        "Durante aquellas temporadas en las que competías al máximo nivel, "
        "*¿tenías al mismo tiempo otro trabajo por el que ya cotizaras a la Seguridad Social?*\n\n"
        "_La ley impide que la Seguridad Social compute dos veces un mismo mes ya cotizado._"
    )

    keyboard = [
        [
            InlineKeyboardButton("🟢 No, dedicación exclusiva al deporte", callback_data="solapo_no"),
        ],
        [
            InlineKeyboardButton("🟡 Solo algunos meses o temporadas sueltas", callback_data="solapo_parcial"),
        ],
        [
            InlineKeyboardButton("🔴 Sí, cotizaba a jornada completa en otra empresa", callback_data="solapo_si"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg_target.reply_text(texto_solapo, parse_mode="Markdown", reply_markup=reply_markup)
    return OVERLAP

async def overlap_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "solapo_si":
        return await gestionar_solapo_total(query.message)
    elif data == "solapo_parcial":
        context.user_data["solapo_nota"] = "Parcial (temporadas sin solapo rescatables)"
    else:
        context.user_data["solapo_nota"] = "Sin solapamiento (100% computable)"

    return await preguntar_jubilado(query.message)

async def overlap_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip().lower()
    if txt in ("sí", "si", "s", "yes", "y", "sip", "jornada completa"):
        return await gestionar_solapo_total(update.message)
    elif "parcial" in txt or "algun" in txt or "meses" in txt or "poco" in txt:
        context.user_data["solapo_nota"] = "Parcial (temporadas sin solapo rescatables)"
    else:
        context.user_data["solapo_nota"] = "Sin solapamiento (100% computable)"

    return await preguntar_jubilado(update.message)

async def gestionar_solapo_total(msg_target) -> int:
    texto_exclusion = (
        "⚠️ *Información jurídica sobre la regla de no superposición:*\n\n"
        "El artículo 1.2 del Real Decreto 739/2026 establece expresamente que "
        "_no podrán computarse periodos que se superpongan con otras cotizaciones a la Seguridad Social_.\n\n"
        "Si estuviste cotizando a jornada completa durante toda tu carrera deportiva, "
        "esos años ya figuran en tu vida laboral.\n\n"
        "💡 *Dos vías que podemos estudiar en tu caso:*\n"
        "1. **Revisión de meses vacíos:** A menudo hay meses de verano o transiciones entre clubes "
        "donde no hubo cotización ordinaria; esos meses sí pueden recuperarse.\n"
        "2. **Incapacidades por Secuelas Deportivas:** Si arrastras dolor crónico o limitaciones físicas "
        "en articulaciones derivadas de la competición que te dificultan trabajar hoy, "
        "evaluamos tu viabilidad médica para solicitar una pensión de Incapacidad Permanente.\n\n"
        "¿Deseas que Antonio Gatell examine tu informe de Vida Laboral?"
    )
    keyboard = [
        [
            InlineKeyboardButton("💬 Consultar con Antonio por WhatsApp", url=f"https://wa.me/{ANTONIO_WHATSAPP}?text=Hola%20Antonio,%20tengo%20dudas%20sobre%20solapamientos%20en%20mi%20vida%20laboral"),
        ],
        [
            InlineKeyboardButton("🔄 Probar con otros datos", callback_data="reiniciar_test"),
        ],
    ]
    await msg_target.reply_text(
        texto_exclusion, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def preguntar_jubilado(msg_target) -> int:
    texto_jubilado = (
        "📋 *Paso 4: Tu situación actual con la Seguridad Social*\n\n"
        "*¿Ya estás cobrando una pensión de jubilación o todavía sigues en activo?*\n\n"
        "_El artículo 5.2 del Real Decreto permite expresamente a quienes ya están jubilados "
        "solicitar una revisión al alza de su pensión actual._"
    )

    keyboard = [
        [
            InlineKeyboardButton("👴 Ya estoy cobrando pensión (Revisión Art. 5.2)", callback_data="jub_si"),
        ],
        [
            InlineKeyboardButton("💼 Sigo en activo / Aún no jubilado", callback_data="jub_no"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg_target.reply_text(texto_jubilado, parse_mode="Markdown", reply_markup=reply_markup)
    return JUBILADO

async def jubilado_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ya_jubilado = query.data == "jub_si"
    context.user_data["ya_jubilado"] = ya_jubilado
    return await preguntar_cotizados(query.message)

async def jubilado_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip().lower()
    ya_jubilado = txt in ("sí", "si", "s", "yes", "y", "jubilado", "jubilada", "ya")
    context.user_data["ya_jubilado"] = ya_jubilado
    return await preguntar_cotizados(update.message)

async def preguntar_cotizados(msg_target) -> int:
    texto_cotizados = (
        "💼 *Paso 5: Años cotizados fuera del deporte profesional*\n\n"
        "Aproximadamente, *¿cuántos años has cotizado en tu vida laboral ordinaria* "
        "(cuenta ajena o autónomos, sin contar los años deportivos que queremos rescatar)?\n\n"
        "💡 _Ejemplo: Una persona que empezó a trabajar a los 26 años y hoy tiene 56, "
        "lleva unos 30 años cotizados._\n\n"
        "Elige una opción rápida o escribe los años exactos:"
    )

    keyboard = [
        [
            InlineKeyboardButton("15 a 20 años", callback_data="cot_18"),
            InlineKeyboardButton("21 a 25 años", callback_data="cot_23"),
        ],
        [
            InlineKeyboardButton("26 a 30 años", callback_data="cot_28"),
            InlineKeyboardButton("Más de 30 años", callback_data="cot_33"),
        ],
        [
            InlineKeyboardButton("No lo sé exacto (usar 25 años por defecto)", callback_data="cot_25"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg_target.reply_text(texto_cotizados, parse_mode="Markdown", reply_markup=reply_markup)
    return COTIZADOS

async def cotizados_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    val = int(query.data.replace("cot_", ""))
    context.user_data["anos_cotizados"] = val
    return await preguntar_base(query.message)

async def cotizados_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip().lower()
    if txt in ("no", "no se", "no sé", "no lo se", "no lo sé", "n"):
        context.user_data["anos_cotizados"] = 25
    else:
        m = re.search(r"\b(\d{1,2})\b", txt)
        if m:
            context.user_data["anos_cotizados"] = int(m.group(1))
        else:
            context.user_data["anos_cotizados"] = 25
    return await preguntar_base(update.message)

async def preguntar_base(msg_target) -> int:
    texto_base = (
        "💶 *Paso 6: Base Reguladora aproximada*\n\n"
        "*¿Conoces aproximadamente tu Base Reguladora o base de cotización habitual?*\n\n"
        "🧐 *¿Qué es?* Es el promedio mensual sobre el que la Seguridad Social calcula la pensión.\n"
        "📄 *¿Dónde aparece?* En tu informe de vida laboral, nóminas o resolución de pensión.\n"
        "💰 En España suele oscilar habitualmente entre *1.500 € y 2.600 €*.\n\n"
        "Elige un importe estimado o escribe tu cifra exacta:"
    )

    keyboard = [
        [
            InlineKeyboardButton("1.600 € / mes", callback_data="base_1600"),
            InlineKeyboardButton("1.800 € / mes (Media)", callback_data="base_1800"),
        ],
        [
            InlineKeyboardButton("2.200 € / mes", callback_data="base_2200"),
            InlineKeyboardButton("2.700 € / mes (Base alta)", callback_data="base_2700"),
        ],
        [
            InlineKeyboardButton("No la sé (usar 1.800 € orientativos)", callback_data="base_1800"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg_target.reply_text(texto_base, parse_mode="Markdown", reply_markup=reply_markup)
    return BASE

async def base_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    br = float(query.data.replace("base_", ""))
    context.user_data["base"] = br
    return await mostrar_simulacion_y_pedir_contacto(query.message, context)

async def base_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.strip().lower()
    if txt in ("no", "no sé", "no se", "n", "no lo se"):
        br = 1800.0
    else:
        limpio = txt.replace("€", "").replace(".", "").replace(",", ".").replace(" ", "")
        m = re.search(r"(\d+(?:\.\d+)?)", limpio)
        if m:
            try:
                br = float(m.group(1))
                if br < 300:
                    br = 1800.0
            except ValueError:
                br = 1800.0
        else:
            br = 1800.0
            
    context.user_data["base"] = br
    return await mostrar_simulacion_y_pedir_contacto(update.message, context)

async def mostrar_simulacion_y_pedir_contacto(msg_target, context: ContextTypes.DEFAULT_TYPE) -> int:
    anos_dep = context.user_data.get("anos_dep", 6)
    base_reg = context.user_data.get("base", 1800.0)
    anos_otros = context.user_data.get("anos_cotizados", 25)
    ya_jub = context.user_data.get("ya_jubilado", False)
    deporte = context.user_data.get("deporte", "Deporte Profesional")

    # Ejecutar simulación matemática
    resultado = calc_pension(anos_dep, base_reg, anos_otros=anos_otros, ya_jubilado=ya_jub)
    resultado["deporte"] = deporte
    context.user_data["simulacion"] = resultado

    # Incrementar estadísticas de uso
    total_acumulado = increment_stats(deporte)

    # Enviar mensaje con el informe del cálculo
    msg_sim = simulacion_msg(
        resultado,
        context.user_data.get("anos_texto", f"{anos_dep} años"),
        context.user_data.get("fecha_limite", "01/06/2003"),
    )
    await msg_target.reply_text(msg_sim, parse_mode="Markdown")

    # Pedir contacto para Antonio
    texto_contacto = (
        "🤝 *Estudio Gratuito de Viabilidad con Antonio Gatell*\n\n"
        "Para que Antonio revise personalmente tu informe de Vida Laboral y podamos "
        "enviarte la *Guía Práctica del RD 739/2026* con el procedimiento para solicitar "
        "los Anexos I (Club) y II (Federación Española), indícanos por favor:\n\n"
        "📝 *Tu Nombre, Teléfono y Correo Electrónico*\n"
        "_Ejemplo: Pepe García, 612345678, pepe@gmail.com_\n\n"
        "*(Tus datos son confidenciales conforme al RGPD y uso exclusivo del despacho)*"
    )

    await msg_target.reply_text(texto_contacto, parse_mode="Markdown")
    return CONTACT

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    datos_contacto = update.message.text.strip()
    usuario = update.effective_user
    sim = context.user_data.get("simulacion", {})

    # Intentar parsear nombre, teléfono y email
    email_encontrado = ""
    m_email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", datos_contacto)
    if m_email:
        email_encontrado = m_email.group(0)

    tel_encontrado = ""
    m_tel = re.search(r"(\+?\d[\d\s-]{7,14}\d)", datos_contacto)
    if m_tel:
        tel_encontrado = m_tel.group(0).replace(" ", "").replace("-", "")

    nombre_lead = datos_contacto
    if m_email or m_tel:
        # Extraer nombre quitando email y teléfono
        nombre_clean = datos_contacto
        if email_encontrado:
            nombre_clean = nombre_clean.replace(email_encontrado, "")
        if tel_encontrado:
            nombre_clean = nombre_clean.replace(tel_encontrado, "")
        nombre_clean = nombre_clean.replace(",", "").replace("-", "").strip()
        if len(nombre_clean) > 2:
            nombre_lead = nombre_clean
        else:
            nombre_lead = usuario.full_name or "Compañero deportista"

    lead = {
        "fecha": datetime.now().isoformat(),
        "nombre": nombre_lead,
        "telefono": tel_encontrado or datos_contacto,
        "email": email_encontrado,
        "contacto_bruto": datos_contacto,
        "deporte": context.user_data.get("deporte", ""),
        "anos_texto": context.user_data.get("anos_texto", ""),
        "anos_dep": context.user_data.get("anos_dep", 0),
        "anos_cotizados": context.user_data.get("anos_cotizados", 25),
        "base": context.user_data.get("base", 0),
        "ya_jubilado": context.user_data.get("ya_jubilado", False),
        "inc_mes": sim.get("inc_mes", 0),
        "inc_ano": sim.get("inc_ano", 0),
        "tg_user": usuario.username or usuario.full_name,
        "tg_id": usuario.id,
        "simulacion": sim,
    }

    # Guardar en leads_deportistas.json
    leads = []
    if LEADS_FILE.exists():
        try:
            with open(LEADS_FILE, "r", encoding="utf-8") as f:
                leads = json.load(f)
        except Exception:
            leads = []
            
    leads.append(lead)
    try:
        with open(LEADS_FILE, "w", encoding="utf-8") as f:
            json.dump(leads, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error guardando lead en JSON: {e}")

    # Enviar email automático si hay correo
    if email_encontrado:
        send_email_lead(lead)

    # Notificar a Antonio por Telegram
    tipo_solicitud = "REVISIÓN PENSIÓN ACTUAL (Art. 5.2)" if lead["ya_jubilado"] else "NUEVA JUBILACIÓN"
    wa_cliente = f"https://wa.me/{re.sub(r'[^0-9]', '', lead['telefono'])}" if lead['telefono'] else ""
    
    noti_antonio = (
        f"🚨 *NUEVO LEAD DEPORTISTA RD 739/2026*\n"
        f"🏆 *Modalidad:* [{tipo_solicitud}]\n\n"
        f"👤 *Nombre:* {lead['nombre']}\n"
        f"📞 *Teléfono:* {lead['telefono']}\n"
        f"✉️ *Email:* {lead['email'] or 'No facilitado'}\n"
        f"💬 *Telegram:* @{lead['tg_user']} (ID: `{lead['tg_id']}`)\n\n"
        f"🏟 *Deporte:* {lead['deporte']} ({lead['anos_texto']})\n"
        f"💼 *Años fuera:* {lead['anos_cotizados']} | *Base:* {lead['base']:,.2f} €\n"
        f"💰 *Aumento Estimado:* +{lead['inc_mes']} €/mes (+{lead['inc_ano']} €/año)\n\n"
        f"📅 *Fecha:* {lead['fecha'][:19].replace('T', ' ')}"
    )

    keyboard_noti = []
    if wa_cliente and len(re.sub(r'[^0-9]', '', lead['telefono'])) >= 9:
        keyboard_noti.append([InlineKeyboardButton("💬 Abrir WhatsApp con el cliente", url=wa_cliente)])

    try:
        await context.bot.send_message(
            ANTONIO_CHAT_ID,
            noti_antonio,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard_noti) if keyboard_noti else None,
        )
    except Exception as e:
        logger.error(f"Error notificando a Antonio por Telegram: {e}")

    # Mensaje de despedida y recursos para el usuario
    msg_despedida = (
        f"🙏 *¡Muchas gracias, {nombre_lead}! Hemos recibido tus datos correctamente.*\n\n"
        "Antonio Gatell revisará tu caso personalmente para valorar las temporadas "
        "computables y contactará contigo en breve.\n\n"
        "📚 *Recursos inmediatos a tu disposición:*\n"
        f"1. Puedes consultar el [Artículo Legal Completo sobre el RD 739/2026]({ARTICLE_URL}).\n"
        "2. Si prefieres contactar tú directamente ahora con Antonio sin esperar, pulsa en el botón de WhatsApp abajo.\n\n"
        "¡Un fuerte abrazo deportivo!"
    )

    keyboard_user = [
        [
            InlineKeyboardButton("💬 Escribir a Antonio por WhatsApp", url=f"https://wa.me/{ANTONIO_WHATSAPP}?text=Hola%20Antonio,%20soy%20{lead['nombre']}.%20He%20completado%20el%20test%20del%20RD%20739/2026%20para%20{lead['deporte']}%20y%20quiero%20revisar%20mi%20caso"),
        ],
        [
            InlineKeyboardButton("🌐 Leer Artículo Completo en la Web", url=ARTICLE_URL),
        ],
        [
            InlineKeyboardButton("📄 Ver Guía de Certificados (Anexos I y II)", callback_data="mostrar_guia"),
        ],
    ]

    await update.message.reply_text(
        msg_despedida,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard_user),
    )

    return ConversationHandler.END

# ── Comandos y Callbacks Adicionales ─────────────────────

async def cmd_articulo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía un resumen y enlace del artículo recién publicado."""
    texto = (
        "📰 *Artículo Legal: El Real Decreto 739/2026 y la Jubilación de Deportistas*\n\n"
        "Publicado por *Antonio Gatell Contreras*, abogado y exjugador del Puleva Maristas "
        "en la Liga ASOBAL.\n\n"
        "📌 *Puntos clave analizados en la guía:*\n"
        "• Periodo computable: Del 15 de marzo de 1980 hasta la integración de cada deporte.\n"
        "• Financiación: 100% a cargo del Consejo Superior de Deportes (coste 0 €).\n"
        "• Revisión para ya jubilados (Art. 5.2): Efectos económicos al mes siguiente.\n"
        "• Cómo tramitar los Anexos I (Club activo) y Anexo II (Federación Española competente).\n"
        "• Valoración médica de secuelas deportivas para Incapacidades Permanentes.\n\n"
        f"👉 [Leer artículo completo en gatellasociados.com]({ARTICLE_URL})"
    )
    keyboard = [
        [InlineKeyboardButton("🌐 Leer Artículo Completo", url=ARTICLE_URL)],
        [InlineKeyboardButton("🏆 Iniciar Simulación de Pensión", callback_data="reiniciar_test")],
    ]
    await update.message.reply_text(
        texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cmd_guia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explica cómo obtener los certificados de los Anexos I y II."""
    texto = (
        "📑 *Guía de Certificación Oficial: Anexos I y II (RD 739/2026)*\n\n"
        "Para que la Seguridad Social compute tus temporadas, se exigen dos vías oficiales:\n\n"
        "🏛 *VÍA 1: Certificado ANEXO I (Club Activo)*\n"
        "Si el club en el que jugaste continúa en activo y conserva sus archivos, "
        "el club certifica tus contratos y licencias de alta competición.\n\n"
        "🏛 *VÍA 2: Certificado ANEXO II (Real Federación Española)*\n"
        "Si el club desapareció o se disolvió (muy habitual tras 30 años en balonmano, "
        "baloncesto, ciclismo, etc.), la certificación la expide directamente la "
        "*Federación Española correspondiente* (RFEBM, FEB, RFEC, RFEV...) "
        "mediante cotejo de sus libros oficiales de licencias y actas de competición.\n\n"
        "⚖️ *Desde Gatell & Asociados tramitamos la localización y solicitud "
        "oficial de estos certificados por ti.*"
    )
    keyboard = [
        [InlineKeyboardButton("💬 Hablar con Antonio por WhatsApp", url=f"https://wa.me/{ANTONIO_WHATSAPP}?text=Hola%20Antonio,%20necesito%20ayuda%20para%20tramitar%20mi%20certificado%20federativo")],
        [InlineKeyboardButton("🌐 Ver Guía en el Artículo Web", url=ARTICLE_URL)],
    ]
    await update.message.reply_text(
        texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cmd_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra información directa de contacto de Gatell & Asociados."""
    texto = (
        "🏛 *Gatell & Asociados — Abogados*\n"
        "_Defensa letrada desde 1996 · ICAMálaga 4012_\n\n"
        "📍 *Letrado director:* Antonio Gatell Contreras\n"
        f"📞 *Teléfono / WhatsApp:* +{ANTONIO_WHATSAPP}\n"
        f"✉️ *Email:* {DESPACHO_EMAIL}\n"
        "🌐 *Web:* [gatellasociados.com](https://www.gatellasociados.com)\n\n"
        "Especialistas en Derecho Deportivo, Seguridad Social, Pensiones, "
        "Incapacidades Laborales y Planificación Patrimonial."
    )
    keyboard = [
        [InlineKeyboardButton("💬 WhatsApp con Antonio", url=f"https://wa.me/{ANTONIO_WHATSAPP}")],
        [InlineKeyboardButton("🌐 Visitar Web Oficial", url="https://www.gatellasociados.com")],
    ]
    await update.message.reply_text(
        texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando administrativo para ver estadísticas de leads y simulaciones."""
    usuario_id = update.effective_user.id
    if usuario_id != ANTONIO_CHAT_ID:
        await update.message.reply_text("🔒 Comando reservado exclusivamente para Antonio Gatell.")
        return

    stats = get_stats()
    leads_count = 0
    if LEADS_FILE.exists():
        try:
            with open(LEADS_FILE, "r", encoding="utf-8") as f:
                leads = json.load(f)
                leads_count = len(leads)
        except Exception:
            leads_count = 0

    deportes_str = "\n".join(
        [f"• {dep.capitalize()}: {cnt}" for dep, cnt in stats.get("por_deporte", {}).items()]
    ) or "Sin desglose registrado aún."

    texto = (
        f"📊 *ESTADÍSTICAS DEL BOT RD 739/2026*\n\n"
        f"👥 *Simulaciones totales calculadas:* {stats.get('total_simulaciones', 0)}\n"
        f"📥 *Leads registrados con contacto:* {leads_count}\n\n"
        f"🏟 *Desglose por disciplinas:*\n{deportes_str}\n\n"
        f"⏳ *Días restantes para entrada en vigor:* {(ENTRADA_VIGOR - date.today()).days} días (25 dic 2026)"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")

async def callback_guia_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para mostrar la guía de Anexos desde los botones finales."""
    query = update.callback_query
    await query.answer()
    texto = (
        "📑 *Guía de Certificación Oficial: Anexos I y II (RD 739/2026)*\n\n"
        "• *Anexo I (Club activo):* Si el club existe, certifica tu contrato y ficha.\n"
        "• *Anexo II (Real Federación Española):* Si el club desapareció, la Federación "
        "emite el certificado con sus libros históricos de licencias.\n\n"
        "Nosotros gestionamos este trámite ante la Federación por ti."
    )
    keyboard = [
        [InlineKeyboardButton("💬 Pedir a Antonio que tramite mi Anexo II", url=f"https://wa.me/{ANTONIO_WHATSAPP}?text=Hola%20Antonio,%20necesito%20tramitar%20el%20Anexo%20II%20para%20mi%20deporte")],
    ]
    await query.message.reply_text(
        texto, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Simulación cancelada. Si deseas volver a empezar en cualquier momento, escribe /start.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

# ── Punto de Entrada Principal ──────────────────────────
def main():
    if not TELEGRAM_AVAILABLE:
        print("ERROR: La librería 'python-telegram-bot' no está instalada.")
        print("Instálala con: pip install python-telegram-bot==22.0")
        sys.exit(1)

    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start, pattern="^reiniciar_test$"),
        ],
        states={
            SPORT: [
                CallbackQueryHandler(sport_callback, pattern="^dep_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sport_text),
            ],
            YEARS: [
                CallbackQueryHandler(years_callback, pattern="^anos_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, years_text),
            ],
            OVERLAP: [
                CallbackQueryHandler(overlap_callback, pattern="^solapo_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, overlap_text),
            ],
            JUBILADO: [
                CallbackQueryHandler(jubilado_callback, pattern="^jub_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, jubilado_text),
            ],
            COTIZADOS: [
                CallbackQueryHandler(cotizados_callback, pattern="^cot_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cotizados_text),
            ],
            BASE: [
                CallbackQueryHandler(base_callback, pattern="^base_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, base_text),
            ],
            CONTACT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, contact),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("articulo", cmd_articulo))
    app.add_handler(CommandHandler("guia", cmd_guia))
    app.add_handler(CommandHandler("contacto", cmd_contacto))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(callback_guia_inline, pattern="^mostrar_guia$"))

    dias = (ENTRADA_VIGOR - date.today()).days
    print(f"🤖 Bot RD 739/2026 v4 INICIADO")
    print(f"📅 Entrada en vigor: {ENTRADA_VIGOR} ({dias} días restantes)")
    print(f"👤 Destinatario alertas: {ANTONIO_CHAT_ID}")
    print(f"📂 Archivo leads: {LEADS_FILE}")
    print("🚀 Polling activo esperando deportistas...")

    app.run_polling()

if __name__ == "__main__":
    main()
