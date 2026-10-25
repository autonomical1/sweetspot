import os

# speakerplacer imports matplotlib; never open GUI windows during tests.
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("ENGINE3D_BACKEND", "off")
