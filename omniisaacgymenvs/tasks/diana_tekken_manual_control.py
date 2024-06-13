import math
import numpy as np
import torch
import carb
from gym import spaces
from abc import abstractmethod, ABC

from omni.isaac.core.utils.torch.maths import tensor_clamp
from omni.isaac.core.articulations import ArticulationView
from omni.isaac.core.utils.prims import get_prim_at_path
from omni.isaac.core.prims import GeometryPrimView, RigidPrimView
from omni.isaac.core.utils.stage import add_reference_to_stage
from omni.isaac.core.utils.torch.rotations import (
    get_euler_xyz, quat_diff_rad, euler_angles_to_quats,
    quat_conjugate, quat_mul, quat_diff_rad, xyzw2wxyz
)
from omni.isaac.core.objects import (
    FixedCuboid, DynamicSphere, DynamicCuboid,
    VisualCuboid, FixedSphere
)
from omniisaacgymenvs.tasks.base.rl_task import RLTask
from omniisaacgymenvs.robots.articulations.diana_tekken import DianaTekken
from omniisaacgymenvs.robots.articulations.views.diana_tekken_view import DianaTekkenView
from omniisaacgymenvs.robots.articulations.utils.kinematic_solver import KinematicsSolver
from omniisaacgymenvs.tasks.diana_tekken_task import DianaTekkenTask

class DianaTekkenManualControlTask(DianaTekkenTask):

    def __init__(self, name: str, sim_config, env, offset=None) -> None:
        super().__init__(name=name, sim_config=sim_config, env=env, offset=offset)
        self._num_actions = 4
        self.obs_buf = torch.zeros(self._num_observations)

    def set_up_scene(self, scene) -> None:
        # self.get_reference_cube()
        super().set_up_scene(scene)
        # self._ref_cubes = GeometryPrimView(
        #     prim_paths_expr="/World/envs/.*/ref_cube",
        #     name="ref_cube_view",
        #     reset_xform_properties=False
        # )
        # scene.add(self._ref_cubes)
        # scene.add(self._robot)

    def get_reference_cube(self):
        self._ref_cube = VisualCuboid(
            prim_path=self.default_zero_env_path + "/ref_cube",
            name="ref_cube",
            translation=torch.tensor([0.4, 0., 0.8], device=self._device),
            orientation=euler_angles_to_quats(torch.tensor([0., -torch.pi/6, 0.], device=self._device).unsqueeze(0)).squeeze(0),
            scale=torch.tensor([0.02, 0.02, 0.02], device=self._device),
            color=torch.tensor([1, 0, 0], device=self._device)
        )

    def post_reset(self):
        self.cloned_robot_actions = np.zeros(8)
        self.joint_targets = torch.ones(len(self._robots.actuated_finger_dof_indices), device=self._device) * 0.8
        super().post_reset()

    def pre_physics_step(self, actions: torch.tensor) -> None:
        delta_pos = actions[:3]
        delta_rot = actions[3:6]
        # target_pos, target_rot = self._ref_cubes.get_world_poses()
        # target_pos -= self._env_pos
        # rpy_target = torch.tensor(get_euler_xyz(target_rot), device=self._device).unsqueeze(0)
        # target_pos[0, :3] += delta_pos
        # rpy_target[0, :3] += delta_rot
        # target_rot = euler_angles_to_quats(rpy_target)

        # self._ref_cubes.set_world_poses(positions=target_pos, orientations=target_rot)

        # This can be 0. or 1. I check 0.5 just because of floating point
        if actions[-1] >= 0.5:
            joint_targets = torch.ones(len(self._robots.actuated_finger_dof_indices), device=self._device) * 0.8
        else:
            joint_targets = - torch.ones(len(self._robots.actuated_finger_dof_indices), device=self._device) * 0.8

        pos_error_world = delta_pos * self.ik_action_scale * self.dt
        rot_error_world = delta_rot * self.ik_action_scale * self.dt 
        jeef = self._robots.get_jacobians()[:, self.ee_idx, :, :7]

        dpose = torch.cat([pos_error_world, rot_error_world], -1).unsqueeze(-1)  # (num_envs,6,1)
        delta_action = 1. * self.control_ik(j_eef=jeef, dpose=dpose, num_envs=self._num_envs, num_dofs=7) / (self.dt * self.joint_action_scale)


        action = torch.cat([delta_action, joint_targets.unsqueeze(0)], dim=1)

        super().pre_physics_step(action)

    def get_observations(self) -> dict:
        super().get_observations()

    # def is_done(self) -> None:
    #     pass
