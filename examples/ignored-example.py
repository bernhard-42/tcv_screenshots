from build123d import *
from ocp_vscode import show

box = Box(1, 1, 1)
box = fillet(box.edges(), 0.1)

show(box)
