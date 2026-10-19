from build123d import *

box = Box(1, 1, 1)
box = fillet(box.edges(), 0.1)


def main():
    from tcv_screenshots import Render, screenshot, get_screenshots

    screenshot(box, name="faces_only", cad_width=500, height=375, modes=[Render.FACES])
    screenshot(box, name="edges_only", cad_width=500, height=375, modes=[Render.EDGES])

    return get_screenshots()
