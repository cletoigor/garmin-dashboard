"""
Garmin Health Dashboard — localhost:5557
"""

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template_string, request, send_from_directory
from garminconnect import Garmin

load_dotenv(Path(__file__).resolve().parent / ".env")

app = Flask(__name__)

# Build de producao da nova SPA React (web/), servida em /app — nao substitui a "/" vanilla.
SPA_DIST = Path(__file__).resolve().parent / "web" / "dist"


def fmt_duration(secs):
    """Segundos -> 'm:ss' ou 'h:mm:ss'."""
    if not secs:
        return "--"
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fmt_pace(speed_ms):
    """Velocidade (m/s) -> pace min/km 'm:ss'."""
    if not speed_ms or speed_ms <= 0:
        return "--"
    sec_per_km = 1000 / speed_ms
    m, s = divmod(int(round(sec_per_km)), 60)
    return f"{m}:{s:02d}"


app.jinja_env.filters["hms"] = fmt_duration

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL = 900
TOKEN_DIR = os.path.expanduser("~/.garminconnect")

_client = None


def get_client():
    global _client
    if _client:
        return _client
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("GARMIN_EMAIL e GARMIN_PASSWORD devem estar no .env")
    _client = Garmin(email, password, prompt_mfa=lambda: input("MFA code: "))
    _client.login(TOKEN_DIR)
    return _client


def cached_fetch(key, fetch_fn, ttl=CACHE_TTL):
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < ttl:
            return json.loads(cache_file.read_text())
    data = fetch_fn()
    cache_file.write_text(json.dumps(data, default=str))
    return data


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_daily_snapshot(target_date):
    ds = target_date if isinstance(target_date, str) else target_date.isoformat()

    def _fetch():
        client = get_client()
        result = {"date": ds}
        try:
            stats = client.get_stats(ds)
            result["steps"] = stats.get("totalSteps", 0)
            result["calories"] = stats.get("totalKilocalories", 0)
            result["resting_hr"] = stats.get("restingHeartRate")
            raw_stress = stats.get("averageStressLevel")
            result["avg_stress"] = raw_stress if raw_stress and raw_stress > 0 else None
            raw_max_stress = stats.get("maxStressLevel")
            result["max_stress"] = raw_max_stress if raw_max_stress and raw_max_stress > 0 else None
            result["bb_high"] = stats.get("bodyBatteryHighestValue")
            result["bb_low"] = stats.get("bodyBatteryLowestValue")
            result["active_minutes"] = (
                (stats.get("moderateIntensityMinutes") or 0)
                + (stats.get("vigorousIntensityMinutes") or 0)
            )
            result["floors"] = stats.get("floorsAscended")
            result["distance_km"] = round((stats.get("totalDistanceMeters") or 0) / 1000, 1)
        except Exception:
            pass
        try:
            sleep = client.get_sleep_data(ds)
            dto = sleep.get("dailySleepDTO", {})
            sleep_secs = dto.get("sleepTimeSeconds") or 0
            result["sleep_hours"] = round(sleep_secs / 3600, 1)
            result["deep_sleep_min"] = round((dto.get("deepSleepSeconds") or 0) / 60)
            result["rem_sleep_min"] = round((dto.get("remSleepSeconds") or 0) / 60)
            result["light_sleep_min"] = round((dto.get("lightSleepSeconds") or 0) / 60)
            result["awake_min"] = round((dto.get("awakeSleepSeconds") or 0) / 60)
            result["avg_spo2"] = dto.get("averageSpO2Value")
            result["avg_hrv"] = dto.get("averageHRV")
            scores = sleep.get("sleepScores", {})
            result["sleep_score"] = (scores.get("overall", {}) or {}).get("value")
        except Exception:
            pass
        try:
            hr = client.get_heart_rates(ds)
            result["hr_min"] = hr.get("minHeartRate")
            result["hr_max"] = hr.get("maxHeartRate")
            if not result.get("resting_hr"):
                result["resting_hr"] = hr.get("restingHeartRate")
        except Exception:
            pass
        try:
            resp = client.get_respiration_data(ds)
            result["avg_respiration"] = resp.get("avgWakingRespirationValue")
            result["sleep_respiration"] = resp.get("avgSleepRespirationValue")
        except Exception:
            pass
        return result

    # Dias passados nao mudam mais: cache de 24h. So o dia de hoje precisa
    # do TTL curto (dados ainda chegando do relogio ao longo do dia).
    ttl = CACHE_TTL if ds == date.today().isoformat() else 24 * 3600
    return cached_fetch(f"daily_{ds}", _fetch, ttl=ttl)


def fetch_multi_day(days=14):
    today = date.today()
    return [fetch_daily_snapshot((today - timedelta(days=i)).isoformat()) for i in range(days)]


def fetch_activities(days=30):
    def _fetch():
        client = get_client()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        raw = client.get_activities(0, 100)
        activities = []
        for a in raw:
            d = (a.get("startTimeLocal") or "")[:10]
            if d < cutoff:
                break
            activities.append({
                "id": a.get("activityId"),
                "name": a.get("activityName", ""),
                "type": (a.get("activityType", {}) or {}).get("typeKey", "other"),
                "date": d,
                "datetime": a.get("startTimeLocal", ""),
                "duration_min": round((a.get("duration") or 0) / 60, 1),
                "distance_km": round((a.get("distance") or 0) / 1000, 2),
                "avg_hr": a.get("averageHR"),
                "max_hr": a.get("maxHR"),
                "calories": a.get("calories"),
                "avg_speed": a.get("averageSpeed"),
                "elevation_gain": a.get("elevationGain"),
                "vo2max": a.get("vO2MaxValue"),
            })
        return activities

    return cached_fetch("activities_30d", _fetch)


def fetch_fitness():
    """VO2max mais recente disponivel + previsoes de corrida (5k/10k/meia/maratona)."""
    def _fetch():
        client = get_client()
        out = {"vo2max": None, "vo2max_date": None, "predictions": {}}
        today = date.today()
        for i in range(0, 30):
            d = (today - timedelta(days=i)).isoformat()
            try:
                mm = client.get_max_metrics(d)
            except Exception:
                mm = None
            if mm:
                gen = (mm[0] or {}).get("generic") or {}
                v = gen.get("vo2MaxValue") or gen.get("vo2MaxPreciseValue")
                if v:
                    out["vo2max"] = round(v, 1)
                    out["vo2max_date"] = gen.get("calendarDate") or d
                    out["fitness_age"] = gen.get("fitnessAge")
                    break
        try:
            rp = client.get_race_predictions() or {}
            out["predictions"] = {
                "5k": rp.get("time5K"),
                "10k": rp.get("time10K"),
                "half": rp.get("timeHalfMarathon"),
                "marathon": rp.get("timeMarathon"),
            }
        except Exception:
            pass
        return out

    return cached_fetch("fitness", _fetch, ttl=6 * 3600)


def fetch_activity_detail(activity_id):
    """Zonas de FC e splits por km de uma atividade."""
    def _fetch():
        client = get_client()
        out = {"hr_zones": [], "splits": []}
        try:
            zones = client.get_activity_hr_in_timezones(activity_id) or []
            out["hr_zones"] = [
                {
                    "zone": z.get("zoneNumber"),
                    "secs": round(z.get("secsInZone") or 0),
                    "low": z.get("zoneLowBoundary"),
                }
                for z in zones
            ]
        except Exception:
            pass
        try:
            sp = client.get_activity_splits(activity_id) or {}
            laps = sp.get("lapDTOs") or []
            out["splits"] = [
                {
                    "distance_km": round((lap.get("distance") or 0) / 1000, 2),
                    "duration_s": round(lap.get("duration") or 0),
                    "speed": lap.get("averageSpeed"),
                    "avg_hr": lap.get("averageHR"),
                    "cadence": round(lap.get("averageRunCadence")) if lap.get("averageRunCadence") else None,
                    "elev_gain": round(lap.get("elevationGain")) if lap.get("elevationGain") else None,
                }
                for lap in laps
            ]
        except Exception:
            pass
        return out

    return cached_fetch(f"activity_{activity_id}", _fetch, ttl=24 * 3600)


# ---------------------------------------------------------------------------
# Sync status (frescor dos dados + alerta de falha)
# ---------------------------------------------------------------------------

SYNC_FILE = Path(__file__).resolve().parent / "last_sync.json"


def write_sync_status(ok, message="", source="app"):
    try:
        SYNC_FILE.write_text(json.dumps({
            "ts": time.time(),
            "ok": bool(ok),
            "message": message,
            "source": source,
        }))
    except Exception:
        pass


def read_sync_status():
    info = {"ts": None, "ok": None, "age_hours": None, "message": "", "level": "unknown"}
    ts = None
    if SYNC_FILE.exists():
        try:
            data = json.loads(SYNC_FILE.read_text())
            info.update(data)
            ts = data.get("ts")
        except Exception:
            pass
    if ts is None:
        # fallback: mtime do snapshot diario mais recente
        files = list(CACHE_DIR.glob("daily_*.json"))
        if files:
            ts = max(f.stat().st_mtime for f in files)
            info["ts"] = ts
            info["ok"] = True
    if ts:
        age = (time.time() - ts) / 3600
        info["age_hours"] = round(age, 1)
        if info.get("ok") is False:
            info["level"] = "fail"
        elif age > 26:
            info["level"] = "stale"
        else:
            info["level"] = "ok"
    return info


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

METRICS_CONFIG = {
    "steps":      {"field": "steps",      "label": "Passos",        "polarity": "positive_up", "fmt": "{:.0f}"},
    "resting_hr": {"field": "resting_hr", "label": "FC Repouso",    "polarity": "negative_up", "fmt": "{:.0f}", "unit": "bpm"},
    "sleep_hours":{"field": "sleep_hours","label": "Sono",          "polarity": "positive_up", "fmt": "{:.1f}", "unit": "h"},
    "avg_stress": {"field": "avg_stress", "label": "Estresse",      "polarity": "negative_up", "fmt": "{:.0f}"},
    "bb_high":    {"field": "bb_high",    "label": "Body Battery",  "polarity": "positive_up", "fmt": "{:.0f}"},
}


def compute_trends(daily_data, days=7):
    this_week = daily_data[:days]
    last_week = daily_data[days:2 * days]
    result = {}
    for key, cfg in METRICS_CONFIG.items():
        field = cfg["field"]
        cur_vals = [d[field] for d in this_week if d.get(field) is not None]
        prev_vals = [d[field] for d in last_week if d.get(field) is not None]
        cur_avg = sum(cur_vals) / len(cur_vals) if cur_vals else 0
        prev_avg = sum(prev_vals) / len(prev_vals) if prev_vals else 0
        change = ((cur_avg - prev_avg) / prev_avg * 100) if prev_avg else 0
        direction = "up" if change > 1 else "down" if change < -1 else "flat"
        if cfg["polarity"] == "positive_up":
            sentiment = "positive" if direction == "up" else "negative" if direction == "down" else "neutral"
        else:
            sentiment = "negative" if direction == "up" else "positive" if direction == "down" else "neutral"
        result[key] = {
            "label": cfg["label"],
            "current": round(cur_avg, 1),
            "previous": round(prev_avg, 1),
            "change_pct": round(change, 1),
            "direction": direction,
            "sentiment": sentiment,
            "unit": cfg.get("unit", ""),
        }
    return result


TYPE_LABELS = {
    "running": "Corrida",
    "trail_running": "Trail Run",
    "treadmill_running": "Esteira",
    "cycling": "Ciclismo",
    "mountain_biking": "MTB",
    "swimming": "Natacao",
    "walking": "Caminhada",
    "hiking": "Trilha",
    "strength_training": "Musculacao",
    "cardio_training": "Cardio",
    "yoga": "Yoga",
    "other": "Outro",
}


def generate_training_report(activities, daily_data=None):
    if not activities:
        return {"summary": {}, "by_type": [], "insights": {}, "recent": []}

    total_dist = sum(a["distance_km"] for a in activities)
    total_dur = sum(a["duration_min"] for a in activities)
    total_cal = sum(a["calories"] or 0 for a in activities)

    by_type = {}
    for a in activities:
        t = a["type"]
        if t not in by_type:
            by_type[t] = {"type": t, "label": TYPE_LABELS.get(t, t), "count": 0, "distance_km": 0, "hrs": [], "duration_min": 0}
        by_type[t]["count"] += 1
        by_type[t]["distance_km"] += a["distance_km"]
        by_type[t]["duration_min"] += a["duration_min"]
        if a["avg_hr"]:
            by_type[t]["hrs"].append(a["avg_hr"])

    type_list = []
    for t, info in sorted(by_type.items(), key=lambda x: x[1]["count"], reverse=True):
        avg_hr = round(sum(info["hrs"]) / len(info["hrs"])) if info["hrs"] else None
        type_list.append({
            "type": t,
            "label": info["label"],
            "count": info["count"],
            "distance_km": round(info["distance_km"], 1),
            "avg_hr": avg_hr,
            "duration_min": round(info["duration_min"]),
        })

    insights = _generate_insights(activities, type_list, daily_data)

    return {
        "summary": {
            "total_activities": len(activities),
            "total_km": round(total_dist, 1),
            "total_hours": round(total_dur / 60, 1),
            "total_calories": round(total_cal),
        },
        "by_type": type_list,
        "insights": insights,
        "recent": activities[:10],
    }


INSIGHT_ICONS = {
    "Sono": "\U0001F319",
    "Saude": "❤️",
    "Tendencias": "\U0001F4C8",
    "Treino": "\U0001F3CB️",
    "Correlacoes": "\U0001F517",
}


def _ins(text, sentiment="neutral"):
    return {"text": text, "sentiment": sentiment}


def _generate_insights(activities, type_list, daily_data):
    blocks = {}
    today = date.today()

    # --- Sono ---
    sono = []
    if daily_data:
        last = daily_data[0]
        sh = last.get("sleep_hours")
        ss = last.get("sleep_score")
        deep = last.get("deep_sleep_min")
        rem = last.get("rem_sleep_min")
        if sh and sh > 0:
            parts = [f"Ultima noite: {sh}h de sono"]
            if ss:
                parts.append(f"score {ss}")
            if deep:
                parts.append(f"{deep}min profundo")
            if rem:
                parts.append(f"{rem}min REM")
            quality = "excelente" if (ss and ss >= 80) else "boa" if (ss and ss >= 60) else "fraca" if ss else None
            if quality:
                parts.append(f"qualidade {quality}")
            sent = "good" if quality in ("excelente", "boa") else "warn" if quality == "fraca" else "neutral"
            sono.append(_ins(" | ".join(parts), sent))
        sleep_scores = [d["sleep_score"] for d in daily_data[:7] if d.get("sleep_score")]
        if sleep_scores:
            avg_sleep = sum(sleep_scores) / len(sleep_scores)
            if avg_sleep < 60:
                sono.append(_ins(f"Sleep Score medio baixo ({avg_sleep:.0f}) — qualidade do sono precisa de atencao", "warn"))
            else:
                sono.append(_ins(f"Sleep Score medio da semana: {avg_sleep:.0f}", "neutral"))
    if sono:
        blocks["Sono"] = sono

    # --- Saude ---
    saude = []
    if daily_data:
        recent = daily_data[:7]
        rhr_vals = [d["resting_hr"] for d in recent if d.get("resting_hr")]
        bb_vals = [d["bb_high"] for d in recent if d.get("bb_high")]
        stress_vals = [d["avg_stress"] for d in recent if d.get("avg_stress")]
        if rhr_vals and len(rhr_vals) >= 3:
            if rhr_vals[0] and rhr_vals[-1] and rhr_vals[0] < rhr_vals[-1]:
                saude.append(_ins(f"FC repouso em queda ({rhr_vals[-1]} -> {rhr_vals[0]} bpm) — bom sinal de recuperacao", "good"))
            elif rhr_vals[0] and rhr_vals[-1] and rhr_vals[0] > rhr_vals[-1] + 3:
                saude.append(_ins(f"FC repouso subindo ({rhr_vals[-1]} -> {rhr_vals[0]} bpm) — atencao a recuperacao", "warn"))
        if bb_vals:
            avg_bb = sum(bb_vals) / len(bb_vals)
            if avg_bb < 50:
                saude.append(_ins(f"Body Battery media baixa ({avg_bb:.0f}) — priorize descanso", "warn"))
            else:
                saude.append(_ins(f"Body Battery media da semana: {avg_bb:.0f}", "neutral"))
        if stress_vals:
            avg_stress = sum(stress_vals) / len(stress_vals)
            if avg_stress > 50:
                saude.append(_ins(f"Estresse medio elevado ({avg_stress:.0f}) — considere pausas e descanso", "warn"))
            elif avg_stress <= 25:
                saude.append(_ins(f"Estresse medio baixo ({avg_stress:.0f}) — otimo controle", "good"))
    if saude:
        blocks["Saude"] = saude

    # --- Tendencias ---
    tendencias = []
    week_acts = [a for a in activities if a["date"] >= (today - timedelta(days=7)).isoformat()]
    prev_week_acts = [a for a in activities if (today - timedelta(days=14)).isoformat() <= a["date"] < (today - timedelta(days=7)).isoformat()]
    if week_acts and prev_week_acts:
        cur_dist = sum(a["distance_km"] for a in week_acts)
        prev_dist = sum(a["distance_km"] for a in prev_week_acts)
        if prev_dist > 0:
            pct = ((cur_dist - prev_dist) / prev_dist) * 100
            if pct > 10:
                tendencias.append(_ins(f"Volume subiu {pct:.0f}% esta semana ({cur_dist:.1f} km vs {prev_dist:.1f} km)", "neutral"))
            elif pct < -10:
                tendencias.append(_ins(f"Volume caiu {abs(pct):.0f}% esta semana ({cur_dist:.1f} km vs {prev_dist:.1f} km)", "neutral"))
    for t_info in type_list:
        t = t_info["type"]
        t_acts_week = [a for a in week_acts if a["type"] == t]
        t_acts_prev = [a for a in prev_week_acts if a["type"] == t]
        if t_acts_week and t_acts_prev:
            cur_hrs = [a["avg_hr"] for a in t_acts_week if a["avg_hr"]]
            prev_hrs = [a["avg_hr"] for a in t_acts_prev if a["avg_hr"]]
            if cur_hrs and prev_hrs:
                cur_avg = sum(cur_hrs) / len(cur_hrs)
                prev_avg = sum(prev_hrs) / len(prev_hrs)
                diff = prev_avg - cur_avg
                if diff > 3:
                    tendencias.append(_ins(f"FC media em {t_info['label']} caiu {diff:.0f} bpm vs semana passada — melhor eficiencia aerobica", "good"))
    if tendencias:
        blocks["Tendencias"] = tendencias

    # --- Treino ---
    treino = []
    endurance_types = {"running", "trail_running", "treadmill_running", "cycling", "mountain_biking", "swimming"}
    endurance_acts = [a for a in activities if a["type"] in endurance_types and a["distance_km"] > 0]
    if endurance_acts:
        longest = max(endurance_acts, key=lambda a: a["distance_km"])
        treino.append(_ins(f"Maior atividade recente: {longest['distance_km']:.1f} km ({TYPE_LABELS.get(longest['type'], longest['type'])}) em {longest['date']}", "neutral"))
    types_this_week = set(a["type"] for a in week_acts)
    strength_types = {"strength_training", "cardio_training"}
    endurance_only = types_this_week.issubset(endurance_types)
    strength_only = types_this_week.issubset(strength_types)
    if endurance_only and len(week_acts) >= 3:
        treino.append(_ins("Semana so de aerobico — considere adicionar forca", "warn"))
    elif strength_only and len(week_acts) >= 3:
        treino.append(_ins("Semana so de forca — considere adicionar aerobico", "warn"))
    for t_info in type_list:
        if t_info["count"] >= 3:
            treino.append(_ins(f"{t_info['count']}x {t_info['label']} — boa consistencia", "good"))
    if treino:
        blocks["Treino"] = treino

    # --- Correlacoes ---
    corr = []
    # Sono -> estresse do dia seguinte (daily_data[0] = hoje; i-1 e o dia seguinte de i)
    short_next, good_next = [], []
    for i in range(1, len(daily_data)):
        night = daily_data[i].get("sleep_hours")
        next_stress = daily_data[i - 1].get("avg_stress")
        if not night or not next_stress:
            continue
        if night < 6.5:
            short_next.append(next_stress)
        elif night >= 7:
            good_next.append(next_stress)
    if len(short_next) >= 2 and len(good_next) >= 2:
        avg_short = sum(short_next) / len(short_next)
        avg_good = sum(good_next) / len(good_next)
        diff = avg_short - avg_good
        if diff >= 5:
            corr.append(_ins(
                f"Noites curtas (<6.5h) elevam seu estresse no dia seguinte: {avg_short:.0f} vs {avg_good:.0f} apos noites boas (+{diff:.0f})",
                "warn",
            ))
        elif diff <= -5:
            corr.append(_ins(
                f"Seu estresse nao parece sofrer com noites curtas (media {avg_short:.0f} vs {avg_good:.0f})", "good"
            ))
    # Carga de treino vs recuperacao (FC repouso)
    week_cut = (today - timedelta(days=7)).isoformat()
    km_week = sum(a["distance_km"] for a in activities if a["date"] >= week_cut)
    rhr_recent = [d["resting_hr"] for d in daily_data[:7] if d.get("resting_hr")]
    if km_week >= 20 and len(rhr_recent) >= 4 and rhr_recent[0] > rhr_recent[-1] + 2:
        corr.append(_ins(
            f"Carga alta na semana ({km_week:.0f} km) com FC repouso subindo ({rhr_recent[-1]} -> {rhr_recent[0]} bpm) — priorize recuperacao",
            "warn",
        ))
    if corr:
        blocks["Correlacoes"] = corr

    return blocks


def generate_daily_summary(snapshot):
    parts = []
    steps = snapshot.get("steps")
    if steps and steps > 0:
        if steps >= 10000:
            parts.append(f"dia ativo com {steps:,} passos".replace(",", "."))
        elif steps >= 5000:
            parts.append(f"{steps:,} passos — dia moderado".replace(",", "."))
        else:
            parts.append(f"dia tranquilo com {steps:,} passos".replace(",", "."))

    bb = snapshot.get("bb_high")
    if bb:
        if bb >= 70:
            parts.append("energia alta")
        elif bb >= 40:
            parts.append("energia moderada")
        else:
            parts.append("energia baixa")

    stress = snapshot.get("avg_stress")
    if stress and stress > 0:
        if stress <= 25:
            parts.append("baixo estresse")
        elif stress <= 50:
            parts.append("estresse moderado")
        else:
            parts.append("estresse elevado")

    sleep_h = snapshot.get("sleep_hours")
    if sleep_h and sleep_h > 0:
        if sleep_h >= 7:
            parts.append(f"boa noite de sono ({sleep_h}h)")
        elif sleep_h >= 5:
            parts.append(f"sono curto ({sleep_h}h)")
        else:
            parts.append(f"sono insuficiente ({sleep_h}h)")

    rhr = snapshot.get("resting_hr")
    if rhr:
        parts.append(f"FC repouso {rhr} bpm")

    active = snapshot.get("active_minutes")
    if active and active > 0:
        parts.append(f"{active} min ativos")

    if not parts:
        return "Dados ainda sendo coletados hoje."

    summary = parts[0][0].upper() + parts[0][1:]
    if len(parts) > 1:
        summary += ", " + ", ".join(parts[1:])
    summary += "."
    return summary


# ---------------------------------------------------------------------------
# Metas, streak e fallback de dia incompleto
# ---------------------------------------------------------------------------

DEFAULT_GOALS = {"steps_day": 8000, "km_week": 25, "active_min_week": 150}
GOALS_FILE = Path(__file__).resolve().parent / "goals.json"


def load_goals():
    g: "dict[str, float]" = {**DEFAULT_GOALS}
    if GOALS_FILE.exists():
        try:
            saved = json.loads(GOALS_FILE.read_text())
            for k in DEFAULT_GOALS:
                if isinstance(saved.get(k), (int, float)) and saved[k] > 0:
                    g[k] = saved[k]
        except Exception:
            pass
    return g


def save_goals(new):
    g = load_goals()
    for k in DEFAULT_GOALS:
        v = new.get(k)
        if isinstance(v, (int, float)) and v > 0:
            g[k] = int(v) if k != "km_week" else round(float(v), 1)
    GOALS_FILE.write_text(json.dumps(g))
    return g


def is_complete_snapshot(s):
    return bool(s and (s.get("steps") or s.get("resting_hr") or s.get("sleep_hours")))


def pick_display_snapshot(daily_data):
    """Retorna (snapshot, is_fallback). Se hoje estiver incompleto, usa o ultimo dia completo."""
    if not daily_data:
        return {}, False
    today = daily_data[0]
    if is_complete_snapshot(today):
        return today, False
    for s in daily_data[1:]:
        if is_complete_snapshot(s):
            return s, True
    return today, False


def compute_goals(daily_data, activities):
    today = date.today()
    goals = load_goals()
    week = daily_data[:7]
    steps_today = (daily_data[0] or {}).get("steps") or 0
    if not steps_today:
        # hoje incompleto -> usa ultimo dia com passos
        for d in daily_data:
            if d.get("steps"):
                steps_today = d["steps"]
                break
    week_cut = (today - timedelta(days=7)).isoformat()
    week_acts = [a for a in activities if a["date"] >= week_cut]
    km_week = sum(a["distance_km"] for a in week_acts)
    active_min = sum((d.get("active_minutes") or 0) for d in week)

    def pct(v, g):
        return min(100, round(v / g * 100)) if g else 0

    return [
        {"key": "steps_day", "label": "Passos (dia)", "value": int(steps_today), "goal": goals["steps_day"], "unit": "", "pct": pct(steps_today, goals["steps_day"]), "color": "var(--blue)"},
        {"key": "km_week", "label": "Distancia (7d)", "value": round(km_week, 1), "goal": goals["km_week"], "unit": "km", "pct": pct(km_week, goals["km_week"]), "color": "var(--green)"},
        {"key": "active_min_week", "label": "Min ativos (7d)", "value": int(active_min), "goal": goals["active_min_week"], "unit": "min", "pct": pct(active_min, goals["active_min_week"]), "color": "var(--orange)"},
    ]


def compute_streak(daily_data, goal=None):
    """Dias consecutivos (do mais recente completo pra tras) batendo a meta de passos."""
    goal = goal or load_goals()["steps_day"]
    streak = 0
    started = False
    for d in daily_data:
        steps = d.get("steps")
        if steps is None or steps == 0:
            if not started:
                # hoje ainda incompleto: ignora sem quebrar
                continue
            break
        started = True
        if steps >= goal:
            streak += 1
        else:
            break
    return streak


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Garmin Dashboard</title>
<script>document.documentElement.setAttribute('data-theme', localStorage.getItem('garmin-theme') || 'dark');</script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Manrope:wght@700;800&display=swap" rel="stylesheet">
<style>
:root {
  --bg:       #12161d;
  --surface:  #1a1f27;
  --surface2: #232a35;
  --surface3: #2d3541;
  --border:   #343d4a;
  --text:     #e4e8ee;
  --muted:    #98a3b3;
  --green:    #34d399;
  --red:      #f87171;
  --yellow:   #fbbf24;
  --blue:     #60a5fa;
  --purple:   #a78bfa;
  --cyan:     #22d3ee;
  --orange:   #fb923c;
  --sleep-deep: #4f46e5; --sleep-deep-d: #3730a3;
  --sleep-rem: #d946ef; --sleep-rem-d: #a21caf;
  --sleep-light: #22d3ee; --sleep-light-d: #0e7490;
  --sleep-awake: #f87171; --sleep-awake-d: #b91c1c;
  --mono: ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace;
  --sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --display: 'Manrope', var(--sans);
  --shadow: 0 4px 16px rgba(0,0,0,0.28);
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.22);
}
[data-theme="light"] {
  --bg:       #f4f6f9;
  --surface:  #ffffff;
  --surface2: #eef1f5;
  --surface3: #e2e7ee;
  --border:   #d3dae3;
  --text:     #1b2430;
  --muted:    #5e6b7a;
  --green:    #059669;
  --red:      #dc2626;
  --yellow:   #d97706;
  --blue:     #2563eb;
  --purple:   #7c3aed;
  --cyan:     #0891b2;
  --orange:   #ea580c;
  --shadow: 0 4px 16px rgba(30,41,59,0.08);
  --shadow-sm: 0 2px 8px rgba(30,41,59,0.06);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { -webkit-text-size-adjust: 100%; }
body { font-family: var(--sans);
       background: var(--bg); color: var(--text); min-height: 100vh; font-size: 15px;
       letter-spacing: 0.1px; line-height: 1.6;
       -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }

header {
  background: linear-gradient(180deg, var(--surface) 0%, var(--bg) 100%);
  border-bottom: 1px solid var(--border);
  padding: 0 clamp(20px, 4vw, 64px); height: 60px;
  display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; z-index: 10;
}
.logo { display: flex; align-items: center; gap: 12px; font-family: var(--display); font-weight: 800; font-size: 17px; letter-spacing: 0.2px; }
.logo-icon { font-size: 20px; }
.header-right { display: flex; align-items: center; gap: 16px; }
.clock { font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }
.refresh-btn {
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--text); font-size: 12px; padding: 6px 14px;
  border-radius: 8px; cursor: pointer; transition: all 0.15s;
}
.refresh-btn:hover { background: var(--surface3); border-color: var(--blue); }
.theme-btn {
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--text); font-size: 14px; line-height: 1; padding: 6px 10px;
  border-radius: 8px; cursor: pointer; transition: all 0.15s;
}
.theme-btn:hover { background: var(--surface3); border-color: var(--yellow); }
.shutdown-btn {
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--red); font-size: 12px; padding: 6px 14px;
  border-radius: 8px; cursor: pointer; transition: all 0.15s;
}
.shutdown-btn:hover { background: rgba(248,113,113,0.1); border-color: var(--red); }

.stats-bar {
  display: flex; gap: 0; background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.stat-cell {
  flex: 1; padding: 18px 20px; text-align: center;
  border-right: 1px solid var(--border); transition: background 0.15s;
}
.stat-cell:last-child { border-right: none; }
.stat-cell:hover { background: var(--surface2); }
.stat-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; font-weight: 500; }
.stat-value { font-size: 26px; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -0.5px; font-family: var(--mono); }
.stat-unit { font-size: 11px; color: var(--muted); font-weight: 400; margin-left: 2px; }

main { width: 100%; max-width: 1920px; margin: 0 auto;
       padding: 32px clamp(20px, 4vw, 64px); display: flex; flex-direction: column; gap: 24px; }

.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; overflow: hidden; box-shadow: var(--shadow-sm);
}
.card-header {
  padding: 16px 24px; border-bottom: 1px solid var(--border);
  font-weight: 700; font-size: 13px; text-transform: uppercase; letter-spacing: 0.7px;
  display: flex; align-items: center; gap: 10px; color: var(--muted);
}
.card-header .card-icon { font-size: 16px; }
.card-header .card-date { color: var(--text); font-weight: 600; text-transform: none; letter-spacing: 0; }
.card-body { padding: 24px; }

.daily-summary {
  background: linear-gradient(135deg, rgba(96,165,250,0.08) 0%, rgba(167,139,250,0.08) 100%);
  border: 1px solid rgba(96,165,250,0.15); border-radius: 10px;
  padding: 18px 22px; margin-bottom: 20px;
  font-size: 14.5px; line-height: 1.75; letter-spacing: 0.1px; color: var(--text);
}

.health-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 24px; }
.health-section h4 {
  font-size: 11px; color: var(--muted); text-transform: uppercase;
  letter-spacing: 1px; margin-bottom: 14px; font-weight: 600;
  padding-bottom: 8px; border-bottom: 2px solid var(--border);
}
.health-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 0;
}
.health-row + .health-row { border-top: 1px solid var(--border); }
.health-key { color: var(--muted); font-size: 13.5px; letter-spacing: 0.15px; }
.health-val { font-weight: 700; font-variant-numeric: tabular-nums; font-size: 14.5px; font-family: var(--mono); }

.sleep-bar { display: flex; height: 28px; border-radius: 6px; overflow: hidden; margin-bottom: 14px; }
.sleep-bar div { display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: #fff; overflow: hidden; }
.sleep-deep { background: linear-gradient(135deg, var(--sleep-deep-d), var(--sleep-deep)); }
.sleep-rem { background: linear-gradient(135deg, var(--sleep-rem-d), var(--sleep-rem)); }
.sleep-light { background: linear-gradient(135deg, var(--sleep-light-d), var(--sleep-light)); }
.sleep-awake { background: linear-gradient(135deg, var(--sleep-awake-d), var(--sleep-awake)); }

.sleep-legend { display: flex; gap: 16px; font-size: 11px; color: var(--muted); margin-bottom: 14px; }
.sleep-legend span { display: flex; align-items: center; gap: 4px; }
.legend-dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }

.trend-pills { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; transition: opacity .25s ease; }
.trend-pill {
  background: var(--surface2); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 18px; flex: 1; min-width: 155px; text-align: center;
  transition: border-color 0.15s;
}
.trend-pill:hover { border-color: var(--blue); }
.trend-pill .label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; font-weight: 500; }
.trend-pill .value { font-size: 22px; font-weight: 800; letter-spacing: -0.5px; font-family: var(--mono); }
.trend-pill .change { font-size: 12px; font-weight: 700; margin-top: 4px; display: flex; align-items: center; justify-content: center; gap: 4px; }
.trend-pill .change.positive { color: var(--green); }
.trend-pill .change.negative { color: var(--red); }
.trend-pill .change.neutral { color: var(--muted); }
.trend-pill .prev { font-size: 10px; color: var(--muted); margin-top: 2px; }

.charts-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; transition: opacity .25s ease; }
.chart-card {
  background: var(--surface2); border: 1px solid var(--border); border-radius: 10px;
  padding: 18px; transition: border-color 0.15s;
}
.chart-card:hover { border-color: var(--surface3); }
.chart-card h5 { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; font-weight: 600; }
.chart-container { position: relative; height: 200px; margin-bottom: 6px; }
.chart-subtitle { font-size: 10px; color: var(--muted); font-style: italic; }

.summary-row { display: flex; gap: 12px; margin-bottom: 24px; }
.summary-cell {
  flex: 1; background: var(--surface2); border: 1px solid var(--border);
  border-radius: 10px; padding: 18px; text-align: center; transition: border-color 0.15s;
}
.summary-cell:hover { border-color: var(--blue); }
.summary-cell .num { font-size: 26px; font-weight: 800; letter-spacing: -0.5px; font-family: var(--mono); }
.summary-cell:nth-child(1) .num { color: var(--blue); }
.summary-cell:nth-child(2) .num { color: var(--green); }
.summary-cell:nth-child(3) .num { color: var(--purple); }
.summary-cell:nth-child(4) .num { color: var(--orange); }
.summary-cell .lbl { font-size: 10px; color: var(--muted); margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; font-weight: 500; }

table { width: 100%; border-collapse: collapse; margin-top: 4px; }
th {
  text-align: left; font-size: 10px; color: var(--muted); text-transform: uppercase;
  letter-spacing: 1px; padding: 10px 14px; border-bottom: 2px solid var(--border); font-weight: 600;
}
td {
  padding: 11px 14px; font-variant-numeric: tabular-nums; font-size: 13.5px; letter-spacing: 0.1px;
}
tr { border-bottom: 1px solid var(--border); transition: background 0.1s; }
tr:last-child { border-bottom: none; }
tr:hover { background: rgba(96,165,250,0.04); }

.section-title {
  font-size: 11px; color: var(--muted); text-transform: uppercase;
  letter-spacing: 1px; font-weight: 600; padding-bottom: 10px;
  border-bottom: 2px solid var(--border); margin-bottom: 12px;
}

.insights { margin-top: 20px; }
/* Analise por IA */
.ai-analysis { font-size: 14.5px; line-height: 1.75; letter-spacing: 0.1px; color: var(--text); }
.ai-analysis h3 { font-size: 12px; color: var(--blue); text-transform: uppercase; letter-spacing: 1px;
  font-weight: 700; margin: 18px 0 8px; }
.ai-analysis h3:first-child { margin-top: 0; }
.ai-analysis p { margin: 0 0 12px; }
.ai-analysis ul { margin: 0 0 12px; padding-left: 20px; }
.ai-analysis li { margin-bottom: 6px; }
.ai-analysis strong { color: var(--text); font-weight: 700; }
.quick-insights .section-title { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-bottom: 12px; }

.insights-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.insight-block {
  background: var(--surface2); border: 1px solid var(--border); border-radius: 12px;
  padding: 16px 18px; transition: border-color 0.15s, transform 0.15s;
}
.insight-block:hover { border-color: var(--surface3); transform: translateY(-1px); }
.insight-block-title {
  font-size: 12px; color: var(--text); text-transform: none; letter-spacing: 0;
  font-weight: 700; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 8px;
}
.insight-block-title .ico { font-size: 15px; }
.insight-item {
  display: flex; align-items: flex-start; gap: 10px; padding: 8px 0;
  font-size: 13.5px; line-height: 1.6; letter-spacing: 0.1px;
}
.insight-item + .insight-item { border-top: 1px solid var(--border); }
.insight-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--blue); margin-top: 6px; flex-shrink: 0; box-shadow: 0 0 0 3px transparent; }
.insight-dot.s-good  { background: var(--green);  box-shadow: 0 0 0 3px rgba(52,211,153,0.15); }
.insight-dot.s-warn  { background: var(--yellow); box-shadow: 0 0 0 3px rgba(251,191,36,0.15); }
.insight-dot.s-neutral { background: var(--blue); box-shadow: 0 0 0 3px rgba(96,165,250,0.15); }
.insight-legend { margin-left: auto; display: flex; gap: 14px; text-transform: none; letter-spacing: 0; font-size: 11px; font-weight: 500; color: var(--muted); }
.insight-legend span { display: flex; align-items: center; gap: 6px; }
.insight-legend .insight-dot { margin-top: 0; }
@media (max-width: 768px) { .insight-legend { display: none; } }

/* Termos tecnicos: tooltip simples para leigos */
.hint {
  position: relative;
  display: inline-flex; align-items: center; justify-content: center;
  width: 15px; height: 15px; border-radius: 50%; background: var(--surface3);
  color: var(--muted); font-size: 10px; font-weight: 700; margin-left: 5px;
  cursor: help; vertical-align: middle; flex-shrink: 0;
}
.hint:hover, .hint:focus-visible { background: var(--blue); color: #fff; outline: none; }
.hint::after {
  content: attr(data-tip);
  position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%) translateY(4px);
  width: 220px; max-width: 60vw; background: var(--surface3); color: var(--text);
  border: 1px solid var(--border); border-radius: 8px; padding: 8px 11px;
  font-size: 12px; font-weight: 400; line-height: 1.5; text-transform: none; letter-spacing: 0.1px;
  white-space: normal; text-align: left; box-shadow: var(--shadow);
  opacity: 0; visibility: hidden; pointer-events: none; transition: opacity .15s, transform .15s;
  z-index: 30;
}
.hint::before {
  content: ""; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
  border: 5px solid transparent; border-top-color: var(--border);
  opacity: 0; visibility: hidden; transition: opacity .15s; z-index: 30;
}
.hint:hover::after, .hint:focus-visible::after { opacity: 1; visibility: visible; transform: translateX(-50%) translateY(0); }
.hint:hover::before, .hint:focus-visible::before { opacity: 1; visibility: visible; }

/* Barra de abas */
.tab-nav {
  display: flex; gap: 6px; background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 12px clamp(20px, 4vw, 64px); overflow-x: auto; position: sticky; top: 60px; z-index: 9;
}
.tab-btn {
  background: transparent; border: 1px solid transparent; color: var(--muted); font-family: var(--sans);
  font-weight: 700; font-size: 13.5px; padding: 10px 18px; cursor: pointer;
  border-radius: 10px; transition: all 0.15s ease;
  white-space: nowrap; display: flex; align-items: center; gap: 8px;
  letter-spacing: 0.3px;
}
.tab-btn .ico { font-size: 16px; filter: grayscale(1); opacity: 0.7; transition: filter 0.15s, opacity 0.15s; }
.tab-btn:hover { color: var(--text); background: var(--surface2); border-color: var(--border); }
.tab-btn:hover .ico { opacity: 1; }
.tab-btn.active {
  color: #fff; background: var(--blue); border-color: var(--blue);
  box-shadow: 0 3px 12px rgba(96,165,250,0.35);
}
.tab-btn.active .ico { filter: none; opacity: 1; }
.tab-panel { display: none; }
.tab-panel.active { display: flex; flex-direction: column; gap: 24px; }

/* Accordion da analise completa */
.analysis-toggle {
  display: flex; align-items: center; gap: 8px; background: var(--surface2);
  border: 1px solid var(--border); color: var(--muted); font-size: 12px; font-weight: 600;
  padding: 10px 16px; border-radius: 8px; cursor: pointer; width: 100%; text-align: left;
  font-family: inherit; transition: all 0.15s;
}
.analysis-toggle:hover { border-color: var(--blue); color: var(--text); }
.analysis-toggle .chev { margin-left: auto; transition: transform 0.2s; }
.analysis-toggle.open .chev { transform: rotate(180deg); }
.analysis-body { display: none; padding-top: 16px; }
.analysis-body.open { display: block; }

.color-green { color: var(--green); }
.color-red { color: var(--red); }
.color-yellow { color: var(--yellow); }
.color-blue { color: var(--blue); }
.color-muted { color: var(--muted); }

.period-btn {
  background: var(--surface2); border: 1px solid var(--border); color: var(--muted);
  font-size: 11px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; transition: all 0.15s;
}
.period-btn:hover { border-color: var(--blue); color: var(--text); }
.period-btn.active { background: var(--blue); border-color: var(--blue); color: #fff; }
.period-group { display: flex; align-items: center; gap: 4px; }
.period-caption { font-size: 11px; font-weight: 400; text-transform: none; letter-spacing: 0; color: var(--muted); margin-right: 8px; }

.spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid var(--border); border-top-color: var(--blue); border-radius: 50%; animation: spin .6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Sync badge */
.sync-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600;
  padding: 4px 10px; border-radius: 20px; border: 1px solid var(--border); background: var(--surface2); }
.sync-dot { width: 7px; height: 7px; border-radius: 50%; }
.sync-ok    { color: var(--green); }  .sync-ok .sync-dot    { background: var(--green); box-shadow: 0 0 6px var(--green); }
.sync-stale { color: var(--yellow); } .sync-stale .sync-dot { background: var(--yellow); }
.sync-fail  { color: var(--red); }    .sync-fail .sync-dot  { background: var(--red); animation: pulse 1.4s infinite; }
.sync-unknown { color: var(--muted); } .sync-unknown .sync-dot { background: var(--muted); }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

/* Banner de fallback */
.fallback-banner { display: flex; align-items: center; gap: 8px; background: rgba(251,191,36,0.12);
  border: 1px solid rgba(251,191,36,0.3); color: var(--yellow); border-radius: 8px;
  padding: 10px 14px; font-size: 12px; margin-bottom: 16px; }

/* Metas */
.goals-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.goal-item .goal-top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
.goal-item .goal-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
.goal-item .goal-val { font-size: 15px; font-weight: 800; font-family: var(--mono); }
.goal-item .goal-val small { font-size: 11px; color: var(--muted); font-weight: 500; }
.goal-bar { height: 8px; background: var(--surface3); border-radius: 6px; overflow: hidden; }
.goal-bar > div { height: 100%; border-radius: 6px; transition: width 0.5s; }
.streak-pill { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700;
  color: var(--orange); background: rgba(251,146,60,0.12); border: 1px solid rgba(251,146,60,0.3);
  padding: 4px 12px; border-radius: 20px; }
.edit-btn { background: var(--surface2); border: 1px solid var(--border); color: var(--muted);
  font-size: 11px; font-weight: 600; padding: 4px 12px; border-radius: 8px; cursor: pointer; transition: all 0.15s; }
.edit-btn:hover { border-color: var(--blue); color: var(--text); }
.goals-edit { display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-end; }
.goal-edit-row { display: flex; flex-direction: column; gap: 6px; }
.goal-edit-row label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
.goal-edit-row input { width: 130px; background: var(--surface); border: 1px solid var(--border); color: var(--text);
  border-radius: 8px; padding: 8px 12px; font-size: 14px; font-weight: 700; outline: none; font-family: inherit; }
.goal-edit-row input:focus { border-color: var(--blue); }
.goal-edit-actions { display: flex; gap: 8px; margin-left: auto; }
.save-btn { background: var(--blue); border: none; color: #fff; font-size: 12px; font-weight: 600;
  padding: 8px 18px; border-radius: 8px; cursor: pointer; }
.save-btn:hover { opacity: 0.9; }
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.cancel-btn { background: var(--surface2); border: 1px solid var(--border); color: var(--muted);
  font-size: 12px; font-weight: 600; padding: 8px 18px; border-radius: 8px; cursor: pointer; }
.cancel-btn:hover { color: var(--text); }

/* Fitness (VO2max + previsoes) */
.fitness-grid { display: flex; gap: 24px; flex-wrap: wrap; align-items: center; }
.vo2-box { text-align: center; padding: 8px 20px; border-right: 1px solid var(--border); }
.vo2-num { font-size: 40px; font-weight: 800; letter-spacing: -1px; color: var(--cyan); line-height: 1; font-family: var(--mono); }
.vo2-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-top: 6px; }
.vo2-date { font-size: 10px; color: var(--muted); margin-top: 2px; }
.predict-grid { display: flex; gap: 12px; flex-wrap: wrap; flex: 1; }
.predict-cell { flex: 1; min-width: 90px; background: var(--surface2); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px 14px; text-align: center; }
.predict-cell .pdist { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
.predict-cell .ptime { font-size: 20px; font-weight: 800; letter-spacing: -0.5px; margin-top: 4px; font-variant-numeric: tabular-nums; font-family: var(--mono); }

/* Atividade clicavel + detalhe */
tr.act-row { cursor: pointer; transition: background 0.15s; }
tr.act-row:hover { background: var(--surface2); }
tr.act-row .chevron { color: var(--muted); font-size: 10px; }
.act-detail td { background: var(--surface2); padding: 16px 18px; }
.zone-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; font-size: 12px; }
.zone-name { width: 56px; color: var(--muted); font-weight: 600; }
.zone-bar { flex: 1; height: 16px; background: var(--surface3); border-radius: 4px; overflow: hidden; }
.zone-bar > div { height: 100%; }
.zone-time { width: 64px; text-align: right; font-variant-numeric: tabular-nums; color: var(--text); }
.z1{background:#60a5fa}.z2{background:#34d399}.z3{background:#fbbf24}.z4{background:#fb923c}.z5{background:#f87171}
.splits-table { width: 100%; margin-top: 12px; border-collapse: collapse; font-size: 12px; }
.splits-table th { text-align: left; color: var(--muted); text-transform: uppercase; font-size: 10px; letter-spacing: 0.5px; padding: 4px 8px; }
.splits-table td { padding: 4px 8px; font-variant-numeric: tabular-nums; border-top: 1px solid var(--border); }

/* Movimento e polimento (efeito animata, em CSS puro) */
.card { transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease; }
.card:hover { transform: translateY(-2px); box-shadow: var(--shadow); border-color: var(--surface3); }
.trend-pill, .summary-cell, .chart-card {
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
.trend-pill:hover, .summary-cell:hover, .chart-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-sm); }

/* Entrada suave dos cards ao carregar / trocar de aba (stagger leve) */
@keyframes fadeInUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
.tab-panel.active > .card { animation: fadeInUp .45s ease both; }
.tab-panel.active > .card:nth-child(1) { animation-delay: .02s; }
.tab-panel.active > .card:nth-child(2) { animation-delay: .09s; }
.tab-panel.active > .card:nth-child(3) { animation-delay: .16s; }
.tab-panel.active > .card:nth-child(n+4) { animation-delay: .22s; }

@media (prefers-reduced-motion: reduce) {
  .card, .trend-pill, .summary-cell, .chart-card { transition: none; }
  .card:hover, .trend-pill:hover, .summary-cell:hover, .chart-card:hover { transform: none; }
  .tab-panel.active > .card { animation: none; }
}

@media (max-width: 768px) {
  .health-grid { grid-template-columns: 1fr; }
  .charts-grid { grid-template-columns: 1fr; }
  .stats-bar { flex-wrap: wrap; }
  .stat-cell { min-width: 50%; }
  .summary-row { flex-wrap: wrap; }
  .summary-cell { min-width: 45%; }
  .trend-pill { min-width: 100%; }
  main { padding: 16px; }
  /* Tabelas largas rolam horizontalmente em vez de estourar a largura */
  table { display: block; overflow-x: auto; white-space: nowrap; -webkit-overflow-scrolling: touch; }
  .splits-table { display: block; overflow-x: auto; white-space: nowrap; }
}
@media (max-width: 520px) {
  .clock { display: none; }
  .stat-cell { min-width: 100%; border-right: none; }
  .header-right { gap: 8px; }
}
</style>
</head>
<body>

<header>
  <div class="logo"><span class="logo-icon">&#9201;</span> Garmin Dashboard</div>
  <div class="header-right">
    {% set lvl = sync.level %}
    <span class="sync-badge sync-{{ lvl }}" title="{{ sync.message or '' }}">
      <span class="sync-dot"></span>
      {% if lvl == 'ok' %}Sincronizado{% if sync.age_hours is not none %} há {{ sync.age_hours }}h{% endif %}
      {% elif lvl == 'stale' %}Sync desatualizada ({{ sync.age_hours }}h)
      {% elif lvl == 'fail' %}Falha na sincronização
      {% else %}Sem sincronização{% endif %}
    </span>
    <span class="clock" id="clock"></span>
    <button class="theme-btn" id="themeBtn" onclick="toggleTheme()" title="Alternar tema">&#9790;</button>
    <button class="refresh-btn" onclick="doRefresh()">&#8635; Sincronizar</button>
    <button class="shutdown-btn" onclick="doShutdown()">&#9632; Encerrar</button>
  </div>
</header>

<div class="stats-bar">
  <div class="stat-cell">
    <div class="stat-label">Passos</div>
    <div class="stat-value color-blue">{{ '{:,}'.format(snapshot.steps).replace(',','.') if snapshot.steps else '--' }}</div>
  </div>
  <div class="stat-cell">
    <div class="stat-label">FC Repouso</div>
    <div class="stat-value">{{ snapshot.resting_hr or '--' }}<span class="stat-unit">bpm</span></div>
  </div>
  <div class="stat-cell">
    <div class="stat-label">Body Battery<span class="hint" tabindex="0" data-tip="Medidor de energia do corpo (0-100): sobe quando você descansa, cai com estresse e atividade.">?</span></div>
    <div class="stat-value {% if snapshot.bb_high and snapshot.bb_high >= 70 %}color-green{% elif snapshot.bb_high and snapshot.bb_high >= 40 %}color-yellow{% elif snapshot.bb_high %}color-red{% endif %}">{{ snapshot.bb_high or '--' }}</div>
  </div>
  <div class="stat-cell">
    <div class="stat-label">Estresse<span class="hint" tabindex="0" data-tip="Estimativa do nível de estresse do corpo (0-100) a partir dos batimentos cardíacos.">?</span></div>
    <div class="stat-value {% if snapshot.avg_stress and snapshot.avg_stress <= 25 %}color-green{% elif snapshot.avg_stress and snapshot.avg_stress <= 50 %}color-yellow{% elif snapshot.avg_stress %}color-red{% endif %}">{{ snapshot.avg_stress or '--' }}</div>
  </div>
</div>

<nav class="tab-nav">
  <button class="tab-btn active" data-tab="hoje" onclick="switchTab('hoje')"><span class="ico">&#127774;</span> Hoje</button>
  <button class="tab-btn" data-tab="tendencias" onclick="switchTab('tendencias')"><span class="ico">&#128200;</span> Tendências</button>
  <button class="tab-btn" data-tab="treino" onclick="switchTab('treino')"><span class="ico">&#127939;</span> Treino</button>
  <button class="tab-btn" data-tab="metas" onclick="switchTab('metas')"><span class="ico">&#127919;</span> Metas</button>
  <button class="tab-btn" data-tab="condicionamento" onclick="switchTab('condicionamento')"><span class="ico">&#128293;</span> Condicionamento</button>
</nav>

<main>

<!-- HOJE (DAILY DIGEST) -->
<div class="tab-panel active" id="tab-hoje">

  <!-- INSIGHTS RAPIDOS (glanceable) -->
  <div class="card">
    <div class="card-header"><span class="card-icon">&#128161;</span> INSIGHTS RÁPIDOS
      <span class="insight-legend">
        <span><span class="insight-dot s-good"></span> achado positivo</span>
        <span><span class="insight-dot s-warn"></span> pede atenção</span>
        <span><span class="insight-dot s-neutral"></span> informativo</span>
      </span>
    </div>
    <div class="card-body">
      {% if report.insights %}
      {% set names = {'Sono': 'Sono', 'Saude': 'Saúde', 'Tendencias': 'Tendências', 'Treino': 'Treino', 'Correlacoes': 'Correlações'} %}
      <div class="insights-grid">
        {% for block_name, items in report.insights.items() %}
        <div class="insight-block">
          <div class="insight-block-title"><span class="ico">{{ insight_icons.get(block_name, '💡') }}</span> {{ names.get(block_name, block_name) }}</div>
          {% for ins in items %}
          <div class="insight-item"><div class="insight-dot s-{{ ins.sentiment }}"></div><span>{{ ins.text }}</span></div>
          {% endfor %}
        </div>
        {% endfor %}
      </div>
      {% else %}
      <div style="color:var(--muted);font-style:italic;">Ainda sem insights suficientes — continue sincronizando os dados.</div>
      {% endif %}

      <button class="analysis-toggle" id="analysisToggleBtn" onclick="toggleAnalysis()" style="margin-top:18px;">
        <span>&#129302; Ver análise completa da IA</span>
        <span class="chev">&#9660;</span>
      </button>
      <div class="analysis-body" id="analysisBody">
        <div id="aiAnalysis" class="ai-analysis">
          <div style="color:var(--muted);font-size:13px;"><span class="spinner"></span> Gerando análise com IA...</div>
        </div>
        <button class="edit-btn" id="analysisRefreshBtn" onclick="loadAnalysis(true)" title="Regenerar análise com IA" style="margin-top:12px;">&#8635; Regenerar</button>
      </div>
    </div>
  </div>

  <!-- SAUDE HOJE -->
  <div class="card">
    <div class="card-header"><span class="card-icon">&#9829;</span> SAUDE HOJE <span style="margin-left:auto" class="card-date">{{ snapshot.date }}</span></div>
    <div class="card-body">
      {% if snapshot_is_fallback %}
      <div class="fallback-banner">&#9888; Dados de hoje ({{ today_date }}) ainda incompletos — exibindo o último dia completo ({{ snapshot.date }}).</div>
      {% endif %}
      <div class="daily-summary">{{ daily_summary }}</div>
      <div class="health-grid">
        <div class="health-section">
          <h4>&#9789; Sono</h4>
          {% if snapshot.sleep_hours %}
          <div style="margin-bottom:10px;font-size:20px;font-weight:800;letter-spacing:-0.5px;font-family:var(--mono);">{{ snapshot.sleep_hours }}h</div>
          {% set total_sleep = (snapshot.deep_sleep_min or 0) + (snapshot.rem_sleep_min or 0) + (snapshot.light_sleep_min or 0) + (snapshot.awake_min or 0) %}
          {% if total_sleep > 0 %}
          {% set deep_pct = (snapshot.deep_sleep_min or 0) / total_sleep * 100 %}
          {% set rem_pct = (snapshot.rem_sleep_min or 0) / total_sleep * 100 %}
          {% set light_pct = (snapshot.light_sleep_min or 0) / total_sleep * 100 %}
          {% set awake_pct = (snapshot.awake_min or 0) / total_sleep * 100 %}
          <div class="sleep-bar">
            <div class="sleep-deep" style="width:{{ deep_pct }}%">{% if deep_pct >= 8 %}{{ snapshot.deep_sleep_min }}m{% endif %}</div>
            <div class="sleep-rem" style="width:{{ rem_pct }}%">{% if rem_pct >= 8 %}{{ snapshot.rem_sleep_min }}m{% endif %}</div>
            <div class="sleep-light" style="width:{{ light_pct }}%">{% if light_pct >= 8 %}{{ snapshot.light_sleep_min }}m{% endif %}</div>
            <div class="sleep-awake" style="width:{{ awake_pct }}%">{% if awake_pct >= 8 %}{{ snapshot.awake_min }}m{% endif %}</div>
          </div>
          <div class="sleep-legend">
            <span><span class="legend-dot" style="background:var(--sleep-deep)"></span> Profundo {{ snapshot.deep_sleep_min or 0 }}m<span class="hint" tabindex="0" data-tip="Fase mais profunda do sono: o corpo repara tecidos, fortalece o sistema imune e libera hormônio do crescimento. É a fase mais restauradora fisicamente.">?</span></span>
            <span><span class="legend-dot" style="background:var(--sleep-rem)"></span> REM {{ snapshot.rem_sleep_min or 0 }}m<span class="hint" tabindex="0" data-tip="Fase dos sonhos mais vívidos. Importante para consolidar memória e processar emoções e aprendizado.">?</span></span>
            <span><span class="legend-dot" style="background:var(--sleep-light)"></span> Leve {{ snapshot.light_sleep_min or 0 }}m<span class="hint" tabindex="0" data-tip="Fase de transição entre sono profundo e REM. Mais fácil de despertar nela. Normalmente ocupa a maior parte da noite.">?</span></span>
            <span><span class="legend-dot" style="background:var(--sleep-awake)"></span> Acordado {{ snapshot.awake_min or 0 }}m<span class="hint" tabindex="0" data-tip="Minutos em que você ficou acordado durante a noite, mesmo sem lembrar depois. Quanto menor, melhor a continuidade do sono.">?</span></span>
          </div>
          {% endif %}
          {% else %}
          <div style="color:var(--muted);font-style:italic;margin-bottom:12px;">Sem dados de sono registrados</div>
          {% endif %}
        </div>
        <div class="health-section">
          <h4>&#9889; Corpo</h4>
          <div class="health-row"><span class="health-key">FC Repouso</span><span class="health-val">{{ snapshot.resting_hr or '--' }} bpm</span></div>
          <div class="health-row"><span class="health-key">FC Min / Max</span><span class="health-val">{{ snapshot.hr_min or '--' }} / {{ snapshot.hr_max or '--' }} bpm</span></div>
          <div class="health-row"><span class="health-key">Estresse medio<span class="hint" tabindex="0" data-tip="Estimativa do nível de estresse do corpo (0-100).">?</span></span><span class="health-val">{{ snapshot.avg_stress or '--' }}</span></div>
          <div class="health-row"><span class="health-key">Estresse max</span><span class="health-val">{{ snapshot.max_stress or '--' }}</span></div>
          <div class="health-row"><span class="health-key">Body Battery<span class="hint" tabindex="0" data-tip="Medidor de energia do corpo (0-100): sobe descansando, cai com estresse e atividade.">?</span></span><span class="health-val">{{ snapshot.bb_low or '--' }} &#10230; {{ snapshot.bb_high or '--' }}</span></div>
          <div class="health-row"><span class="health-key">Minutos ativos</span><span class="health-val">{{ snapshot.active_minutes or '--' }} min</span></div>
          <div class="health-row"><span class="health-key">Andares subidos</span><span class="health-val">{{ snapshot.floors or '--' }}</span></div>
          <div class="health-row"><span class="health-key">Distancia</span><span class="health-val">{{ snapshot.distance_km or '--' }} km</span></div>
          <div class="health-row"><span class="health-key">Respiracao</span><span class="health-val">{{ snapshot.avg_respiration or '--' }}{% if snapshot.avg_respiration %} rpm{% endif %}</span></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- TENDENCIAS -->
<div class="tab-panel" id="tab-tendencias">
  <div class="card">
    <div class="card-header">
      <span class="card-icon">&#9992;</span> TENDENCIAS
      <div class="period-group" style="margin-left:auto;">
        <span class="period-caption" id="trendCaption">ultimos 7 dias vs 7 anteriores</span>
        <button class="period-btn active" data-days="7" onclick="switchPeriod(7)">7 dias</button>
        <button class="period-btn" data-days="15" onclick="switchPeriod(15)">15 dias</button>
        <button class="period-btn" data-days="30" onclick="switchPeriod(30)">30 dias</button>
      </div>
    </div>
    <div class="card-body">
      <div class="trend-pills" id="trendPills">
        {% for key, t in trends.items() %}
        <div class="trend-pill">
          <div class="label">{{ t.label }}</div>
          <div class="value">{{ t.current }}{% if t.unit %}<span class="stat-unit">{{ t.unit }}</span>{% endif %}</div>
          <div class="change {{ t.sentiment }}">
            {% if t.direction == 'up' %}&#9650;{% elif t.direction == 'down' %}&#9660;{% else %}&#9644;{% endif %}
            {{ t.change_pct }}%
          </div>
          <div class="prev">anterior: {{ t.previous }}{% if t.unit %} {{ t.unit }}{% endif %}</div>
        </div>
        {% endfor %}
      </div>
      <div class="charts-grid" id="chartsGrid">
        <div class="chart-card">
          <h5>&#128694; Passos Diarios</h5>
          <div class="chart-container"><canvas id="stepsChart"></canvas></div>
          <div class="chart-subtitle">Meta recomendada: 8.000+ passos/dia</div>
        </div>
        <div class="chart-card">
          <h5>&#10084; FC em Repouso</h5>
          <div class="chart-container"><canvas id="hrChart"></canvas></div>
          <div class="chart-subtitle">Valores menores indicam melhor condicionamento</div>
        </div>
        <div class="chart-card">
          <h5>&#9889; Body Battery</h5>
          <div class="chart-container"><canvas id="bbChart"></canvas></div>
          <div class="chart-subtitle">70+ alta | 40-69 moderada | &lt;40 baixa</div>
        </div>
        <div class="chart-card">
          <h5>&#128168; Estresse Medio</h5>
          <div class="chart-container"><canvas id="stressChart"></canvas></div>
          <div class="chart-subtitle">0-25 baixo | 26-50 medio | 51+ alto</div>
        </div>
        <div class="chart-card" style="grid-column: 1 / -1;">
          <h5>&#9789; Sono — Fases por Dia</h5>
          <div class="chart-container"><canvas id="sleepChart"></canvas></div>
          <div class="sleep-legend" style="margin-top:10px;">
            <span><span class="legend-dot" style="background:var(--sleep-deep)"></span> Profundo<span class="hint" tabindex="0" data-tip="Fase mais profunda do sono: o corpo repara tecidos, fortalece o sistema imune e libera hormônio do crescimento. É a fase mais restauradora fisicamente.">?</span></span>
            <span><span class="legend-dot" style="background:var(--sleep-rem)"></span> REM<span class="hint" tabindex="0" data-tip="Fase dos sonhos mais vívidos. Importante para consolidar memória e processar emoções e aprendizado.">?</span></span>
            <span><span class="legend-dot" style="background:var(--sleep-light)"></span> Leve<span class="hint" tabindex="0" data-tip="Fase de transição entre sono profundo e REM. Mais fácil de despertar nela. Normalmente ocupa a maior parte da noite.">?</span></span>
            <span><span class="legend-dot" style="background:var(--sleep-awake)"></span> Acordado<span class="hint" tabindex="0" data-tip="Minutos em que você ficou acordado durante a noite, mesmo sem lembrar depois. Quanto menor, melhor a continuidade do sono.">?</span></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- TREINO -->
<div class="tab-panel" id="tab-treino">
  <div class="card">
    <div class="card-header">
      <span class="card-icon">&#127939;</span> RELATORIO DE TREINO
      <div class="period-group" style="margin-left:auto;">
        <button class="period-btn active" data-days="7" onclick="switchPeriod(7)">7 dias</button>
        <button class="period-btn" data-days="15" onclick="switchPeriod(15)">15 dias</button>
        <button class="period-btn" data-days="30" onclick="switchPeriod(30)">30 dias</button>
      </div>
    </div>
    <div class="card-body" id="reportBody">
      <div style="text-align:center;padding:40px;color:var(--muted);"><span class="spinner"></span> Carregando...</div>
    </div>
  </div>
</div>

<!-- METAS -->
<div class="tab-panel" id="tab-metas">
  <div class="card">
    <div class="card-header">
      <span class="card-icon">&#127919;</span> METAS DA SEMANA
      <div style="margin-left:auto;display:flex;align-items:center;gap:10px;">
        {% if streak > 0 %}<span class="streak-pill">&#128293; {{ streak }} {{ 'dia' if streak == 1 else 'dias' }} batendo a meta de passos</span>{% endif %}
        <button class="edit-btn" id="goalsEditBtn" onclick="toggleGoalsEdit()" title="Editar metas">&#9881; Editar</button>
      </div>
    </div>
    <div class="card-body">
      <div class="goals-grid" id="goalsView">
        {% for g in goals %}
        <div class="goal-item">
          <div class="goal-top">
            <span class="goal-label">{{ g.label }}</span>
            <span class="goal-val">{{ '{:,}'.format(g.value).replace(',','.') }}{% if g.unit %} {{ g.unit }}{% endif %}<small> / {{ '{:,}'.format(g.goal).replace(',','.') }}</small></span>
          </div>
          <div class="goal-bar"><div style="width:{{ g.pct }}%;background:{{ g.color }}"></div></div>
        </div>
        {% endfor %}
      </div>
      <div class="goals-edit" id="goalsEdit" style="display:none;">
        {% for g in goals %}
        <div class="goal-edit-row">
          <label for="goalinput_{{ g.key }}">{{ g.label }}{% if g.unit %} ({{ g.unit }}){% endif %}</label>
          <input type="number" min="1" step="{{ '0.5' if g.key == 'km_week' else '100' if g.key == 'steps_day' else '10' }}" id="goalinput_{{ g.key }}" value="{{ g.goal }}">
        </div>
        {% endfor %}
        <div class="goal-edit-actions">
          <button class="save-btn" id="goalsSaveBtn" onclick="saveGoals()">Salvar</button>
          <button class="cancel-btn" onclick="toggleGoalsEdit()">Cancelar</button>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- CONDICIONAMENTO: VO2MAX + PREVISOES -->
<div class="tab-panel" id="tab-condicionamento">
  {% if fitness.vo2max or fitness.predictions.values()|select|list %}
  <div class="card">
    <div class="card-header"><span class="card-icon">&#128293;</span> CONDICIONAMENTO &amp; PREVISÕES DE CORRIDA</div>
    <div class="card-body">
      <div class="fitness-grid">
        {% if fitness.vo2max %}
        <div class="vo2-box">
          <div class="vo2-num">{{ fitness.vo2max }}</div>
          <div class="vo2-label">VO₂max<span class="hint" tabindex="0" data-tip="Capacidade aeróbica estimada: quanto maior, mais eficiente seu corpo usa oxigênio ao se exercitar.">?</span></div>
          <div class="vo2-date">{{ fitness.vo2max_date }}</div>
        </div>
        {% endif %}
        <div class="predict-grid">
          <div class="predict-cell"><div class="pdist">5K</div><div class="ptime">{{ fitness.predictions['5k'] | hms }}</div></div>
          <div class="predict-cell"><div class="pdist">10K</div><div class="ptime">{{ fitness.predictions['10k'] | hms }}</div></div>
          <div class="predict-cell"><div class="pdist">Meia</div><div class="ptime">{{ fitness.predictions['half'] | hms }}</div></div>
          <div class="predict-cell"><div class="pdist">Maratona</div><div class="ptime">{{ fitness.predictions['marathon'] | hms }}</div></div>
        </div>
      </div>
    </div>
  </div>
  {% else %}
  <div class="card"><div class="card-body" style="color:var(--muted);font-style:italic;">Ainda sem dados de condicionamento suficientes.</div></div>
  {% endif %}
</div>

</main>

<script>
// Tema dark/light (persistido em localStorage)
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const btn = document.getElementById('themeBtn');
  if (btn) btn.innerHTML = theme === 'light' ? '&#9728;' : '&#9790;';
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  const next = cur === 'light' ? 'dark' : 'light';
  localStorage.setItem('garmin-theme', next);
  applyTheme(next);
  // Chart.js nao herda as variaveis CSS: redesenha com as cores do novo tema
  if (typeof renderCharts === 'function' && currentDailyData) renderCharts(currentDailyData);
}
applyTheme(localStorage.getItem('garmin-theme') || 'dark');

// Abas
const TAB_KEY = 'garmin-tab';
let tendenciasVisited = false;
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
  localStorage.setItem(TAB_KEY, name);
  if (name === 'tendencias') {
    // Chart.js precisa do canvas visivel para calcular o tamanho corretamente
    requestAnimationFrame(() => renderCharts(currentDailyData));
  }
}
(function restoreTab() {
  const saved = localStorage.getItem(TAB_KEY);
  if (saved && document.getElementById('tab-' + saved)) switchTab(saved);
})();

// Analise IA colapsavel
function toggleAnalysis() {
  const btn = document.getElementById('analysisToggleBtn');
  const body = document.getElementById('analysisBody');
  const opening = !body.classList.contains('open');
  body.classList.toggle('open', opening);
  btn.classList.toggle('open', opening);
}

// Edicao de metas
function toggleGoalsEdit() {
  const view = document.getElementById('goalsView');
  const edit = document.getElementById('goalsEdit');
  const showing = edit.style.display !== 'none';
  edit.style.display = showing ? 'none' : 'flex';
  view.style.display = showing ? 'grid' : 'none';
  document.getElementById('goalsEditBtn').style.display = showing ? '' : 'none';
}
async function saveGoals() {
  const btn = document.getElementById('goalsSaveBtn');
  const body = {};
  ['steps_day', 'km_week', 'active_min_week'].forEach(k => {
    const el = document.getElementById('goalinput_' + k);
    if (el && el.value) body[k] = parseFloat(el.value);
  });
  btn.disabled = true; btn.textContent = 'Salvando...';
  try {
    const res = await fetch('/api/goals', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    });
    if (res.ok) { location.reload(); return; }
    throw new Error('falha');
  } catch(e) {
    btn.disabled = false; btn.textContent = 'Erro — tentar de novo';
  }
}

// Analise por IA
function renderMarkdown(md) {
  const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const inline = s => esc(s).replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
  const lines = md.split('\\n');
  let html = '', inList = false;
  const closeList = () => { if (inList) { html += '</ul>'; inList = false; } };
  let para = [];
  const flushPara = () => { if (para.length) { html += '<p>' + inline(para.join(' ')) + '</p>'; para = []; } };
  for (let raw of lines) {
    const line = raw.trim();
    if (!line) { flushPara(); closeList(); continue; }
    const h = line.match(/^#{1,6}\\s+(.*)/);
    if (h) { flushPara(); closeList(); html += '<h3>' + inline(h[1]) + '</h3>'; continue; }
    const b = line.match(/^[-*]\\s+(.*)/);
    if (b) { flushPara(); if (!inList) { html += '<ul>'; inList = true; } html += '<li>' + inline(b[1]) + '</li>'; continue; }
    para.push(line);
  }
  flushPara(); closeList();
  return html || '<p>' + inline(md) + '</p>';
}

async function loadAnalysis(force) {
  const el = document.getElementById('aiAnalysis');
  const btn = document.getElementById('analysisRefreshBtn');
  el.innerHTML = '<div style="color:var(--muted);font-size:13px;"><span class="spinner"></span> Gerando análise com IA' + (force ? ' (atualizando)' : '') + '...</div>';
  if (btn) btn.disabled = true;
  try {
    const res = await fetch('/api/analysis' + (force ? '?force=1' : ''));
    const data = await res.json();
    if (data.ok && data.text) {
      el.innerHTML = renderMarkdown(data.text);
    } else {
      el.innerHTML = '<div style="color:var(--muted);font-size:13px;">Análise indisponível: ' + (data.error || 'sem resposta') + '</div>';
    }
  } catch(e) {
    el.innerHTML = '<div style="color:var(--red);font-size:13px;">Erro ao gerar a análise.</div>';
  }
  if (btn) btn.disabled = false;
}

function updateClock() {
  document.getElementById('clock').textContent = new Date().toLocaleString('pt-BR');
}
setInterval(updateClock, 1000);
updateClock();

async function doRefresh() {
  const btn = document.querySelector('.refresh-btn');
  btn.innerHTML = '<span class="spinner"></span>';
  btn.disabled = true;
  try {
    await fetch('/refresh', {method: 'POST'});
    location.reload();
  } catch(e) {
    btn.textContent = 'Erro';
    setTimeout(() => { btn.textContent = 'Refresh'; btn.disabled = false; }, 2000);
  }
}

async function doShutdown() {
  if (!confirm('Encerrar o Garmin Dashboard?')) return;
  try { await fetch('/shutdown', {method: 'POST'}); } catch(e) {}
  document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;color:#7d8a9a;font-family:system-ui;font-size:16px;">Dashboard encerrado.</div>';
}

// Contadores animados (efeito animata, em JS puro)
// Anima .stat-value (stats-bar, milhar pt-BR "1.234") e .trend-pill .value
// (float do Python "7614.3"); preserva unidade em <span class="stat-unit"> e
// respeita prefers-reduced-motion.
function prefersReducedMotion() {
  return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
function parseCounter(el) {
  const unitEl = el.querySelector('.stat-unit');
  const unitHTML = unitEl ? unitEl.outerHTML : '';
  const clone = el.cloneNode(true);
  const u = clone.querySelector('.stat-unit');
  if (u) u.remove();
  const raw = clone.textContent.trim();
  if (!raw || raw === '--') return null;
  // "1.234" / "12.345" => ponto de milhar pt-BR (inteiro)
  if (/^\\d{1,3}(\\.\\d{3})+$/.test(raw)) {
    return { target: parseInt(raw.replace(/\\./g, ''), 10), decimals: 0, useThousands: true, unitHTML };
  }
  // "85", "52.0", "7614.3" => numero simples com ponto decimal
  const num = parseFloat(raw);
  if (!isFinite(num)) return null;
  const dot = raw.indexOf('.');
  const decimals = dot >= 0 ? raw.length - dot - 1 : 0;
  return { target: num, decimals, useThousands: false, unitHTML };
}
function animateCounter(el, cfg) {
  const dur = 900;
  const start = performance.now();
  const easeOutQuart = t => 1 - Math.pow(1 - t, 4);
  const fmt = v => (cfg.useThousands ? Math.round(v).toLocaleString('pt-BR') : v.toFixed(cfg.decimals)) + cfg.unitHTML;
  function frame(now) {
    const p = Math.min((now - start) / dur, 1);
    el.innerHTML = fmt(cfg.target * easeOutQuart(p));
    if (p < 1) requestAnimationFrame(frame);
    else el.innerHTML = fmt(cfg.target);
  }
  requestAnimationFrame(frame);
}
function initCounters(root) {
  if (prefersReducedMotion()) return; // valores ja renderizados pelo servidor
  const scope = root || document;
  scope.querySelectorAll('.stat-value, .trend-pill .value').forEach(el => {
    if (el.dataset.counted) return;
    const cfg = parseCounter(el);
    if (!cfg) return;
    el.dataset.counted = '1';
    animateCounter(el, cfg);
  });
}

// Chart data — re-renderizavel conforme o filtro de dias
const chartInstances = {};

// Le uma variavel de tema do :root (ex.: '--text'), com fallback
function themeColor(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}
// hex (#rgb / #rrggbb) -> rgba(...,alpha); repassa outros formatos inalterados
function withAlpha(color, alpha) {
  const c = (color || '').trim();
  const m = c.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (!m) return c;
  let h = m[1];
  if (h.length === 3) h = h.split('').map(x => x + x).join('');
  const r = parseInt(h.slice(0,2),16), g = parseInt(h.slice(2,4),16), b = parseInt(h.slice(4,6),16);
  return `rgba(${r},${g},${b},${alpha})`;
}
// Montado a cada render para acompanhar o tema atual (dark/light)
function chartDefaults() {
  const text    = themeColor('--text', '#e4e8ee');
  const muted   = themeColor('--muted', '#98a3b3');
  const surface = themeColor('--surface', '#1a1f27');
  const border  = themeColor('--border', '#343d4a');
  const grid    = withAlpha(muted, 0.15);
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: 'index' },
    animation: { duration: 900, easing: 'easeOutQuart' },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: surface,
        borderColor: border,
        borderWidth: 1,
        titleColor: text,
        bodyColor: text,
        padding: 10,
        cornerRadius: 6,
      },
    },
    scales: {
      x: { ticks: { color: muted, font: { size: 10 } }, grid: { color: grid } },
      y: { ticks: { color: muted, font: { size: 10 } }, grid: { color: grid } },
    },
  };
}

function makeChart(id, label, data, color, opts, labels) {
  const filtered = data.map(v => (v === null || v === undefined || v <= 0) ? null : v);
  const ctx = document.getElementById(id);
  const cfg = chartDefaults();
  if (opts) {
    if (opts.suggestedMin !== undefined) cfg.scales.y.suggestedMin = opts.suggestedMin;
    if (opts.suggestedMax !== undefined) cfg.scales.y.suggestedMax = opts.suggestedMax;
  }
  cfg.plugins.tooltip.callbacks = {
    label: function(ctx) {
      const v = ctx.parsed.y;
      if (v === null) return label + ': sem dados';
      const suffix = opts && opts.unit ? ' ' + opts.unit : '';
      return label + ': ' + v.toLocaleString('pt-BR') + suffix;
    }
  };
  if (chartInstances[id]) chartInstances[id].destroy();
  chartInstances[id] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: label,
        data: filtered,
        borderColor: color,
        backgroundColor: color.replace(')', ',0.08)').replace('rgb', 'rgba'),
        fill: true,
        tension: 0.3,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: color,
        pointBorderColor: themeColor('--surface', '#161b22'),
        pointBorderWidth: 2,
        spanGaps: true,
      }]
    },
    options: cfg,
  });
}

function makeSleepChart(dailyData, labels) {
  const reversed = [...dailyData].reverse();
  const ctx = document.getElementById('sleepChart');
  const cfg = chartDefaults();
  cfg.scales.x.stacked = true;
  cfg.scales.y.stacked = true;
  cfg.scales.y.suggestedMax = 540;
  cfg.scales.y.ticks.callback = function(v) { return Math.floor(v/60) + 'h'; };
  cfg.plugins.tooltip.callbacks = {
    label: function(ctx) {
      const v = ctx.parsed.y;
      if (v === null || v === 0) return null;
      const h = Math.floor(v/60);
      const m = v % 60;
      return ctx.dataset.label + ': ' + (h > 0 ? h + 'h ' : '') + m + 'min';
    },
    footer: function(items) {
      const total = items.reduce((s, i) => s + (i.parsed.y || 0), 0);
      const h = Math.floor(total/60);
      const m = total % 60;
      return 'Total: ' + h + 'h ' + m + 'min';
    }
  };
  if (chartInstances['sleepChart']) chartInstances['sleepChart'].destroy();
  chartInstances['sleepChart'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        { label: 'Profundo', data: reversed.map(d => d.deep_sleep_min || 0), backgroundColor: 'rgba(79,70,229,0.85)', borderRadius: 2 },
        { label: 'REM', data: reversed.map(d => d.rem_sleep_min || 0), backgroundColor: 'rgba(217,70,239,0.85)', borderRadius: 2 },
        { label: 'Leve', data: reversed.map(d => d.light_sleep_min || 0), backgroundColor: 'rgba(34,211,238,0.85)', borderRadius: 2 },
        { label: 'Acordado', data: reversed.map(d => d.awake_min || 0), backgroundColor: 'rgba(248,113,113,0.85)', borderRadius: 2 },
      ]
    },
    options: cfg,
  });
}

// Re-renderiza todos os graficos para o periodo selecionado
function renderCharts(dailyData) {
  if (!dailyData || !dailyData.length) return;
  const labels = dailyData.map(d => { const p = d.date.split('-'); return p[2] + '/' + p[1]; }).reverse();
  makeChart('stepsChart', 'Passos', dailyData.map(d => d.steps).reverse(), 'rgb(88,166,255)', { suggestedMin: 0, unit: 'passos' }, labels);
  makeChart('hrChart', 'FC Repouso', dailyData.map(d => d.resting_hr).reverse(), 'rgb(248,81,73)', { suggestedMin: 40, suggestedMax: 80, unit: 'bpm' }, labels);
  makeChart('bbChart', 'Body Battery', dailyData.map(d => d.bb_high).reverse(), 'rgb(63,185,80)', { suggestedMin: 0, suggestedMax: 100, unit: '' }, labels);
  makeChart('stressChart', 'Estresse', dailyData.map(d => d.avg_stress).reverse(), 'rgb(210,153,34)', { suggestedMin: 0, suggestedMax: 100, unit: '' }, labels);
  makeSleepChart(dailyData, labels);
}

// Dados do periodo atual, guardados para re-renderizar os graficos ao trocar de aba
let currentDailyData = {{ daily_data | tojson }};

// Paint inicial (dados injetados pelo servidor); switchPeriod re-renderiza ao trocar o filtro
renderCharts(currentDailyData);
initCounters();

// Period toggle (controla Tendencias + Treino juntos)
let currentPeriod = 7;
let periodRequestSeq = 0;
async function switchPeriod(days) {
  currentPeriod = days;
  const seq = ++periodRequestSeq;
  document.querySelectorAll('.period-btn').forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.days) === days);
  });
  const caption = document.getElementById('trendCaption');
  if (caption) caption.textContent = 'ultimos ' + days + ' dias vs ' + days + ' anteriores';
  const body = document.getElementById('reportBody');
  const pills = document.getElementById('trendPills');
  const chartsGrid = document.getElementById('chartsGrid');
  body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--muted);"><span class="spinner"></span> Carregando...</div>';
  pills.style.opacity = '0.4';
  if (chartsGrid) chartsGrid.style.opacity = '0.35';
  const wait = ms => new Promise(r => setTimeout(r, ms));
  try {
    // espera minima p/ o esmaecimento ficar visivel mesmo com cache local (resposta quase instantanea)
    const [res] = await Promise.all([fetch('/api/report?days=' + days), wait(400)]);
    const data = await res.json();
    if (seq !== periodRequestSeq) return; // resposta antiga de um clique anterior — descarta
    currentDailyData = data.daily;
    renderTrends(data.trends);
    renderReport(data.report, data.days);
    // opacidade volta antes do redraw dos graficos, para as barras/linhas
    // "subirem" suavemente enquanto o Chart.js anima a entrada dos novos dados
    pills.style.opacity = '1';
    if (chartsGrid) chartsGrid.style.opacity = '1';
    renderCharts(currentDailyData);
  } catch(e) {
    if (seq !== periodRequestSeq) return;
    body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--red);">Erro ao carregar dados</div>';
    pills.style.opacity = '1';
    if (chartsGrid) chartsGrid.style.opacity = '1';
  }
}

function renderTrends(trends) {
  if (!trends) return;
  const arrow = d => d === 'up' ? '▲' : d === 'down' ? '▼' : '▬';
  let html = '';
  Object.values(trends).forEach(t => {
    const unit = t.unit ? '<span class="stat-unit">' + t.unit + '</span>' : '';
    const unitPrev = t.unit ? ' ' + t.unit : '';
    html += `
      <div class="trend-pill">
        <div class="label">${t.label}</div>
        <div class="value">${t.current}${unit}</div>
        <div class="change ${t.sentiment}">${arrow(t.direction)} ${t.change_pct}%</div>
        <div class="prev">anterior: ${t.previous}${unitPrev}</div>
      </div>`;
  });
  const pills = document.getElementById('trendPills');
  pills.innerHTML = html;
  initCounters(pills); // reanima os valores recem-criados
}

function renderReport(r, days) {
  const s = r.summary || {};
  const fmt = n => (n || 0).toLocaleString('pt-BR');
  let html = `
    <div class="summary-row">
      <div class="summary-cell"><div class="num">${s.total_activities || 0}</div><div class="lbl">Atividades</div></div>
      <div class="summary-cell"><div class="num">${s.total_km || 0}</div><div class="lbl">Km totais</div></div>
      <div class="summary-cell"><div class="num">${s.total_hours || 0}</div><div class="lbl">Horas</div></div>
      <div class="summary-cell"><div class="num">${fmt(s.total_calories)}</div><div class="lbl">Calorias</div></div>
    </div>`;

  if (r.by_type && r.by_type.length) {
    html += '<div class="section-title">Por tipo de atividade</div><table><thead><tr><th>Tipo</th><th>Qtd</th><th>Distancia</th><th>FC media</th><th>Duracao</th></tr></thead><tbody>';
    r.by_type.forEach(t => {
      html += `<tr><td style="font-weight:600">${t.label}</td><td>${t.count}x</td><td>${t.distance_km} km</td><td>${t.avg_hr || '--'}<span class="stat-unit">bpm</span></td><td>${t.duration_min} min</td></tr>`;
    });
    html += '</tbody></table>';
  }

  if (r.recent && r.recent.length) {
    html += '<div class="section-title" style="margin-top:24px">Atividades recentes <span style="font-weight:400;text-transform:none;letter-spacing:0;color:var(--muted)">— clique para ver zonas de FC e splits</span></div><table><thead><tr><th>Data</th><th>Nome</th><th>Dist</th><th>Duracao</th><th>FC med</th><th>Cal</th><th></th></tr></thead><tbody>';
    r.recent.forEach(a => {
      const clickable = a.id ? `class="act-row" onclick="toggleActivity(${a.id}, this)"` : '';
      const chev = a.id ? '<span class="chevron">▼</span>' : '';
      html += `<tr ${clickable}><td>${a.date.slice(5)}</td><td style="font-weight:600">${a.name || a.type}</td><td>${a.distance_km} km</td><td>${Math.round(a.duration_min)} min</td><td>${a.avg_hr || '--'}<span class="stat-unit">bpm</span></td><td>${a.calories || '--'}</td><td>${chev}</td></tr>`;
    });
    html += '</tbody></table>';
  }

  document.getElementById('reportBody').innerHTML = html;
}

const ZONE_NAMES = ['Z1', 'Z2', 'Z3', 'Z4', 'Z5'];
const ZONE_TIPS = [
  'Recuperação ativa — intensidade muito leve, ajuda o corpo a se recuperar entre treinos.',
  'Base aeróbica — ritmo leve e sustentável, melhora a resistência usando gordura como combustível principal.',
  'Aeróbico moderado — intensidade moderada, melhora a eficiência cardiovascular.',
  'Limiar anaeróbico — intensidade alta, o corpo passa a acumular lactato; melhora a tolerância ao esforço intenso.',
  'Esforço máximo — intensidade próxima do limite, usada em picos curtos de velocidade ou potência.',
];
const activityCache = {};

function fmtSecs(s) {
  if (!s) return '--';
  s = Math.round(s);
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = s%60;
  return h ? `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}` : `${m}:${String(sec).padStart(2,'0')}`;
}
function paceFromSpeed(speed) {
  if (!speed || speed <= 0) return '--';
  const spk = 1000/speed, m = Math.floor(spk/60), s = Math.round(spk%60);
  return `${m}:${String(s).padStart(2,'0')}/km`;
}

async function toggleActivity(id, rowEl) {
  const existing = rowEl.nextElementSibling;
  if (existing && existing.classList.contains('act-detail')) {
    existing.remove();
    rowEl.querySelector('.chevron').textContent = '▼';
    return;
  }
  rowEl.querySelector('.chevron').textContent = '▲';
  const detail = document.createElement('tr');
  detail.className = 'act-detail';
  const td = document.createElement('td');
  td.colSpan = 7;
  td.innerHTML = '<div style="color:var(--muted);font-size:12px;"><span class="spinner"></span> Carregando detalhe...</div>';
  detail.appendChild(td);
  rowEl.after(detail);
  try {
    const data = activityCache[id] || await (await fetch('/api/activity/' + id)).json();
    activityCache[id] = data;
    td.innerHTML = renderActivityDetail(data);
  } catch(e) {
    td.innerHTML = '<div style="color:var(--red);font-size:12px;">Erro ao carregar detalhe</div>';
  }
}

function renderActivityDetail(data) {
  let html = '';
  const zones = (data.hr_zones || []).filter(z => z.secs > 0);
  if (zones.length) {
    const maxSecs = Math.max(...zones.map(z => z.secs));
    html += '<div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;font-weight:600;margin-bottom:8px;">Zonas de frequência cardíaca</div>';
    zones.forEach(z => {
      const w = maxSecs ? (z.secs/maxSecs*100) : 0;
      html += `<div class="zone-row"><span class="zone-name">${ZONE_NAMES[z.zone-1]||('Z'+z.zone)} <span style="color:var(--muted)">${z.low||''}</span></span><span class="hint" tabindex="0" data-tip="${ZONE_TIPS[z.zone-1]||''}">?</span><span class="zone-bar"><div class="z${z.zone}" style="width:${w}%"></div></span><span class="zone-time">${fmtSecs(z.secs)}</span></div>`;
    });
  }
  const splits = data.splits || [];
  if (splits.length) {
    html += '<table class="splits-table"><thead><tr><th>Km</th><th>Tempo</th><th>Pace</th><th>FC</th><th>Cad</th><th>Elev</th></tr></thead><tbody>';
    splits.forEach((s, i) => {
      html += `<tr><td>${i+1}</td><td>${fmtSecs(s.duration_s)}</td><td>${paceFromSpeed(s.speed)}</td><td>${s.avg_hr ? Math.round(s.avg_hr) : '--'}</td><td>${s.cadence || '--'}</td><td>${s.elev_gain != null ? s.elev_gain+'m' : '--'}</td></tr>`;
    });
    html += '</tbody></table>';
  }
  return html || '<div style="color:var(--muted);font-size:12px;">Sem dados de zonas/splits para esta atividade.</div>';
}

// Load default period + analise de IA on page load
switchPeriod(7);
loadAnalysis(false);
</script>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Analise por IA (Gemini API)
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

ANALYSIS_INSTRUCTIONS = """Voce e um treinador e analista de saude/performance. Analise os dados do Garmin do usuario (Igor) e escreva uma analise COMPLETA e PERSONALIZADA em portugues do Brasil.

Regras de formato (markdown):
- Use 3 a 4 secoes curtas com titulo em '## Titulo'.
- Sugestao de secoes: '## Visao geral', '## Sono e recuperacao', '## Treino e condicionamento', '## Recomendacoes'.
- Escreva em PARAGRAFOS analiticos (NAO apenas bullets soltos). Pode usar no maximo alguns bullets dentro das recomendacoes.
- Cite NUMEROS concretos dos dados (passos, FC repouso, sono, VO2max, km, tendencias) e INTERPRETE o que significam.
- Seja direto e acionavel. Maximo ~320 palavras no total. Nao invente dados que nao estao no contexto.
"""


def _build_analysis_context():
    daily_data = fetch_multi_day(14)
    activities = fetch_activities()
    snapshot, _ = pick_display_snapshot(daily_data)
    trends = compute_trends(daily_data)
    report = generate_training_report(activities, daily_data)
    fitness = fetch_fitness()
    summary = generate_daily_summary(snapshot)
    compact = [
        {k: d.get(k) for k in ("date", "steps", "resting_hr", "avg_stress", "bb_high", "sleep_hours", "sleep_score")}
        for d in daily_data
    ]
    return f"""## Dia mais recente ({snapshot.get('date', 'N/A')})
{summary}
Snapshot: {json.dumps(snapshot, ensure_ascii=False, default=str)}

## Tendencias (7 dias vs 7 anteriores)
{json.dumps(trends, ensure_ascii=False, default=str)}

## Condicionamento
VO2max: {fitness.get('vo2max')} ({fitness.get('vo2max_date')}) | Previsoes (s): {json.dumps(fitness.get('predictions', {}), ensure_ascii=False)}

## Relatorio de treino
Resumo: {json.dumps(report.get('summary', {}), ensure_ascii=False)}
Por tipo: {json.dumps(report.get('by_type', []), ensure_ascii=False)}
Insights regrados: {json.dumps(report.get('insights', {}), ensure_ascii=False)}

## Ultimas atividades
{json.dumps(report.get('recent', [])[:8], ensure_ascii=False, default=str)}

## Serie diaria (14 dias, [0] = mais recente)
{json.dumps(compact, ensure_ascii=False)}
"""


def generate_ai_analysis(force=False):
    cache_file = CACHE_DIR / "ai_analysis.json"
    if not force and cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 3 * 3600:
            try:
                return json.loads(cache_file.read_text())
            except Exception:
                pass
    if not GEMINI_API_KEY:
        return {
            "ok": False,
            "error": "GEMINI_API_KEY nao configurada no .env. Gere uma gratis em https://aistudio.google.com/apikey",
        }
    prompt = ANALYSIS_INSTRUCTIONS + "\n\n# DADOS\n" + _build_analysis_context()
    try:
        resp = requests.post(
            GEMINI_URL,
            headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "Timeout — a analise demorou demais"}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"Erro de conexao com o Gemini: {e}"[:300]}

    if resp.status_code != 200:
        try:
            msg = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            msg = resp.text
        return {"ok": False, "error": f"Gemini {resp.status_code}: {msg}"[:300]}

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        reason = data.get("promptFeedback", {}).get("blockReason", "sem candidatos na resposta")
        return {"ok": False, "error": f"Gemini nao retornou texto ({reason})"}
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        return {"ok": False, "error": "Gemini retornou resposta vazia"}

    out = {"ok": True, "text": text, "generated_at": time.time()}
    cache_file.write_text(json.dumps(out))
    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/api/analysis")
def api_analysis():
    force = bool(request.args.get("force"))
    return jsonify(generate_ai_analysis(force=force))


@app.route("/legacy")
def index():
    daily_data = fetch_multi_day(14)
    activities = fetch_activities()
    snapshot, snapshot_is_fallback = pick_display_snapshot(daily_data)
    today_date = (daily_data[0] or {}).get("date") if daily_data else date.today().isoformat()
    trends = compute_trends(daily_data)
    report = generate_training_report(activities, daily_data)
    daily_summary = generate_daily_summary(snapshot)
    return render_template_string(
        HTML,
        snapshot=snapshot,
        snapshot_is_fallback=snapshot_is_fallback,
        today_date=today_date,
        trends=trends,
        report=report,
        daily_data=daily_data,
        daily_summary=daily_summary,
        fitness=fetch_fitness(),
        goals=compute_goals(daily_data, activities),
        streak=compute_streak(daily_data),
        sync=read_sync_status(),
        insight_icons=INSIGHT_ICONS,
    )


@app.route("/api/state")
def api_state():
    daily_data = fetch_multi_day(14)
    activities = fetch_activities()
    snapshot, snapshot_is_fallback = pick_display_snapshot(daily_data)
    today_date = (daily_data[0] or {}).get("date") if daily_data else date.today().isoformat()
    trends = compute_trends(daily_data)
    report = generate_training_report(activities, daily_data)
    daily_summary = generate_daily_summary(snapshot)
    return jsonify(
        snapshot=snapshot,
        snapshot_is_fallback=snapshot_is_fallback,
        today_date=today_date,
        trends=trends,
        report=report,
        daily_data=daily_data,
        daily_summary=daily_summary,
        fitness=fetch_fitness(),
        goals=compute_goals(daily_data, activities),
        streak=compute_streak(daily_data),
        sync=read_sync_status(),
    )


@app.route("/api/activity/<int:activity_id>")
def api_activity(activity_id):
    return jsonify(fetch_activity_detail(activity_id))


@app.route("/api/goals", methods=["GET", "POST"])
def api_goals():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        new = {}
        for k in DEFAULT_GOALS:
            try:
                if data.get(k) is not None:
                    new[k] = float(data[k])
            except (TypeError, ValueError):
                pass
        saved = save_goals(new)
        return jsonify(ok=True, goals=saved)
    return jsonify(load_goals())


@app.route("/api/data")
def api_data():
    daily_data = fetch_multi_day(14)
    snapshot = daily_data[0] if daily_data else {}
    activities = fetch_activities()
    trends = compute_trends(daily_data)
    report = generate_training_report(activities, daily_data)
    return jsonify(snapshot=snapshot, trends=trends, report=report, daily_data=daily_data)


@app.route("/api/report")
def api_report():
    days = request.args.get("days", 30, type=int)
    all_activities = fetch_activities()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    filtered = [a for a in all_activities if a["date"] >= cutoff]
    daily_data = fetch_multi_day(2 * days)
    report = generate_training_report(filtered, daily_data)
    trends = compute_trends(daily_data, days)
    return jsonify(report=report, trends=trends, daily=daily_data[:days], days=days)


@app.route("/shutdown", methods=["POST"])
def shutdown():
    import signal
    os.kill(os.getpid(), signal.SIGTERM)
    return jsonify(ok=True)


@app.route("/refresh", methods=["POST"])
def refresh():
    global _client
    _client = None
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
    try:
        fetch_multi_day(14)
        fetch_activities()
        fetch_fitness()
        write_sync_status(True, "Sincronizado pelo dashboard", "refresh")
        return jsonify(ok=True)
    except Exception as e:
        write_sync_status(False, str(e)[:200], "refresh")
        return jsonify(ok=False, error=str(e)[:200]), 500


@app.route("/")
def spa_index():
    return send_from_directory(SPA_DIST, "index.html")


@app.route("/assets/<path:filename>")
def spa_assets(filename):
    return send_from_directory(SPA_DIST / "assets", filename)


@app.route("/favicon.svg")
def spa_favicon():
    return send_from_directory(SPA_DIST, "favicon.svg")


@app.route("/icons.svg")
def spa_icons():
    return send_from_directory(SPA_DIST, "icons.svg")


@app.route("/app")
@app.route("/app/")
def spa_app_redirect():
    # Compat: bookmarks antigos de /app (slice 4) continuam levando pra SPA em "/".
    return redirect("/")


if __name__ == "__main__":
    print("Garmin Dashboard: http://localhost:5557")
    app.run(host="127.0.0.1", port=5557, debug=False, threaded=True)
