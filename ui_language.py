"""English display labels without changing stored activity names or baselines."""

ACTIVITY_LABELS = {
    '静坐自然呼吸': 'Seated, natural breathing',
    '站立自然呼吸': 'Standing, natural breathing',
    '缓慢行走': 'Slow walking',
    '小跑': 'Jogging',
    '小跳': 'Small jumps',
}
_ACTIVITY_VALUES = {label: value for value, label in ACTIVITY_LABELS.items()}


def canonical_activity(value):
    """Keep existing recording names and normal baselines for known activities."""
    return _ACTIVITY_VALUES.get(value, value)


def fit_english_labels(widget):
    """Allow longer English labels to remain visible without changing controls."""
    import ipywidgets as W
    for child in getattr(widget, 'children', ()):
        fit_english_labels(child)
    style = getattr(widget, 'style', None)
    if style is not None and style.has_trait('description_width'):
        style.description_width = 'initial'
    if isinstance(widget, W.Button):
        widget.layout.width = 'auto'
        widget.layout.min_width = '90px'
