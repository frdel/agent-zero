# Running Agent-Zero on NixOS

The command `nix develop` will give you a shell with python and system
dependencies installed. (This uses the provided `flake.nix` in the project
root)

Then install the python dependencies using pip in a virtual-environment:

```
python3 -m venv virtual-environment-dir
source virtual-environment-dir/bin/activate
pip install -r requirements.txt
```

