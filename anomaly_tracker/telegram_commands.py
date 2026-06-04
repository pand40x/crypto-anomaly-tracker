from __future__ import annotations

from anomaly_tracker.outputs import display_symbol


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
}


def normalize_command(text: str | None) -> str | None:
    if not text:
        return None
    first = text.strip().split(maxsplit=1)[0].lower()
    if not first.startswith("/"):
        return None
    command = first.split("@", 1)[0]
    return COMMAND_ALIASES.get(command)


def build_help_message(public_base_url: str | None = None) -> str:
    panel = f"\nPanel: {public_base_url.rstrip('/')}/dashboard" if public_base_url else ""
    return "\n".join(
        [
            "🐼 Panda Anomali Radarı",
            "Komutlar:",
            "/status - servis ve son tarama durumu",
            "/signals - son sinyaller",
            "/scan - yeni tarama başlat",
            "/dashboard - panel bağlantısı",
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
        f"Piyasa referansı: {health.get('market_reference_symbol', 'BTCUSDT')}",
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
    if not candidates:
        lines.append("Şu anda aktif sinyal yok.")
    for candidate in candidates[:limit]:
        lines.append(_candidate_line(candidate))
    return "\n".join(lines)


def command_response(
    text: str | None,
    health: dict,
    signals: dict,
    public_base_url: str | None = None,
) -> tuple[str | None, str | None]:
    command = normalize_command(text)
    if command is None:
        return None, None
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
    return build_help_message(public_base_url), None
