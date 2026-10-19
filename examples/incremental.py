from build123d import *
from tcv_screenshots import Render, screenshot, get_screenshots


size = {"cad_width": 500, "height": 375}

# Step 1: Create base box
box = Box(10, 10, 10)
screenshot(box, name="incremental_step1_box", **size)

# Step 2: Add fillet
filleted = fillet(box.edges(), 1)
screenshot(filleted, name="incremental_step2_fillet", **size)

# Step 3: Add hole
final = filleted - Pos(0, 0, 0) * Cylinder(2, 10)
screenshot(final, name="incremental_step3_hole", modes=[Render.FACES], **size)


def main():

    return get_screenshots()
