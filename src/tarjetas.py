# -*- coding: utf-8 -*-
"""
Lobby - Generador de tarjetas compartibles para redes sociales
Produce imágenes PNG 1080x1080 con branding Lobby listas para Twitter/Instagram/LinkedIn.

Uso:
    from src import tarjetas
    png_bytes = tarjetas.tarjeta_legislador({
        'nombre': 'Pichetto, Miguel Ángel',
        'bloque': 'Hacemos Coalición Federal',
        'camara': 'Diputados',
        'provincia': 'Buenos Aires',
        'proyectos': 124, 'asistencia_pct': 87.5,
        'patrimonio_total': 450_000_000,
    })
    # luego: st.download_button("Descargar", png_bytes, file_name="pichetto.png", mime="image/png")
"""
from __future__ import annotations

import io
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# ============================================
# PALETA Y CONSTANTES
# ============================================

WIDTH = 1080
HEIGHT = 1080

COLOR_NAVY = (15, 34, 64)          # #0F2240
COLOR_GOLD = (232, 197, 71)        # #E8C547
COLOR_WHITE = (255, 255, 255)
COLOR_BG = (250, 250, 245)         # off-white suave
COLOR_TEXT = (17, 24, 39)          # slate-900
COLOR_MUTED = (107, 114, 128)      # slate-500
COLOR_BORDER = (229, 231, 235)     # slate-200

COLOR_AFIRM = (5, 150, 105)        # emerald-600
COLOR_NEG = (220, 38, 38)          # red-600
COLOR_AUS = (156, 163, 175)        # gray-400
COLOR_ABS = (217, 119, 6)          # amber-600

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _first_existing(*candidates: str) -> Optional[str]:
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _font(size: int, *, bold: bool = False, serif: bool = False) -> ImageFont.ImageFont:
    if serif:
        path = _first_existing(
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        )
    else:
        path = _first_existing(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        )
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ============================================
# HELPERS DE DIBUJO
# ============================================

def _nuevo_canvas() -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG)
    return img


def _header(draw: ImageDraw.ImageDraw, img: Image.Image, titulo_seccion: str = "Inteligencia Pública"):
    # Franja navy arriba (140px)
    draw.rectangle([0, 0, WIDTH, 140], fill=COLOR_NAVY)
    # Logo "L" dorado
    logo_size = 72
    logo_x = 60
    logo_y = 34
    draw.rounded_rectangle(
        [logo_x, logo_y, logo_x + logo_size, logo_y + logo_size],
        radius=12, fill=COLOR_GOLD,
    )
    font_logo = _font(52, bold=True, serif=True)
    _draw_centered_text(draw, "L", (logo_x + logo_size // 2, logo_y + logo_size // 2), font_logo, COLOR_NAVY)

    # Wordmark
    font_brand = _font(44, bold=False, serif=True)
    draw.text((logo_x + logo_size + 20, logo_y + 4), "Lobby", fill=COLOR_WHITE, font=font_brand)
    # Tagline
    font_tag = _font(20, bold=False)
    draw.text((logo_x + logo_size + 22, logo_y + 48), titulo_seccion, fill=(200, 210, 224), font=font_tag)


def _footer(draw: ImageDraw.ImageDraw):
    y0 = HEIGHT - 80
    draw.rectangle([0, y0, WIDTH, HEIGHT], fill=COLOR_NAVY)
    font = _font(18)
    draw.text((60, y0 + 20), "Datos oficiales: HCDN · Senado · CIJ · Infoleg", fill=(200, 210, 224), font=font)
    font_dom = _font(18, bold=True)
    dom_txt = "lobby.ar"
    bbox = draw.textbbox((0, 0), dom_txt, font=font_dom)
    w = bbox[2] - bbox[0]
    draw.text((WIDTH - 60 - w, y0 + 20), dom_txt, fill=COLOR_GOLD, font=font_dom)
    font_date = _font(14)
    draw.text((60, y0 + 48), "Compartí responsablemente · mención ≠ culpabilidad", fill=(150, 160, 175), font=font_date)


def _draw_centered_text(draw, text, center_xy, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = center_xy[0] - w // 2
    y = center_xy[1] - h // 2 - bbox[1]  # compensar offset
    draw.text((x, y), text, fill=fill, font=font)


def _wrap_text(text: str, max_chars: int, max_lines: int = 3) -> list[str]:
    """Wrap simple por palabras, sin silaba-breaker."""
    if not text:
        return [""]
    words = str(text).split()
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = f"{cur} {w}".strip()
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) >= max_lines - 1:
                break
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    return lines


def _fmt_money(value) -> str:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return "$ —"
    if n >= 1_000_000_000:
        return f"$ {n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"$ {n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"$ {n/1_000:.0f}K"
    return f"$ {n:,.0f}".replace(",", ".")


def _to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ============================================
# TARJETAS
# ============================================

def tarjeta_legislador(data: dict) -> bytes:
    """
    Campos esperados (opcionales, se rellena con '—' si falta):
        nombre, bloque, camara, provincia,
        proyectos (int), asistencia_pct (float), patrimonio_total (num),
        menciones_cij (int, opcional)
    """
    img = _nuevo_canvas()
    draw = ImageDraw.Draw(img)
    _header(draw, img, "Perfil de legislador")

    nombre = data.get("nombre") or "—"
    bloque = data.get("bloque") or "Sin bloque"
    camara = data.get("camara") or "—"
    provincia = data.get("provincia") or "—"
    menciones = int(data.get("menciones_cij") or 0)

    # Nombre (serif grande, wrap a 2 líneas)
    y = 220
    lines_nombre = _wrap_text(nombre, max_chars=22, max_lines=2)
    font_nombre = _font(68, bold=True, serif=True)
    for line in lines_nombre:
        draw.text((60, y), line, fill=COLOR_TEXT, font=font_nombre)
        y += 78

    # Meta: bloque · cámara · provincia
    y += 10
    font_meta = _font(26)
    meta_txt = f"{bloque}  ·  {camara}  ·  {provincia}"
    # Truncar si es muy largo
    if len(meta_txt) > 60:
        meta_txt = meta_txt[:57] + "…"
    draw.text((60, y), meta_txt, fill=COLOR_MUTED, font=font_meta)
    y += 60

    # Badge CIJ si corresponde
    if menciones > 0:
        badge_txt = f"⚠ {menciones} {'menciones' if menciones != 1 else 'mención'} en el CIJ"
        font_badge = _font(22, bold=True)
        bbox = draw.textbbox((60, y), badge_txt, font=font_badge)
        pad = 12
        draw.rounded_rectangle(
            [bbox[0] - pad, bbox[1] - pad // 2, bbox[2] + pad, bbox[3] + pad // 2],
            radius=8, fill=(254, 242, 242), outline=COLOR_NEG, width=2,
        )
        draw.text((60, y), badge_txt, fill=COLOR_NEG, font=font_badge)
        y += 70
    else:
        y += 20

    # Caja con stats (3 columnas)
    box_top = y + 20
    box_h = 340
    col_w = (WIDTH - 120) // 3
    for i, (label, value, color) in enumerate([
        ("Proyectos firmados", _int_str(data.get("proyectos")), COLOR_NAVY),
        ("Asistencia", _pct_str(data.get("asistencia_pct")), COLOR_AFIRM),
        ("Patrimonio decl.", _fmt_money(data.get("patrimonio_total")), COLOR_GOLD),
    ]):
        cx = 60 + col_w * i + col_w // 2
        # Valor grande
        font_val = _font(64, bold=True, serif=True)
        _draw_centered_text(draw, value, (cx, box_top + 110), font_val, color if color != COLOR_GOLD else COLOR_NAVY)
        # Label
        font_lbl = _font(22)
        _draw_centered_text(draw, label, (cx, box_top + 210), font_lbl, COLOR_MUTED)

    # Línea separadora
    draw.line([(60, box_top + box_h - 10), (WIDTH - 60, box_top + box_h - 10)], fill=COLOR_BORDER, width=2)

    _footer(draw)
    return _to_bytes(img)


def tarjeta_votacion(data: dict) -> bytes:
    """
    Campos esperados:
        fecha, hora, asunto, resultado,
        afirmativos, negativos, abstenciones, ausentes (ints),
        camara (default 'Diputados'),
        autor (str opcional), bloque_autor (str opcional), expediente (str opcional)
    """
    img = _nuevo_canvas()
    draw = ImageDraw.Draw(img)
    _header(draw, img, "Votación nominal")

    fecha = data.get("fecha") or "—"
    hora = data.get("hora") or ""
    asunto = data.get("asunto") or "(sin asunto)"
    resultado = data.get("resultado") or "—"
    camara = data.get("camara") or "Diputados"
    autor = data.get("autor")
    bloque_autor = data.get("bloque_autor")
    expediente = data.get("expediente")

    afirm = int(data.get("afirmativos") or 0)
    neg = int(data.get("negativos") or 0)
    abst = int(data.get("abstenciones") or 0)
    aus = int(data.get("ausentes") or 0)
    total_emitidos = max(afirm + neg + abst, 1)

    # Fecha + cámara
    font_meta = _font(24, bold=True)
    meta = f"{fecha}"
    if hora:
        meta += f"  ·  {hora}"
    meta += f"  ·  Cámara de {camara}"
    draw.text((60, 195), meta, fill=COLOR_MUTED, font=font_meta)

    # Asunto (serif wrap)
    font_asunto = _font(46, bold=True, serif=True)
    lines = _wrap_text(asunto, max_chars=36, max_lines=3)
    y = 250
    for line in lines:
        draw.text((60, y), line, fill=COLOR_TEXT, font=font_asunto)
        y += 58

    # Expediente + autor
    y += 20
    if expediente:
        font_exp = _font(22, bold=True)
        draw.text((60, y), f"Exp. {expediente}", fill=COLOR_NAVY, font=font_exp)
        y += 34
    if autor:
        autor_line = f"Autor: {autor}"
        if bloque_autor:
            autor_line += f"  ·  {bloque_autor}"
        if len(autor_line) > 70:
            autor_line = autor_line[:67] + "…"
        font_autor = _font(22)
        draw.text((60, y), autor_line, fill=COLOR_MUTED, font=font_autor)
        y += 36

    # Caja resultado grande
    result_y = max(y + 30, 660)
    result_box_h = 220
    # Color según resultado
    if "afirmat" in resultado.lower() or "aprob" in resultado.lower():
        res_color = COLOR_AFIRM
    elif "rechaz" in resultado.lower() or "negat" in resultado.lower():
        res_color = COLOR_NEG
    else:
        res_color = COLOR_NAVY
    draw.rounded_rectangle(
        [60, result_y, WIDTH - 60, result_y + result_box_h],
        radius=16, fill=COLOR_WHITE, outline=res_color, width=3,
    )
    font_res_label = _font(22, bold=True)
    draw.text((80, result_y + 16), "RESULTADO", fill=COLOR_MUTED, font=font_res_label)
    font_res = _font(40, bold=True, serif=True)
    resultado_txt = resultado.upper()[:50]
    draw.text((80, result_y + 44), resultado_txt, fill=res_color, font=font_res)

    # Barras de votos
    bar_y = result_y + 120
    bar_x = 80
    usable = WIDTH - 160
    total_nz = afirm + neg + abst
    if total_nz == 0:
        total_nz = 1
    w_a = int(usable * afirm / total_nz)
    w_n = int(usable * neg / total_nz)
    w_ab = usable - w_a - w_n
    h_bar = 26
    draw.rounded_rectangle([bar_x, bar_y, bar_x + w_a, bar_y + h_bar], radius=6, fill=COLOR_AFIRM)
    draw.rounded_rectangle([bar_x + w_a, bar_y, bar_x + w_a + w_n, bar_y + h_bar], radius=6, fill=COLOR_NEG)
    draw.rounded_rectangle([bar_x + w_a + w_n, bar_y, bar_x + w_a + w_n + w_ab, bar_y + h_bar], radius=6, fill=COLOR_ABS)

    font_votos = _font(24, bold=True)
    draw.text((bar_x, bar_y + h_bar + 10),
              f"✓ {afirm}   ✗ {neg}   ⊘ {abst}   · {aus} ausentes",
              fill=COLOR_TEXT, font=font_votos)

    _footer(draw)
    return _to_bytes(img)


def tarjeta_patrimonio(data: dict) -> bytes:
    """
    Campos esperados:
        nombre, bloque, camara,
        anio (int), patrimonio_total (num), variacion_pct (num opcional),
        bienes (num), deudas (num), anio_anterior (int opcional)
    """
    img = _nuevo_canvas()
    draw = ImageDraw.Draw(img)
    _header(draw, img, "Declaración patrimonial")

    nombre = data.get("nombre") or "—"
    bloque = data.get("bloque") or "—"
    camara = data.get("camara") or "—"
    anio = data.get("anio") or "—"
    var = data.get("variacion_pct")
    anio_ant = data.get("anio_anterior")

    # Nombre
    font_nombre = _font(56, bold=True, serif=True)
    lines_nombre = _wrap_text(nombre, max_chars=26, max_lines=2)
    y = 210
    for line in lines_nombre:
        draw.text((60, y), line, fill=COLOR_TEXT, font=font_nombre)
        y += 68

    # Meta
    font_meta = _font(24)
    meta = f"{bloque}  ·  {camara}"
    if len(meta) > 60:
        meta = meta[:57] + "…"
    draw.text((60, y + 8), meta, fill=COLOR_MUTED, font=font_meta)
    y += 60

    # Caja principal: patrimonio total + año
    y += 30
    box_y = y
    draw.rounded_rectangle(
        [60, box_y, WIDTH - 60, box_y + 230],
        radius=16, fill=COLOR_NAVY,
    )
    font_label = _font(22, bold=True)
    draw.text((90, box_y + 24), f"PATRIMONIO DECLARADO · DDJJ {anio}", fill=COLOR_GOLD, font=font_label)
    font_monto = _font(104, bold=True, serif=True)
    monto_txt = _fmt_money(data.get("patrimonio_total"))
    draw.text((90, box_y + 62), monto_txt, fill=COLOR_WHITE, font=font_monto)

    if var is not None:
        try:
            var_f = float(var)
            var_sign = "▲" if var_f >= 0 else "▼"
            var_color = COLOR_NEG if abs(var_f) >= 100 else COLOR_GOLD
            font_var = _font(28, bold=True)
            var_txt = f"{var_sign} {var_f:+.1f}% vs {anio_ant or '–'}"
            draw.text((90, box_y + 186), var_txt, fill=var_color, font=font_var)
        except (TypeError, ValueError):
            pass

    y = box_y + 260

    # Componentes: bienes vs deudas
    comp_y = y
    col_w = (WIDTH - 120 - 30) // 2
    for i, (label, value, color) in enumerate([
        ("Bienes", _fmt_money(data.get("bienes")), COLOR_AFIRM),
        ("Deudas", _fmt_money(data.get("deudas")), COLOR_NEG),
    ]):
        x0 = 60 + i * (col_w + 30)
        draw.rounded_rectangle(
            [x0, comp_y, x0 + col_w, comp_y + 140],
            radius=12, fill=COLOR_WHITE, outline=COLOR_BORDER, width=2,
        )
        font_lbl = _font(22, bold=True)
        draw.text((x0 + 20, comp_y + 16), label.upper(), fill=COLOR_MUTED, font=font_lbl)
        font_val = _font(46, bold=True, serif=True)
        draw.text((x0 + 20, comp_y + 58), value, fill=color, font=font_val)

    _footer(draw)
    return _to_bytes(img)


# ============================================
# HELPERS DE FORMATO
# ============================================

def _int_str(v) -> str:
    try:
        return f"{int(v):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def _pct_str(v) -> str:
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return "—"
