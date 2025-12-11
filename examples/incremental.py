from build123d import *
from tcv_screenshots import save_model, get_saved_models


config = {
    "cadWidth": 500,
    "height": 375,
}

# Step 1: Create base box
box = Box(10, 10, 10)
save_model(box, "incremental_step1_box", config)

# Step 2: Add fillet
filleted = fillet(box.edges(), 1)
save_model(filleted, "incremental_step2_fillet", config)

# Step 3: Add hole
final = filleted - Pos(0, 0, 0) * Cylinder(2, 10)
save_model(final, "incremental_step3_hole", {**config, "render_edges": False})


def main():

    return get_saved_models()
