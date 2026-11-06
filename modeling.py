"""Original class-balanced L2 logistic optimizer, made importable."""
import numpy as np

def sigmoid(s):
    s = np.asarray(s, float)
    return np.exp(-np.logaddexp(0, -s))

def metrics(y, s, threshold=0):
    y = np.asarray(y, bool)
    pred = np.asarray(s) >= threshold
    tp = int(np.sum(y & pred))
    fp = int(np.sum(~y & pred))
    fn = int(np.sum(y & ~pred))
    tn = int(np.sum(~y & ~pred))
    return {'detected_simulated': tp, 'missed_simulated': fn, 'flagged_normal': fp, 'unflagged_normal': tn, 'simulated_n': tp + fn, 'normal_n': tn + fp, 'simulated_recall': tp / (tp + fn) if tp + fn else None, 'normal_false_positive_fraction': fp / (fp + tn) if fp + tn else None}

def fit_ridge_logistic(X, y, lam=1.0, gradient_tolerance=1e-08):
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd = np.where(sd < 1e-12, 1, sd)
    Z = np.column_stack([np.ones(len(X)), (X - mu) / sd])
    n0 = np.sum(y == 0)
    n1 = np.sum(y == 1)
    if not n0 or not n1:
        raise ValueError('Two observed task labels are required')
    weights = np.where(y == 1, len(y) / (2 * n1), len(y) / (2 * n0))
    penalty = np.diag(np.r_[0.0, np.full(X.shape[1], lam)])
    b = np.zeros(Z.shape[1])
    loss = lambda v: float(np.sum(weights * (np.logaddexp(0, Z @ v) - y * (Z @ v))) + 0.5 * v @ penalty @ v)
    converged = False
    for it in range(100):
        probs = sigmoid(Z @ b)
        grad = Z.T @ (weights * (probs - y)) + penalty @ b
        if np.max(np.abs(grad)) < gradient_tolerance:
            converged = True
            break
        hessian = Z.T @ ((weights * probs * (1 - probs))[:, None] * Z) + penalty
        step = np.linalg.solve(hessian, grad)
        scale = 1.0
        while scale > 1e-09 and loss(b - scale * step) > loss(b) - 0.0001 * scale * float(grad @ step):
            scale *= 0.5
        b -= scale * step
    coeff = b[1:] / sd
    intercept = b[0] - float(coeff @ mu)
    assert converged, (it, float(np.max(np.abs(grad))))
    return {'intercept': float(intercept), 'coefficients': coeff.tolist(), 'lambda': lam, 'standardized_coefficients': b.tolist(), 'training_mean': mu.tolist(), 'training_sd': sd.tolist(), 'gradient_max_abs': float(np.max(np.abs(grad))), 'iterations': it + 1, 'fit_converged': converged, 'label_semantics': '0 normal; 1 self-simulated action. Margin is NOT panic probability.'}
