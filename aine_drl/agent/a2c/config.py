from typing import NamedTuple, Optional

class A2CConfig(NamedTuple):
    """
    A2C configurations.

    Args:
        `training_freq (int)`: training frequency which is the number of time steps to gather experiences
        `gamma (float, optional)`: discount factor. Defaults to 0.99.
        `lam (float, optional)`: regularization parameter which controls the balanace of Generalized Advantage Estimation (GAE) between bias and variance Defaults to 0.95.
        `value_loss_coef (float, optional)`: state value loss (critic loss) multiplier. Defaults to 0.5.
        `entropy_coef (float, optional)`: entropy multiplier used to compute loss. It adjusts exploration/exploitation balance. Defaults to 0.001.
        `grad_clip_max_norm (float | None, optional)`: maximum norm for the gradient clipping. Defaults to no gradient clipping.
    """
    training_freq: int
    gamma: float = 0.99
    lam: float = 0.95
    value_loss_coef: float = 0.5
    entropy_coef: float = 0.001
    grad_clip_max_norm: Optional[float] = None