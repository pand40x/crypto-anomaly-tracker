from __future__ import annotations

from pathlib import Path

from anomaly_tracker.outputs import display_symbol
from anomaly_tracker.sectors import SECTOR_LABELS
from anomaly_tracker.watchlist import WatchlistStore


COMMAND_ALIASES = {
    "/start": "/help",
    "/help": "/help",
    "/yardim": "/help",
    "/yardım": "/help",
    "/status": "/status",
    "/durum": "/status",
    "/signals": "/signals",
    "/sinyaller": "/signals",
    "/scan": "/scan",
    "/tara": "/scan",
    "/dashboard": "/dashboard",
    "/panel": "/dashboard",
    "/izle": "/watch_add",
    "/watch": "/watch_add",
    "/izleme": "/watch_list",
    "/watchlist": "/watch_list",
    "/kaldir": "/watch_remove",
    "/unwatch": "/watch_remove",
    "/mod": "/watch_mode",
    "/etiket": "/watch_tags",
    "/sektor": "/sector",
    "/sector": "/sector",
    "/sektorler": "/sectors",
    "/sectors": "/sectors",
}


def normalize_command(text: str | None) -> tuple[str | None, list[str]]:
    if not text:
        return None, []
    parts = text.strip().split()
    if not parts or not parts[0].startswith("/"):
        return None, []
    command = parts[0].lower().split("@", 1)[0]
    return COMMAND_ALIASES.get(command), parts[1:]


def build_help_message(public_base_url: str | None = None) -> str:
    panel = f"\nPanel: {public_base_url.rstrip('/')}/dashboard" if public_base_url else ""
    return "\n".join(
        [
            "🐼 Panda Anomali Radarı",
            "Komutlar:",
            "/status - servis ve son tarama",
            "/signals - son sinyaller",
            "/scan - yeni tarama",
            "/dashboard - panel",
            "/izle BTC [etiket...] - izleme listesine ekle",
            "/izleme - izleme listesi",
            "/kaldir BTC - listeden çıkar",
            "/mod BTC instant|digest|critical_only",
            "/etiket BTC ai meme - etiket güncelle",
            "/sektor [ai|meme|l2|...] - sektör ısınması",
            "/sektorler - sektör listesi",
            panel,
        ]
    ).strip()


def build_status_message(health: dict) -> str:
    running = bool(health.get("running"))
    summary = health.get("last_result_summary") or {}
    duration = health.get("last_scan_duration_seconds")
    duration_text = f"{duration:.1f} sn" if isinstance(duration, (int, float)) else "henüz yok"
    status = "Tarama çalışıyor" if running else "Hazır"
    error = health.get("last_error")
    lines = [
        "🐼 Panda Anomali Radarı",
        f"Durum: {status}",
        f"Son tarama: {duration_text}",
        (
            f"Aday: {summary.get('candidate_count', 0)} | "
            f"Gönderilebilir: {summary.get('sendable_count', 0)} | "
            f"Bastırılan: {summary.get('suppressed_count', 0)} | "
            f"Filtrelenen: {summary.get('filtered_count', 0)}"
        ),
        f"Piyasa: {', '.join(health.get('market_reference_symbols') or [health.get('market_reference_symbol', 'BTCUSDT')])}",
    ]
    if error:
        lines.append(f"Hata: {error}")
    return "\n".join(lines)


def _candidate_line(candidate: dict) -> str:
    symbol = display_symbol(str(candidate.get("symbol", "")))
    decision = (candidate.get("send_decision") or {}).get("reason", "unknown")
    message = str(candidate.get("message", "")).splitlines()
    headline = message[0] if message else symbol
    move = message[1] if len(message) > 1 else ""
    return f"• {headline}\n  {move}\n  Karar: {decision}"


def build_signals_message(signals: dict, limit: int = 5) -> str:
    context = signals.get("market_context") or {}
    market_text = "Piyasa: referans yok"
    if context:
        pct = context.get("pct_change")
        pct_text = f"{pct:+.2f}%" if isinstance(pct, (int, float)) else "-"
        market_text = f"Piyasa: {context.get('reference_symbol', 'BTCUSDT')}: {context.get('mode', 'neutral')} ({pct_text})"
    candidates = signals.get("candidates") or []
    lines = [
        "📡 Son Sinyaller",
        market_text,
        (
            f"Aday: {signals.get('candidate_count', 0)} | "
            f"Gönderilebilir: {signals.get('sendable_count', 0)} | "
            f"Bastırılan: {signals.get('suppressed_count', 0)} | "
            f"Filtrelenen: {signals.get('filtered_count', 0)}"
        ),
    ]
    sector_heat = signals.get("sector_heat") or []
    if sector_heat:
        top = sector_heat[0]
        lines.append(f"Sektör: {top.get('label')} ({top.get('count')} coin)")
    if not candidates:
        lines.append("Şu anda aktif sinyal yok.")
    for candidate in candidates[:limit]:
        lines.append(_candidate_line(candidate))
    return "\n".join(lines)


def build_watchlist_message(store: WatchlistStore) -> str:
    entries = store.entries()
    if not entries:
        return "İzleme listesi boş.\nEkle: /izle BTC ai core"
    lines = ["👀 İzleme Listesi"]
    for entry in entries:
        tags = ", ".join(entry.tags) if entry.tags else "-"
        lines.append(
            f"• {display_symbol(entry.symbol)} | {entry.alert_mode} | min={entry.min_level} | {tags}"
        )
    return "\n".join(lines)


def build_sectors_message() -> str:
    lines = ["🧺 Sektör Sepetleri"]
    for sector_id, label in SECTOR_LABELS.items():
        lines.append(f"• {sector_id}: {label}")
    lines.append("Detay: /sektor ai")
    return "\n".join(lines)


def build_sector_detail_message(sector_id: str, signals: dict) -> str:
    heats = signals.get("sector_heat") or []
    match = next((item for item in heats if item.get("sector_id") == sector_id), None)
    label = SECTOR_LABELS.get(sector_id, sector_id)
    if match:
        direction = "yükseliş" if match.get("direction") == "up" else "düşüş"
        return "\n".join(
            [
                f"🧺 {label}",
                f"Isınma: {match.get('count')} coin · {direction}",
                f"Skor: {match.get('avg_score')}",
                f"Semboller: {', '.join(match.get('symbols') or [])}",
            ]
        )
    return f"{label} sektöründe son taramada ısınma yok.\nKomut: /sektorler"


def command_response(
    text: str | None,
    health: dict,
    signals: dict,
    public_base_url: str | None = None,
    watchlist_path: Path | None = None,
) -> tuple[str | None, str | None]:
    command, args = normalize_command(text)
    if command is None:
        return None, None
    store = WatchlistStore(watchlist_path) if watchlist_path else None

    if command == "/help":
        return build_help_message(public_base_url), None
    if command == "/status":
        return build_status_message(health), None
    if command == "/signals":
        return build_signals_message(signals), None
    if command == "/dashboard":
        if public_base_url:
            return f"Panel: {public_base_url.rstrip('/')}/dashboard", None
        return "Panel yolu: /dashboard\nBu bağlantıyı tam URL yapmak için ANOMALY_PUBLIC_BASE_URL tanımlanmalı.", None
    if command == "/scan":
        if health.get("running"):
            return "Tarama zaten çalışıyor. Bittiğinde /signals ile sonucu görebilirsin.", None
        return "Yeni taramayı başlatıyorum. Bittiğinde /signals ile sonucu görebilirsin.", "scan"
    if command == "/watch_list":
        if store is None:
            return "İzleme listesi yapılandırılmamış.", None
        return build_watchlist_message(store), None
    if command == "/watch_add":
        if store is None:
            return "İzleme listesi yapılandırılmamış.", None
        if not args:
            return "Kullanım: /izle BTC [etiket...]", None
        entry = store.add(args[0], tags=args[1:])
        return f"Eklendi: {display_symbol(entry.symbol)} ({', '.join(entry.tags) or 'etiketsiz'})", None
    if command == "/watch_remove":
        if store is None or not args:
            return "Kullanım: /kaldir BTC", None
        if store.remove(args[0]):
            return f"Kaldırıldı: {display_symbol(args[0])}", None
        return "Sembol izleme listesinde değil.", None
    if command == "/watch_mode":
        if store is None or len(args) < 2:
            return "Kullanım: /mod BTC instant|digest|critical_only", None
        try:
            entry = store.set_mode(args[0], args[1])
        except KeyError:
            return "Sembol izleme listesinde değil. Önce /izle BTC", None
        except ValueError as exc:
            return str(exc), None
        return f"{display_symbol(entry.symbol)} modu: {entry.alert_mode}", None
    if command == "/watch_tags":
        if store is None or len(args) < 2:
            return "Kullanım: /etiket BTC ai meme", None
        try:
            entry = store.set_tags(args[0], args[1:])
        except KeyError:
            return "Sembol izleme listesinde değil.", None
        return f"{display_symbol(entry.symbol)} etiketleri: {', '.join(entry.tags)}", None
    if command == "/sectors":
        return build_sectors_message(), None
    if command == "/sector":
        sector_id = (args[0] if args else "").lower()
        if not sector_id:
            heats = signals.get("sector_heat") or []
            if not heats:
                return "Son taramada sektör ısınması yok.\n/sektorler ile listeyi gör.", None
            top = heats[0]
            return build_sector_detail_message(str(top.get("sector_id")), signals), None
        if sector_id not in SECTOR_LABELS:
            return "Bilinmeyen sektör. /sektorler ile listeyi gör.", None
        return build_sector_detail_message(sector_id, signals), None
    return build_help_message(public_base_url), None