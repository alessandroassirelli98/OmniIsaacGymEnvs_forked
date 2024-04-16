import torch
import torch.nn as nn

# import the skrl components to build the RL system
from skrl.agents.torch.td3 import TD3, TD3_DEFAULT_CONFIG
from skrl.envs.loaders.torch import load_omniverse_isaacgym_env
from skrl.envs.wrappers.torch import wrap_env
from skrl.memories.torch import RandomMemory
from skrl.models.torch import DeterministicMixin, Model
from skrl.resources.noises.torch import GaussianNoise
from skrl.resources.preprocessors.torch import RunningStandardScaler
from skrl.trainers.torch import SequentialTrainer
from skrl.utils import set_seed
from omniisaacgymenvs.demonstrations.demo_parser import parse_json_demo


# seed for reproducibility
set_seed()  # e.g. `set_seed(42)` for fixed seed
headless=False

# define models (deterministic models) using mixins
class DeterministicActor(DeterministicMixin, Model):
    def __init__(self, observation_space, action_space, device, clip_actions=False):
        Model.__init__(self, observation_space, action_space, device)
        DeterministicMixin.__init__(self, clip_actions)

        self.net = nn.Sequential(nn.Linear(self.num_observations, 256),
                                 nn.ReLU(),
                                 nn.Linear(256, 128),
                                 nn.ReLU(),
                                 nn.Linear(128, self.num_actions),
                                 nn.Tanh())

    def compute(self, inputs, role):
        return self.net(inputs["states"]), {}

class Critic(DeterministicMixin, Model):
    def __init__(self, observation_space, action_space, device, clip_actions=False):
        Model.__init__(self, observation_space, action_space, device)
        DeterministicMixin.__init__(self, clip_actions)

        self.net = nn.Sequential(nn.Linear(self.num_observations + self.num_actions, 256),
                                 nn.ReLU(),
                                 nn.Linear(256, 128),
                                 nn.ReLU(),
                                 nn.Linear(128, 1))

    def compute(self, inputs, role):
        return self.net(torch.cat([inputs["states"], inputs["taken_actions"]], dim=1)), {}


# load and wrap the Omniverse Isaac Gym environment
env = load_omniverse_isaacgym_env(task_name="DianaTekken")
env = wrap_env(env)

device = env.device


# instantiate a memory as rollout buffer (any memory can be used for this)
memory = RandomMemory(memory_size=50000, num_envs=env.num_envs, device=device)


# instantiate the agent's models (function approximators).
# TD3 requires 5 models, visit its documentation for more details
# https://skrl.readthedocs.io/en/latest/api/agents/td3.html#models
models = {}
models["policy"] = DeterministicActor(env.observation_space, env.action_space, device)
models["target_policy"] = DeterministicActor(env.observation_space, env.action_space, device)
models["critic_1"] = Critic(env.observation_space, env.action_space, device)
models["critic_2"] = Critic(env.observation_space, env.action_space, device)
models["target_critic_1"] = Critic(env.observation_space, env.action_space, device)
models["target_critic_2"] = Critic(env.observation_space, env.action_space, device)


# configure and instantiate the agent (visit its documentation to see all the options)
# https://skrl.readthedocs.io/en/latest/api/agents/ddpg.html#configuration-and-hyperparameters
cfg = TD3_DEFAULT_CONFIG.copy()
cfg["exploration"]["noise"] = GaussianNoise(0, 0.1, device=device)
cfg["smooth_regularization_noise"] = GaussianNoise(0, 0.2, device=device)
cfg["smooth_regularization_clip"] = 0.5
cfg["gradient_steps"] = 1
cfg["batch_size"] = 4096
cfg["discount_factor"] = 0.95
cfg["polyak"] = 0.05
cfg["actor_learning_rate"] = 1e-3
cfg["critic_learning_rate"] = 1e-3
cfg["random_timesteps"] = 80
cfg["learning_starts"] = 80
cfg["state_preprocessor"] = RunningStandardScaler
cfg["state_preprocessor_kwargs"] = {"size": env.observation_space, "device": device}
# logging to TensorBoard and write checkpoints (in timesteps)
cfg["experiment"]["write_interval"] = 400
cfg["experiment"]["checkpoint_interval"] = 8000
cfg["experiment"]["wandb"] = True
cfg["experiment"]["directory"] = "runs/torch/DianaTekken"

agent = TD3(models=models,
             memory=memory,
             cfg=cfg,
             observation_space=env.observation_space,
             action_space=env.action_space,
             device=device)


# configure and instantiate the RL trainer
cfg_trainer = {"timesteps": 160000, "headless": headless}
trainer = SequentialTrainer(cfg=cfg_trainer, env=env, agents=agent)


# Buffer prefill
episode = parse_json_demo()
for tstep in episode:
    states = torch.tensor(tstep["states"], device=device).repeat(env.num_envs, 1)
    actions = torch.tensor(tstep["actions"], device=device).repeat(env.num_envs, 1)
    rewards = torch.tensor(tstep["rewards"], device=device).repeat(env.num_envs, 1)
    terminated = torch.tensor(tstep["terminated"], device=device).repeat(env.num_envs, 1)
    next_states = torch.tensor(tstep["next_states"], device=device).repeat(env.num_envs, 1)
    memory.add_samples(states=states, actions=actions, rewards=rewards, next_states=next_states,terminated=terminated)
    
# start training
trainer.train()


# agent.load("/home/ows-user/devel/git-repos/OmniIsaacGymEnvs_forked/omniisaacgymenvs/runs/torch/DianaTekken/24-03-27_18-08-46-681507_DDPG/checkpoints/best_agent.pt")
# trainer.eval()