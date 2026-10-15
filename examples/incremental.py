from build123d import *
from tcv_screenshots import Render, save_model, get_saved_models


size = {"cad_width": 500, "height": 375}

# Step 1: Create base box
box = Box(10, 10, 10)
save_model(box, name="incremental_step1_box", **size)

# Step 2: Add fillet
filleted = fillet(box.edges(), 1)
save_model(filleted, name="incremental_step2_fillet", **size)

# Step 3: Add hole
final = filleted - Pos(0, 0, 0) * Cylinder(2, 10)
save_model(final, name="incremental_step3_hole", modes=[Render.FACES], **size)


def main():

    return get_saved_models()
