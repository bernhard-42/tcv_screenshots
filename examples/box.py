from build123d import *

box = Box(1, 1, 1)
box = fillet(box.edges(), 0.1)


def main():
    from tcv_screenshots import Render, save_model, get_saved_models

    save_model(box, name="faces_only", cad_width=500, height=375, modes=[Render.FACES])
    save_model(box, name="edges_only", cad_width=500, height=375, modes=[Render.EDGES])

    return get_saved_models()
