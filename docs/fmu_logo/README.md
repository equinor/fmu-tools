# FMU LOGO

Here are the source files for the FMU logo.

Stored in SVG using the free software tool [Inkscape](https://inkscape.org/), version 0.92.2


## Text font:

Use the free google font named DOSIS. Download and
install Personal use (download the zip and double click each TTF
to install in RHEL 7). After using fonts, the text should be converted to PATHS:

Path: Object to PATH

## Files

fmu_logo.svg, logo in plain or inkscape SVG
fmu_logo_with_text.svg, logo w text in Inkscape SVG (due to text)
fmu_logo_coviz.svg, logo for coviz, plain or inkscape SVG

## Conversion to plain SVG

The SVG files may have some inkscape or sodipodi tags. For plain SVG to include elsewhere:

```inkscape --export-plain-svg=output.svg input.svg```

e.g.
```inkscape --export-plain-svg=FMU_logo_with_text.svg fmu_logo_with_text.svg```

Then upload FMU_logo_with_text.svg to internal wiki.


## Contact

JRIV if issues
