#!/usr/bin/env python3
"""Replay exported UniLab Go2 student ONNX in Genesis 1.3.3."""
import argparse,csv,json,math,re,time,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,onnxruntime as ort
ROOT=Path(__file__).resolve().parents[1]
SCENE=ROOT/"src/unilab/assets/robots/go2/scene_flat.xml"
XML=ROOT/"src/unilab/assets/robots/go2/go2.xml"
MODEL=ROOT/"runs/rma/student_mapping_v1_500.onnx"
LEGS=["FL","FR","RL","RR"]
J=[f"{l}_{p}_joint" for l in LEGS for p in ("hip","thigh","calf")]
OFF=np.array([0,.5,.5,0],np.float32)
def nparr(x): return np.asarray(x.detach().cpu().numpy() if hasattr(x,"detach") else x)
def rotate(v,q):
 t=2*np.cross(q[1:],v); return v+q[0]*t+np.cross(q[1:],t)
def invrotate(v,q):
 qi=q.copy(); qi[1:]*=-1; return rotate(v,qi)
def qmul(a,b):
 aw,ax,ay,az=a; bw,bx,by,bz=b
 return np.array([aw*bw-ax*bx-ay*by-az*bz,aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw],np.float32)
def parsevec(s): return np.asarray([float(x) for x in s.split()],np.float32)
def scalar(path,key,default):
 m=re.search(r"^\s*"+re.escape(key)+r"\s*:\s*([-+0-9.eE]+)\s*$",path.read_text(),re.M)
 return float(m.group(1)) if m else default
def read_contract(model):
 m=json.loads(model.with_suffix(".json").read_text())
 req={"format":"unilab-rma-deployment-v1","obs_dim":49,"history_length":50,"action_dim":12,"policy_period_s":.02,"action_scale":.25,"history_order":"oldest_to_newest_including_current","history_reset":"zero_pad_then_append_reset_observation"}
 for k,v in req.items():
  if m.get(k)!=v: raise ValueError(f"ONNX metadata {k} mismatch: {m.get(k)!r}")
 fields=[["gyro",3],["projected_gravity",3],["joint_pos_rel",12],["joint_vel_rel",12],["last_action",12],["command",3],["gait_phase",4]]
 if m.get("observation_fields")!=fields or m.get("action_joint_order")!=LEGS: raise ValueError("Unexpected ONNX observation/action layout")
 scene=ET.parse(SCENE).getroot(); key=next((x for x in scene.findall("./keyframe/key") if x.get("name")=="home"),None)
 if key is None: raise ValueError("Go2 home keyframe missing")
 home=parsevec(key.get("qpos","")); ctrl=parsevec(key.get("ctrl",""))
 if home.size!=19 or ctrl.size!=12: raise ValueError("Expected qpos=19, ctrl=12")
 root=ET.parse(XML).getroot(); joints=[x.get("name") for x in root.iter("joint") if x.get("name")]; acts=[x.get("name") for x in root.findall("./actuator/*")]
 legs=[]
 for a in acts:
  if a.split("_",1)[0] not in legs: legs.append(a.split("_",1)[0])
 if len(joints)!=12 or len(set(joints))!=12 or len(acts)!=12: raise ValueError("Expected 12 Go2 joints and actuators")
 if legs!=m.get("scene_actuator_order"): raise ValueError("Scene actuator order differs from ONNX metadata")
 mapping=[acts.index(x.removesuffix("_joint")) for x in J]
 if mapping!=m.get("action_to_actuator_indices"): raise ValueError("Policy-to-actuator mapping mismatch")
 cfg=ROOT/"src/unilab/conf/ppo/task/go2_joystick_flat/base.yaml"
 dt=scalar(cfg,"sim_dt",.01); duration=scalar(cfg,"max_episode_seconds",20.)
 ratio=.02/dt; nsub=round(ratio)
 if not math.isclose(ratio,nsub,abs_tol=1e-9): raise ValueError("Control period not divisible by sim_dt")
 imu=root.find(".//site[@name='imu']")
 if imu is None: raise ValueError("Missing IMU site")
 if any(imu.get(k) is not None for k in ("quat","euler","axisangle","xyaxes","zaxis")): raise ValueError("Rotated IMU needs an explicit sensor-frame transform")
 return dict(meta=m,home=home,joints=joints,acts=acts,mapping=mapping,dt=dt,nsub=nsub,timeout=round(duration/.02),imu_offset=parsevec(imu.get("pos","0 0 0")))
def cli():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--model",type=Path,default=MODEL); p.add_argument("--steps",type=int,default=1000); p.add_argument("--seed",type=int,default=123)
 p.add_argument("--command",nargs=3,type=float,default=[.5,0.,0.],metavar=("VX","VY","WZ")); p.add_argument("--device",choices=["gpu","cpu"],default="gpu")
 p.add_argument("--reset-mode",choices=["unilab","home"],default="unilab"); p.add_argument("--observation-noise",action=argparse.BooleanOptionalAction,default=True)
 p.add_argument("--sim2sim-nominal",action="store_true",help="Match MuJoCo evaluation: home, zero noise, friction=1, kv=0, training sensor conventions")
 p.add_argument("--control-diagnostics",action="store_true",help="Opt-in physics-step contact/control telemetry to separate .control.csv and .control.json files")
 p.add_argument("--physics-substeps",type=int,default=1,help="Genesis solver substeps per 0.01 s physics step; policy period remains 0.02 s")
 p.add_argument("--render",action="store_true"); p.add_argument("--realtime",action="store_true"); p.add_argument("--output",type=Path); return p
class PolicyReplay:
 def __init__(self,torch,scene,robot,c,sess,args):
  self.torch,self.scene,self.robot,self.c,self.sess,self.args=torch,scene,robot,c,sess,args; self.rng=np.random.default_rng(args.seed)
  self.cmd=np.asarray(args.command,np.float32); self.phase=np.float32(0); self.stepn=0; self.epstep=0; self.episode=0; self.completed=0; self.last=np.zeros(12,np.float32)
  self.di=[int(robot.get_joint(x).dofs_idx_local[0]) for x in J]; self.qi=[int(robot.get_joint(x).qs_idx_local[0]) for x in J]
  if len(set(self.di))!=12 or min(self.di)<6 or min(self.qi)<7: raise ValueError("Bad Genesis joint indices")
  self.base=int(robot.get_link("base").idx_local); self.home=nparr(robot.get_qpos())[0].astype(np.float32).copy(); self.home[:7]=c["home"][:7]
  for name,angle in zip(c["joints"],c["home"][7:]): self.home[int(robot.get_joint(name).qs_idx_local[0])]=angle
  self.default=self.home[self.qi].copy(); self.kp=nparr(robot.get_dofs_kp(dofs_idx_local=self.di)).reshape(-1); self.kv=nparr(robot.get_dofs_kv(dofs_idx_local=self.di)).reshape(-1)
  self.damping=nparr(robot.get_dofs_damping(dofs_idx_local=self.di)).reshape(-1)
  if not np.allclose(self.kp,35,atol=1e-3): raise ValueError(f"Genesis kp expected 35, got {self.kp}")
  self.diagnostics=None
  self.hist=np.zeros((1,50,49),np.float32); self.reset(True)
 def ten(self,x): return self.torch.as_tensor(x,dtype=self.torch.float32,device=self.torch.device("cuda:0" if self.args.device=="gpu" else "cpu"))
 def reset(self,initial=False):
  q=self.home.copy(); qv=np.zeros(18,np.float32)
  if self.args.reset_mode=="unilab":
   q[:2]+=self.rng.uniform(-.5,.5,2); yaw=self.rng.uniform(-math.pi,math.pi); q[3:7]=qmul(q[3:7],np.array([math.cos(yaw/2),0,0,math.sin(yaw/2)],np.float32))
   qv[:3]=self.rng.uniform(-.5,.5,3); qv[3:6]=invrotate(self.rng.uniform(-.5,.5,3).astype(np.float32),q[3:7])
  self.robot.set_qpos(self.ten(q[None])); self.robot.set_dofs_velocity(self.ten(qv[None])); self.last.fill(0); self.epstep=0
  if not initial: self.episode+=1
  self.obs=self.observation(); self.hist.fill(0); self.hist[0,-1]=self.obs
 def observation(self):
  q=nparr(self.robot.get_qpos())[0].astype(np.float32); qv=nparr(self.robot.get_dofs_velocity())[0].astype(np.float32)
  # Training negates the MJCF framezaxis sensor (world-frame site z-axis).
  # Reproduce that existing policy contract, even though its label says gravity.
  gravity_fn=rotate if self.args.sim2sim_nominal else invrotate
  gravity=gravity_fn(np.array([0,0,-1],np.float32),q[3:7]); phase=np.remainder(self.phase+OFF,np.float32(1))
  gyro=self.velocity()[1] if self.args.sim2sim_nominal else qv[3:6]
  o=np.concatenate((gyro,gravity,q[self.qi]-self.default,qv[self.di],self.last,self.cmd,phase)).astype(np.float32)
  if o.shape!=(49,) or not np.isfinite(o).all(): raise ValueError("Invalid policy observation")
  if self.args.observation_noise: o[:30]+=self.rng.uniform(-.2,.2,30).astype(np.float32)
  return o
 def velocity(self):
  q=nparr(self.robot.get_qpos())[0].astype(np.float32); v=nparr(self.robot.get_links_vel(links_idx_local=[self.base]))[0,0]; w=nparr(self.robot.get_links_ang(links_idx_local=[self.base]))[0,0]
  if self.args.sim2sim_nominal: v=v+np.cross(w,rotate(self.c["imu_offset"],q[3:7]))
  return invrotate(v,q[3:7]),invrotate(w,q[3:7])
 def step(self):
  raw_action=self.sess.run(["action"],{"observation":self.obs[None],"history":self.hist})[0][0].astype(np.float32); a=np.clip(raw_action,-1,1); target=self.default+.25*a
  start=time.perf_counter(); self.robot.control_dofs_position(self.ten(target[None]),dofs_idx_local=self.di)
  for substep in range(self.c["nsub"]):
   if self.diagnostics is not None: diagnostic_row=self.diagnostics.before_substep(target,raw_action,a,substep)
   self.scene.step()
   if self.diagnostics is not None: self.diagnostics.after_substep(diagnostic_row,target)
  elapsed=time.perf_counter()-start; self.stepn+=1; self.epstep+=1; self.phase=np.fmod(self.phase+np.float32(.04),np.float32(1))
  q=nparr(self.robot.get_qpos())[0].astype(np.float32); grav=invrotate(np.array([0,0,-1],np.float32),q[3:7]); tilt=math.degrees(math.acos(float(np.clip(-grav[2],-1,1))))
  reason="time_out" if self.epstep>=self.c["timeout"] else ("bad_orientation" if tilt>60 else "")
  v,w=self.velocity(); self.last=a.copy(); new=self.observation()
  row={"policy_step":self.stepn,"sim_time_s":self.stepn*.02,"episode":self.episode,"episode_step":self.epstep,"vx_m_s":float(v[0]),"vy_m_s":float(v[1]),"yaw_rate_rad_s":float(w[2]),"base_z_m":float(q[2]),"tilt_deg":tilt,"action_abs_max":float(np.abs(a).max()),"action_rms":float(np.sqrt(np.mean(a*a))),"reset_reason":reason}
  row.update({f"action_{i}":float(a[i]) for i in range(12)}); row.update({f"joint_pos_rel_{i}_rad":float(q[self.qi[i]]-self.default[i]) for i in range(12)})
  if reason: self.completed+=1; self.reset()
  else: self.obs=new; self.hist[0,:-1]=self.hist[0,1:].copy(); self.hist[0,-1]=self.obs
  return row,elapsed
def main():
 a=cli().parse_args()
 if a.sim2sim_nominal:
  a.reset_mode="home"; a.observation_noise=False
 if a.steps<1 or a.physics_substeps<1 or not all(math.isfinite(x) for x in a.command): raise SystemExit("Invalid --steps, physics-substeps or command")
 c=read_contract(a.model); sess=ort.InferenceSession(str(a.model),providers=["CPUExecutionProvider"])
 shapes={x.name:x.shape for x in sess.get_inputs()}
 if shapes!={"observation":[1,49],"history":[1,50,49]}: raise ValueError(f"Bad ONNX input shapes: {shapes}")
 if [x.name for x in sess.get_outputs()]!=["action"]: raise ValueError("ONNX output should be action")
 import genesis as gs
 gs.init(backend=gs.gpu if a.device=="gpu" else gs.cpu,precision="32",logging_level="warning",seed=a.seed)
 try:
  rigid=gs.options.RigidOptions(enable_self_collision=True,enable_torsional_friction=True,enable_rolling_friction=True,friction_cone=gs.friction_cone.elliptic,integrator=gs.integrator.approximate_implicitfast)
  scene=gs.Scene(show_viewer=a.render,sim_options=gs.options.SimOptions(dt=c["dt"],substeps=a.physics_substeps),rigid_options=rigid)
  robot=scene.add_entity(gs.morphs.MJCF(file=str(SCENE.resolve()))); scene.build(n_envs=1)
  actual=[x.name for x in robot.joints if x.name in c["joints"]]
  if actual!=c["joints"]: raise ValueError(f"Genesis joint order differs: {actual}")
  if a.sim2sim_nominal:
   robot.set_friction(1.0)
   robot.set_dofs_kv(np.zeros(12,np.float32),dofs_idx_local=[int(robot.get_joint(x).dofs_idx_local[0]) for x in J])
  policy=PolicyReplay(__import__("torch"),scene,robot,c,sess,a)
  out=a.output or ROOT/"runs/rma/genesis"/("go2_seed%d_%s.csv"%(a.seed,datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))); out.parent.mkdir(parents=True,exist_ok=True)
  columns=["policy_step","sim_time_s","episode","episode_step","vx_m_s","vy_m_s","yaw_rate_rad_s","base_z_m","tilt_deg","action_abs_max","action_rms","reset_reason"]+[f"action_{i}" for i in range(12)]+[f"joint_pos_rel_{i}_rad" for i in range(12)]
  rows=[]
  if a.control_diagnostics:
   from tools.genesis_feasibility.control_diagnostics import GenesisControlDiagnostics
   if out.exists(): raise FileExistsError(f"Refusing to overwrite replay trace: {out}")
   policy.diagnostics=GenesisControlDiagnostics(policy,out,gs.GEOM_TYPE)
  complete=False
  try:
   with out.open("x" if a.control_diagnostics else "w",newline="",encoding="utf-8") as f:
    writer=csv.DictWriter(f,fieldnames=columns); writer.writeheader()
    for _ in range(a.steps):
     row,elapsed=policy.step(); writer.writerow(row); rows.append(row)
     if a.render and a.realtime: time.sleep(max(0,.02-elapsed))
   complete=True
  finally:
   if policy.diagnostics is not None: policy.diagnostics.close(complete)
  vx=np.array([x["vx_m_s"] for x in rows]); vy=np.array([x["vy_m_s"] for x in rows]); wz=np.array([x["yaw_rate_rad_s"] for x in rows])
  print("GENESIS GO2 CONTRACT AUDIT")
  print(json.dumps({"genesis":getattr(gs,"__version__","?"),"physics":a.device,"policy_runtime":"ONNX Runtime CPU",
   "obs/history/action_shapes":[[1,49],[1,50,49],[1,12]],"observation_fields":c["meta"]["observation_fields"],"policy_joints":J,"genesis_joints":actual,"genesis_dof_indices":policy.di,
   "mujoco_actuator_order":c["acts"],"policy_to_mujoco_actuator_indices":c["mapping"],"home_joint_angles":policy.default.tolist(),
   "genesis_kp":policy.kp.tolist(),"genesis_kv":policy.kv.tolist(),"joint_damping":policy.damping.tolist(),
   "action_scale":.25,"sim_dt_s":c["dt"],"policy_dt_s":.02,"physics_steps_per_action":c["nsub"],"genesis_solver_substeps":a.physics_substeps,
   "reset_mode":a.reset_mode,"evaluation_mode":"sim2sim_nominal_v2" if a.sim2sim_nominal else "legacy_replay","gravity_observation":"negative world site z-axis (training contract)" if a.sim2sim_nominal else "body-frame gravity (legacy)","velocity_reference":"IMU site" if a.sim2sim_nominal else "base origin","history_reset":"zero-pad then append current obs; gait phase persists","noise":"U(-.2,.2) on first 30 values" if a.observation_noise else "off",
   "differences":["MJCF home keyframe applied explicitly; sensor values reconstructed from state","No reset PD-gain, friction or payload randomization","Contact solvers and integration remain engine-specific","Nominal mode matches negative framezaxis training observation; legacy mode does not","Interface checks do not imply equal trajectories"],
   "control_diagnostics":str(policy.diagnostics.path.resolve()) if policy.diagnostics is not None else None,
   "steps":a.steps,"completed_episodes":policy.completed,"command":a.command,"mean_body_velocity":[float(vx.mean()),float(vy.mean()),float(wz.mean())],
   "planar_velocity_rmse_m_s":float(np.sqrt(np.mean((vx-a.command[0])**2+(vy-a.command[1])**2))),"trace_csv":str(out.resolve())},indent=2))
 finally: gs.destroy()
if __name__=="__main__": main()
