import sys
sys.path.append(".")

import argparse
from typing import List, Optional, Tuple, Union
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import gym
import gym.spaces
import gym.vector
import aine_drl
import aine_drl.util as util
import aine_drl.training.gym_action_communicator as gac

class CartPoleNoVelEnv(gym.Env):
    """CartPole with no velocity env."""
    def __init__(self) -> None:        
        super().__init__()
        
        self.gym_env = gym.make("CartPole-v1", new_step_api=True, render_mode="human")
        self.obs_mask = np.array([1, 0, 1, 0], dtype=np.bool8)
        
    def masked_obs(self, full_obs):
        return full_obs[self.obs_mask]

    def reset(self, *, seed: Optional[int] = None, return_info: bool = False, options: Optional[dict] = None):
        full_obs = self.gym_env.reset(seed=seed, return_info=return_info, options=options)
        return self.masked_obs(full_obs)

    def step(self, action):
        full_obs, reward, terminated, truncated, info = self.gym_env.step(action)
        return self.masked_obs(full_obs), reward, terminated, truncated, info      
    
    @property
    def action_space(self):
        return self.gym_env.action_space
    
class CartPoleNoVelVectorEnv(gym.vector.VectorEnv):
    """CartPole with no velocity vector env."""

    def __init__(self, num_envs: int):
        self.gym_env = gym.vector.make("CartPole-v1", num_envs=num_envs, new_step_api=True)
        self.obs_mask = np.array([1, 0, 1, 0], dtype=np.bool8)
        low = self.gym_env.single_observation_space.low[self.obs_mask]
        high = self.gym_env.single_observation_space.high[self.obs_mask]
        self.final_obs_key = "final_observation"
        
        super().__init__(num_envs, gym.spaces.Box(low, high), self.gym_env.single_action_space, True)
        
    def masked_obs(self, full_obs):
        return full_obs[:, self.obs_mask]

    def reset(self, *, seed: Optional[Union[int, List[int]]] = None, return_info: bool = False, options: Optional[dict] = None):
        full_obs = self.gym_env.reset(seed=seed, return_info=return_info, options=options)
        return self.masked_obs(full_obs)
        
    def step(self, actions):
        full_obs, reward, terminated, truncated, info = self.gym_env.step(actions)
        if self.final_obs_key in info.keys():
            is_final = info[f"_{self.final_obs_key}"]
            final_obs = info[self.final_obs_key][is_final]
            for i, item in enumerate(final_obs):
                final_obs[i] = item[self.obs_mask]
            info[self.final_obs_key][is_final] = final_obs
        return self.masked_obs(full_obs), reward, terminated, truncated, info        

class CartPoleNoVelRecurrentActorCriticNet(aine_drl.RecurrentActorCriticSharedNetwork):
    # Recurrent PPO uses RecurrentActorCriticSharedNetwork.
    
    def __init__(self, obs_shape, num_discrete_actions) -> None:
        super().__init__()
        
        self.lstm_in_features = 128
        self.hidden_feature = 64
        self._obs_shape = obs_shape
        
        # encoding layer for shared network
        self.encoding_layer = nn.Sequential(
            nn.Linear(obs_shape, 64),
            nn.ReLU(),
            nn.Linear(64, self.lstm_in_features),
            nn.ReLU()
        )
        
        # recurrent layer using LSTM
        self.lstm_layer = nn.LSTM(self.lstm_in_features, self.hidden_feature, batch_first=True)
        
        # actor-critic layer
        self.actor_layer = aine_drl.DiscreteActionLayer(self.hidden_feature, num_discrete_actions)
        self.critic_layer = nn.Linear(self.hidden_feature, 1)
        
        # optimizer
        self.optimizer = optim.Adam(self.parameters(), lr=3e-4)
    
    def forward(self, obs_seq: torch.Tensor, hidden_state: torch.Tensor) -> Tuple[aine_drl.PolicyDistributionParameter, torch.Tensor, torch.Tensor]:
        # feed forward to the encoding layer
        # (num_seq, seq_len, *obs_shape) -> (num_seq * seq_len, *obs_shape)
        seq_len = obs_seq.shape[1]
        obs_batch = obs_seq.flatten(0, 1)
        encoded_batch = self.encoding_layer(obs_batch)
        
        # LSTM layer
        unpacked_hidden_state = aine_drl.RecurrentNetwork.unpack_lstm_hidden_state(hidden_state)
        # (num_seq * seq_len, lstm_in_features) -> (num_seq, seq_len, lstm_in_features)
        encoded_seq = encoded_batch.reshape(-1, seq_len, self.lstm_in_features)
        encoded_seq, unpacked_next_hidden_state = self.lstm_layer(encoded_seq, unpacked_hidden_state)
        next_hidden_state = aine_drl.RecurrentNetwork.pack_lstm_hidden_state(unpacked_next_hidden_state)
        
        # actor-critic layer
        # (num_seq, seq_len, D x H_out) -> (num_seq * seq_len, D x H_out)
        encoded_batch = encoded_seq.flatten(0, 1)
        pdparam_batch = self.actor_layer(encoded_batch)
        state_value_batch = self.critic_layer(encoded_batch)
        
        # (num_seq * seq_len, *shape) -> (num_seq, seq_len, *shape)
        pdparam_seq = pdparam_batch.flattened_to_sequence(seq_len)
        state_value_seq = state_value_batch.reshape(-1, seq_len, 1)
        
        return pdparam_seq, state_value_seq, next_hidden_state
    
    # override
    # def forward(self, obs: torch.Tensor, hidden_state: torch.Tensor) -> Tuple[aine_drl.PolicyDistributionParameter, torch.Tensor, torch.Tensor]:
    #     # encoding layer
    #     # (num_seq, seq_len, *obs_shape) -> (num_seq * seq_len, *obs_shape)
    #     seq_len = obs.shape[1]
    #     flattend = obs.flatten(0, 1)
    #     encoding = self.encoding_layer(flattend)
        
    #     # lstm layer
    #     unpacked_hidden_state = self.unpack_lstm_hidden_state(hidden_state)
    #     # (batch_size * seq_len, *lstm_in_feature) -> (batch_size, seq_len, *lstm_in_feature)
    #     encoding = encoding.reshape(-1, seq_len, self.lstm_in_feature)
    #     encoding, unpacked_hidden_state = self.lstm_layer(encoding, unpacked_hidden_state)
    #     next_hidden_state = self.pack_lstm_hidden_state(unpacked_hidden_state)
        
    #     # actor-critic layer
    #     # (batch_size, seq_len, *hidden_feature) -> (batch_size * seq_len, *hidden_feature)
    #     encoding = encoding.flatten(0, 1)
    #     pdparam = self.actor_layer(encoding)
    #     v_pred = self.critic_layer(encoding)
        
    #     return pdparam, v_pred, next_hidden_state
    
    # override
    def train_step(self, loss: torch.Tensor, grad_clip_max_norm: Optional[float], training_step: int):
        self.basic_train_step(loss, self.optimizer, grad_clip_max_norm)
        
    # override    
    @property
    def hidden_state_shape(self) -> Tuple[int, int]:
        return (1, self.hidden_feature * 2)
    
class CartPoleNoVelActorCriticNet(aine_drl.ActorCriticSharedNetwork):
    # Naive PPO uses ActorCriticSharedNetwork.
    
    def __init__(self, obs_shape, num_discrete_actions) -> None:
        super().__init__()
        
        self.hidden_feature = 128
        
        # encoding layer for shared network
        self.encoding_layer = nn.Sequential(
            nn.Linear(obs_shape, 64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Linear(128, self.hidden_feature),
            nn.ReLU()
        )
        
        # actor-critic layer
        self.actor_layer = aine_drl.DiscreteActionLayer(self.hidden_feature, num_discrete_actions)
        self.critic_layer = nn.Linear(self.hidden_feature, 1)
        
        # optimizer
        self.optimizer = optim.Adam(self.parameters(), lr=0.001)
    
    # overrride
    def forward(self, obs: torch.Tensor) -> Tuple[aine_drl.PolicyDistributionParameter, torch.Tensor]:
        encoding = self.encoding_layer(obs)
        pdparam = self.actor_layer(encoding)
        v_pred = self.critic_layer(encoding)
        
        return pdparam, v_pred
    
    # override
    def train_step(self, loss: torch.Tensor, grad_clip_max_norm: Optional[float], training_step: int):
        self.basic_train_step(loss, self.optimizer, grad_clip_max_norm)


def run_recurrent_ppo(inference: bool = False):
    # AINE-DRL configuration manager
    aine_config = aine_drl.AINEConfig("config/experiments/cartpole_v1_no_velocity_recurrent_ppo.yaml")
    
    # make gym training instance
    gym_env = CartPoleNoVelVectorEnv(aine_config.num_envs)
    gym_training = aine_config.make_gym_training(gym_env)
    
    # create recurrent actor-critic shared network
    obs_shape = gym_training.observation_space.shape[0]
    num_actions = gym_training.action_space.n
    network = CartPoleNoVelRecurrentActorCriticNet(obs_shape, num_actions)
    
    # create policy for discrete action type
    policy = aine_drl.CategoricalPolicy()
    
    # make Recurrent PPO agent
    recurrent_ppo = aine_config.make_agent(network, policy)
    
    if not inference:
        gym_training.train(recurrent_ppo)
    else:
        inference_gym_env = CartPoleNoVelEnv()
        gym_training.set_inference_gym_env(inference_gym_env, gac.GymActionCommunicator.make(inference_gym_env))
        gym_training.inference(recurrent_ppo, num_episodes=10, agent_save_file_dir="experiments/cartpole_v1_no_velocity/CartPole-v1-NoVelocity_RecurrentPPO/agent.pt")
    
    # training close safely
    gym_training.close()
    
def run_naive_ppo(inference: bool = False):
    # AINE-DRL configuration manager
    aine_config = aine_drl.AINEConfig("config/experiments/cartpole_v1_no_velocity_ppo.yaml")
    
    # make gym training instance
    gym_env = CartPoleNoVelVectorEnv(aine_config.num_envs)
    gym_training = aine_config.make_gym_training(gym_env)
    
    # create actor-critic shared network
    obs_shape = gym_training.observation_space.shape[0]
    num_actions = gym_training.action_space.n
    network = CartPoleNoVelActorCriticNet(obs_shape, num_actions)
    
    # create policy for discrete action type
    policy = aine_drl.CategoricalPolicy()
    
    # make Naive PPO agent
    ppo = aine_config.make_agent(network, policy)
    
    if not inference:
        gym_training.train(ppo)
    else:
        inference_gym_env = CartPoleNoVelEnv()
        gym_training.set_inference_gym_env(inference_gym_env, gac.GymActionCommunicator.make(inference_gym_env))
        gym_training.inference(ppo, num_episodes=10, agent_save_file_dir="experiments/cartpole_v1_no_velocity/CartPole-v1-NoVelocity_Naive_PPO/agent.pt")
    
    # training close safely
    gym_training.close()
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode", default="training")
    mode = parser.parse_args().mode
    
    seed = 0
    util.seed(seed)
    
    if mode == "training":
        run_recurrent_ppo()
        run_naive_ppo()
    elif mode == "inference": 
        # run_recurrent_ppo(inference=True)
        run_naive_ppo(inference=True)
    else:
        raise ValueError(f"\'training\', \'inference\' are only supported modes but you've input {mode}.")
