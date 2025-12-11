from build123d import *
from tcv_screenshots import save_model, get_saved_models

box = Box(1, 1, 1)
box = fillet(box.edges(), 0.1)

config = {
    "cadWidth": 500,
    "height": 375,
    "render_edges": False,
}

save_model(box, "faces_only", config)

config = {
    "cadWidth": 500,
    "height": 375,
    "render_faces": False,
}

save_model(box, "edges_only", config)


def main():

    return get_saved_models()
