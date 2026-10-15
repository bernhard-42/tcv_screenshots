from build123d import *

box = Box(1, 1, 1)
box = fillet(box.edges(), 0.1)
cyl = Cylinder(0.3, 2)


def main():
    from tcv_screenshots import save_model, get_saved_models

    save_model(
        box,
        cyl,
        name="box_cyl_colors",
        cad_width=500,
        height=375,
        colors=["magenta", "green"],
        alphas=[0.5, 1.0],
    )

    return get_saved_models()
