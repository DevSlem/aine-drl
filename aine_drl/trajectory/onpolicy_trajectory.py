from aine_drl.drl_util import ExperienceBatch
from aine_drl.trajectory import BatchTrajectory
from aine_drl.util.decorator import aine_api

class OnPolicyTrajectory(BatchTrajectory):
    """
    It's an on-policy trajectory for the batch learning.
    """    
    def __init__(self, num_exp_per_env: int, num_envs: int = 1) -> None:
        """
        Args:
            num_exp_per_env (int): number of experiences per environment
            num_envs (int, optional): number of environments. Defaults to 1.
        """
        assert num_exp_per_env > 0
        super().__init__(num_exp_per_env * num_envs, num_envs)
        self.freq = num_exp_per_env
        
    @aine_api
    @property
    def can_train(self) -> bool:
        return int(self._count / self.num_envs) == self.freq
    
    @aine_api
    def sample(self) -> ExperienceBatch:
        """
        Sample from the trajectory. You should call this function only if can train.
        
        The batch size is num_exp_per_env * num_envs.

        Returns:
            ExperienceBatch: sampled experience batch
        """
        # temporarily extends
        self.states.extend(self.next_state_buffer)
        experience_batch = ExperienceBatch.create(
            self.states[:-self.num_envs], # states
            self.actions,
            self.states[self.num_envs:], # next states
            self.rewards,
            self.terminateds
        )
        # because it's on-policy method, all experiences which are used to train must be discarded.
        self.reset()
        return experience_batch
    