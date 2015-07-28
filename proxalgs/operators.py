"""
Proximal operators

Evaluates proximal operators for various functions.

Notes
-----
evaluates expressions of the form:

.. math:: \mathrm{prox}_{f,rho} (x0) = \mathrm{argmin}_x ( f(x) + (rho / 2) ||x-x0||_2^2 )

"""

# imports
import numpy as np
import scipy.optimize as opt
from scipy.sparse import spdiags
from scipy.sparse.linalg import spsolve
from skimage.restoration import denoise_tv_bregman
from toolz import curry
from toolz.functoolz import isunary


@curry
def sfo(x0, rho, optimizer, num_steps=50):
    """
    Proximal operator for an arbitrary function minimized via the Sum-of-Functions optimizer (SFO)

    Notes
    -----
    SFO is a function optimizer for the
    case where the target function breaks into a sum over minibatches, or a sum
    over contributing functions. It is
    described in more detail in [1]_.

    Parameters
    ----------
    x0 : array_like
        The starting or initial point used in the proximal update step

    rho : float
        Momentum parameter for the proximal step (larger value -> stays closer to x0)

    optimizer : SFO instance
        Instance of the SFO object in `SFO_admm.py`

    num_steps : int, optional
        Number of SFO steps to take

    Returns
    -------
    theta : array_like
    The parameter vector found after running `num_steps` iterations of the SFO optimizer

    References
    ----------
    .. [1] Jascha Sohl-Dickstein, Ben Poole, and Surya Ganguli. Fast large-scale optimization by unifying stochastic
        gradient and quasi-Newton methods. International Conference on Machine Learning (2014). `arXiv preprint
        arXiv:1311.2115 (2013) <http://arxiv.org/abs/1311.2115>`_.

    """

    # set the current parameter value of SFO to the given value
    optimizer.set_theta(x0, float(rho))

    # set the previous ADMM location as the flattened paramter array
    optimizer.theta_admm_prev = optimizer.theta_original_to_flat(x0)

    # run the optimizer for n steps
    return optimizer.optimize(num_steps=num_steps)


@curry
def poissreg(x0, rho, x, y):
    """
    Proximal operator for Poisson regression

    Computes the proximal operator of the negative log-likelihood loss assumping a Poisson noise distribution.

    Parameters
    ----------
    x0 : array_like
        The starting or initial point used in the proximal update step

    rho : float
        Momentum parameter for the proximal step (larger value -> stays closer to x0)

    x : (n, k) array_like
        A design matrix consisting of n examples of k-dimensional features (or input).

    y : (n,) array_like
        A vector containing the responses (outupt) to the n features given in x.

    Returns
    -------
    theta : array_like
        The parameter vector found after running the proximal update step


    """

    # objective and gradient
    n = float(x.shape[0])
    f = lambda w: np.mean(np.exp(x.dot(w)) - y * x.dot(w))
    df = lambda w: (x.T.dot(np.exp(x.dot(w))) - x.T.dot(y)) / n

    # minimize via BFGS
    return bfgs(x0, rho, f, df)


@curry
def bfgs(x0, rho, f, fgrad):
    """
    Proximal operator for minimizing an arbitrary function using BFGS

    Uses the BFGS algorithm to find the proximal update for an arbitrary function, `f`, whose gradient is known.

    Parameters
    ----------
    x0 : array_like
        The starting or initial point used in the proximal update step

    rho : float
        Momentum parameter for the proximal step (larger value -> stays closer to x0)

    f : function
        The function to use when applying the proximal operator. Must take as input a parameter vector (array_like) and
        return a real number (floating point value)

    df : function
        A function that computes the gradient of `f` with respect to the parameters. Must take as input a parameter
        vector (array_like) and returns another ndarray of the same size.

    Returns
    -------
    theta : array_like
        The parameter vector found after running the proximal update step

    """

    # specify the objective function and gradient for the proximal operator
    g = lambda x: f(x) + (rho / 2) * np.sum((x.reshape(x0.shape) - x0) ** 2)
    dg = lambda x: fgrad(x) + rho * (x.reshape(x0.shape) - x0)

    # minimize via BFGS
    return opt.fmin_bfgs(g, x0, dg, disp=False)


@curry
def smooth(x0, rho, gamma):
    """
    Proximal operator for a smoothing function enforced via the discrete laplacian operator

    Parameters
    ----------
    x0 : array_like
        The starting or initial point used in the proximal update step

    rho : float
        Momentum parameter for the proximal step (larger value -> stays closer to x0)

    gamma : float
        A constant that weights how strongly to enforce the constraint

    Returns
    -------
    theta : array_like
        The parameter vector found after running the proximal update step

    """

    # Apply Laplacian smoothing
    n = x0.shape[0]
    lap_op = spdiags([(2 + rho / gamma) * np.ones(n), -1 * np.ones(n), -1 * np.ones(n)], [0, -1, 1], n, n, format='csc')
    x_out = spsolve(gamma * lap_op, rho * x0)

    return x_out


@curry
def nucnorm(x0, rho, gamma):
    """
    Proximal operator for the nuclear norm (sum of the singular values of a matrix)

    Parameters
    ----------
    x0 : array_like
        The starting or initial point used in the proximal update step

    rho : float
        Momentum parameter for the proximal step (larger value -> stays closer to x0)

    gamma : float
        A constant that weights how strongly to enforce the constraint

    Returns
    -------
    theta : array_like
        The parameter vector found after running the proximal update step

    """

    # compute SVD
    u, s, v = np.linalg.svd(x0, full_matrices=False)

    # soft threshold the singular values
    sthr = np.maximum(s - (gamma / float(rho)), 0)

    # reconstruct
    x_out = (u.dot(np.diag(sthr)).dot(v))

    return x_out


@curry
def squared_error(x0, rho, x_obs):
    """
    Proximal operator for the pairwise difference between two matrices (Frobenius norm)

    Parameters
    ----------
    x0 : array_like
        The starting or initial point used in the proximal update step

    rho : float
        Momentum parameter for the proximal step (larger value -> stays closer to x0)

    x_obs : array_like
        The true matrix that we want to approximate. The error between the parameters and this matrix is minimized.

    Returns
    -------
    x0 : array_like
        The parameter vector found after running the proximal update step

    """
    return (x0 + x_obs / rho) / (1 + 1 / rho)


@curry
def tvd(x0, rho, gamma):
    """
    Proximal operator for the total variation denoising penalty

    Requires scikit-image be installed

    Parameters
    ----------
    x0 : array_like
        The starting or initial point used in the proximal update step

    rho : float
        Momentum parameter for the proximal step (larger value -> stays closer to x0)

    gamma : float
        A constant that weights how strongly to enforce the constraint

    Returns
    -------
    theta : array_like
        The parameter vector found after running the proximal update step

    Raises
    ------
    ImportError
        If scikit-image fails to be imported

    """

    return denoise_tv_bregman(x0, rho / gamma)


@curry
def sparse(x0, rho, gamma):
    """
    Proximal operator for the l1 norm (induces sparsity)

    Parameters
    ----------
    x0 : array_like
        The starting or initial point used in the proximal update step

    rho : float
        Momentum parameter for the proximal step (larger value -> stays closer to x0)

    gamma : float
        A constant that weights how strongly to enforce the constraint

    Returns
    -------
    theta : array_like
        The parameter vector found after running the proximal update step

    """

    lmbda = float(gamma) / rho

    return (x0 - lmbda) * (x0 >= lmbda) + (x0 + lmbda) * (x0 <= -lmbda)


@curry
def nonneg(x0, rho):
    """
    Proximal operator for enforcing non-negativity (indicator function over the set x >= 0)

    Parameters
    ----------
    x0 : array_like
        The starting or initial point used in the proximal update step

    rho : float
        Unused parameter

    Returns
    -------
    theta : array_like
        The parameter vector found after running the proximal update step

    """

    return np.maximum(x0, 0)


@curry
def linsys(x0, rho, P, q):
    """
    Proximal operator for the linear approximation Ax = b

    Minimizes the function:

    .. math:: f(x) = (1/2)||Ax-b||_2^2 = (1/2)x^TA^TAx - (b^TA)x + b^Tb

    Parameters
    ----------
    x0 : array_like
        The starting or initial point used in the proximal update step

    rho : float
        Momentum parameter for the proximal step (larger value -> stays closer to x0)

    P : array_like
        The symmetric matrix A^TA, where we are trying to approximate Ax=b

    q : array_like
        The vector A^Tb, where we are trying to approximate Ax=b

    Returns
    -------
    theta : array_like
        The parameter vector found after running the proximal update step

    """
    return np.linalg.solve(rho * np.eye(q.size) + P, rho * x0.copy() + q)
