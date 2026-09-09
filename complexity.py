"""
Curve math + the dark, oscilloscope-styled complexity chart.
Kept separate from app.py so the plotting logic is easy to tweak on its own.
"""
import math
import re
import matplotlib.pyplot as plt

# Ordered worst -> best growth rate. Colors run hot (bad) -> cool (good).
# `key` must match the exact strings the LLM is instructed to return (see prompts.py).
COMPLEXITY_CLASSES = [
    {"key": "O(n!)",       "label": "O(n!)",       "color": "#FF4D6D"},
    {"key": "O(2^n)",      "label": "O(2ⁿ)",       "color": "#FF7A4A"},
    {"key": "O(n^3)",      "label": "O(n³)",       "color": "#FFA23F"},
    {"key": "O(n^2)",      "label": "O(n²)",       "color": "#FFCC45"},
    {"key": "O(n log n)",  "label": "O(n log n)",  "color": "#CFE55A"},
    {"key": "O(n)",        "label": "O(n)",        "color": "#7ED957"},
    {"key": "O(log n)",    "label": "O(log n)",    "color": "#34D399"},
    {"key": "O(1)",        "label": "O(1)",        "color": "#14B8A6"},
]
CLASS_BY_KEY = {c["key"]: c for c in COMPLEXITY_CLASSES}

N_MAX = 12  # kept small so O(n!)/O(2^n) stay renderable on a shared log axis

BG = "#0A0E0C"
GRID = "#1B2620"
TEXT_DIM = "#5B6E63"

_CURVE_FN = {
    "O(1)": lambda n: 1,
    "O(log n)": lambda n: max(math.log2(n), 0.1),
    "O(n)": lambda n: n,
    "O(n log n)": lambda n: n * max(math.log2(n), 0.1),
    "O(n^2)": lambda n: n ** 2,
    "O(n^3)": lambda n: n ** 3,
    "O(2^n)": lambda n: 2 ** n,
    "O(n!)": lambda n: math.factorial(n),
}


_VALID_KEYS = {c["key"] for c in COMPLEXITY_CLASSES}


def normalize_complexity(raw: str) -> tuple[str, str]:
    """
    Safety net for whatever the LLM actually returns in the 'complexity' field.
    Returns (bucketed, exact):
      - bucketed is guaranteed to be one of the 8 fixed classes (safe to plot/index).
      - exact is the original raw string, kept as-is for display even when it doesn't
        fit a bucket exactly (e.g. "O(n^4)").
    The prompt already asks the model to do this rounding itself; this is a
    backstop so a stray/invalid value never produces an error state.
    """
    raw = (raw or "").strip()
    exact = raw or "unknown"

    if raw in _VALID_KEYS:
        return raw, exact

    m = re.search(r"n\s*\^\s*(\d+)", raw)
    if m:
        power = int(m.group(1))
        if power <= 0:
            return "O(1)", exact
        if power == 1:
            return "O(n)", exact
        if power in (2, 3):
            return f"O(n^{power})", exact
        return "O(2^n)", exact  # degree >= 4: round up to exponential bucket

    if "!" in raw or "factorial" in raw.lower():
        return "O(n!)", exact

    if re.search(r"\d+\s*\^\s*n", raw.replace(" ", "")):
        return "O(2^n)", exact

    if "log" in raw.lower():
        if "nlogn" in raw.lower().replace(" ", ""):
            return "O(n log n)", exact
        return "O(log n)", exact

    if raw in ("O(1)", "O(c)") or "constant" in raw.lower():
        return "O(1)", exact

    return "O(n^2)", exact  # conservative fallback


def curve_points(key: str):
    xs = list(range(1, N_MAX + 1))
    ys = [_CURVE_FN[key](n) for n in xs]
    return xs, ys


def plot_scope(detected: str | None, target: str | None):
    """Returns a matplotlib Figure with all 8 curves, highlighting detected/target."""
    plt.rcParams["font.family"] = "monospace"
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=160)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    for cls in COMPLEXITY_CLASSES:
        key = cls["key"]
        is_detected = key == detected
        is_target = key == target and target != detected
        xs, ys = curve_points(key)
        highlighted = is_detected or is_target

        if is_detected:
            lw, alpha, ls = 4.2, 1.0, "-"
        elif is_target:
            lw, alpha, ls = 3.6, 1.0, "--"
        else:
            # dim, but still clearly readable, not washed out
            lw, alpha, ls = 2.0, 0.55 if detected else 0.9, "-"

        # subtle dark halo behind highlighted curves so they pop against the others
        if highlighted:
            ax.plot(xs, ys, color=BG, linewidth=lw + 2.4, alpha=0.9,
                     linestyle=ls, solid_capstyle="round", zorder=2)

        ax.plot(xs, ys, color=cls["color"], linewidth=lw, alpha=alpha,
                 linestyle=ls, solid_capstyle="round", label=cls["label"],
                 zorder=4 if highlighted else 3)

        if highlighted:
            ax.scatter([xs[-1]], [ys[-1]], color=cls["color"], s=70, zorder=5,
                        edgecolors=BG, linewidths=1.5)
            tag = "DETECTED" if is_detected else "TARGET"
            ax.annotate(
                f" {cls['label']} · {tag}", xy=(xs[-1], ys[-1]),
                xytext=(6, 0), textcoords="offset points",
                color=cls["color"], fontsize=10, fontweight="bold",
                va="center", annotation_clip=False,
            )

    ax.set_yscale("log")
    ax.set_xlim(1, N_MAX + 2.6)  # headroom on the right for end-of-curve labels
    ax.set_xlabel("INPUT SIZE (n)", color=TEXT_DIM, fontsize=10, labelpad=8)
    ax.set_ylabel("OPS", color=TEXT_DIM, fontsize=10, labelpad=8)
    ax.tick_params(colors=TEXT_DIM, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.7, linestyle=(0, (2, 4)))
    for spine in ax.spines.values():
        spine.set_color(GRID)

    # legend below the plot, wrapped across columns - never gets clipped by a
    # narrow container the way a right-side legend can.
    legend = ax.legend(
        loc="upper center", bbox_to_anchor=(0.42, -0.16), ncol=4, frameon=False,
        fontsize=9.5, labelcolor=TEXT_DIM, handlelength=1.6, columnspacing=1.3,
    )
    for text in legend.get_texts():
        text.set_color("#A9C2B4")

    fig.subplots_adjust(bottom=0.24, right=0.86)
    return fig
