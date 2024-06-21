# Copyright (c) 2018-2022, NVIDIA Corporation
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from datetime import datetime

import numpy as np
import torch
from omni.isaac.gym.vec_env import VecEnvBase


# VecEnv Wrapper for RL training
class VecEnvRLGames(VecEnvBase):
    def _process_data(self):
        self._obs = torch.clamp(self._obs, -self._task.clip_obs, self._task.clip_obs).to(self._task.rl_device)
        self._rew = self._rew.to(self._task.rl_device)
        self._states = torch.clamp(self._states, -self._task.clip_obs, self._task.clip_obs).to(self._task.rl_device)
        self._resets = self._resets.to(self._task.rl_device)
        self._extras = self._extras

    def set_task(self, task, backend="numpy", sim_params=None, init_sim=True, rendering_dt=1.0 / 60.0) -> None:
        super().set_task(task, backend, sim_params, init_sim, rendering_dt)

        self.num_states = self._task.num_states
        self.state_space = self._task.state_space

    def step(self, actions):
        # only enable rendering when we are recording, or if the task already has it enabled
        to_render = self._render
        if self._record:
            if not hasattr(self, "step_count"):
                self.step_count = 0
            if self.step_count % self._task.cfg["recording_interval"] == 0:
                self.is_recording = True
                self.record_length = 0
            if self.is_recording:
                self.record_length += 1
                if self.record_length > self._task.cfg["recording_length"]:
                    self.is_recording = False
            if self.is_recording:
                to_render = True
            else:
                if (self._task.cfg["headless"] and not self._task.enable_cameras and not self._task.cfg["enable_livestream"]):
                    to_render = False
            self.step_count += 1

        if self._task.randomize_actions:
            actions = self._task._dr_randomizer.apply_actions_randomization(
                actions=actions, reset_buf=self._task.reset_buf
            )

        actions = torch.clamp(actions, -self._task.clip_actions, self._task.clip_actions).to(self._task.device)

        self._task.pre_physics_step(actions)

        if (self.sim_frame_count + self._task.control_frequency_inv) % self._task.rendering_interval == 0:
            for _ in range(self._task.control_frequency_inv - 1):
                self._world.step(render=False)
                self.sim_frame_count += 1
            self._world.step(render=to_render)
            self.sim_frame_count += 1
        else:
            for _ in range(self._task.control_frequency_inv):
                self._world.step(render=False)
                self.sim_frame_count += 1

        self._obs, self._rew, self._resets, self._extras = self._task.post_physics_step()

        if self._task.randomize_observations:
            self._obs = self._task._dr_randomizer.apply_observations_randomization(
                observations=self._obs.to(device=self._task.rl_device), reset_buf=self._task.reset_buf
            )

        self._states = self._task.get_states()
        self._process_data()

        obs_dict = {"obs": self._obs, "states": self._states}

        return obs_dict, self._rew, self._resets, self._extras

    def reset(self, seed=None, options=None):
        """Resets the task and applies default zero actions to recompute observations and states."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Running RL reset")

        self._task.reset()
        actions = torch.zeros((self.num_envs, self._task.num_actions), device=self._task.rl_device)
        obs_dict, _, _, _ = self.step(actions)

        return obs_dict
    
    def start_logging(self, save_path):
        self.data_logger = self._world.get_data_logger() # a DataLogger object is defined in the World by default
        self._save_path = save_path
        robot = self._task._frankas
        ee = self.task._frankas._hands
        ik_scale = self.task.ik_velocity
        task = self._task

        # A data logging function is called at every time step index if the data logger is started already.
        # We define the function here. The tasks and scene are passed to this function when called.
        def frame_logging_func(tasks, scene):
            # return always a dict
            
            return  {robot.name : {"states" : task.obs_buf.tolist(),
                                   "actions" : task.actions.tolist(),
                                #    "ee_pos": (task.hand_pos).tolist(),
                                #    "ee_pos_des": task.hand_pos_des.tolist() ,
                                    "rewards": task.rew_buf.tolist(),
                                    "terminated": task.reset_buf.tolist(),
                                    "applied_joint_actions": robot.get_applied_actions().joint_positions.tolist()}}
        
        self.data_logger.add_data_frame_logging_func(frame_logging_func)
        
        # self.data_logger.start() # Do Not execute this, otherwise the logger will be called inside the world step. Instead we want to call it after post step

    
    def logging_step(self):
        data = self.data_logger._data_frame_logging_func(tasks=self._world.get_current_tasks(), scene=self._world.scene)
        self.data_logger.add_data(
            data=data, current_time_step=self._world.current_time_step_index, current_time=self._world.current_time
        )

    def save_log(self):
        self.data_logger.save(self._save_path)