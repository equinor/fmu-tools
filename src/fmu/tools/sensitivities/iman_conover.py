# -*- coding: utf-8 -*-
"""
An implementation of the Iman-Conover transformation.

Sources include:
    - A distribution-free approach to inducing rank correlation among input variables
      https://www.tandfonline.com/doi/epdf/10.1080/03610918208812265?needAccess=true
    - https://blogs.sas.com/content/iml/2021/06/14/simulate-iman-conover-transformation.html
    - https://blogs.sas.com/content/iml/2021/06/16/geometry-iman-conover-transformation.html


"""

import numpy as np
import scipy as sp
import pandas as pd
import requests
import io
import matplotlib.pyplot as plt

def plotmat(mat, title):
    """Plot a matrix."""
    plt.figure()
    plt.title(title)
    plt.scatter(*mat.T)
    plt.show()

# Download the CARS dataset used in
# https://blogs.sas.com/content/iml/2021/06/16/geometry-iman-conover-transformation.html
csv = requests.get("https://raw.githubusercontent.com/sassoftware/sas-viya-programming/refs/heads/master/data/cars.csv").text
filepath = io.StringIO(csv)
df = pd.read_csv(filepath)# .sample(5, random_state=42)
X = df[["EngineSize", "MPG_Highway"]].to_numpy()

# Add some noise to tie-break variables
# TODO: look more into what happens when ties are not broken
X = X + np.random.randn(*X.shape) * 0.1

# TODO: Another interesting data set is
if False:
    theta = np.random.rand(100) * np.pi * 2
    x = np.cos(theta) + np.random.randn(len(theta)) * 0.1
    y = np.sin(theta) + np.random.randn(len(theta)) * 0.1
    X = np.vstack((x, y)).T
    
    
# TODO: Look into QMC methods like LatinHypercube
if True:
    # LatinHypercube or Sobol
    sampler = sp.stats.qmc.Sobol(
        d=2, seed=42, scramble=False
    )
    lhs_samples = sampler.random(n=100) # on interval [0, 1]
    lhs_samples = np.clip(lhs_samples, a_min=1e-3, a_max=1-1e-3)
    plotmat(lhs_samples, "lhs_samples")
    X = sp.stats.norm.ppf(lhs_samples) # map to normal
    X = np.vstack((sp.stats.norm.ppf(lhs_samples[:, 0]), 
                   sp.stats.gamma.ppf(lhs_samples[:, 1], a=1))).T


# Create a correlation matrix that we want to replicate
C = np.eye(2)
C[0, 1] = C[1, 0] = 0.6


plotmat(X, "input data X")

# Step one - Map data to normal scores
N, K = X.shape
ranks = sp.stats.rankdata(X, method="average", axis=0) / (N + 1)
normal_scores = sp.stats.norm.ppf(ranks)
plotmat(normal_scores, "normal_scores")

assert np.isclose(sp.stats.spearmanr(X).statistic,
                  sp.stats.spearmanr(normal_scores).statistic), "spearman corr before and after should be the same"



# Step two - Remove correlations
I = np.corrcoef(normal_scores, rowvar=False)
Q = np.linalg.cholesky(I)  # QQ' = I
decorrelated_scores = normal_scores @ np.linalg.inv(Q).T
plotmat(decorrelated_scores, "decorrelated_scores")
assert np.allclose(np.corrcoef(decorrelated_scores, rowvar=False), np.eye(K))

decorrelated_scores2 = np.linalg.solve(Q, normal_scores.T).T
assert np.allclose(decorrelated_scores, decorrelated_scores2)

# Step three - Induce correlations
P = np.linalg.cholesky(C)  # PP' = C
correlated_scores = decorrelated_scores @ P.T
assert np.allclose(np.corrcoef(correlated_scores, rowvar=False), C)
plotmat(correlated_scores, "correlated_scores")

corr = sp.stats.spearmanr(correlated_scores).statistic
print(f"Rank correlation of correlated_scores: {corr:.6f}")
corr = sp.stats.pearsonr(*correlated_scores.T).statistic
print(f"Correlation of correlated_scores: {corr:.6f}")

# Step four - Restore marginal distributions
result = np.empty_like(X)
for k in range(K):
    #sorted_idx = np.argsort(R_star[:, k])
    #result[:, k] = np.sort(X[:, k])[sorted_idx] # X[sorted_idx, k]
    ranks = sp.stats.rankdata(correlated_scores[:, k]).astype(int) - 1
    result[:, k] = np.sort(X[:, k])[ranks]
    
plotmat(result, "result")


assert np.allclose(np.sort(X[:, 0]), np.sort(result[:, 0])), "Marginal must match"

corr = sp.stats.pearsonr(*result.T).statistic
print(f"Correlation of result: {corr:.6f}")
corr = sp.stats.spearmanr(result).statistic
print(f"Rank correlation of result: {corr:.6f}")


obs_corr = sp.stats.pearsonr(*result.T).statistic
assert np.isclose(obs_corr, 0.6, atol=0.1)