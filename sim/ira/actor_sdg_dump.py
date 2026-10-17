"""
actor_sdg_dump.py — Isaac Sim's tools/actor_sdg/actor_sdg.py plus ONE addition: every
frame while the timeline plays, write the world position of EVERY registered agent to
a JSONL file, keyed by timeline time in seconds.

Why: IRA's writers only list agents visible to a camera (Phase 0: 3 of 10 walkers were
ever seen across 3 cameras). Clearance (t50/t90/t100) needs every agent every frame,
camera-independent. Cameras stay for the film.

Run exactly like actor_sdg.py, with the same bind mounts, adding --dump:

  /isaac-sim/python.sh /workspace/sim/ira/actor_sdg_dump.py -c /workspace/sim/ira/hospital_base.yaml \
      --dump /workspace/results/ira_hospital_base/agent_positions.jsonl

One line per agent per frame:
  {"t": 12.5, "agent": "/World/Characters/evac_E3/...", "name": "evac_E3_4", "group": "evac_E3",
   "x": .., "y": .., "z": .., "speed": 1.31, "task": "MoveTo"}
Positions come from IRA's agent objects (the animation runtime), not from USD transforms — characters
move in Fabric and their USD xform stays at the spawn pose.
"""
import argparse
import json
import os
import sys
import traceback

from isaacsim import SimulationApp

BASE_EXP_PATH = os.path.join(os.environ["EXP_PATH"], "isaacsim.exp.action_and_event_data_generation.base.kit")
APP_CONFIG = {"headless": True, "width": 1920, "height": 1080}


class ActorSDGDump:
    def __init__(self, sim_app, config_file_path, dump_path):
        self._sim_app = sim_app
        self.config_file_path = config_file_path
        self.dump_path = dump_path
        self._sub = None
        self._file = None
        self._agents = None
        self._last_t = None
        self._frames = 0

    async def run(self):
        self._set_simulation_settings()
        await self._sim_app.app.next_update_async()

        from isaacsim.replicator.agent.core import api as IRA

        if not IRA.load_config_file(self.config_file_path):
            print(f"Failed to load config file at {self.config_file_path}. Exit.")
            return False
        print(f"config file loaded: {IRA.get_config_file()}")

        await IRA.setup_simulation()
        self._start_dump()
        try:
            await IRA.start_data_generation_async()
        finally:
            self._stop_dump()
        return True

    # ---- the addition -------------------------------------------------------------
    def _start_dump(self):
        import omni.kit.app
        import omni.timeline
        from omni.metropolis.pipeline.agent import AgentsManager

        os.makedirs(os.path.dirname(os.path.abspath(self.dump_path)), exist_ok=True)
        self._file = open(self.dump_path, "w")
        timeline = omni.timeline.get_timeline_interface()
        manager = AgentsManager.get_instance()

        def on_update(_event):
            if not timeline.is_playing():
                return
            t = timeline.get_current_time()
            if self._last_t is not None and t <= self._last_t:      # paused or repeated frame
                return
            self._last_t = t
            # Characters move in the animation runtime (Fabric), not in USD: reading USD xforms
            # gives the spawn pose forever. IRA's agent objects expose the live position, the same
            # source as metro_agent_data.world_position in the writer output.
            if not self._agents:
                self._agents = list(manager.get_runtime_agent_instances())
                if self._agents:
                    print(f"[agent_dump] tracking {len(self._agents)} agents -> {self.dump_path}", flush=True)
            for agent in self._agents:
                pos = agent.get_world_position()
                if pos is None:
                    continue
                self._file.write(json.dumps({
                    "t": round(t, 4), "agent": str(agent.prim.GetPrimPath()), "name": agent.name, "group": agent.group,
                    "x": round(float(pos[0]), 3), "y": round(float(pos[1]), 3), "z": round(float(pos[2]), 3),
                    "speed": None if agent.get_speed() is None else round(float(agent.get_speed()), 3),
                    "task": agent.get_current_task_name()}) + "\n")
            self._frames += 1

        app = omni.kit.app.get_app()
        try:                                                           # Kit's classic update stream
            self._sub = app.get_update_event_stream().create_subscription_to_pop(on_update, name="grimoires_agent_dump")
        except Exception:                                              # newer Kit: eventdispatcher
            import carb.eventdispatcher
            self._sub = carb.eventdispatcher.get_eventdispatcher().observe_event(
                event_name=omni.kit.app.GLOBAL_EVENT_UPDATE, on_event=on_update, observer_name="grimoires_agent_dump")
        print(f"[agent_dump] armed -> {self.dump_path}", flush=True)

    def _stop_dump(self):
        self._sub = None
        if self._file:
            self._file.close()
            self._file = None
        print(f"[agent_dump] done: {self._frames} frames, {len(self._agents or [])} agents, last t = {self._last_t}", flush=True)
    # -------------------------------------------------------------------------------

    def _set_simulation_settings(self):
        import carb
        import omni.replicator.core as rep

        rep.settings.carb_settings("/omni/replicator/backend/writeThreads", 16)
        self._settings = carb.settings.get_settings()
        self._settings.set("/app/scripting/ignoreWarningDialog", True)
        self._settings.set("/app/omni.graph.scriptnode/enable_opt_in", False)
        self._settings.set("/rtx/raytracing/fractionalCutoutOpacity", True)
        # Omniverse Flow (fire/smoke) renders only with these on; a referenced preset's layer settings are not
        # inherited by the stage. Harmless when the stage has no Flow prims.
        for k in ("enabled", "rayTracedTranslucencyEnabled", "rayTracedReflectionsEnabled", "pathTracingEnabled"):
            self._settings.set(f"/rtx/flow/{k}", True)
        self._settings.set("/log/level", "info")
        for ch in ("omni.replicator.core", "omni.behavior.composer.core", "isaacsim.anim.robot",
                   "isaacsim.sensors.rtx.placement", "isaacsim.replicator.agent.core"):
            self._settings.set(f"/log/channels/{ch}", "info")


def get_args():
    parser = argparse.ArgumentParser("Actor SDG + agent position dump")
    parser.add_argument("-c", "--config_file", required=True, help="Path to an IRA config file")
    parser.add_argument("--dump", required=True, help="JSONL output: one line per agent per frame")
    args, _ = parser.parse_known_args()
    return args


def main():
    args = get_args()
    if not os.path.isfile(args.config_file):
        print("Invalid config file path. Exit.", file=sys.stderr)
        return
    sim_app = SimulationApp(launch_config=APP_CONFIG, experience=BASE_EXP_PATH)
    sdg = ActorSDGDump(sim_app, os.path.abspath(args.config_file), os.path.abspath(args.dump))

    from omni.kit.async_engine import run_coroutine

    task = run_coroutine(sdg.run())
    try:
        while not task.done():
            sim_app.update()
        exc = task.exception()
        if exc:
            traceback.print_exception(exc, file=sys.stderr)
        elif not task.result():
            print("Failed to run SDG")
    finally:
        sim_app.close()
        print("SDG finished, exiting...")


if __name__ == "__main__":
    main()
