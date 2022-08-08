from abc import ABC, abstractmethod
from typing import Union, List
from aine_drl import aine_api
import aine_drl.util as util
from aine_drl.experience import Experience, ExperienceBatch
import numpy as np

class Trajectory(ABC):
    def __init__(self, max_count_per_env: int, env_count: int = 1) -> None:
        assert max_count_per_env > 0 and env_count > 0
        self.env_count = env_count
        self.max_count = env_count * max_count_per_env
        self.reset()
        
    @property
    def count(self):
        """
        Returns stored experiences count.
        """
        return self._count
        
    @aine_api
    def reset(self):
        """
        Reset the trajectory.
        """
        self._count = 0
        self.recent_idx = -1
        
        self.states = [None] * self.max_count
        self.actions = [None] * self.max_count
        self.rewards = [None] * self.max_count
        self.terminateds = [None] * self.max_count
        self.next_state_buffer = [None] * self.env_count
        
    @aine_api
    def add(self, experiences: Union[Experience, List[Experience]]):
        """Add one or more experiences.

        Args:
            experiences (Experience | List[Experience]): 
            both single or list are okay, but be sure that count equals to environment count
        """
        if isinstance(experiences, Experience):
            experiences = [experiences]
            
        assert len(experiences) == self.env_count
        
        for i, ex in enumerate(experiences):
            self.recent_idx = (self.recent_idx + 1) % self.max_count
            self._count = min(self._count + 1, self.max_count)
            
            self.states[self.recent_idx] = ex.state
            self.actions[self.recent_idx] = ex.action
            self.rewards[self.recent_idx] = ex.reward
            self.terminateds[self.recent_idx] = ex.terminated
            self.next_state_buffer[i] = ex.next_state
    
    @aine_api
    @property
    @abstractmethod
    def can_train(self) -> bool:
        """
        Returns wheter you can train or not.
        """
        pass
        
    @aine_api
    @abstractmethod
    def sample(self) -> ExperienceBatch:
        """Sample from the trajectory.

        Returns:
            ExperienceBatch: sampled experience batch
        """
        pass
    
    def _sample_next_states(self, batch_idxs: np.ndarray) -> np.ndarray:
        """
        Sample next states from the trajectory. TODO: #6 It needs to be tested.
        
        The source of this method is kengz/SLM-Lab (Github) https://github.com/kengz/SLM-Lab/blob/master/slm_lab/agent/memory/replay.py.

        Args:
            batch_idxs (np.ndarray): batch indexes which mean current state indexes

        Returns:
            np.ndarray: next state batch
        """
        # [state1, state2, state3, next_state1, next_state2, next_state3]
        next_state_idxs = (batch_idxs + self.env_count) % self.max_count
        # if recent < next_state_index <= recent + env_count, next_state is stored in next_state_buffer
        # e.g. [recent1, recent2, recent3, oldest1, oldest2, oldest3]
        # next_state_index = 4 (oldest2) -> 2 (recent=recent3) < next_state_index < 2 + 3
        not_exsists_next_state = np.argwhere(
            (self.recent_idx < next_state_idxs) & (next_state_idxs <= self.recent_idx + self.env_count)
        ).flatten()
        # get the next state batch
        next_states = util.get_batch(self.states, next_state_idxs)
        if not_exsists_next_state.size > 0:
            # recent < next_state_index <= recent + env_count
            # 0 <= next_state_index - recent - 1 < env_count
            next_state_buffer_idxs = next_state_idxs[not_exsists_next_state] - self.recent_idx - 1
            # replace them
            next_states[not_exsists_next_state] = util.get_batch(self.next_state_buffer, next_state_buffer_idxs)
        return next_states