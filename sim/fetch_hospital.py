# copy the NVIDIA Hospital environment folder from the asset server to /workspace/assets/hospital
import sys
from isaacsim.simulation_app import SimulationApp
app = SimulationApp({"headless": True})
try:
    import omni.client
    from isaacsim.storage.native import get_assets_root_path
    root = get_assets_root_path()
    src = f"{root}/Isaac/Environments/Hospital"
    dst = "/workspace/assets/hospital"
    print(f"[F] copy {src} -> {dst}")
    res = omni.client.copy(src, dst, behavior=omni.client.CopyBehavior.OVERWRITE)
    print(f"[F] result: {res}")
    r, entries = omni.client.list(dst)
    for e in entries:
        print(f"[F]   {e.relative_path}")
finally:
    app.close()
