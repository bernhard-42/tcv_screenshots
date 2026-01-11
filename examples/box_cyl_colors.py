from build123d import *

box = Box(1, 1, 1)
box = fillet(box.edges(), 0.1)
cyl = Cylinder(0.3, 2)


def main():
    from tcv_screenshots import save_model, get_saved_models

    config = {
        "cadWidth": 500,
        "height": 375,
        "colors": ["magenta", "green"],
        "alphas": [0.5, 1.0],
    }

    save_model([box, cyl], "faces_only", config)

    return get_saved_models()
