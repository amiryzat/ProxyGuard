import os

import matplotlib.pyplot as plt

GENUINE_LIVENESS_ATTEMPTS = 30
SUCCESSFUL_LIVENESS_CHECKS = 24
LIVENESS_TIMEOUTS = 6
SUCCESSFUL_TRIAL_DURATION_SUM_SECONDS = 157.6
SUCCESSFUL_TRIALS = 24

TAR = SUCCESSFUL_LIVENESS_CHECKS / GENUINE_LIVENESS_ATTEMPTS * 100
FRR_LIVENESS = LIVENESS_TIMEOUTS / GENUINE_LIVENESS_ATTEMPTS * 100
AVG_LATENCY = SUCCESSFUL_TRIAL_DURATION_SUM_SECONDS / SUCCESSFUL_TRIALS

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "liveness_metrics_charts.png")

def plot_metrics():
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    ax = axes[0]
    bars = ax.bar(["TAR", "FRR (liveness)"], [TAR, FRR_LIVENESS], color=["#8fbc94", "#e8a2a2"])
    ax.set_ylim(0, 100)
    ax.set_ylabel("%")
    ax.set_title("Liveness TAR vs FRR")
    for bar, value in zip(bars, [TAR, FRR_LIVENESS]):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 2, f"{value:.1f}%", ha="center")

    ax = axes[1]
    ax.pie(
        [SUCCESSFUL_LIVENESS_CHECKS, LIVENESS_TIMEOUTS],
        labels=["Successful", "Timeout"],
        autopct="%1.1f%%",
        colors=["#8fbc94", "#e8a2a2"],
        startangle=90,
    )
    ax.set_title(f"Genuine Liveness Attempts (n={GENUINE_LIVENESS_ATTEMPTS})")

    ax = axes[2]
    ax.bar(["Avg. Latency"], [AVG_LATENCY], color="#9fc5e8", width=0.4)
    ax.set_ylabel("seconds")
    ax.set_title("Average Check-in Latency")
    ax.text(0, AVG_LATENCY + 0.2, f"{AVG_LATENCY:.2f}s", ha="center")

    fig.suptitle("ProxyGuard Liveness Evaluation Metrics")
    fig.tight_layout()
    return fig

if __name__ == "__main__":
    print(f"TAR: {TAR:.1f}%  |  FRR (liveness): {FRR_LIVENESS:.1f}%  |  Avg. latency: {AVG_LATENCY:.2f}s")
    figure = plot_metrics()
    figure.savefig(OUTPUT_PATH, dpi=150)
    print(f"Saved chart to {os.path.abspath(OUTPUT_PATH)}")
    plt.show()
