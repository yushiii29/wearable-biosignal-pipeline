"""Read-only playback of saved samples with the original SensorPanel plot style.

The plot setup, fields, rolling window, and PNG dimensions follow
lab_suite.SensorPanel.capture. This module never starts acquisition or writes to
data/runs. Historical PNGs were not saved by SensorPanel itself.
"""

import csv
import html
import io
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FIELDS = {
    "esp32": ["counter"],
    "pressure": ["pressure_adc"],
    "imu": ["ax_g", "ay_g", "az_g"],
    "ecg": ["ecg_adc"],
}
SCREENSHOT_ID = ""
ARCHIVE = ROOT / "analysis" / "20261105_original_ui_waveforms"


def list_recordings(root=ROOT):
    """Keep classifications and metadata as recorded; exclude checkpoint copies."""
    records = []
    for path in sorted((Path(root) / "data" / "runs").rglob("*.csv")):
        if ".ipynb_checkpoints" in path.parts:
            continue
        meta_path = path.with_suffix(".json")
        metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        kinds = [k for k in FIELDS if any(row.get("kind") == k for row in rows)]
        if not kinds and rows and metadata.get("kind") in FIELDS:
            kinds = [metadata["kind"]]
        records.append({
            "path": path,
            "metadata_path": meta_path,
            "metadata": metadata,
            "classification": path.parent.name,
            "rows": rows,
            "kinds": kinds,
        })
    return records


def channel_rows(record, kind):
    return [r for r in record["rows"] if r.get("kind", kind) == kind]


def render_original_plot(record, kind, end_count=None):
    """Return the original 770 x 286 PNG, not a newly designed overview chart.

    end_count is the number of samples received so far in the selected channel.
    ECG shows the last 1250 samples, other channels the last 3000, exactly as
    the acquisition UI did. Device timestamps and unmodified raw values are used.
    """
    import matplotlib.pyplot as plt

    rows = channel_rows(record, kind)
    if not rows:
        raise ValueError("This recording has no samples for this channel.")
    count = len(rows) if end_count is None else max(1, min(int(end_count), len(rows)))
    shown = rows[:count][-(1250 if kind == "ecg" else 3000):]
    fields = FIELDS[kind]
    source = record["metadata"].get("source") or shown[0].get("source") or "DEVICE"

    # Same setup and redraw order as lab_suite.SensorPanel.capture.
    with plt.style.context("default"), plt.ioff():
        fig, ax = plt.subplots(figsize=(7, 2.6))
        lines = [ax.plot([], [], label=f)[0] for f in fields]
        ax.set_xlabel("Device / simulation time (s)")
        ax.set_title(source + " / " + kind)
        ax.legend(loc="upper right")
        ax.grid(alpha=.2)
        fig.tight_layout()
        x = [float(r["t_ms"]) / 1000 for r in shown]
        for line, field in zip(lines, fields):
            line.set_data(x, [float(r[field]) for r in shown])
        ax.relim()
        ax.autoscale_view()
        # The live UI redraws repeatedly. Let tight_layout settle the same way.
        for _ in range(2):
            fig.tight_layout()
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=110)
        plt.close(fig)
    return buffer.getvalue(), {
        "channel": kind,
        "received_samples": count,
        "displayed_samples": len(shown),
        "first_device_time_s": x[0],
        "last_device_time_s": x[-1],
        "fields": fields,
    }


def _make_compact_history_panel(root=ROOT):
    """Browse past recordings without connecting to a device or changing data."""
    import ipywidgets as W

    recordings = [r for r in list_recordings(root) if r["kinds"]]
    if not recordings:
        return W.HTML("No saved waveform samples were found.")
    options = []
    for i, record in enumerate(recordings):
        meta = record["metadata"]
        label = " | ".join(str(v) for v in (
            record["classification"], meta.get("participant_id", ""),
            meta.get("condition", ""), meta.get("kind", ""),
            "Attempt " + str(meta.get("attempt", "")), meta.get("started_at", ""),
        ))
        options.append((label, i))
    default = next((i for i, r in enumerate(recordings)
                    if r["metadata"].get("capture_id") == SCREENSHOT_ID), 0)
    selector = W.Dropdown(options=options, value=default, description="Recording",
                          layout=W.Layout(width="100%"), style={"description_width": "90px"})
    channel = W.Dropdown(description="Channel", options=recordings[default]["kinds"],
                         style={"description_width": "90px"})
    end = W.IntSlider(description="Samples read", min=1, max=1, value=1,
                      continuous_update=False, layout=W.Layout(width="100%"),
                      style={"description_width": "90px"})
    picture = W.Image(format="png", layout=W.Layout(width="100%", height="auto"))
    status = W.HTML()
    details = W.HTML()
    export = W.Button(description="Save this plot as PNG", layout=W.Layout(width="190px"))
    saved = W.HTML()
    state = {"updating": False, "png": None}

    def redraw(_=None):
        if state["updating"]:
            return
        record = recordings[selector.value]
        png, info = render_original_plot(record, channel.value, end.value)
        state["png"] = png
        picture.value = png
        meta = record["metadata"]
        source = meta.get("source", "DEVICE")
        transport = meta.get("transport", "")
        status.value = html.escape(
            f"HISTORICAL REPLAY | {source} / {transport} | {end.value} samples read | "
            f"displaying {info['first_device_time_s']:.3f}–{info['last_device_time_s']:.3f} s"
        )
        details.value = (
            "<b>Original recording:</b> " + html.escape(record["path"].name)
            + "<br><b>Recorded notes:</b> " + html.escape(meta.get("notes") or "None")
        )
        saved.value = ""

    def update_channel(_=None, initial=False):
        if state["updating"]:
            return
        state["updating"] = True
        record = recordings[selector.value]
        total = len(channel_rows(record, channel.value))
        end.value = 1
        end.max = total
        end.value = (min(4295, total) if initial and
                     record["metadata"].get("capture_id") == SCREENSHOT_ID else total)
        state["updating"] = False
        redraw()

    def update_record(_=None):
        state["updating"] = True
        channel.options = recordings[selector.value]["kinds"]
        channel.value = channel.options[0]
        state["updating"] = False
        update_channel()

    def save_view(_):
        record = recordings[selector.value]
        folder = Path(root) / "analysis" / "20261105_original_ui_waveforms" / "saved_views"
        folder.mkdir(parents=True, exist_ok=True)
        capture_id = record["metadata"].get("capture_id", record["path"].stem)
        path = folder / f"{capture_id}_{channel.value}_sample_{end.value}.png"
        path.write_bytes(state["png"])
        saved.value = "Saved: " + html.escape(str(path.relative_to(root)))

    selector.observe(update_record, names="value")
    channel.observe(update_channel, names="value")
    end.observe(redraw, names="value")
    export.on_click(save_view)
    update_channel(initial=True)
    return W.VBox([
        W.HTML("<b>Historical waveforms — original capture plot style</b><br>"
               "Choose a recording, then move Samples read to revisit its original rolling view. "
               "Blue lines, axes, legend and device time match the capture UI. "
               "Raw samples are unchanged. This is playback, not live acquisition."),
        selector, channel, end, status, picture, details, export, saved,
    ], layout=W.Layout(width="100%"))


def load_recording(capture_id, root=ROOT):
    """Resolve the saved capture identity, without changing its files."""
    for record in list_recordings(root):
        if record["metadata"].get("capture_id") == capture_id:
            return record
    raise FileNotFoundError(f"Saved recording not found: {capture_id}")


def _history_container(children):
    import ipywidgets as W
    # Saved widget views have no live Python connection until the cell is run.
    # A single explicit replay label replaces repeated broken-chain icons.
    # Scope this rule to history views; live acquisition warnings are unchanged.
    css = W.HTML(
        "<style>.history-capture-view.jupyter-widgets-disconnected::before,"
        ".history-capture-view .jupyter-widgets-disconnected::before"
        "{display:none!important;content:none!important}</style>",
        layout=W.Layout(display="none"))
    return W.VBox([css, *children], layout=W.Layout(width="100%")).add_class("history-capture-view")


def make_recording_panel(record, kind=None, end_count=None):
    """Restore the actual SensorPanel widgets with a historical waveform.

    Capture and save callbacks are removed: this is a view of an existing
    recording. Controls whose old values were never saved say 'Not saved'.
    """
    import ipywidgets as W
    from lab_suite import SensorPanel
    from ui_language import ACTIVITY_LABELS

    meta = record["metadata"]
    if kind is None and meta.get("kind") == "all":
        kinds = record["kinds"] or ["ecg", "pressure", "imu"]
        tabs = W.Tab(children=[make_recording_panel(record, k) for k in kinds])
        for i, k in enumerate(kinds):
            tabs.set_title(i, {"ecg": "ECG", "pressure": "Pressure", "imu": "IMU"}[k])
        return _history_container([
            W.HTML("<b>Saved three-channel recording</b><br>Choose a sensor tab to see its original-style capture panel."),
            tabs,
        ])
    kind = kind or meta["kind"]
    panel = SensorPanel(kind, ROOT)
    # Remove callbacks before restoring saved values. None of these controls
    # may start acquisition, check a device, or reclassify historical records.
    for button, callback in ((panel.start, panel.begin), (panel.save, panel.persist),
                             (panel.refresh, panel.list_ports), (panel.wifi_check, panel.check_wifi)):
        button.on_click(callback, remove=True)
    panel.stop._click_handlers.callbacks.clear()
    panel.participant.value = meta.get("participant_id", "")
    condition = meta.get("condition", "")
    panel.condition.value = ACTIVITY_LABELS.get(condition, condition)
    source = meta.get("source", "DEVICE")
    transport = meta.get("transport") or ("SIMULATED" if source == "SIMULATED" else "USB")
    panel.mode.value = ("SIMULATED" if source == "SIMULATED" else "WIFI" if transport == "WIFI" else "DEVICE")
    if meta.get("wireless_address"):
        panel.address.value = meta["wireless_address"]
    duration = meta.get("requested_duration_s")
    if duration is not None:
        panel.duration.max = max(panel.duration.max, int(duration))
        panel.duration.min = min(panel.duration.min, int(duration))
        panel.duration.value = int(duration)
    panel.review.value = meta.get("review_status", "pending")
    panel.record_notes.value = meta.get("notes", "")
    panel.record_info.value = html.escape(
        f"Historical recording | Attempt {meta.get('attempt', '')} | "
        f"{meta.get('started_at', '')} | {record['classification']}"
    )
    panel.confirm.layout.display = "none"  # This checkbox's old state was not saved.
    panel.wifi_info.layout.display = "none"  # Live connection instructions do not apply to playback.
    children = list(panel.widget.children)
    if kind in ("pressure", "imu"):
        children[children.index(panel.control)] = W.Text(
            value="Not saved", description=panel.control.description, disabled=True,
            style={"description_width": "initial"})
    if kind == "ecg":
        if meta.get("capture_id") == SCREENSHOT_ID:
            # These two displayed settings are visible in the supplied screenshot.
            panel.bpm.value = 75
            panel.polarity.value = 1
        else:
            children[children.index(panel.bpm)] = W.Text(
                value="Not saved", description=panel.bpm.description, disabled=True,
                style={"description_width": "initial"})
            if meta.get("ecg_polarity") in (1, -1):
                panel.polarity.value = meta["ecg_polarity"]
            else:
                panel.polarity.options = [("Not saved", 0)]
                panel.polarity.value = 0
    panel.widget.children = tuple(children)

    def disable(widget):
        if widget.has_trait("disabled"):
            widget.disabled = True
        for child in getattr(widget, "children", ()):
            disable(child)
    disable(panel.widget)
    rows = channel_rows(record, kind)
    if not rows:
        panel.status.value = "No samples were saved for this attempt."
        if meta.get("capture_error"):
            panel.status.value += " " + html.escape(meta["capture_error"])
        panel.out.layout.display = "none"
        return _history_container([panel.widget])

    position = W.IntSlider(
        description="Replay position", min=1, max=len(rows),
        value=len(rows) if end_count is None else min(int(end_count), len(rows)),
        continuous_update=False, layout=W.Layout(width="100%"),
        style={"description_width": "initial"})
    def redraw(_=None):
        png, info = render_original_plot(record, kind, position.value)
        panel.out.value = png
        if position.value == len(rows):
            span = (float(rows[-1]["t_ms"]) - float(rows[0]["t_ms"])) / 1000
            rate = (len(rows) - 1) / span if span else 0
            text = (f"Stopped: {source} / {transport}, total {len(rows)} samples; "
                    f"effective rate {rate:.1f} Hz; invalid lines {meta.get('bad_lines', 0)}, "
                    f"missing sequence numbers {meta.get('missing_sequences', 0)}.")
        else:
            text = f"{source} / {transport} | {position.value} samples | historical replay"
        panel.status.value = html.escape(text)
        if meta.get("capture_error"):
            panel.status.value += "<br>Recorded error: " + html.escape(meta["capture_error"])
    position.observe(redraw, names="value")
    redraw()
    return _history_container([
        W.HTML("<b>Historical replay</b> — saved recording; capture controls are read-only."),
        position, panel.widget,
    ])


def make_history_panel(root=ROOT):
    """Select any saved attempt and display its complete original capture panel."""
    import ipywidgets as W

    records = list_recordings(root)
    if not records:
        return W.HTML("No saved recordings were found.")
    options = [(" | ".join(str(v) for v in (
        r["classification"], r["metadata"].get("participant_id", ""),
        r["metadata"].get("condition", ""), r["metadata"].get("kind", ""),
        "Attempt " + str(r["metadata"].get("attempt", "")),
        r["metadata"].get("started_at", ""),
    )), i) for i, r in enumerate(records)]
    default = next((i for i, r in enumerate(records)
                    if r["metadata"].get("capture_id") == SCREENSHOT_ID), 0)
    selector = W.Dropdown(options=options, value=default, description="Saved test",
                          layout=W.Layout(width="100%"), style={"description_width": "initial"})
    content = W.VBox()
    def change(_=None, initial=False):
        record = records[selector.value]
        end = 4295 if initial and record["metadata"].get("capture_id") == SCREENSHOT_ID else None
        content.children = (make_recording_panel(record, end_count=end),)
    selector.observe(change, names="value")
    change(initial=True)
    return _history_container([
        W.HTML("<b>Saved tests — original capture interface</b><br>"
               "Select any previous test to see its saved duration, source, status, notes and original-style waveform. "
               "Replay position moves through the saved samples. Settings not recorded at the time say Not saved."),
        selector, content,
    ])
