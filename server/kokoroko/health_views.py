"""
Health Check & Monitoring Views (S6.4)

Endpoints:
    /health/                → Public simple health check
    /admin-api/health/      → Detailed admin health dashboard (staff only)
    /admin-api/monitoring/  → Enhanced monitoring dashboard (staff only)
    /admin-api/security-events/ → Recent security events (staff only)
"""

import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

logger = logging.getLogger("kokoroko.monitoring")


def health_check_view(request):
    """
    Public health check — returns simple {status: "ok"} or 503.
    Does not expose internal details.
    """
    from kokoroko.monitoring_health import public_health_check
    data = public_health_check()
    status_code = 200 if data["status"] == "ok" else 503
    return JsonResponse(data, status=status_code)


@staff_member_required
def admin_health_view(request):
    """
    Detailed admin health dashboard — all subsystem checks.
    Requires staff authentication.
    """
    from kokoroko.monitoring_health import detailed_health_check
    data = detailed_health_check()
    status_code = 200 if data.get("overall") == "ok" else 503
    return JsonResponse(data, status=status_code)


@staff_member_required
def admin_monitoring_dashboard(request):
    """Enhanced monitoring dashboard with metrics + health + security events."""
    from kokoroko.monitoring import get_dashboard_data
    from kokoroko.monitoring_health import detailed_health_check
    from kokoroko.alerts import get_security_event_counts, get_recent_security_events

    data = get_dashboard_data()
    data["detailed_health"] = detailed_health_check()
    data["security_event_counts"] = get_security_event_counts()
    data["recent_security_events"] = get_recent_security_events(limit=20)
    return JsonResponse(data)


@staff_member_required
def admin_security_events_view(request):
    """Get recent security events with optional filtering."""
    from kokoroko.alerts import get_recent_security_events
    limit = int(request.GET.get("limit", "100"))
    event_filter = request.GET.get("event", None)
    severity_filter = request.GET.get("severity", None)
    events = get_recent_security_events(
        limit=min(limit, 500),
        event_filter=event_filter,
        severity_filter=severity_filter,
    )
    return JsonResponse({"events": events, "count": len(events)})


@staff_member_required
def admin_health_page(request):
    """
    Full-page admin health dashboard with auto-refresh.
    Shows all subsystem health in a visual format.
    """
    html = '''<!DOCTYPE html>
<html><head>
<title>System Health | Kokoroko Admin</title>
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0A0A0A; color:#E8E0D4; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
.container { max-width:1400px; margin:0 auto; padding:20px; }
h1 { color:#D4A843; margin-bottom:20px; display:flex; align-items:center; gap:10px; }
h1 i { font-size:28px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); gap:16px; }
.card { background:#141414; border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:16px; }
.card h3 { color:#D4A843; font-size:14px; text-transform:uppercase; letter-spacing:1px; margin-bottom:12px; display:flex; align-items:center; gap:8px; }
.card h3 i { font-size:18px; }
.status { display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.status-ok { background:rgba(34,197,94,0.15); color:#22C55E; }
.status-warning { background:rgba(234,179,8,0.15); color:#EAB308; }
.status-error { background:rgba(239,68,68,0.15); color:#EF4444; }
.status-degraded { background:rgba(234,179,8,0.15); color:#EAB308; }
.metric { display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.04); font-size:13px; }
.metric:last-child { border-bottom:none; }
.metric .label { color:#A8A29E; }
.metric .value { color:#E8E0D4; font-weight:500; }
.overall { text-align:center; padding:20px; margin-bottom:20px; border-radius:12px; }
.overall-ok { background:rgba(34,197,94,0.1); border:1px solid rgba(34,197,94,0.3); }
.overall-degraded { background:rgba(234,179,8,0.1); border:1px solid rgba(234,179,8,0.3); }
.overall-error { background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); }
.overall h2 { font-size:24px; }
.refresh { color:#A8A29E; font-size:12px; margin-top:4px; }
#loading { text-align:center; padding:40px; color:#A8A29E; }
</style>
</head>
<body>
<div class="container">
<h1><i class="material-icons">monitor_heart</i> System Health Dashboard</h1>
<div id="loading">Loading health checks...</div>
<div id="content" style="display:none">
    <div id="overall" class="overall"></div>
    <div class="grid" id="checks"></div>
</div>
<div class="refresh" id="refresh-info"></div>
</div>
<script>
function statusClass(s) { return 'status-' + (s || 'ok'); }
function statusBadge(s) { return '<span class="status ' + statusClass(s) + '">' + (s||'ok').toUpperCase() + '</span>'; }
function renderMetric(label, value) {
    return '<div class="metric"><span class="label">' + label + '</span><span class="value">' + (value ?? '-') + '</span></div>';
}
function renderCard(title, icon, check) {
    let html = '<div class="card"><h3><i class="material-icons">' + icon + '</i> ' + title + ' ' + statusBadge(check.status) + '</h3>';
    for (let [k,v] of Object.entries(check)) {
        if (k === 'status') continue;
        if (typeof v === 'object' && v !== null) v = JSON.stringify(v);
        html += renderMetric(k.replace(/_/g, ' '), v);
    }
    return html + '</div>';
}
async function loadHealth() {
    try {
        const resp = await fetch('/admin-api/health/');
        const data = await resp.json();
        document.getElementById('loading').style.display = 'none';
        document.getElementById('content').style.display = 'block';
        const ov = document.getElementById('overall');
        ov.className = 'overall overall-' + (data.overall || 'ok');
        ov.innerHTML = '<h2>' + (data.overall || 'ok').toUpperCase() + '</h2><div class="refresh">Last check: ' + (data.timestamp || 'now') + '</div>';
        const icons = {database:'storage',redis_cache:'memory',redis_detailed:'dns',redis_channels:'hub',celery_workers:'engineering',celery_beat:'schedule',celery_queues:'queue',disk_space:'hard_drive',media_directory:'folder',ffmpeg:'videocam',mysql_status:'table_chart',backups:'backup',recording_health:'fiber_smart_record'};
        let grid = '';
        for (let [k,v] of Object.entries(data)) {
            if (['overall','timestamp'].includes(k)) continue;
            if (typeof v !== 'object' || v === null) continue;
            grid += renderCard(k.replace(/_/g, ' '), icons[k] || 'check_circle', v);
        }
        document.getElementById('checks').innerHTML = grid;
        document.getElementById('refresh-info').textContent = 'Auto-refreshes every 30s';
    } catch(e) {
        document.getElementById('loading').textContent = 'Error loading health: ' + e.message;
    }
}
loadHealth();
setInterval(loadHealth, 30000);
</script>
</body></html>'''
    return HttpResponse(html)
