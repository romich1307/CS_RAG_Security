"""Generación de figuras científicas reproducibles en formatos SVG y PNG (T20).

Implementa la visualización gráfica de los seis ejes empíricos requeridos para el artículo:
1. Comparación de exactitud A/B/C (desacoplando pipeline y salida cruda del LLM).
2. Desglose de validez y sustento fáctico de citas documentales.
3. Tasas de abstención del pipeline y desglose de causas formales.
4. Tasa de éxito de ataques (ASR) por condición (con advertencia ante datos mock o pendientes).
5. Sensibilidad (Recall) y Tasa de Falsos Positivos (FPR) del detector heurístico.
6. Latencias de inferencia y llamada al generador por condición.

Reglas científicas estrictas:
- Etiquetas claras, unidades explícitas, numeradores y denominadores consignados.
- Desacoplamiento estricto entre salida final validada del pipeline y salida cruda del LLM.
- NUNCA representar valores faltantes, denominadores cero o evaluaciones pendientes como 0%.
- Generación dual simultánea: gráficos vectoriales SVG estándar y gráficos ráster PNG mediante Pillow.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from cs_rag_security.defenses import MODES


# Paleta científica estándar (accesible y diferenciada)
COLOR_BG = "#ffffff"
COLOR_TEXT_PRIMARY = "#1a202c"
COLOR_TEXT_MUTED = "#4a5568"
COLOR_GRID = "#e2e8f0"
COLOR_BORDER = "#cbd5e0"
COLOR_PENDING_BG = "#edf2f7"
COLOR_PENDING_BORDER = "#a0aec0"

# Colores por condición o serie
COLOR_PIPELINE = "#2b6cb0"      # Azul sobrio
COLOR_LLM_RAW = "#319795"       # Verde azulado
COLOR_VALID = "#2f855a"         # Verde oscuro (citas válidas)
COLOR_PARTIAL = "#dd6b20"       # Naranja (sustento parcial / brecha)
COLOR_INVALID = "#c53030"       # Rojo (alucinación / fuera de contexto)
COLOR_MISSING = "#718096"       # Gris (sin citas)
COLOR_RECALL = "#2b6cb0"        # Azul para recall
COLOR_FPR = "#c53030"           # Rojo para FPR
COLOR_LAT_PIPE = "#2b6cb0"      # Azul
COLOR_LAT_LLM = "#805ad5"       # Púrpura


class ScientificCanvas:
    """Lienzo para renderizado simultáneo de figuras en SVG y PNG."""

    def __init__(self, width: int = 900, height: int = 550, title: str = "", subtitle: str = ""):
        self.width = width
        self.height = height
        self.title = title
        self.subtitle = subtitle

        # Elementos SVG
        self.svg_elements: List[str] = []

        # Lienzo PIL para PNG
        self.img = Image.new("RGB", (self.width, self.height), COLOR_BG)
        self.draw = ImageDraw.Draw(self.img)

        # Cargar fuente con respaldo seguro y adaptable a cualquier SO
        try:
            self.font_title = ImageFont.truetype("/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf", 20)
            self.font_sub = ImageFont.truetype("/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf", 13)
            self.font_body = ImageFont.truetype("/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf", 12)
            self.font_bold = ImageFont.truetype("/usr/share/fonts/Adwaita/AdwaitaMono-Bold.ttf", 12)
            self.font_small = ImageFont.truetype("/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf", 10)
        except Exception:
            try:
                self.font_title = ImageFont.load_default(size=20)
                self.font_sub = ImageFont.load_default(size=13)
                self.font_body = ImageFont.load_default(size=12)
                self.font_bold = ImageFont.load_default(size=12)
                self.font_small = ImageFont.load_default(size=10)
            except Exception:
                self.font_title = ImageFont.load_default()
                self.font_sub = ImageFont.load_default()
                self.font_body = ImageFont.load_default()
                self.font_bold = ImageFont.load_default()
                self.font_small = ImageFont.load_default()

        # Dibujar encabezados iniciales
        if title:
            self.add_text(30, 25, title, font_size=18, is_bold=True, color=COLOR_TEXT_PRIMARY)
        if subtitle:
            self.add_text(30, 52, subtitle, font_size=12, color=COLOR_TEXT_MUTED)

    def add_text(
        self,
        x: float,
        y: float,
        text: str,
        font_size: int = 12,
        is_bold: bool = False,
        color: str = COLOR_TEXT_PRIMARY,
        anchor: str = "start",  # 'start', 'middle', 'end'
    ) -> None:
        """Agrega texto tanto a la definición SVG como al búfer PNG."""
        # SVG
        text_anchor = anchor
        svg_elem = (
            f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{font_size}" '
            f'font-weight="{"bold" if is_bold else "normal"}" fill="{color}" '
            f'text-anchor="{text_anchor}">{text}</text>'
        )
        self.svg_elements.append(svg_elem)

        # PIL
        # Seleccionar fuente PIL
        if font_size >= 18:
            pil_font = self.font_title
        elif font_size >= 13:
            pil_font = self.font_sub
        elif is_bold:
            pil_font = self.font_bold
        elif font_size <= 10:
            pil_font = self.font_small
        else:
            pil_font = self.font_body

        # Ajuste de coordenadas según anclaje en PIL
        pil_anchor = "la" if anchor == "start" else ("ma" if anchor == "middle" else "ra")
        # En SVG y suele ser la línea base; en PIL ajustamos levemente
        self.draw.text((x, y - (font_size * 0.7)), text, fill=color, font=pil_font, anchor=pil_anchor)

    def add_rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str,
        outline: Optional[str] = None,
        rx: float = 0,
    ) -> None:
        """Dibuja un rectángulo en SVG y PNG."""
        if w <= 0 or h <= 0:
            return
        # SVG
        stroke_attr = f' stroke="{outline}" stroke-width="1"' if outline else ""
        rx_attr = f' rx="{rx}"' if rx > 0 else ""
        self.svg_elements.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"{stroke_attr}{rx_attr}/>')

        # PIL
        self.draw.rectangle([x, y, x + w, y + h], fill=fill, outline=outline, width=1 if outline else 0)

    def add_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: str = COLOR_GRID,
        width: int = 1,
        dashed: bool = False,
    ) -> None:
        """Dibuja una línea en SVG y PNG."""
        dash_attr = ' stroke-dasharray="4,4"' if dashed else ""
        self.svg_elements.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{dash_attr}/>')
        self.draw.line([x1, y1, x2, y2], fill=color, width=width)

    def add_notice_box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        message: str,
        border_color: str = "#d69e2e",
        bg_color: str = "#fffaf0",
    ) -> None:
        """Dibuja una caja de advertencia o aclaración metodológica."""
        self.add_rect(x, y, w, h, fill=bg_color, outline=border_color, rx=4)
        self.add_text(x + 15, y + 22, title, font_size=12, is_bold=True, color="#975a16")
        self.add_text(x + 15, y + 42, message, font_size=11, color="#744210")

    def to_svg_string(self) -> str:
        """Genera el código XML del SVG completo."""
        res = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">',
            f'<rect width="{self.width}" height="{self.height}" fill="{COLOR_BG}"/>',
        ]
        res.extend(self.svg_elements)
        res.append("</svg>")
        return "\n".join(res)

    def save(self, svg_path: Union[str, Path], png_path: Union[str, Path]) -> Tuple[Path, Path]:
        """Exporta la figura en ambos formatos: SVG y PNG."""
        s_path = Path(svg_path)
        p_path = Path(png_path)
        s_path.parent.mkdir(parents=True, exist_ok=True)
        p_path.parent.mkdir(parents=True, exist_ok=True)

        s_path.write_text(self.to_svg_string(), encoding="utf-8")
        self.img.save(p_path, format="PNG")
        return s_path, p_path


def generate_fig_exactitud_abc(
    accuracy_data: Optional[Dict[str, Any]] = None,
    output_dir: Union[str, Path] = "results",
) -> Tuple[Path, Path]:
    """Figura 1: Exactitud humana de respuestas por condición (Rúbrica v0.2).

    Diferencia entre Pipeline y LLM Raw. Si no hay datos evaluables (T12 pendiente),
    NO grafica 0%, sino un recuadro de pendiente con su justificación.
    """
    canvas = ScientificCanvas(
        width=920,
        height=540,
        title="Figura 1. Exactitud Humana de Contenido por Condición Experimental",
        subtitle="Evaluación semántica según Rúbrica T10 v0.2. Comparación entre Pipeline y LLM Raw.",
    )

    # Coordenadas de los ejes
    ax_x = 100
    ax_y = 110
    ax_w = 760
    ax_h = 320

    # Dibujar cuadrícula y eje Y (0 a 100%)
    for pct in range(0, 101, 20):
        y_pos = ax_y + ax_h - (pct / 100.0) * ax_h
        canvas.add_line(ax_x, y_pos, ax_x + ax_w, y_pos, color=COLOR_GRID, dashed=(pct > 0))
        canvas.add_text(ax_x - 10, y_pos + 4, f"{pct}%", font_size=11, color=COLOR_TEXT_MUTED, anchor="end")

    # Eje base X
    canvas.add_line(ax_x, ax_y + ax_h, ax_x + ax_w, ax_y + ax_h, color=COLOR_BORDER, width=2)

    # Leyenda superior derecha
    leg_x = ax_x + ax_w - 240
    leg_y = 65
    canvas.add_rect(leg_x, leg_y, 14, 14, fill=COLOR_PIPELINE)
    canvas.add_text(leg_x + 22, leg_y + 11, "Salida Final Pipeline", font_size=11, color=COLOR_TEXT_PRIMARY)
    canvas.add_rect(leg_x + 130, leg_y, 14, 14, fill=COLOR_LLM_RAW)
    canvas.add_text(leg_x + 152, leg_y + 11, "LLM Raw (cruda)", font_size=11, color=COLOR_TEXT_PRIMARY)

    # 3 Grupos: A, B, C
    group_w = ax_w / 3.0
    conds = [("A_sin_defensa", "A (Sin Defensa)"), ("B_defensa_basica", "B (Defensa Básica)"), ("C_defensa_propuesta", "C (Defensa Propuesta)")]

    for i, (cond_key, cond_lbl) in enumerate(conds):
        gx = ax_x + i * group_w
        cx = gx + group_w / 2.0
        canvas.add_text(cx, ax_y + ax_h + 25, cond_lbl, font_size=12, is_bold=True, anchor="middle")

        # Verificar si hay datos evaluados para esta condición
        pipe_data = accuracy_data.get(cond_key, {}).get("pipeline") if accuracy_data else None
        raw_data = accuracy_data.get(cond_key, {}).get("llm_raw") if accuracy_data else None

        # Si no hay datos evaluados (caso real actual: T12 pendiente)
        if not pipe_data and not raw_data:
            box_w = group_w - 30
            box_h = 100
            bx = gx + 15
            by = ax_y + ax_h - box_h - 20
            canvas.add_rect(bx, by, box_w, box_h, fill=COLOR_PENDING_BG, outline=COLOR_PENDING_BORDER, rx=4)
            canvas.add_text(cx, by + 35, "Evaluación Humana Pendiente", font_size=11, is_bold=True, color=COLOR_TEXT_MUTED, anchor="middle")
            canvas.add_text(cx, by + 55, "Rúbrica T10 v0.2 asignada a León (T12)", font_size=10, color=COLOR_TEXT_MUTED, anchor="middle")
            canvas.add_text(cx, by + 75, "Denominador evaluable: n=0", font_size=10, is_bold=True, color="#c53030", anchor="middle")
        else:
            # Si existen datos (ej. en pruebas o ejecuciones futuras de T12)
            bar_w = 38
            if pipe_data and pipe_data.get("denominator", 0) > 0:
                val = pipe_data.get("value", 0) or 0
                bh = (val * ax_h)
                bx = cx - bar_w - 5
                by = ax_y + ax_h - bh
                canvas.add_rect(bx, by, bar_w, bh, fill=COLOR_PIPELINE)
                canvas.add_text(bx + bar_w / 2.0, by - 8, f"{val*100:.1f}%\n({pipe_data['numerator']}/{pipe_data['denominator']})", font_size=10, anchor="middle")

            if raw_data and raw_data.get("denominator", 0) > 0:
                val = raw_data.get("value", 0) or 0
                bh = (val * ax_h)
                bx = cx + 5
                by = ax_y + ax_h - bh
                canvas.add_rect(bx, by, bar_w, bh, fill=COLOR_LLM_RAW)
                canvas.add_text(bx + bar_w / 2.0, by - 8, f"{val*100:.1f}%\n({raw_data['numerator']}/{raw_data['denominator']})", font_size=10, anchor="middle")

    # Nota de pie de figura
    canvas.add_text(
        ax_x,
        ax_y + ax_h + 60,
        "Nota: Ningún valor faltante o pendiente se grafica como 0%. En Modo A (T11 real), las 10 consultas registraron abstención formal por motivo canónico 'citas_invalidas_o_ausentes'.",
        font_size=10,
        color=COLOR_TEXT_MUTED,
    )

    out = Path(output_dir)
    return canvas.save(out / "fig1_exactitud_abc.svg", out / "fig1_exactitud_abc.png")


def generate_fig_validez_citas(
    citation_data: Optional[Dict[str, Any]] = None,
    output_dir: Union[str, Path] = "results",
) -> Tuple[Path, Path]:
    """Figura 2: Desglose de validez y sustento fáctico de citas documentales."""
    canvas = ScientificCanvas(
        width=920,
        height=540,
        title="Figura 2. Validez y Sustento Factual de Citas Documentales",
        subtitle="Pertenencia estricta al contexto recuperado frente al respaldo factual de las afirmaciones (Rúbrica v0.2).",
    )

    ax_x = 90
    ax_y = 110
    ax_w = 780
    ax_h = 310

    # Eje Y (0 a 100%)
    for pct in range(0, 101, 25):
        y_pos = ax_y + ax_h - (pct / 100.0) * ax_h
        canvas.add_line(ax_x, y_pos, ax_x + ax_w, y_pos, color=COLOR_GRID, dashed=(pct > 0))
        canvas.add_text(ax_x - 10, y_pos + 4, f"{pct}%", font_size=11, color=COLOR_TEXT_MUTED, anchor="end")

    canvas.add_line(ax_x, ax_y + ax_h, ax_x + ax_w, ax_y + ax_h, color=COLOR_BORDER, width=2)

    # Leyenda de categorías
    cats = [
        ("Citas Válidas Completas (en contexto + sustento)", COLOR_VALID),
        ("Brecha: En Contexto pero Sustento Insuficiente", COLOR_PARTIAL),
        ("Citas Fuera de Contexto (Alucinadas)", COLOR_INVALID),
        ("Sin Citas", COLOR_MISSING),
    ]
    lx = ax_x
    ly = 70
    for label, col in cats:
        canvas.add_rect(lx, ly, 12, 12, fill=col)
        canvas.add_text(lx + 18, ly + 10, label, font_size=10, color=COLOR_TEXT_PRIMARY)
        lx += 190

    # Categorías evaluadas: Pipeline vs LLM Raw (sobre datos disponibles o pendientes)
    groups = [
        ("Pipeline (Salida Final)", "pipeline"),
        ("LLM Raw (Salida Cruda LLM)", "llm_raw"),
    ]
    gw = ax_w / 2.0

    for i, (g_label, g_key) in enumerate(groups):
        gx = ax_x + i * gw
        cx = gx + gw / 2.0
        canvas.add_text(cx, ax_y + ax_h + 25, g_label, font_size=12, is_bold=True, anchor="middle")

        g_data = citation_data.get(g_key) if citation_data else None

        if not g_data or g_data.get("substantive_responses", 0) == 0:
            bw = gw - 60
            bh = 110
            bx = gx + 30
            by = ax_y + ax_h - bh - 30
            canvas.add_rect(bx, by, bw, bh, fill=COLOR_PENDING_BG, outline=COLOR_PENDING_BORDER, rx=4)
            canvas.add_text(cx, by + 35, "Sustento Factual Pendiente (T12)", font_size=11, is_bold=True, color=COLOR_TEXT_MUTED, anchor="middle")
            canvas.add_text(cx, by + 55, "Pertenencia contextual y sustento semántico", font_size=10, color=COLOR_TEXT_MUTED, anchor="middle")
            canvas.add_text(cx, by + 75, "requieren anotación humana independiente de León", font_size=10, color=COLOR_TEXT_MUTED, anchor="middle")
        else:
            # Si hay datos de proporciones, graficar barras apiladas
            n_sust = g_data["substantive_responses"]
            v_val = (g_data.get("valida_completa", 0) / n_sust) * ax_h
            v_gap = (g_data.get("brecha", 0) / n_sust) * ax_h
            v_out = (g_data.get("alucinada", 0) / n_sust) * ax_h
            v_mis = (g_data.get("sin_citas", 0) / n_sust) * ax_h

            bar_w = 60
            bx = cx - bar_w / 2.0
            curr_y = ax_y + ax_h

            for h_val, col in [(v_val, COLOR_VALID), (v_gap, COLOR_PARTIAL), (v_out, COLOR_INVALID), (v_mis, COLOR_MISSING)]:
                if h_val > 0:
                    curr_y -= h_val
                    canvas.add_rect(bx, curr_y, bar_w, h_val, fill=col)

    canvas.add_text(
        ax_x,
        ax_y + ax_h + 60,
        "Nota: Distinción crucial de T18: una cita puede pertenecer al contexto pero no sustentar la proposición afirmada (falsa apariencia de respaldo).",
        font_size=10,
        color=COLOR_TEXT_MUTED,
    )

    out = Path(output_dir)
    return canvas.save(out / "fig2_validez_citas.svg", out / "fig2_validez_citas.png")


def generate_fig_tasas_abstencion(
    abstention_data: Optional[Dict[str, Any]] = None,
    output_dir: Union[str, Path] = "results",
) -> Tuple[Path, Path]:
    """Figura 3: Tasas de abstención y motivos canónicos T16."""
    canvas = ScientificCanvas(
        width=920,
        height=540,
        title="Figura 3. Tasas de Abstención del Pipeline y Motivos Canónicos T16",
        subtitle="Porcentaje de consultas donde el pipeline emitió abstención formal y distribución de motivos.",
    )

    ax_x = 90
    ax_y = 110
    ax_w = 780
    ax_h = 310

    for pct in range(0, 101, 20):
        y_pos = ax_y + ax_h - (pct / 100.0) * ax_h
        canvas.add_line(ax_x, y_pos, ax_x + ax_w, y_pos, color=COLOR_GRID, dashed=(pct > 0))
        canvas.add_text(ax_x - 10, y_pos + 4, f"{pct}%", font_size=11, color=COLOR_TEXT_MUTED, anchor="end")

    canvas.add_line(ax_x, ax_y + ax_h, ax_x + ax_w, ax_y + ax_h, color=COLOR_BORDER, width=2)

    # 3 Condiciones
    gw = ax_w / 3.0
    conds = [
        ("A_sin_defensa", "A (Sin Defensa)", 1.0, 10, 10, "10/10 citas_invalidas_o_ausentes (T11 real)"),
        ("B_defensa_basica", "B (Defensa Básica)", None, 0, 0, "Pendiente de corrida experimental T17"),
        ("C_defensa_propuesta", "C (Defensa Propuesta)", None, 0, 0, "Pendiente de corrida experimental T17"),
    ]

    for i, (ckey, clabel, rate, num, den, obs) in enumerate(conds):
        gx = ax_x + i * gw
        cx = gx + gw / 2.0
        canvas.add_text(cx, ax_y + ax_h + 25, clabel, font_size=12, is_bold=True, anchor="middle")

        # Sobrescribir con datos reales si fueron pasados
        if abstention_data and ckey in abstention_data:
            item = abstention_data[ckey]
            rate = item.get("rate")
            num = item.get("numerator", 0)
            den = item.get("denominator", 0)
            obs = item.get("observation", obs)

        if rate is not None and den > 0:
            bw = 65
            bh = rate * ax_h
            bx = cx - bw / 2.0
            by = ax_y + ax_h - bh
            canvas.add_rect(bx, by, bw, bh, fill=COLOR_PIPELINE)
            canvas.add_text(cx, by - 12, f"{rate*100:.1f}%\n({num}/{den})", font_size=11, is_bold=True, anchor="middle")
            canvas.add_text(cx, by + bh / 2.0, "Citas inválidas\n(100%)", font_size=10, color="#ffffff", anchor="middle")
        else:
            bw = gw - 40
            bh = 90
            bx = gx + 20
            by = ax_y + ax_h - bh - 20
            canvas.add_rect(bx, by, bw, bh, fill=COLOR_PENDING_BG, outline=COLOR_PENDING_BORDER, rx=4)
            canvas.add_text(cx, by + 35, "Corrida Pendiente (T17)", font_size=11, is_bold=True, color=COLOR_TEXT_MUTED, anchor="middle")
            canvas.add_text(cx, by + 55, obs, font_size=9, color=COLOR_TEXT_MUTED, anchor="middle")

    # Banner explicativo inferior
    canvas.add_notice_box(
        ax_x,
        ax_y + ax_h + 40,
        ax_w,
        45,
        "Motivo Registrado en Modo A (T11):",
        "En las 10 consultas legítimas evaluadas en T11, el pipeline registró abstención formal por el motivo canónico 'citas_invalidas_o_ausentes' (ABSTENTION_REASON_INVALID_CITATIONS). No se formulan afirmaciones causales no demostradas.",
    )

    out = Path(output_dir)
    return canvas.save(out / "fig3_tasas_abstencion.svg", out / "fig3_tasas_abstencion.png")


def generate_fig_asr_condicion(
    security_data: Optional[Dict[str, Any]] = None,
    output_dir: Union[str, Path] = "results",
) -> Tuple[Path, Path]:
    """Figura 4: Tasa de éxito de ataques (ASR).

    Alerta explícita: mock no mide ASR de LLM. Si T19 no está disponible, se expone banner.
    """
    canvas = ScientificCanvas(
        width=920,
        height=540,
        title="Figura 4. Tasa de Éxito de Ataques (Attack Success Rate - ASR)",
        subtitle="Eficacia defensiva frente a inyecciones indirectas controladas (attacks.jsonl).",
    )

    ax_x = 90
    ax_y = 110
    ax_w = 780
    ax_h = 300

    # Verificar si disponemos de métricas reales de T19
    has_real_t19 = (security_data is not None and any("real" in str(k) or "asr" in str(v) for k, v in security_data.items()))

    if not has_real_t19:
        # Dibujar área de pendiente metodológica sin inventar barras en 0
        canvas.add_rect(ax_x, ax_y, ax_w, ax_h, fill="#fffaf0", outline="#d69e2e", rx=6)
        cx = ax_x + ax_w / 2.0
        cy = ax_y + ax_h / 2.0

        canvas.add_text(cx, cy - 60, "MÉTRICAS DE SEGURIDAD CON LLM REAL PENDIENTES (T19)", font_size=16, is_bold=True, color="#975a16", anchor="middle")
        canvas.add_text(cx, cy - 25, "La tarea T19 está formalmente asignada a León para su ejecución sobre el LLM real local.", font_size=12, color="#744210", anchor="middle")

        canvas.add_rect(cx - 320, cy + 5, 640, 75, fill="#ffffff", outline="#ecc94b", rx=4)
        canvas.add_text(cx, cy + 25, "Límite metodológico fundamental (AGENTS.md / docs/METODOLOGIA.md):", font_size=11, is_bold=True, color="#744210", anchor="middle")
        canvas.add_text(cx, cy + 45, "Los resultados mock (A: 4/4, B: 4/4, C: 1/4) corresponden a extractos sintéticos de texto", font_size=11, color="#744210", anchor="middle")
        canvas.add_text(cx, cy + 63, "y NO constituyen medida de obediencia ni ASR de un modelo de lenguaje.", font_size=11, is_bold=True, color="#975a16", anchor="middle")

        canvas.add_text(cx, cy + 115, "Estado actual: N/A (Denominador real = 0). Jamás se grafica como 0% de ataque.", font_size=11, color=COLOR_TEXT_MUTED, anchor="middle")
    else:
        # Si T19 estuviese disponible, graficar barras
        for pct in range(0, 101, 20):
            y_pos = ax_y + ax_h - (pct / 100.0) * ax_h
            canvas.add_line(ax_x, y_pos, ax_x + ax_w, y_pos, color=COLOR_GRID, dashed=(pct > 0))
            canvas.add_text(ax_x - 10, y_pos + 4, f"{pct}%", font_size=11, color=COLOR_TEXT_MUTED, anchor="end")
        canvas.add_line(ax_x, ax_y + ax_h, ax_x + ax_w, ax_y + ax_h, color=COLOR_BORDER, width=2)

    out = Path(output_dir)
    return canvas.save(out / "fig4_asr_condicion.svg", out / "fig4_asr_condicion.png")


def generate_fig_detector_metricas(
    detector_data: Optional[Dict[str, Any]] = None,
    output_dir: Union[str, Path] = "results",
) -> Tuple[Path, Path]:
    """Figura 5: Rendimiento diagnóstico preliminar del detector heurístico (Recall y FPR)."""
    from cs_rag_security.evaluation.tables import extract_detector_diagnostic_from_run

    canvas = ScientificCanvas(
        width=920,
        height=540,
        title="Figura 5. Rendimiento Diagnóstico Preliminar del Detector Heurístico",
        subtitle="Resultados diagnósticos preliminares: Sensibilidad (Recall) y Falsos Positivos (FPR) sobre batería sintética (n=8).",
    )

    ax_x = 100
    ax_y = 110
    ax_w = 740
    ax_h = 300

    for pct in range(0, 101, 25):
        y_pos = ax_y + ax_h - (pct / 100.0) * ax_h
        canvas.add_line(ax_x, y_pos, ax_x + ax_w, y_pos, color=COLOR_GRID, dashed=(pct > 0))
        canvas.add_text(ax_x - 10, y_pos + 4, f"{pct}%", font_size=11, color=COLOR_TEXT_MUTED, anchor="end")

    canvas.add_line(ax_x, ax_y + ax_h, ax_x + ax_w, ax_y + ax_h, color=COLOR_BORDER, width=2)

    diag = detector_data if detector_data is not None else extract_detector_diagnostic_from_run()

    if diag and diag.get("attacks_total") and diag.get("benign_total"):
        rec_val = diag.get("recall") or 0.0
        rec_num = diag.get("tp", 0)
        rec_den = diag.get("attacks_total", 0)

        fpr_val = diag.get("fpr") or 0.0
        fpr_num = diag.get("fp", 0)
        fpr_den = diag.get("benign_total", 0)

        bar_w = 110
        # Barra Recall
        bx1 = ax_x + 160
        bh1 = rec_val * ax_h
        by1 = ax_y + ax_h - bh1
        canvas.add_rect(bx1, by1, bar_w, bh1, fill=COLOR_RECALL, rx=4)
        canvas.add_text(bx1 + bar_w / 2.0, by1 - 12, f"{rec_val*100:.1f}%\n({rec_num}/{rec_den})", font_size=13, is_bold=True, anchor="middle")
        canvas.add_text(bx1 + bar_w / 2.0, ax_y + ax_h + 25, "Sensibilidad / Recall (Preliminar)\n(Ataques detectados TP)", font_size=11, is_bold=True, anchor="middle")

        # Barra FPR
        bx2 = ax_x + 470
        bh2 = fpr_val * ax_h
        by2 = ax_y + ax_h - bh2
        canvas.add_rect(bx2, by2, bar_w, bh2, fill=COLOR_FPR, rx=4)
        canvas.add_text(bx2 + bar_w / 2.0, by2 - 12, f"{fpr_val*100:.1f}%\n({fpr_num}/{fpr_den})", font_size=13, is_bold=True, anchor="middle")
        canvas.add_text(bx2 + bar_w / 2.0, ax_y + ax_h + 25, "Falsos Positivos / FPR (Preliminar)\n(Alarmas en controles benignos FP)", font_size=11, is_bold=True, anchor="middle")

        # Recuadros explicativos de casos específicos
        canvas.add_notice_box(
            ax_x,
            ax_y + ax_h + 50,
            ax_w / 2.0 - 15,
            45,
            "Sensibilidad Preliminar:",
            "Detecta a1 (directo), a2 (unicode) y a3 (prioridad). Evasión registrada: a4 indirecto.",
            border_color="#90cdf4",
            bg_color="#ebf8ff",
        )
        canvas.add_notice_box(
            ax_x + ax_w / 2.0 + 15,
            ax_y + ax_h + 50,
            ax_w / 2.0 - 15,
            45,
            "Falsa Alarma Preliminar:",
            "b3 (cita de seguridad) dispara regla por patrones léxicos. b1, b2, b4 superan el filtro.",
            border_color="#feb2b2",
            bg_color="#fff5f5",
        )
    else:
        # Sin artefacto disponible: no dibujar barras en cero
        cx = ax_x + ax_w / 2.0
        cy = ax_y + ax_h / 2.0
        canvas.add_rect(ax_x + 40, cy - 50, ax_w - 80, 100, fill=COLOR_PENDING_BG, outline=COLOR_PENDING_BORDER, rx=4)
        canvas.add_text(cx, cy - 20, "Diagnóstico del Detector No Disponible", font_size=13, is_bold=True, color=COLOR_TEXT_MUTED, anchor="middle")
        canvas.add_text(cx, cy + 5, "No se identificaron artefactos de métricas del detector en las corridas analizadas.", font_size=11, color=COLOR_TEXT_MUTED, anchor="middle")
        canvas.add_text(cx, cy + 25, "Denominador: 0/0 (N/A). No se representa como cero.", font_size=10, color=COLOR_TEXT_MUTED, anchor="middle")

    out = Path(output_dir)
    return canvas.save(out / "fig5_detector_metricas.svg", out / "fig5_detector_metricas.png")


def generate_fig_latencias_condicion(
    latencies_data: Optional[Dict[str, Any]] = None,
    output_dir: Union[str, Path] = "results",
) -> Tuple[Path, Path]:
    """Figura 6: Latencias de inferencia y llamada al LLM por condición calculadas dinámicamente."""
    canvas = ScientificCanvas(
        width=920,
        height=540,
        title="Figura 6. Latencias de Inferencia y Generación por Condición Experimental",
        subtitle="Tiempo total de ejecución del pipeline frente al tiempo de llamada al modelo local.",
    )

    ax_x = 90
    ax_y = 110
    ax_w = 780
    ax_h = 300

    # Determinar estructura por condición
    por_cond = {}
    if latencies_data and isinstance(latencies_data, dict):
        if "por_condicion" in latencies_data:
            por_cond = latencies_data["por_condicion"]
        else:
            por_cond = latencies_data

    # Determinar escala máxima dinámica a partir de las observaciones reales
    found_lats: List[float] = []
    for ckey in MODES:
        c_info = por_cond.get(ckey, {}) if isinstance(por_cond, dict) else {}
        if isinstance(c_info, dict):
            p_m = c_info.get("latencia_pipeline", {})
            g_m = c_info.get("latencia_generacion", {})
            if isinstance(p_m, dict) and p_m.get("media") is not None:
                found_lats.append(float(p_m["media"]))
            elif c_info.get("pipeline_media") is not None:
                found_lats.append(float(c_info["pipeline_media"]))
            if isinstance(g_m, dict) and g_m.get("media") is not None:
                found_lats.append(float(g_m["media"]))
            elif c_info.get("llm_media") is not None:
                found_lats.append(float(c_info["llm_media"]))

    max_val = max(found_lats) if found_lats else 30.0
    max_sec = max(35.0, math.ceil(max_val / 5.0) * 5.0 + 5.0)
    step = 5 if max_sec <= 40 else 10

    for sec in range(0, int(max_sec) + 1, step):
        y_pos = ax_y + ax_h - (sec / max_sec) * ax_h
        canvas.add_line(ax_x, y_pos, ax_x + ax_w, y_pos, color=COLOR_GRID, dashed=(sec > 0))
        canvas.add_text(ax_x - 10, y_pos + 4, f"{sec} s", font_size=11, color=COLOR_TEXT_MUTED, anchor="end")

    canvas.add_line(ax_x, ax_y + ax_h, ax_x + ax_w, ax_y + ax_h, color=COLOR_BORDER, width=2)

    # Leyenda
    leg_x = ax_x + ax_w - 260
    leg_y = 65
    canvas.add_rect(leg_x, leg_y, 14, 14, fill=COLOR_LAT_PIPE)
    canvas.add_text(leg_x + 22, leg_y + 11, "Pipeline Total (s)", font_size=11, color=COLOR_TEXT_PRIMARY)
    canvas.add_rect(leg_x + 130, leg_y, 14, 14, fill=COLOR_LAT_LLM)
    canvas.add_text(leg_x + 152, leg_y + 11, "Generador LLM (s)", font_size=11, color=COLOR_TEXT_PRIMARY)

    # 3 Condiciones
    gw = ax_w / 3.0
    conds = [
        ("A_sin_defensa", "A (Sin Defensa)"),
        ("B_defensa_basica", "B (Defensa Básica)"),
        ("C_defensa_propuesta", "C (Defensa Propuesta)"),
    ]

    for i, (ckey, clabel) in enumerate(conds):
        gx = ax_x + i * gw
        cx = gx + gw / 2.0
        canvas.add_text(cx, ax_y + ax_h + 25, clabel, font_size=12, is_bold=True, anchor="middle")

        c_info = por_cond.get(ckey, {}) if isinstance(por_cond, dict) else {}
        compatible = c_info.get("configuracion_compatible", True) if isinstance(c_info, dict) else True

        if not compatible:
            bw = gw - 35
            bh = 90
            bx = gx + 17
            by = ax_y + ax_h - bh - 20
            canvas.add_rect(bx, by, bw, bh, fill=COLOR_PENDING_BG, outline=COLOR_PENDING_BORDER, rx=4)
            canvas.add_text(cx, by + 35, "Configuración Incompatible", font_size=11, is_bold=True, color=COLOR_TEXT_MUTED, anchor="middle")
            canvas.add_text(cx, by + 55, "No se promedian mediciones heterogéneas", font_size=9, color=COLOR_TEXT_MUTED, anchor="middle")
            continue

        p_m = c_info.get("latencia_pipeline", {}) if isinstance(c_info, dict) else {}
        g_m = c_info.get("latencia_generacion", {}) if isinstance(c_info, dict) else {}

        lat_pipe = p_m.get("media") if isinstance(p_m, dict) else c_info.get("pipeline_media")
        lat_llm = g_m.get("media") if isinstance(g_m, dict) else c_info.get("llm_media")
        n_cases = p_m.get("observaciones_validas", 0) if isinstance(p_m, dict) else c_info.get("n", 0)

        if lat_pipe is not None and lat_llm is not None and n_cases > 0:
            bw = 42
            bh_p = (lat_pipe / max_sec) * ax_h
            bx_p = cx - bw - 4
            by_p = ax_y + ax_h - bh_p
            canvas.add_rect(bx_p, by_p, bw, bh_p, fill=COLOR_LAT_PIPE)
            canvas.add_text(bx_p + bw / 2.0, by_p - 8, f"{lat_pipe:.2f} s", font_size=10, is_bold=True, anchor="middle")

            bh_l = (lat_llm / max_sec) * ax_h
            bx_l = cx + 4
            by_l = ax_y + ax_h - bh_l
            canvas.add_rect(bx_l, by_l, bw, bh_l, fill=COLOR_LAT_LLM)
            canvas.add_text(bx_l + bw / 2.0, by_l - 8, f"{lat_llm:.2f} s", font_size=10, is_bold=True, anchor="middle")

            canvas.add_text(cx, ax_y + ax_h + 45, f"n = {n_cases}", font_size=10, color=COLOR_TEXT_MUTED, anchor="middle")
        else:
            bw = gw - 35
            bh = 90
            bx = gx + 17
            by = ax_y + ax_h - bh - 20
            canvas.add_rect(bx, by, bw, bh, fill=COLOR_PENDING_BG, outline=COLOR_PENDING_BORDER, rx=4)
            canvas.add_text(cx, by + 35, "Medición Pendiente (N/A)", font_size=11, is_bold=True, color=COLOR_TEXT_MUTED, anchor="middle")
            canvas.add_text(cx, by + 55, "Sin trazas disponibles (n = 0)", font_size=9, color=COLOR_TEXT_MUTED, anchor="middle")

    canvas.add_text(
        ax_x,
        ax_y + ax_h + 65,
        "Nota: Inferencia ejecutada en CPU local mediante Ollama. Métricas calculadas dinámicamente desde trazas de telemetría. En ausencia de trazas se reporta N/A sin graficar ceros espurios.",
        font_size=10,
        color=COLOR_TEXT_MUTED,
    )

    out = Path(output_dir)
    return canvas.save(out / "fig6_latencias_condicion.svg", out / "fig6_latencias_condicion.png")


def generate_all_paper_figures(
    extracted_data: Optional[Dict[str, Any]] = None,
    output_dir: Union[str, Path] = "results",
) -> Dict[str, Tuple[Path, Path]]:
    """Genera las seis figuras científicas requeridas en formatos SVG y PNG."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = extracted_data or {}

    saved = {
        "fig1_exactitud_abc": generate_fig_exactitud_abc(data.get("accuracy"), out),
        "fig2_validez_citas": generate_fig_validez_citas(data.get("citations"), out),
        "fig3_tasas_abstencion": generate_fig_tasas_abstencion(data.get("abstentions"), out),
        "fig4_asr_condicion": generate_fig_asr_condicion(data.get("security"), out),
        "fig5_detector_metricas": generate_fig_detector_metricas(data.get("detector"), out),
        "fig6_latencias_condicion": generate_fig_latencias_condicion(data.get("latencies"), out),
    }
    return saved
