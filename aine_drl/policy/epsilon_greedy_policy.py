from aine_drl.policy import Policy
from aine_drl.drl_util import EpsilonGreedy, Decay, NoDecay
from aine_drl.util import aine_api
from aine_drl.util import logger
import torch
from torch.distributions import Distribution

class EpsilonGreedyPolicy(Policy):
    """
    Epsilon greedy policy. `pdparam` is Q value that is action value function. It works only if the action is discrete. 
    """
    
    def __init__(self, epsilon_decay: Decay = None) -> None:
        """
        Epsilon greedy policy. `pdparam` is Q value that is action value function. It works only if the action is discrete. 

        Args:
            epsilon_decay (Decay, optional): epsilon hypterparameter controller. Defaults to NoDecay(0.1).
        """
        if epsilon_decay is None:
            epsilon_decay = NoDecay(0.1)
        epsilon = epsilon_decay.value(0)
        assert epsilon >= 0 and epsilon <= 1
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
    
    @aine_api
    def get_policy_distribution(self, pdparam: torch.Tensor) -> Distribution:
        return EpsilonGreedy(pdparam, self.epsilon)
    
    @aine_api
    def update_hyperparams(self, time_step: int):
        self.epsilon = self.epsilon_decay(time_step)
        
    @aine_api
    def log_data(self, time_step: int):
        logger.log("Policy/Epsilon", self.epsilon, time_step)
