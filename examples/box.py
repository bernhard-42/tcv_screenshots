from build123d import *


def main():
    box = Box(1, 1, 1)
    box = fillet(box.edges(), 0.1)

    config = {
        "cadWidth": 500,
        "height": 375,
    }

    return box, config
