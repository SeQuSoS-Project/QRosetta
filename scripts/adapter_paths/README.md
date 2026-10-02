# Comparing two versions of a runner adapter

`compare_paths.py` runs `main_old.py` and `main.py` of one runner on the same random corpus
inside its container and reports every case whose statevector bytes, counts, executed text
or gate metrics differ. `time_paths.py` reports median compilation, simulation and total time
of both on three fixed circuits.

```bash
C=pytket-qulacs-runner
git show <old-commit>:runners/$C/main.py > /tmp-free-dir/main_old.py   # any dir outside /tmp
podman cp /tmp-free-dir/main_old.py $C:/home/appuser/app/main_old.py
podman cp runners/$C/main.py $C:/home/appuser/app/main.py
podman cp scripts/adapter_paths/compare_paths.py $C:/home/appuser/app/
podman exec $C sh -c 'cd /home/appuser/app && python compare_paths.py 150 sv 0,1,2'
podman exec $C sh -c 'cd /home/appuser/app && python compare_paths.py 200 measured 0,2'
```

Set `SINGLE_REGISTER=1` for adapters that need one quantum register when called without the
API's register merge (qsim). Copy changed `shared/qrosetta_commons` files into the
container's site-packages first if the image predates them.
