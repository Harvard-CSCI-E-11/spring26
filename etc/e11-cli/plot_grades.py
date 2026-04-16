import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys

fname = sys.argv[1]

def generate_both_plots(csv_file):
    df = pd.read_csv(csv_file)
    grades = df.iloc[:, -1].dropna().sort_values()
    n = len(grades)

    # --- PLOT 1: RAW CUMULATIVE COUNTS ---
    plt.figure(figsize=(8, 5))
    counts = np.arange(1, n + 1)
    plt.step(grades, counts, where='post', color='blue')

    plt.title(f'Cumulative Raw Counts {fname}')
    plt.ylabel('Number of Students')
    plt.xlabel('Grade')

    # Save before clearing!
    plt.savefig(csv_file.replace(".csv", "_counts.pdf"))
    print("Saved Raw Counts PDF.")

    # THE MAGIC COMMAND: Wipe the figure for the next plot
    plt.clf()

    # --- PLOT 2: CDF (NORMALIZED) ---
    # We don't need plt.figure() again if we want same size
    probabilities = np.arange(1, n + 1) / n
    plt.step(grades, probabilities, where='post', color='green')

    plt.title(f'Cumulative Distribution Function (CDF) {fname}')
    plt.ylabel('Cumulative Probability (0.0 - 1.0)')
    plt.xlabel('Grade')

    plt.savefig(csv_file.replace(".csv", "_cdf.pdf"))
    print("Saved CDF PDF.")


# Usage
generate_both_plots(fname)
