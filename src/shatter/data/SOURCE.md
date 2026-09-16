# Sanzo Wada colour data — provenance

`sanzo_wada_colors.json` is copied unmodified from
[mattdesl/dictionary-of-colour-combinations](https://github.com/mattdesl/dictionary-of-colour-combinations)
(MIT licensed, see below), which itself digitises the 159 named colours and
348 colour combinations from Sanzo Wada's *A Dictionary of Color
Combinations* (1933, public domain).

That project's data originates from **Dain M. Blodorn Kim**'s
[dblodorn/sanzo-wada](https://github.com/dblodorn/sanzo-wada); **Matt
DesLauriers** corrected some entries and redid the CMYK -> RGB conversion
for [mattdesl/dictionary-of-colour-combinations](https://github.com/mattdesl/dictionary-of-colour-combinations).

Each entry has a `name`, `combinations` (IDs 1-348 of the palettes it
belongs to), `cmyk`, `lab`, `rgb`, and `hex`. `shatter.wada`
inverts this into combination-id -> list-of-colours at load time. The `lab`
field is left as upstream shipped it but is **not** what the contrast floor reads
(design doc section 12.1, decision 13).

## License (MIT, mattdesl/dictionary-of-colour-combinations)

Copyright (c) 2020 Matt DesLauriers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
OR OTHER DEALINGS IN THE SOFTWARE.
