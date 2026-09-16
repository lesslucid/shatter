def has_label_pixels(image):
    """True if tile-index labels were drawn on this image.

    Labels are antialiased, so this looks for red dominance rather than an exact
    colour match. Nothing in the pastel/tile/overlap palette is red-dominant.
    """
    return any(
        red > green + 40 and red > blue + 40
        for _count, (red, green, blue) in image.convert("RGB").getcolors(1 << 24)
    )
