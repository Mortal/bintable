# bintable

A numpy binary format for astropy tables

## Example command-line use

```
python3 -m venv .venv
.venv/bin/pip install astropy git+https://github.com/Mortal/bintable
.venv/bin/python -m bintable -i my_votable.vot -o my_bintable
```

## Example Python use

```
import bintable

table = bintable.read("my_bintable")
```
