# src/visualize_recognition_metrics.py
# Standalone chart generator for the leave-one-out recognition experiment
# numbers already reported in docs/report.md (FAR/FRR at the original vs
# tightened thresholds, and FTE). Not wired into main.py/checkin_app/
# dashboard/experiment_far_frr.py on purpose -- this only re-visualizes
# numbers that were already computed elsewhere.
#
# Run: python3 src/visualize_recognition_metrics.py
# Saves docs/recognition_metrics_charts.png and opens an interactive window.

import os

import matplotlib.pyplot as plt

# --- Source numbers (from docs/report.md) -----------------------------
IMPOSTOR_ATTEMPTS = 41
GENUINE_ATTEMPTS = 40
SUBMITTED_IMAGES = 46
UNUSABLE_IMAGES = 5

FALSE_ACCEPTS_ORIGINAL = 13
FALSE_ACCEPTS_TIGHTENED = 1
FALSE_REJECTS_ORIGINAL = 1
FALSE_REJECTS_TIGHTENED = 2

THRESHOLDS = ["Original\n(tol 0.50, margin 0.05)", "Tightened\n(tol 0.45, margin 0.10)"]

FAR = [FALSE_ACCEPTS_ORIGINAL / IMPOSTOR_ATTEMPTS * 100, FALSE_ACCEPTS_TIGHTENED / IMPOSTOR_ATTEMPTS * 100]
FRR = [FALSE_REJECTS_ORIGINAL / GENUINE_ATTEMPTS * 100, FALSE_REJECTS_TIGHTENED / GENUINE_ATTEMPTS * 100]
FTE = UNUSABLE_IMAGES / SUBMITTED_IMAGES * 100

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "recognition_metrics_charts.png")

# Same soft palette as visualize_liveness_metrics.py, for consistent report figures.
SOFT_GREEN = "#8fbc94"
SOFT_RED = "#e8a2a2"
SOFT_BLUE = "#9fc5e8"


def plot_metrics():
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))

    # 1. FAR/FRR vs threshold -- a line graph, since the point is the
    # tradeoff/trend as the threshold tightens, not a one-off comparison.
    ax = axes[0]
    ax.plot(THRESHOLDS, FAR, marker="o", color=SOFT_RED, linewidth=2, label="FAR (impostor attempts)")
    ax.plot(THRESHOLDS, FRR, marker="o", color=SOFT_BLUE, linewidth=2, label="FRR (genuine attempts)")
    for x, y in enumerate(FAR):
        ax.annotate(f"{y:.2f}%", (x, y), textcoords="offset points", xytext=(0, 8), ha="center")
    for x, y in enumerate(FRR):
        ax.annotate(f"{y:.2f}%", (x, y), textcoords="offset points", xytext=(0, 8), ha="center")
    ax.set_ylabel("%")
    ax.set_ylim(0, max(FAR) + 8)
    ax.set_title("FAR vs FRR as Threshold Tightens")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # 2. FTE -- a single proportion, so a pie chart (usable vs unusable) fits
    # better than a line/bar.
    ax = axes[1]
    ax.pie(
        [SUBMITTED_IMAGES - UNUSABLE_IMAGES, UNUSABLE_IMAGES],
        labels=["Usable", "Unusable"],
        autopct="%1.2f%%",
        colors=[SOFT_GREEN, SOFT_RED],
        startangle=90,
    )
    ax.set_title(f"Failure-to-Enroll Rate (n={SUBMITTED_IMAGES} submitted)")

    fig.suptitle("ProxyGuard Recognition Evaluation Metrics")
    fig.tight_layout()
    return fig


if __name__ == "__main__":
    print(f"FAR: original {FAR[0]:.2f}%  ->  tightened {FAR[1]:.2f}%")
    print(f"FRR: original {FRR[0]:.2f}%  ->  tightened {FRR[1]:.2f}%")
    print(f"FTE: {FTE:.2f}%")
    figure = plot_metrics()
    figure.savefig(OUTPUT_PATH, dpi=150)
    print(f"Saved chart to {os.path.abspath(OUTPUT_PATH)}")
    plt.show()
