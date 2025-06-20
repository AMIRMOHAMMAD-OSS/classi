
import argparse
import os
from tqdm import tqdm
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from Bio import SeqIO
from classifier2 import Transformer
from XGBoost import XGBoost4
from Configue import CfgNode
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="xgboost")

clf = XGBoost.XGM()
model = Transformer("c")

def edit(sequence):
    return ''.join([char.upper() for char in sequence if char in "ACDEFGHIKLMNPQRSTVWY"])

def enh(scores):
    k = 50
    weights = np.array([1 / (1 + np.exp(-k * (2 * score - 1))) for score in scores])
    return np.sum(np.array(scores) * weights) / np.sum(weights)

def padd(sequence):
    return sequence + [0.0] * (5537 - len(sequence))

def SCORE(P, U):
    def scorer(seq, value):
        padded_seq = np.array(padd(seq) + [value]).reshape(1, 5538)
        prob = clf.predict_proba(padded_seq)[:, 1][0]
        truncated_seq = [v for v in padded_seq.ravel() if v != 0]
        return 0.3 * padded_seq[0, -1] + 0.4 * enh(truncated_seq[:-1]) + 0.3 * prob

    if len(P) > 5537:
        chunks = [P[i * 5537:(i + 1) * 5537] for i in range(len(P) // 5537 + 1)]
        return enh([scorer(chunk, U) for chunk in chunks])
    else:
        return scorer(P, U)

def SW(sequence_chunks):
    if len(sequence_chunks) > 700:
        chunks = [sequence_chunks[i * 700:(i + 1) * 700] for i in range(len(sequence_chunks) // 700 + 1)]
        return [model.predict_proba(chunk) for chunk in chunks if len(chunk) > 0]
    else:
        return model.predict_proba(sequence_chunks)

def d(x, u):
    if u > 0.7:
        return x * np.exp(-1.2 * (x - u))
    else:
        return x if x > 0.7 else x

def Score1(index, scores, L, n):
    index -= 1
    if index <= L:
        return sum(scores[:index + 1]) / (index + 1)
    elif L + 1 <= index < n - L:
        return sum(scores[index - L:index + 1]) / (L + 1)
    else:
        return sum(scores[index - L:n - L + 1]) / (n - index + 1)

def main():
    parser = argparse.ArgumentParser(description="LLPS Analysis Script")
    parser.add_argument("--sequence", type=str, help="Protein sequence to analyze.")
    parser.add_argument("--id", type=str, help="Protein ID.")
    parser.add_argument("--directory", type=str, help="Directory for output files.")
    parser.add_argument("--end_sequence", type=int, default=500, help="Endpoint for scoring.")
    parser.add_argument("--plot", type=bool, default=True, help="Whether to plot results.")
    args = parser.parse_args()

    Sequence = args.sequence
    End_sequence = args.end_sequence
    directory = args.directory
    ID = args.id
    Plot = args.plot 
    if os.path.isdir('/content/Phaseek/Results') == False:
      os.makedirs('/content/Phaseek/Results', exist_ok=True)
    if os.path.isdir('/content/Phaseek/Results/'+directory) == False:
      os.makedirs('/content/Phaseek/Results/'+directory, exist_ok=True)
    if os.path.isdir('/content/Phaseek/Results/'+directory+"/"+ID) == False:
      os.makedirs('/content/Phaseek/Results/'+directory+"/"+ID, exist_ok=True)
        
    if Sequence != None and Sequence != "" and ".fasta" not in Sequence:
        Sequence = edit(Sequence)
        k = max(5, min(50, int(np.ceil(0.1 * len(Sequence)))))
        L = k // 2

        if Plot:
            n = len(Sequence)
            S = [Sequence[i:i + L] for i in range(len(Sequence) - L + 1)]
            Sc = SW(S)
            Sc1 = np.concatenate(Sc) if len(Sc) > 1 else Sc[0]
            if n<= 512:
                u = model.predict_proba([Sequence])[0][0]
            else:
                u = model.predict_proba([Sequence])

            scores = list(map(lambda x: d(Score1(x, Sc1, L, n), u), range(1, n + 1)))
            scores = [float(score[0]) if isinstance(score, np.ndarray) else float(score) for score in scores]
            score = SCORE(scores, u)
            pd.DataFrame({"scores":scores,"seq":list(Sequence)}).to_csv('/content/Phaseek/Results/'+directory+"/"+ID+"/"+"scores.csv")
            print(f"Score: {score}")

    elif Sequence!= None and os.path.exists(Sequence) and ".fasta" in Sequence:
        fasta_data = [(str(record.id), edit(str(record.seq))) for record in SeqIO.parse(Sequence, "fasta")]
        fasta_data = fasta_data[:End_sequence]
        results = {"id":[i[0] for i in fasta_data] , "seq":[i[1] for i in fasta_data], "LLPS_score":[],"Residue-level score":[]}
        for sequence in tqdm(results["seq"]):
            try:
                k = max(5, min(50, int(np.ceil(0.1 * len(sequence)))))
                L = k // 2
                n = len(sequence)
                S = [sequence[i:i + L] for i in range(len(sequence) - L + 1)]
                Sc = SW(S)
                Sc1 = np.concatenate(Sc) if len(Sc) > 1 else Sc[0]
                if n<= 512:
                  u = model.predict_proba([sequence])[0][0]
                else:
                  u = model.predict_proba([sequence])
                scores = list(map(lambda x: d(Score1(x, Sc1, L, n), u), range(1, n + 1)))
                scores = [float(score[0]) if isinstance(score, np.ndarray) else float(score) for score in scores]
                score = SCORE(scores, u)
                results["LLPS_score"].append(score)
                results["Residue-level score"].append(scores)
            except Exception as e:
                results["LLPS_score"].append(None)
                results["Residue-level score"].append(None)
        if os.path.isdir('/content/Phaseek/Results') == False:
          os.makedirs('/content/Phaseek/Results', exist_ok=True)
        if os.path.isdir('/content/Phaseek/Results/'+directory) == False:
          os.makedirs('/content/Phaseek/Results/'+directory, exist_ok=True)
        pd.DataFrame(results).to_csv('/content/Phaseek/Results/'+directory+"/"+ID+"/"+"LLPS_prediction_of_seqs.csv")
        print("Analysis complete.")

if __name__ == "__main__":
    main()
