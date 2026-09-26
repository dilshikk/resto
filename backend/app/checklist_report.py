"""
PDF report for a completed checklist, sent to the managers' Telegram group.

Flow: complete_checklist (web) / complete_my_checklist (bot) commit the
completion, then call schedule_checklist_report(). The report is built and
sent in a background task with its own DB session, so a slow or failing
Telegram call never affects the API response.

No-op when MANAGERS_CHAT_ID or BOT_TOKEN is not configured.
"""

import asyncio
import logging
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from xml.sax.saxutils import escape

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.branch import Branch
from app.models.checklist import Checklist
from app.telegram import send_document

logger = logging.getLogger(__name__)

# Keep strong references so background tasks are not garbage-collected.
_background_tasks: set[asyncio.Task] = set()

_FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"

_SHIFTS = {"morning": "Утро", "afternoon": "День", "evening": "Вечер", "night": "Ночь"}
_DEADLINE = {
    "ON_TIME": "Вовремя",
    "OVERDUE": "С опозданием",
    "NOT_COMPLETED": "Не выполнен",
    None: "Без дедлайна",
}

_PHOTO_MAX_PX = 1200
_PHOTO_WIDTH = 80 * mm


def _register_fonts() -> None:
    """DejaVu supports Cyrillic; Helvetica fallback only if fonts are missing."""
    global _FONT, _FONT_BOLD
    regular, bold = _FONT_DIR / "DejaVuSans.ttf", _FONT_DIR / "DejaVuSans-Bold.ttf"
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("DejaVu", str(regular)))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold)))
        _FONT, _FONT_BOLD = "DejaVu", "DejaVu-Bold"
    else:
        logger.warning("DejaVu fonts not found — Cyrillic text in PDF reports may not render")


_register_fonts()


def _p(text: str, size: int = 10, bold: bool = False, color=colors.black) -> Paragraph:
    style = ParagraphStyle(
        "s", fontName=_FONT_BOLD if bold else _FONT, fontSize=size, leading=size * 1.35, textColor=color
    )
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _fmt(dt, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M") if dt else "—"


def _photo_flowable(url: str, upload_dir: Path) -> Image | None:
    """Load a stored photo from disk, downscale it, and wrap it for the PDF."""
    path = (upload_dir / url.rsplit("/", 1)[-1]).resolve()
    if not str(path).startswith(str(upload_dir.resolve())) or not path.exists():
        return None
    try:
        with PILImage.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((_PHOTO_MAX_PX, _PHOTO_MAX_PX))
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=75)
            w, h = im.size
        buf.seek(0)
        return Image(buf, width=_PHOTO_WIDTH, height=_PHOTO_WIDTH * h / w)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not embed photo %s: %s", path, exc)
        return None


async def build_checklist_pdf(checklist_id: int, completed_by: str | None) -> tuple[bytes, str, str]:
    """Return (pdf_bytes, filename, caption) for a checklist."""
    # Deferred import: app.routers.checklists imports this module.
    from app.routers.checklists import UPLOAD_DIR, _build_items_batch, _compute_deadline_status, _get_ordered_items

    async with AsyncSessionLocal() as db:
        cl = (await db.execute(select(Checklist).where(Checklist.id == checklist_id))).scalar_one()
        branch = (await db.execute(select(Branch).where(Branch.id == cl.branch_id))).scalar_one_or_none()
        items = await _build_items_batch(await _get_ordered_items(checklist_id, db), db)

    try:
        tz = ZoneInfo(branch.timezone if branch else "Asia/Tashkent")
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")

    branch_name = branch.name if branch else "—"
    shift = _SHIFTS.get(cl.shift, cl.shift)
    deadline = _DEADLINE.get(_compute_deadline_status(cl), "—")
    done = sum(1 for i in items if i.is_completed)
    skipped = sum(1 for i in items if i.is_skipped)
    completers = sorted({i.completed_by_name for i in items if i.completed_by_name})

    story: list = [
        _p("Отчёт по чек-листу", 18, bold=True),
        Spacer(1, 4 * mm),
        _p(cl.template_name, 14, bold=True),
        Spacer(1, 4 * mm),
    ]
    info = [
        ("Филиал", branch_name),
        ("Смена", shift),
        ("Дата", cl.date),
        ("Начат", _fmt(cl.started_at, tz)),
        ("Срок", _fmt(cl.due_at, tz)),
        ("Завершён", _fmt(cl.completed_at, tz)),
        ("Статус дедлайна", deadline),
        ("Завершил", completed_by or "—"),
        ("Исполнители", ", ".join(completers) or "—"),
        ("Пункты", f"выполнено {done} из {len(items)}, пропущено {skipped}"),
    ]
    table = Table([[_p(k, bold=True), _p(v)] for k, v in info], colWidths=[45 * mm, 125 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f1f1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [table, Spacer(1, 6 * mm), _p("Пункты чек-листа", 13, bold=True), Spacer(1, 3 * mm)]

    for n, item in enumerate(items, 1):
        if item.is_completed:
            mark, color = "[✓] Выполнено", colors.HexColor("#1a7f37")
        elif item.is_skipped:
            mark, color = "[–] Пропущено", colors.HexColor("#9a6700")
        else:
            mark, color = "[ ] Не выполнено", colors.HexColor("#cf222e")
        block: list = [
            _p(f"{n}. {item.title}", 11, bold=True),
            _p(mark, 10, bold=True, color=color),
        ]
        if item.completed_by_name or item.completed_at:
            block.append(_p(f"{item.completed_by_name or '—'}, {_fmt(item.completed_at, tz)}", 9, color=colors.grey))
        if item.note:
            block.append(_p(f"Комментарий: {item.note}", 10))
        for photo in item.photos:
            img = _photo_flowable(photo.url, UPLOAD_DIR)
            if img:
                block += [Spacer(1, 2 * mm), img]
        block.append(Spacer(1, 5 * mm))
        story.append(KeepTogether(block))

    buf = BytesIO()
    SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"{cl.template_name} — {branch_name} — {cl.date}",
    ).build(story)

    filename = f"checklist_{cl.id}_{cl.date}.pdf"
    caption = (
        f"Чек-лист выполнен: {cl.template_name}\n"
        f"{branch_name} · {shift} · {cl.date}\n"
        f"Дедлайн: {deadline} · Выполнено {done}/{len(items)}"
    )
    return buf.getvalue(), filename, caption


async def _generate_and_send(checklist_id: int, completed_by: str | None) -> None:
    try:
        pdf, filename, caption = await build_checklist_pdf(checklist_id, completed_by)
        await send_document(settings.MANAGERS_CHAT_ID, pdf, filename, caption)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to build/send PDF report for checklist %d", checklist_id)


def schedule_checklist_report(checklist_id: int, completed_by: str | None) -> None:
    """Fire-and-forget: build the PDF and send it to the managers group."""
    if not settings.MANAGERS_CHAT_ID or not settings.BOT_TOKEN:
        return
    task = asyncio.create_task(_generate_and_send(checklist_id, completed_by))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
