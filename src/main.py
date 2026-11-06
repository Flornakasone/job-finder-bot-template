"""
Corrida diaria del bot:

    fuentes -> filtros -> deduplicación -> top N -> Telegram -> guardar seen/history

Uso:
    python -m src.main                       # corrida real (la usa GitHub Actions)
    python -m src.main --dry-run             # trae ofertas reales, imprime el mensaje, NO envía ni guarda
    python -m src.main --dry-run --offline   # igual, pero con el cache de .cache/ (sin requests)

Los logs solo muestran conteos: nunca títulos, links ni datos tuyos.
"""
import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src import store
from src import gap_report, paths
from src.filters import apply_filters, load_list
from src.message import build_messages
from src.models import Job
from src.notifier import NotifierError, send_message
from src.scoring import default_scorer
from src.sources import SourceError, empresas, getonbrd, himalayas, jobicy, remoteok, remotive, weworkremotely
from src.integrity import is_safe_for_llm, sanitize
from src.settings import Settings, load_settings
from src.evaluate import default_evaluator

SOURCES = [remotive, jobicy, himalayas, getonbrd, remoteok, weworkremotely, empresas]

ART = timezone(timedelta(hours=-3))  # Argentina, sin horario de verano


@dataclass
class Summary:
    fetched: int = 0
    passed_filters: int = 0
    new: int = 0
    sent: int = 0
    below_min_score: int = 0   # nuevas que no llegaron al piso de % (no se mandan)
    evaluated: int = 0         # ofertas con evaluación de IA (Groq)
    ai_instructions: int = 0  # avisos con instrucciones para una IA (no van al LLM)
    skipped: bool = False   # True si ya se había mandado el resumen de hoy
    source_errors: list[str] = field(default_factory=list)


def fetch_all(sources) -> tuple[list[Job], list[str]]:
    """Trae de todas las fuentes. Si una falla, sigue con las demás."""
    jobs, errors = [], []
    for source in sources:
        try:
            jobs += source.fetch()
        except SourceError as err:
            errors.append(str(err))
    return jobs, errors


def run(
    sources=SOURCES,
    send=send_message,
    seen_path: Path = store.SEEN_FILE,
    history_path: Path = store.HISTORY_FILE,
    last_run_path: Path = store.LAST_RUN_FILE,
    gap_stats_path: Path = gap_report.STATS_FILE,
    force: bool = False,
    scorer=default_scorer,
    evaluator=default_evaluator,
    today: date | None = None,
    top_n: int | None = None,
    settings: Settings | None = None,
    dry_run: bool = False,
    jobs: list[Job] | None = None,
) -> Summary:
    """
    Todo inyectable (fuentes, envío, rutas, fecha) para poder testearlo
    sin internet, sin Telegram y sin tocar data/ real.
    """
    today = today or datetime.now(ART).date()
    settings = settings or load_settings()
    top_n = top_n if top_n is not None else settings.top_n
    summary = Summary()

    # Idempotencia: hay varios crons por día; solo el primero que corre manda.
    # Los demás terminan acá, sin consultar ninguna fuente (no gastan requests).
    if not dry_run and not force and store.already_sent_today(today, last_run_path):
        summary.skipped = True
        return summary

    if jobs is None:
        jobs, summary.source_errors = fetch_all(sources)
        if sources and len(summary.source_errors) == len(sources):
            # Ninguna fuente respondió: avisar y cortar (sin tocar seen)
            if not dry_run:
                send("⚠️ Hoy no pude leer ninguna fuente de empleo. Reviso mañana.")
            return summary
    summary.fetched = len(jobs)
    jobs = [sanitize(j) for j in jobs]
    summary.ai_instructions = sum(not is_safe_for_llm(j) for j in jobs)

    filtered = apply_filters(jobs)
    summary.passed_filters = len(filtered.kept)
    # Foto del mercado para el reporte semanal: gaps de TODO lo relevante (no solo lo enviado)
    gap_stats = gap_report.prune(gap_report.record(
        gap_report.load_stats(gap_stats_path), filtered.kept, today,
        load_list("tech.txt"), load_list("skills.txt")), today)

    seen = store.load_seen(seen_path)
    new_jobs = store.filter_new(filtered.kept, seen)
    summary.new = len(new_jobs)

    # Ordenar por % de match. Sin perfil (scores=None): las más recientes primero.
    scores = scorer(new_jobs)
    if scores:
        # Piso de calidad: lo que no llega a min_score no se manda (ni se marca como visto)
        good = [j for j in new_jobs if scores[j.uid] >= settings.min_score]
        summary.below_min_score = len(new_jobs) - len(good)
        to_send = sorted(good, key=lambda j: scores[j.uid], reverse=True)[:top_n]

    else:
        to_send = sorted(new_jobs, key=lambda j: j.published_at, reverse=True)[:top_n]

    try:
        evaluations = evaluator(to_send)
    except Exception:            # noqa: BLE001 - nunca puede frenar el envío
        evaluations = {}
    summary.evaluated = len(evaluations)

    for text in build_messages(to_send, today, total_checked=summary.fetched,
                               scores=scores, evaluations=evaluations):
        if dry_run:
            print(text, end="\n\n")
        else:
            send(text)  # si falla, lanza error y NO se guarda nada de abajo
    summary.sent = len(to_send)

    if gap_report.is_report_day(today, settings.weekly_gaps_day):
        report = gap_report.build_report(*gap_report.summarize(gap_stats, today), today)
        if report and dry_run:
            print(report, end="\n\n")
        elif report:
            try:
                send(report)
            except NotifierError:
                print("[aviso] no se pudo mandar el reporte semanal")   # el resumen ya salió: no reintentar

    if dry_run:
        return summary

    # Recién acá, con el envío OK, se marcan como vistas
    seen = store.prune_seen(store.mark_seen(to_send, seen, today), today)
    store.save_json(seen_path, seen)
    history = store.add_to_history(store.load_history(history_path), to_send, today)
    store.save_json(history_path, history)
    store.save_json(gap_stats_path, gap_stats)
    store.mark_sent_today(today, last_run_path)   # último paso: recién acá cuenta como enviado
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="imprime el mensaje, no envía ni guarda")
    parser.add_argument("--force", action="store_true", help="manda aunque ya se haya mandado hoy")
    parser.add_argument("--offline", action="store_true", help="usa .cache/jobs.json (solo con --dry-run)")
    args = parser.parse_args()

    if paths.using_template():
        print("[aviso] no existe la carpeta me/: uso los ejemplos de templates/me/ (ver SETUP.md)")
        
    if args.offline and not args.dry_run:
        print("[error] --offline solo se puede usar con --dry-run", file=sys.stderr)
        return 2

    jobs = None
    if args.offline:
        from src.filters import _load_or_fetch
        jobs = _load_or_fetch(offline=True)

    try:
        s = run(dry_run=args.dry_run, jobs=jobs, force=args.force)
    except NotifierError as err:
        print(f"[error] {err}", file=sys.stderr)
        return 1

    if s.skipped:
        print("[resumen] el resumen de hoy ya se mandó: no se consulta ninguna fuente")
        return 0

    # Solo conteos en el log
    print(f"[resumen] traídas={s.fetched} pasan_filtros={s.passed_filters} "
          f"nuevas={s.new} bajo_piso={s.below_min_score} enviadas={s.sent} "
          f"evaluadas_ia={s.evaluated} con_instrucciones_para_ia={s.ai_instructions}")
    for err in s.source_errors:
        print(f"[aviso] fuente con error: {err}")
    if s.source_errors and s.fetched == 0:
        return 1  # cruz roja en Actions si no respondió ninguna fuente
    return 0



if __name__ == "__main__":
    sys.exit(main())
