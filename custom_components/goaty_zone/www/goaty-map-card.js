const VERSION = "2.0.0";

const CSS = `
:host {
  display: block;
  font-family: var(--primary-font-family, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
}
ha-card {
  overflow: hidden;
  border-radius: 16px;
}
.wrap {
  display: flex;
  flex-direction: column;
}
.map-wrap {
  position: relative;
  width: 100%;
  background: #111;
  overflow: hidden;
}
.map-wrap canvas {
  display: block;
  width: 100%;
  height: auto;
}
.loading,
.error {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  text-align: center;
  color: var(--primary-text-color, #fff);
  background: rgba(0, 0, 0, 0.45);
}
.error {
  color: #ff6b6b;
}
.controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: var(--ha-card-background, #1c1c1e);
}
.nav {
  display: flex;
  align-items: center;
  gap: 8px;
}
.nav button {
  appearance: none;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: var(--primary-text-color, #fff);
  border-radius: 10px;
  padding: 6px 10px;
  font-size: 13px;
  cursor: pointer;
}
.nav button:disabled {
  opacity: 0.35;
  cursor: default;
}
.date {
  min-width: 104px;
  text-align: center;
  font-size: 12px;
  color: var(--secondary-text-color, #9ca3af);
}
.legend {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--secondary-text-color, #9ca3af);
}
.legend-bar {
  width: 72px;
  height: 6px;
  border-radius: 999px;
  background: linear-gradient(90deg, #34c759 0%, #ff3b30 100%);
}
`;

function todayKey() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

class GoatyDayMapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {
      title: "Goaty Karte",
      position_update: 15,
      hours: 24,
    };
    this._apiConfig = null;
    this._img = null;
    this._path = [];
    this._availableDates = [];
    this._viewDate = null;
    this._loading = false;
    this._refreshTimer = null;
    this._canvas = null;
    this._ctx = null;
    console.info(`GOATY-DAY-MAP-CARD v${VERSION}`);
  }

  setConfig(config) {
    this._config = {
      title: config?.title || "Goaty Karte",
      position_update: Number(config?.position_update) || 15,
      hours: Number(config?.hours) || 24,
    };
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._apiConfig) {
      this._bootstrap();
      return;
    }
    this._draw();
  }

  getCardSize() {
    return 6;
  }

  disconnectedCallback() {
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer);
      this._refreshTimer = null;
    }
  }

  _token() {
    return (
      this._hass?.auth?.data?.access_token ||
      this._hass?.auth?.accessToken ||
      document.querySelector("home-assistant")?.auth?.data?.access_token ||
      ""
    );
  }

  async _requestJson(url) {
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${this._token()}`,
      },
    });
    if (!response.ok) {
      throw new Error(`${url} -> ${response.status}`);
    }
    return response.json();
  }

  async _bootstrap() {
    if (this._loading) {
      return;
    }
    this._loading = true;
    this._renderLoading();

    try {
      this._apiConfig = await this._requestJson("/api/goaty_zone/config");
      this._availableDates = await this._loadAvailableDates();
      if (this._apiConfig?.image_path) {
        await this._loadImage(this._apiConfig.image_path);
      }
      await this._loadPath();
      this._draw();
      if (this._refreshTimer) {
        clearInterval(this._refreshTimer);
      }
      this._refreshTimer = setInterval(
        () => this._draw(),
        Math.max(5, this._config.position_update) * 1000,
      );
    } catch (err) {
      console.error("GOATY-DAY-MAP-CARD init error", err);
      this._renderError(err?.message || String(err));
    } finally {
      this._loading = false;
    }
  }

  async _loadAvailableDates() {
    try {
      const data = await this._requestJson("/api/goaty_zone/path/available_dates");
      return Array.isArray(data?.dates) ? data.dates.filter(Boolean) : [];
    } catch (err) {
      console.warn("GOATY-DAY-MAP-CARD available dates unavailable", err);
      return [];
    }
  }

  async _loadImage(src) {
    if (!src) {
      this._img = null;
      return;
    }
    await new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        this._img = img;
        resolve();
      };
      img.onerror = () => reject(new Error(`Bild nicht ladbar: ${src}`));
      img.src = src;
    });
  }

  async _loadPath(date = null) {
    const query = new URLSearchParams();
    if (date) {
      query.set("date", date);
    } else {
      query.set("hours", String(this._config.hours || 24));
    }
    const data = await this._requestJson(`/api/goaty_zone/path?${query.toString()}`);
    this._path = Array.isArray(data?.points) ? data.points : [];
  }

  _ensureCanvas() {
    this._canvas = this.shadowRoot?.getElementById("map") || null;
    this._ctx = this._canvas ? this._canvas.getContext("2d") : null;
  }

  _scale() {
    const scale = Number(this._apiConfig?.scale);
    return Number.isFinite(scale) && scale > 0 ? scale : 0.001;
  }

  _invertYAxis() {
    return Boolean(this._apiConfig?.invert_y_axis);
  }

  _parseHeading(value) {
    const raw = Number(value);
    if (!Number.isFinite(raw)) {
      return 0;
    }
    return Math.abs(raw) > Math.PI * 2 ? (raw * Math.PI) / 180 : raw;
  }

  _rawToMeters(xRaw, yRaw) {
    const scale = this._scale();
    const yValue = this._invertYAxis() ? -Number(yRaw) : Number(yRaw);
    return {
      x: Number(xRaw) * scale,
      y: yValue * scale,
    };
  }

  _metersToPixel(xMeters, yMeters) {
    const cfg = this._apiConfig || {};
    const width = this._canvas?.width || cfg.img_width || 1452;
    const height = this._canvas?.height || cfg.img_height || 2000;
    const scaleX = width / (cfg.img_width || width);
    const scaleY = height / (cfg.img_height || height);
    return {
      x: ((Number(cfg.charger_px_x) || 0) + Number(xMeters) * (Number(cfg.px_per_m_x) || 22.48)) * scaleX,
      y: ((Number(cfg.charger_px_y) || 0) - Number(yMeters) * (Number(cfg.px_per_m_y) || 22.48)) * scaleY,
    };
  }

  _rawToPixel(xRaw, yRaw) {
    const meters = this._rawToMeters(xRaw, yRaw);
    return this._metersToPixel(meters.x, meters.y);
  }

  _pathColor(fraction) {
    const t = Math.min(1, Math.max(0, Number(fraction) || 0));
    const r = Math.round(52 + (255 - 52) * t);
    const g = Math.round(199 - (199 - 69) * t);
    const b = Math.round(89 - (89 - 48) * t);
    return `rgb(${r}, ${g}, ${b})`;
  }

  _selectedDateKey() {
    return this._viewDate || todayKey();
  }

  _isTodaySelected() {
    return !this._viewDate || this._viewDate === todayKey();
  }

  _formatDate(dateKey) {
    if (!dateKey) {
      return "Heute";
    }
    try {
      const label = new Intl.DateTimeFormat("de-DE", {
        weekday: "short",
        day: "2-digit",
        month: "2-digit",
      }).format(new Date(`${dateKey}T12:00:00`));
      return `${dateKey === todayKey() ? "Heute" : label}`;
    } catch {
      return dateKey;
    }
  }

  _currentPosition() {
    const cfg = this._apiConfig || {};
    const tracker = this._hass?.states?.[cfg.position_tracker_entity || "device_tracker.goaty_position"];
    const attrs = tracker?.attributes || {};
    const x = Number(attrs.x_m);
    const y = Number(attrs.y_m);
    if (Number.isFinite(x) && Number.isFinite(y)) {
      return {
        x_m: x,
        y_m: y,
        heading: this._parseHeading(attrs.heading),
      };
    }

    const xState = this._hass?.states?.[cfg.position_x_m_entity];
    const yState = this._hass?.states?.[cfg.position_y_m_entity];
    const hState = this._hass?.states?.[cfg.heading_entity];
    if (!xState || !yState) {
      return null;
    }
    const xMeters = Number(xState.state);
    const yMeters = Number(yState.state);
    if (!Number.isFinite(xMeters) || !Number.isFinite(yMeters)) {
      return null;
    }
    return {
      x_m: xMeters,
      y_m: yMeters,
      heading: this._parseHeading(hState?.state),
    };
  }

  _drawPath(ctx) {
    if (!Array.isArray(this._path) || this._path.length < 2) {
      return;
    }
    const count = this._path.length;
    for (let i = 1; i < count; i += 1) {
      const a = this._path[i - 1];
      const b = this._path[i];
      const pa = this._rawToPixel(a.x, a.y);
      const pb = this._rawToPixel(b.x, b.y);
      ctx.beginPath();
      ctx.strokeStyle = this._pathColor(i / Math.max(1, count - 1));
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
    }
  }

  _drawCharger(ctx) {
    const cfg = this._apiConfig || {};
    const width = this._canvas?.width || cfg.img_width || 1452;
    const height = this._canvas?.height || cfg.img_height || 2000;
    const scaleX = width / (cfg.img_width || width);
    const scaleY = height / (cfg.img_height || height);
    const x = (Number(cfg.charger_px_x) || 0) * scaleX;
    const y = (Number(cfg.charger_px_y) || 0) * scaleY;
    ctx.save();
    ctx.font = "22px serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("⚡", x, y);
    ctx.restore();
  }

  _drawTracker(ctx) {
    if (!this._isTodaySelected()) {
      return;
    }
    const position = this._currentPosition();
    if (!position) {
      return;
    }
    const { x, y } = this._metersToPixel(position.x_m, position.y_m);
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(position.heading || 0);
    ctx.fillStyle = "rgba(239, 68, 68, 0.92)";
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(0, 0, 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    if (position.heading) {
      ctx.beginPath();
      ctx.moveTo(0, -15);
      ctx.lineTo(-5, -7);
      ctx.lineTo(5, -7);
      ctx.closePath();
      ctx.fillStyle = "#ffffff";
      ctx.fill();
    }
    ctx.restore();
  }

  _draw() {
    if (!this._canvas || !this._ctx || !this._apiConfig) {
      this._render();
      return;
    }
    const ctx = this._ctx;
    const width = this._canvas.width;
    const height = this._canvas.height;
    ctx.clearRect(0, 0, width, height);
    if (this._img) {
      ctx.drawImage(this._img, 0, 0, width, height);
    } else {
      ctx.fillStyle = "#151515";
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = "#444";
      ctx.font = "14px system-ui";
      ctx.textAlign = "center";
      ctx.fillText("Kein Luftbild konfiguriert", width / 2, height / 2);
    }
    this._drawPath(ctx);
    this._drawCharger(ctx);
    this._drawTracker(ctx);
  }

  _renderLoading() {
    this.shadowRoot.innerHTML = `
      <style>${CSS}</style>
      <ha-card>
        <div class="wrap">
          <div class="map-wrap" style="min-height: 320px;">
            <div class="loading">Karte wird geladen…</div>
          </div>
        </div>
      </ha-card>
    `;
  }

  _renderError(message) {
    this.shadowRoot.innerHTML = `
      <style>${CSS}</style>
      <ha-card>
        <div class="wrap">
          <div class="map-wrap" style="min-height: 320px;">
            <div class="error">⚠ ${this._escape(message)}<br><small>Ist die goaty_zone Integration installiert?</small></div>
          </div>
        </div>
      </ha-card>
    `;
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  _dateIndex(dateKey) {
    return this._availableDates.indexOf(dateKey);
  }

  _latestPastDate() {
    const today = todayKey();
    for (let i = this._availableDates.length - 1; i >= 0; i -= 1) {
      const candidate = this._availableDates[i];
      if (candidate && candidate < today) {
        return candidate;
      }
    }
    return null;
  }

  _canGoPrevious() {
    if (this._isTodaySelected()) {
      return Boolean(this._latestPastDate());
    }
    return this._dateIndex(this._viewDate) > 0;
  }

  _canGoNext() {
    return !this._isTodaySelected();
  }

  async _navigate(delta) {
    const today = todayKey();
    let nextDate = null;

    if (delta < 0) {
      if (!this._availableDates.length) {
        return;
      }
      if (this._isTodaySelected()) {
        nextDate = this._latestPastDate();
      } else {
        const index = this._dateIndex(this._viewDate);
        if (index <= 0) {
          return;
        }
        nextDate = this._availableDates[index - 1] || null;
      }
    } else if (delta > 0) {
      if (this._isTodaySelected()) {
        return;
      }
      const index = this._dateIndex(this._viewDate);
      if (index >= 0 && index < this._availableDates.length - 1) {
        nextDate = this._availableDates[index + 1] || null;
      } else {
        nextDate = today;
      }
    }

    this._viewDate = nextDate && nextDate !== today ? nextDate : null;
    this._render();
    try {
      await this._loadPath(this._viewDate);
      this._draw();
    } catch (err) {
      console.warn("GOATY-DAY-MAP-CARD navigation path load failed", err);
    }
  }

  _render() {
    const cfg = this._apiConfig || {};
    const width = Number(cfg.img_width) || 1452;
    const height = Number(cfg.img_height) || 2000;
    const dateLabel = this._formatDate(this._viewDate || todayKey());
    const canPrev = this._canGoPrevious();
    const canNext = this._canGoNext();

    this.shadowRoot.innerHTML = `
      <style>${CSS}</style>
      <ha-card>
        <div class="wrap">
          <div class="map-wrap" style="aspect-ratio:${width}/${height}">
            <canvas id="map" width="${width}" height="${height}"></canvas>
            ${this._loading ? `<div class="loading">Karte wird geladen…</div>` : ""}
          </div>
          <div class="controls">
            <div class="nav">
              <button id="prev" type="button" ${canPrev ? "" : "disabled"}>◀ Vorheriger Tag</button>
              <div class="date">${this._escape(dateLabel)}</div>
              <button id="next" type="button" ${canNext ? "" : "disabled"}>Nächster Tag ▶</button>
            </div>
            <div class="legend">
              <span>Älter</span>
              <div class="legend-bar"></div>
              <span>Jetzt</span>
            </div>
          </div>
        </div>
      </ha-card>
    `;
    this._ensureCanvas();
    if (this._ctx) {
      this._draw();
    }
    this.shadowRoot.getElementById("prev")?.addEventListener("click", () => this._navigate(-1));
    this.shadowRoot.getElementById("next")?.addEventListener("click", () => this._navigate(+1));
  }

  static getStubConfig() {
    return { title: "Goaty Karte" };
  }
}

if (!customElements.get("goaty-day-map-card")) {
  customElements.define("goaty-day-map-card", GoatyDayMapCard);
}

if (!customElements.get("goaty-map-card")) {
  customElements.define("goaty-map-card", GoatyDayMapCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "goaty-day-map-card",
  name: "Goaty Day Map Card",
  description: "Tageskarte mit Luftbild, Pfad und GOAT-Tracker.",
  preview: false,
  documentationURL: "https://github.com/der-seemann/ha-goaty",
});
